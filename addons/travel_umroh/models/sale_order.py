from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_travel_booking = fields.Boolean(
        string="Booking Travel Umroh",
        default=False,
        index=True,
        copy=False,
        tracking=True,
    )
    departure_id = fields.Many2one(
        "travel.departure",
        string="Keberangkatan",
        ondelete="restrict",
        check_company=True,
        tracking=True,
    )
    travel_package_id = fields.Many2one(
        "travel.package",
        string="Paket Travel",
        related="departure_id.package_id",
        store=True,
        readonly=True,
    )
    participant_ids = fields.One2many(
        "travel.booking.participant",
        "order_id",
        string="Participant",
        copy=False,
    )
    participant_count = fields.Integer(
        string="Jumlah Participant", compute="_compute_participant_count"
    )

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for order in self:
            order.participant_count = len(order.participant_ids)

    def write(self, values):
        if values.get("is_travel_booking") is False and self.filtered(
            lambda order: order.departure_id or order.participant_ids
        ):
            raise ValidationError(
                _(
                    "Status Booking Travel tidak dapat dilepas setelah "
                    "keberangkatan dipilih."
                )
            )
        return super().write(values)

    @api.constrains(
        "is_travel_booking", "departure_id", "company_id", "pricelist_id"
    )
    def _check_travel_booking_configuration(self):
        for order in self:
            departure = order.departure_id
            if not departure:
                continue
            if not order.is_travel_booking:
                raise ValidationError(
                    _(
                        "Keberangkatan hanya dapat dipilih pada Booking Travel "
                        "Umroh."
                    )
                )
            if departure.state != "open" or not departure.active:
                raise ValidationError(
                    _("Pilih keberangkatan aktif yang berstatus Dibuka.")
                )
            if order.company_id != departure.company_id:
                raise ValidationError(
                    _(
                        "Perusahaan Sales Order harus sama dengan perusahaan "
                        "keberangkatan."
                    )
                )
            if order.currency_id != departure.currency_id:
                raise ValidationError(
                    _(
                        "Mata uang pricelist Sales Order harus sama dengan "
                        "mata uang keberangkatan."
                    )
                )
