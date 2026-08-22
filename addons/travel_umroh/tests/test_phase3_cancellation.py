from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestTravelCancellation(TravelAccountingCase):
    def _posted_downpayment(self, order, paid=False):
        invoice = self._create_downpayment_invoice(order)
        if paid:
            self._post_and_pay(invoice)
        else:
            invoice.with_user(self.finance).action_post()
        return invoice

    def _cancel_wizard(self, order, reason="Permintaan keluarga"):
        order.with_user(self.manager).action_open_travel_cancel_wizard()
        return (
            self.env["travel.booking.cancel.wizard"]
            .with_user(self.manager)
            .create({"order_id": order.id, "reason": reason})
        )

    def _release_notes(self, order):
        return order.message_ids.filtered(
            lambda message: "kursi dilepas" in str(message.body).lower()
        )

    def _standard_cancel(self, order, user):
        result = order.with_user(user).action_cancel()
        if isinstance(result, dict) and result.get("res_model") == (
            "sale.order.cancel"
        ):
            (
                self.env["sale.order.cancel"]
                .with_user(user)
                .with_context(**result["context"])
                .create({"order_id": order.id})
                .action_cancel()
            )

    def test_staff_can_use_standard_cancel_before_posted_invoice(self):
        order = self._confirmed_booking("CANCEL-PRE-DP")
        initial_capacity = self.departure.remaining_seats

        self._standard_cancel(order, self.staff)
        order.invalidate_recordset(["state", "seat_reserved"])

        self.assertEqual(order.state, "cancel")
        self.assertFalse(order.seat_reserved)
        self.assertEqual(self.departure.remaining_seats, initial_capacity)
        self.assertFalse(self._release_notes(order))

    def test_posted_invoice_requires_manager_wizard(self):
        order = self._confirmed_booking("CANCEL-BOUNDARY")
        self._posted_downpayment(order)

        for user in (self.staff, self.finance):
            with self.subTest(user=user.login):
                with self.assertRaises(UserError):
                    order.with_user(user).action_cancel()
                with self.assertRaises(AccessError):
                    order.with_user(
                        user
                    ).action_open_travel_cancel_wizard()

    def test_only_manager_can_create_cancel_wizard(self):
        order = self._confirmed_booking("CANCEL-WIZARD-ACL")
        self._posted_downpayment(order)

        for user in (self.staff, self.finance):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["travel.booking.cancel.wizard"].with_user(
                    user
                ).create(
                    {
                        "order_id": order.id,
                        "reason": "Tidak boleh",
                    }
                )

    def test_blank_cancellation_reason_is_rejected(self):
        order = self._confirmed_booking("CANCEL-BLANK")
        self._posted_downpayment(order, paid=True)
        wizard = self._cancel_wizard(order, reason="   ")

        with self.assertRaises(UserError):
            wizard.action_confirm_cancel()

        self.assertEqual(order.state, "sale")
        self.assertTrue(order.seat_reserved)

    def test_manager_cancel_releases_reserved_seats_once(self):
        order = self._confirmed_booking(
            "CANCEL-PAID", participant_count=2
        )
        self._posted_downpayment(order, paid=True)
        reason = "Jamaah membatalkan karena alasan medis"
        self.assertEqual(self.departure.reserved_seats, 2)

        self._cancel_wizard(order, reason).action_confirm_cancel()
        order.invalidate_recordset(["state", "seat_reserved"])
        self.departure.invalidate_recordset(
            ["reserved_seats", "remaining_seats"]
        )

        self.assertEqual(order.state, "cancel")
        self.assertFalse(order.seat_reserved)
        self.assertEqual(self.departure.reserved_seats, 0)
        self.assertEqual(
            self.departure.remaining_seats, self.departure.quota
        )
        self.assertTrue(
            order.message_ids.filtered(
                lambda message: reason in str(message.body)
            )
        )

        release_note_count = len(self._release_notes(order))
        self.assertFalse(order._travel_release_seats())
        self.assertEqual(len(self._release_notes(order)), release_note_count)

        with self.assertRaises(UserError):
            order.with_user(self.manager).action_draft()
        with self.assertRaises(UserError):
            order.with_user(
                self.manager
            ).action_open_travel_cancel_wizard()

    def test_posted_unpaid_dp_uses_manager_boundary_without_release(self):
        order = self._confirmed_booking("CANCEL-UNPAID")
        self._posted_downpayment(order)
        self.assertFalse(order.seat_reserved)

        self._cancel_wizard(
            order, "Batal sebelum pembayaran diterima"
        ).action_confirm_cancel()
        order.invalidate_recordset(["state", "seat_reserved"])

        self.assertEqual(order.state, "cancel")
        self.assertFalse(order.seat_reserved)
        self.assertEqual(self.departure.reserved_seats, 0)
        self.assertFalse(self._release_notes(order))
