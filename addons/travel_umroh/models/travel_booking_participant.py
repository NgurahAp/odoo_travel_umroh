from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TravelBookingParticipant(models.Model):
    _name = "travel.booking.participant"
    _description = "Participant Booking Travel Umroh"
    _order = "order_id, id"

    order_id = fields.Many2one(
        "sale.order",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
    )
    jamaah_id = fields.Many2one(
        "travel.jamaah",
        string="Jamaah",
        required=True,
        ondelete="restrict",
        index=True,
    )
    room_type = fields.Selection(
        [
            ("quad", "Quad"),
            ("triple", "Triple"),
            ("double", "Double"),
        ],
        string="Tipe Kamar",
        required=True,
    )
    unit_price = fields.Monetary(
        string="Harga Snapshot", required=True, copy=False
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.currency_id",
        store=True,
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Baris Sales Order",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    _sql_constraints = [
        (
            "order_jamaah_uniq",
            "unique(order_id, jamaah_id)",
            "Jamaah tidak boleh didaftarkan dua kali dalam satu booking.",
        ),
        (
            "sale_line_uniq",
            "unique(sale_line_id)",
            "Baris Sales Order participant harus unik.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        prepared_values = []
        for incoming_values in vals_list:
            values = dict(incoming_values)
            order = self.env["sale.order"].browse(values.get("order_id"))
            room_type = values.get("room_type")
            departure_price = self._get_departure_price(order, room_type)
            values["unit_price"] = departure_price.price
            prepared_values.append(values)

        participants = super().create(prepared_values)
        for participant in participants:
            line = self.env[
                "sale.order.line"
            ]._travel_create_participant_lines(
                [participant._prepare_sale_line_values()]
            )
            super(TravelBookingParticipant, participant).write(
                {"sale_line_id": line.id}
            )
        return participants

    def unlink(self):
        lines = self.mapped("sale_line_id")
        result = super().unlink()
        if lines:
            lines._travel_unlink_from_participant()
        return result

    @api.model
    def _get_departure_price(self, order, room_type):
        if not order.exists() or not order.is_travel_booking:
            raise UserError(_("Participant harus berada pada Booking Travel."))
        departure = order.departure_id
        if not departure or departure.state != "open" or not departure.active:
            raise UserError(
                _("Pilih keberangkatan aktif yang berstatus Dibuka terlebih dahulu.")
            )
        prices = departure.price_ids.filtered(
            lambda price: price.room_type == room_type
        )
        if len(prices) != 1:
            room_label = dict(self._fields["room_type"].selection).get(
                room_type, room_type or _("belum dipilih")
            )
            raise UserError(
                _(
                    "Harga kamar %(room)s belum tersedia untuk keberangkatan ini.",
                    room=room_label,
                )
            )
        return prices

    def _prepare_sale_line_values(self):
        self.ensure_one()
        product = self.order_id.travel_package_id.product_id
        room_label = dict(self._fields["room_type"].selection)[self.room_type]
        return {
            "order_id": self.order_id.id,
            "product_id": product.id,
            "product_uom_qty": 1,
            "product_uom": product.uom_id.id,
            "price_unit": self.unit_price,
            "name": _(
                "%(jamaah)s — %(room)s — %(departure)s",
                jamaah=self.jamaah_id.name,
                room=room_label,
                departure=self.order_id.departure_id.display_name,
            ),
            "travel_participant_id": self.id,
        }
