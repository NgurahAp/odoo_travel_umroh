from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        affected_moves = self.move_id
        result = super().reconcile()
        customer_invoices = affected_moves.filtered(
            lambda move: move.state == "posted"
            and move.move_type == "out_invoice"
        )
        customer_invoices.invalidate_recordset(
            ["amount_residual", "payment_state"]
        )
        for invoice in customer_invoices:
            if (
                invoice._travel_is_downpayment_only()
                and invoice.currency_id.is_zero(invoice.amount_residual)
                and invoice.payment_state != "reversed"
            ):
                orders = invoice.invoice_line_ids.sale_line_ids.order_id.filtered(
                    lambda order: order.is_travel_booking
                    and order.state == "sale"
                )
                for order in orders:
                    order._travel_reserve_seats()
        return result
