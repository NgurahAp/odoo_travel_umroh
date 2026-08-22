from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestTravelPaymentState(TravelAccountingCase):
    def _pay_invoice(self, invoice):
        (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "journal_id": self.company_data[
                        "default_journal_bank"
                    ].id,
                }
            )
            .action_create_payments()
        )
        invoice.invalidate_recordset(["amount_residual", "payment_state"])

    def _create_final_invoice(self, order):
        existing_invoices = order.invoice_ids
        self._create_invoice_wizard(
            order,
            "delivered",
            deduct_down_payments=True,
        ).create_invoices()
        order.invalidate_recordset(["invoice_ids", "invoice_status"])
        return (order.invoice_ids - existing_invoices).ensure_one()

    def test_confirmed_booking_without_posted_invoice_is_unpaid(self):
        order = self._confirmed_booking("PAY-NONE")

        self.assertEqual(order.travel_payment_state, "unpaid")

    def test_draft_downpayment_invoice_remains_unpaid(self):
        order = self._confirmed_booking("PAY-DRAFT")
        self._create_downpayment_invoice(order)

        self.assertEqual(order.travel_payment_state, "unpaid")

    def test_posted_unpaid_percentage_downpayment_is_dp(self):
        order = self._confirmed_booking("PAY-POSTED")
        invoice = self._create_downpayment_invoice(order)
        invoice.with_user(self.finance).action_post()

        self.assertEqual(order.travel_payment_state, "dp")

    def test_partial_downpayment_payment_remains_dp(self):
        order = self._confirmed_booking("PAY-PARTIAL")
        invoice = self._create_downpayment_invoice(order)
        invoice.with_user(self.finance).action_post()
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

        self.assertGreater(invoice.amount_residual, 0)
        self.assertEqual(order.travel_payment_state, "dp")

    def test_fully_paid_percentage_downpayment_remains_dp(self):
        order = self._confirmed_booking("PAY-FULL-DP")
        invoice = self._create_downpayment_invoice(order)
        self._post_and_pay(invoice)

        self.assertEqual(invoice.payment_state, "paid")
        self.assertNotEqual(order.invoice_status, "invoiced")
        self.assertEqual(order.travel_payment_state, "dp")

    def test_fixed_downpayment_uses_same_state_rules(self):
        order = self._confirmed_booking("PAY-FIXED")
        invoice = self._create_downpayment_invoice(
            order, method="fixed", amount=5_000_000
        )
        self._post_and_pay(invoice)

        self.assertEqual(order.travel_payment_state, "dp")

    def test_standard_final_invoice_and_payment_reach_paid_once(self):
        order = self._confirmed_booking("PAY-FINAL", participant_count=2)
        downpayment_invoice = self._create_downpayment_invoice(order)

        downpayment_invoice.with_user(self.finance).action_post()
        self.assertEqual(self.departure.reserved_seats, 0)
        self._pay_invoice(downpayment_invoice)
        self.assertEqual(self.departure.reserved_seats, 2)
        self.assertEqual(order.travel_payment_state, "dp")

        final_invoice = self._create_final_invoice(order)
        participant_lines = order.participant_ids.sale_line_id
        linked_sale_lines = final_invoice.invoice_line_ids.sale_line_ids
        deducted_downpayment_lines = final_invoice.invoice_line_ids.filtered(
            lambda line: line.sale_line_ids.filtered("is_downpayment")
        )

        self.assertTrue(participant_lines <= linked_sale_lines)
        self.assertTrue(deducted_downpayment_lines)
        self.assertEqual(
            self.env.company.currency_id.compare_amounts(
                final_invoice.amount_total,
                order.amount_total - downpayment_invoice.amount_total,
            ),
            0,
        )

        self._post_and_pay(final_invoice)
        order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        self.departure.invalidate_recordset(
            ["reserved_seats", "remaining_seats", "is_full"]
        )
        order.invoice_ids.invalidate_recordset(
            ["amount_residual", "payment_state"]
        )

        self.assertEqual(order.invoice_status, "invoiced")
        self.assertTrue(
            all(
                not invoice.amount_residual
                for invoice in order.invoice_ids.filtered(
                    lambda invoice: invoice.state == "posted"
                )
            )
        )
        self.assertEqual(order.travel_payment_state, "paid")
        self.assertEqual(self.departure.reserved_seats, 2)

    def test_posted_unpaid_final_invoice_remains_dp(self):
        order = self._confirmed_booking(
            "PAY-FINAL-UNPAID", participant_count=2
        )
        downpayment_invoice = self._create_downpayment_invoice(order)
        self._post_and_pay(downpayment_invoice)
        final_invoice = self._create_final_invoice(order)

        final_invoice.with_user(self.finance).action_post()
        order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )

        self.assertGreater(final_invoice.amount_residual, 0)
        self.assertEqual(order.travel_payment_state, "dp")

    def test_ordinary_sales_order_has_no_travel_payment_state(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})

        self.assertFalse(order.travel_payment_state)

    def test_travel_payment_state_cannot_be_written(self):
        order = self._confirmed_booking("PAY-FORGE")

        for user in (self.staff, self.finance, self.manager):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                order.with_user(user).write({"travel_payment_state": "paid"})
