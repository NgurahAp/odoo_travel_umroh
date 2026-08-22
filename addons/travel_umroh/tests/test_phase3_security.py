import base64

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseThreeAccountingSecurity(TravelAccountingCase):
    def test_finance_can_invoice_verified_jamaah_without_contact_write(self):
        jamaah = self._create_jamaah(
            "SEC-VERIFIED-BUYER",
            email="verified-buyer@example.test",
            passport_number="SEC-VERIFIED-PASS",
            passport_expiry="2032-01-01",
            ktp_file=base64.b64encode(b"verified-ktp"),
            ktp_filename="verified-ktp.pdf",
            passport_file=base64.b64encode(b"verified-passport"),
            passport_filename="verified-passport.pdf",
        )
        jamaah.with_user(self.staff).action_submit_documents()
        jamaah.with_user(self.manager).action_verify_documents()
        order = self.env["sale.order"].with_user(self.staff).create(
            {
                "partner_id": jamaah.partner_id.id,
                "user_id": self.staff.id,
                "is_travel_booking": True,
                "departure_id": self.departure.id,
            }
        )
        self.env["travel.booking.participant"].with_user(self.staff).create(
            {
                "order_id": order.id,
                "jamaah_id": jamaah.id,
                "room_type": "quad",
            }
        )
        order.with_user(self.staff).action_confirm()

        with self.assertRaises(AccessError):
            jamaah.partner_id.with_user(self.finance).write(
                {"signup_type": "signup"}
            )

        self.env["ir.config_parameter"].sudo().set_param(
            "auth_signup.invitation_scope", "b2c"
        )
        auth_params = (
            jamaah.partner_id.with_user(self.finance)
            .sudo()
            .signup_get_auth_param()
        )
        self.assertIn("auth_signup_token", auth_params[jamaah.partner_id.id])
        invoice = self._create_downpayment_invoice(order)

        self.assertEqual(invoice.partner_id, jamaah.partner_id)
        self.assertEqual(invoice.state, "draft")

    def test_finance_gets_standard_billing_but_not_sales_user(self):
        self.assertTrue(
            self.finance.has_group("account.group_account_invoice")
        )
        self.assertFalse(
            self.finance.has_group("sales_team.group_sale_salesman")
        )
        self.env["sale.advance.payment.inv"].with_user(
            self.finance
        ).check_access("create")

    def test_staff_cannot_run_accounting_wizard_for_travel_booking(self):
        order = self._confirmed_booking("SEC-STAFF")
        wizard = (
            self.env["sale.advance.payment.inv"]
            .with_user(self.staff)
            .with_context(
                active_model="sale.order",
                active_id=order.id,
                active_ids=order.ids,
            )
            .create({"advance_payment_method": "percentage", "amount": 20})
        )

        with self.assertRaises(AccessError):
            wizard.create_invoices()

    def test_staff_cannot_reverse_or_register_accounting_payments(self):
        order = self._confirmed_booking("SEC-REFUND")
        invoice = self._create_downpayment_invoice(order)
        invoice.with_user(self.finance).action_post()

        for model_name in (
            "account.move.reversal",
            "account.payment.register",
        ):
            with self.subTest(model=model_name), self.assertRaises(AccessError):
                self.env[model_name].with_user(self.staff).check_access(
                    "create"
                )
            self.env[model_name].with_user(self.finance).check_access("create")
            self.env[model_name].with_user(self.manager).check_access("create")

    def test_finance_cannot_mutate_booking_despite_standard_account_acl(self):
        order = self._confirmed_booking("SEC-FIN")
        line = order.order_line.filtered(lambda item: not item.display_type)

        with self.assertRaises(AccessError):
            order.with_user(self.finance).write(
                {"client_order_ref": "DENIED"}
            )
        with self.assertRaises(AccessError):
            line.with_user(self.finance).write({"price_unit": 1})
        with self.assertRaises(AccessError):
            line.with_user(self.finance).unlink()

    def test_finance_cannot_create_sales_order_or_ordinary_line(self):
        with self.assertRaises(AccessError):
            self.env["sale.order"].with_user(self.finance).create(
                {"partner_id": self.buyer.id}
            )

    def test_rpc_context_cannot_forge_travel_downpayment_line(self):
        order = self._confirmed_booking("SEC-SPOOF")

        with self.assertRaises(UserError):
            self.env["sale.order.line"].with_user(self.finance).with_context(
                _travel_allow_downpayment_line=True
            ).create(
                {
                    "order_id": order.id,
                    "product_id": self.travel_service_product.id,
                    "product_uom_qty": 1,
                    "price_unit": 1,
                    "is_downpayment": True,
                }
            )

    def test_role_selector_updates_accounting_implications(self):
        account_group = self.env.ref("account.group_account_invoice")
        unrelated_group = self.env["res.groups"].create(
            {"name": "Phase 3 Unrelated Group"}
        )
        user = self._create_role_user("phase3-switch", "group_travel_finance")
        user.groups_id = [Command.link(unrelated_group.id)]

        self.assertIn(account_group, user.groups_id)
        self.assertNotIn(
            self.env.ref("sales_team.group_sale_salesman"), user.groups_id
        )

        user.write({"travel_umroh_role": "manager"})
        self.assertIn(account_group, user.groups_id)
        self.assertIn(
            self.env.ref("sales_team.group_sale_salesman"), user.groups_id
        )

        user.write({"travel_umroh_role": "staff"})
        self.assertNotIn(account_group, user.groups_id)
        self.assertIn(unrelated_group, user.groups_id)
