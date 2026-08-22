from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestTravelQuota(TravelAccountingCase):
    def test_initial_draft_and_confirmed_bookings_do_not_reserve(self):
        self.assertEqual(self.departure.reserved_seats, 0)
        self.assertEqual(self.departure.remaining_seats, self.departure.quota)
        self.assertFalse(self.departure.is_full)

        order = self._confirmed_booking("QUOTA-CONFIRMED", 2)

        self.assertFalse(order.seat_reserved)
        self.assertFalse(order.seat_reserved_at)
        self.assertEqual(self.departure.reserved_seats, 0)

    def test_invoice_creation_posting_and_partial_payment_do_not_reserve(self):
        order = self._confirmed_booking("QUOTA-PARTIAL", 2)
        invoice = self._create_downpayment_invoice(order)
        self.assertEqual(self.departure.reserved_seats, 0)

        invoice.with_user(self.finance).action_post()
        self.assertEqual(self.departure.reserved_seats, 0)

        (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move", active_ids=invoice.ids
            )
            .create(
                {
                    "journal_id": self.company_data[
                        "default_journal_bank"
                    ].id,
                    "amount": invoice.amount_residual / 2,
                }
            )
            .action_create_payments()
        )

        self.assertFalse(order.seat_reserved)
        self.assertEqual(self.departure.reserved_seats, 0)

    def test_full_downpayment_reserves_once_and_sets_timestamp(self):
        order = self._confirmed_booking("QUOTA-FULL", 2)
        invoice = self._create_downpayment_invoice(order)
        self._post_and_pay(invoice)

        self.assertTrue(order.seat_reserved)
        self.assertTrue(order.seat_reserved_at)
        reserved_at = order.seat_reserved_at
        self.assertEqual(self.departure.reserved_seats, 2)
        self.assertEqual(
            self.departure.remaining_seats, self.departure.quota - 2
        )
        self.assertFalse(order._travel_reserve_seats())
        self.assertEqual(order.seat_reserved_at, reserved_at)
        self.assertEqual(self.departure.reserved_seats, 2)

    def test_final_invoice_with_deducted_dp_is_not_dp_only(self):
        order = self._confirmed_booking("QUOTA-FINAL")
        dp_invoice = self._create_downpayment_invoice(order)
        self._post_and_pay(dp_invoice)
        (
            self._create_invoice_wizard(
                order, "delivered", deduct_down_payments=True
            ).create_invoices()
        )
        order.invalidate_recordset(["invoice_ids"])
        final_invoice = (order.invoice_ids - dp_invoice).ensure_one()

        self.assertFalse(final_invoice._travel_is_downpayment_only())
        self.assertEqual(self.departure.reserved_seats, 1)

    def test_quota_cannot_be_lowered_below_reserved_seats(self):
        order = self._confirmed_booking("QUOTA-LOWER", 2)
        self._post_and_pay(self._create_downpayment_invoice(order))

        with self.assertRaises(ValidationError):
            self.departure.with_user(self.manager).write({"quota": 1})

    def test_reservation_fields_cannot_be_written_by_roles(self):
        order = self._confirmed_booking("QUOTA-FORGE")

        for user in (self.staff, self.finance, self.manager):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                order.with_user(user).write(
                    {
                        "seat_reserved": True,
                        "seat_reserved_at": "2027-01-01 00:00:00",
                    }
                )
