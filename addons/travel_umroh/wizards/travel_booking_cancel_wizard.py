from odoo import _, fields, models
from odoo.exceptions import UserError


class TravelBookingCancelWizard(models.TransientModel):
    _name = "travel.booking.cancel.wizard"
    _description = "Travel Booking Cancellation after Down Payment"

    order_id = fields.Many2one(
        "sale.order",
        string="Booking",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    reason = fields.Text(string="Alasan Pembatalan", required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("Alasan pembatalan wajib diisi."))
        self.order_id._travel_cancel_after_dp(reason)
        return {"type": "ir.actions.act_window_close"}
