from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestTravelPaymentState(TravelAccountingCase):
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

    def test_ordinary_sales_order_has_no_travel_payment_state(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})

        self.assertFalse(order.travel_payment_state)

    def test_travel_payment_state_cannot_be_written(self):
        order = self._confirmed_booking("PAY-FORGE")

        for user in (self.staff, self.finance, self.manager):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                order.with_user(user).write({"travel_payment_state": "paid"})
