from odoo import _, api, models
from odoo.exceptions import UserError


class TravelDemo(models.AbstractModel):
    _name = "travel.demo"
    _description = "Travel Umroh Demo Data Loader"

    @api.model
    def _open_demo_departures(self):
        for xmlid in (
            "travel_umroh.demo_departure_reg_01",
            "travel_umroh.demo_departure_reg_02",
        ):
            departure = self.env.ref(xmlid)
            if departure.state == "draft":
                departure.action_open()
        return True

    @api.model
    def _load_demo_accounting_states(self):
        return self._complete_demo_accounting(
            self.env.ref("travel_umroh.demo_booking_dp"),
            self.env.ref("travel_umroh.demo_booking_paid"),
        )

    @api.model
    def _complete_demo_accounting(self, dp_order, paid_order):
        if not self.env.su:
            return self.sudo()._complete_demo_accounting(
                dp_order.sudo(), paid_order.sudo()
            )
        orders = dp_order | paid_order
        if (
            not dp_order
            or not paid_order
            or dp_order == paid_order
            or len(orders) != 2
            or not all(orders.mapped("is_travel_booking"))
        ):
            raise UserError(
                _("Loader demo memerlukan dua Booking Travel yang berbeda.")
            )

        for order in orders:
            if order.state in ("draft", "sent"):
                order.action_confirm()
            elif order.state != "sale":
                raise UserError(
                    _(
                        "Booking demo %(booking)s harus Draft atau Sales Order.",
                        booking=order.display_name,
                    )
                )

        dp_order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        if not dp_order.invoice_ids:
            dp_invoice = self._create_demo_downpayment(dp_order, 20)
            dp_invoice.action_post()
        else:
            self._require_demo_payment_state(dp_order, "dp")

        paid_order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        if not paid_order.invoice_ids:
            paid_dp_invoice = self._create_demo_downpayment(paid_order, 20)
            paid_dp_invoice.action_post()
            self._pay_demo_invoice(paid_dp_invoice)
            final_invoice = self._create_demo_final_invoice(paid_order)
            final_invoice.action_post()
            self._pay_demo_invoice(final_invoice)
        else:
            self._require_demo_payment_state(paid_order, "paid")

        return True

    @api.model
    def _create_demo_downpayment(self, order, percentage):
        return self._create_demo_invoice(
            order,
            "percentage",
            amount=percentage,
        )

    @api.model
    def _create_demo_final_invoice(self, order):
        return self._create_demo_invoice(
            order,
            "delivered",
            deduct_down_payments=True,
        )

    @api.model
    def _create_demo_invoice(self, order, method, **values):
        journal = self._demo_journal(order, "sale")
        self._ensure_demo_income_account(order)
        existing_invoices = order.invoice_ids
        wizard = (
            self.env["sale.advance.payment.inv"]
            .with_company(order.company_id)
            .with_context(
                active_model="sale.order",
                active_id=order.id,
                active_ids=order.ids,
                default_journal_id=journal.id,
            )
            .create({"advance_payment_method": method, **values})
        )
        wizard.create_invoices()
        order.invalidate_recordset(["invoice_ids", "invoice_status"])
        new_invoices = order.invoice_ids - existing_invoices
        if len(new_invoices) != 1:
            raise UserError(
                _(
                    "Workflow invoice demo %(booking)s tidak menghasilkan "
                    "tepat satu invoice.",
                    booking=order.display_name,
                )
            )
        return new_invoices

    @api.model
    def _pay_demo_invoice(self, invoice):
        journal = self._demo_journal(invoice, "bank")
        (
            self.env["account.payment.register"]
            .with_company(invoice.company_id)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create({"journal_id": journal.id})
            .action_create_payments()
        )
        invoice.invalidate_recordset(["amount_residual", "payment_state"])
        return invoice

    @api.model
    def _demo_journal(self, record, journal_type):
        company = record.company_id
        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", company.id),
                ("type", "=", journal_type),
            ],
            limit=1,
        )
        if not journal:
            labels = {"sale": _("Penjualan"), "bank": _("Bank")}
            raise UserError(
                _(
                    "Data demo memerlukan jurnal %(journal)s untuk "
                    "perusahaan %(company)s.",
                    journal=labels[journal_type],
                    company=company.display_name,
                )
            )
        return journal

    @api.model
    def _ensure_demo_income_account(self, order):
        template = order.travel_package_id.product_id.product_tmpl_id
        template = template.with_company(order.company_id)
        if template.property_account_income_id:
            return template.property_account_income_id
        account = self.env["account.account"].search(
            [
                ("company_ids", "in", order.company_id.id),
                ("account_type", "in", ("income", "income_other")),
                ("deprecated", "=", False),
            ],
            limit=1,
        )
        if not account:
            raise UserError(
                _(
                    "Data demo memerlukan akun pendapatan untuk perusahaan "
                    "%(company)s.",
                    company=order.company_id.display_name,
                )
            )
        template.sudo().property_account_income_id = account
        return account

    @staticmethod
    def _require_demo_payment_state(order, expected_state):
        order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        if order.travel_payment_state != expected_state:
            raise UserError(
                _(
                    "Booking demo %(booking)s sudah memiliki invoice tetapi "
                    "status pembayarannya bukan %(state)s.",
                    booking=order.display_name,
                    state=expected_state,
                )
            )
