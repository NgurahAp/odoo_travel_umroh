from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    travel_participant_id = fields.Many2one(
        "travel.booking.participant",
        string="Participant Booking Travel",
        copy=False,
        readonly=True,
        ondelete="set null",
        index=True,
    )

    _sql_constraints = [
        (
            "travel_participant_uniq",
            "unique(travel_participant_id)",
            "Setiap participant hanya boleh memiliki satu baris Sales Order.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        if any(values.get("travel_participant_id") for values in vals_list):
            raise UserError(
                _("Baris participant hanya dapat dibuat melalui Booking Travel.")
            )
        order_ids = {
            values.get("order_id") for values in vals_list if values.get("order_id")
        }
        if self.env["sale.order"].browse(order_ids).filtered(
            "is_travel_booking"
        ):
            raise UserError(
                _(
                    "Baris Sales Booking Travel hanya dapat dibuat dari "
                    "Participant."
                )
            )
        return super().create(vals_list)

    def write(self, values):
        self.check_access("write")
        if self.filtered("travel_participant_id"):
            raise UserError(
                _("Ubah baris harga melalui Participant Booking Travel.")
            )
        return super().write(values)

    def unlink(self):
        self.check_access("unlink")
        if self.filtered("travel_participant_id"):
            raise UserError(
                _("Ubah baris harga melalui Participant Booking Travel.")
            )
        return super().unlink()

    @api.model
    def _travel_create_participant_lines(self, vals_list):
        return super(SaleOrderLine, self).create(vals_list)

    def _travel_write_from_participant(self, values):
        return super(SaleOrderLine, self).write(values)

    def _travel_unlink_from_participant(self):
        return super(SaleOrderLine, self).unlink()
