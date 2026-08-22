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
