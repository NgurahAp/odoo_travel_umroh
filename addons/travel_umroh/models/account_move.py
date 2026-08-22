from odoo import models

from .sale_advance_payment_inv import allow_travel_downpayment_line_posting


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        travel_downpayment_lines = self.invoice_line_ids.sale_line_ids.filtered(
            lambda line: line.is_downpayment
            and line.order_id.is_travel_booking
        )
        if travel_downpayment_lines:
            with allow_travel_downpayment_line_posting():
                return super().action_post()
        return super().action_post()

    def _travel_is_downpayment_only(self):
        self.ensure_one()
        linked_lines = self.invoice_line_ids.sale_line_ids.filtered(
            lambda line: not line.display_type
        )
        downpayment_lines = linked_lines.filtered("is_downpayment")
        regular_lines = linked_lines.filtered(
            lambda line: not line.is_downpayment
        )
        return bool(downpayment_lines) and not regular_lines
