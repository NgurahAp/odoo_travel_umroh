from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .sale_advance_payment_inv import (
    is_travel_downpayment_line_creation_allowed,
)


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
        trusted_downpayment = (
            is_travel_downpayment_line_creation_allowed()
            and vals_list
            and all(
                values.get("is_downpayment")
                and not values.get("travel_participant_id")
                for values in vals_list
            )
        )
        if self._is_travel_finance_only() and not trusted_downpayment:
            raise AccessError(
                _("Finance Travel Umroh tidak dapat membuat baris Sales.")
            )
        if any(values.get("travel_participant_id") for values in vals_list):
            raise UserError(
                _("Baris participant hanya dapat dibuat melalui Booking Travel.")
            )
        order_ids = {
            values.get("order_id") for values in vals_list if values.get("order_id")
        }
        travel_orders = self.env["sale.order"].browse(order_ids).filtered(
            "is_travel_booking"
        )
        if travel_orders and trusted_downpayment:
            if (
                len(travel_orders) != len(order_ids)
                or any(order.state != "sale" for order in travel_orders)
            ):
                raise UserError(
                    _(
                        "Uang muka hanya dapat dibuat untuk Booking Travel "
                        "yang sudah dikonfirmasi."
                    )
                )
            return super().create(vals_list)
        if travel_orders:
            raise UserError(
                _(
                    "Baris Sales Booking Travel hanya dapat dibuat dari "
                    "Participant."
                )
            )
        return super().create(vals_list)

    def write(self, values):
        self.check_access("write")
        if self._is_travel_finance_only():
            raise AccessError(
                _("Finance Travel Umroh tidak dapat mengubah baris Sales.")
            )
        if "order_id" in values:
            target_order = self.env["sale.order"].browse(values["order_id"])
            if target_order.is_travel_booking:
                raise UserError(
                    _(
                        "Baris Sales biasa tidak dapat dipindahkan ke Booking "
                        "Travel. Tambahkan Jamaah melalui Participant."
                    )
                )
        if self.filtered("travel_participant_id"):
            raise UserError(
                _("Ubah baris harga melalui Participant Booking Travel.")
            )
        return super().write(values)

    def unlink(self):
        self.check_access("unlink")
        if self._is_travel_finance_only():
            raise AccessError(
                _("Finance Travel Umroh tidak dapat menghapus baris Sales.")
            )
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

    def _is_travel_finance_only(self):
        user = self.env.user
        return (
            not self.env.is_admin()
            and user.has_group("travel_umroh.group_travel_finance")
            and not user.has_group("travel_umroh.group_travel_staff")
        )
