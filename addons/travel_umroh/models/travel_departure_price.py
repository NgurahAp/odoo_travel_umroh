from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class TravelDeparturePrice(models.Model):
    _name = "travel.departure.price"
    _description = "Harga Keberangkatan Travel Umroh"
    _order = "room_type, id"

    departure_id = fields.Many2one(
        "travel.departure",
        string="Keberangkatan",
        required=True,
        ondelete="cascade",
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
    price = fields.Monetary(string="Harga per Jamaah", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Mata Uang",
        related="departure_id.currency_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "departure_room_type_uniq",
            "unique(departure_id, room_type)",
            "Setiap tipe kamar hanya boleh memiliki satu harga per keberangkatan.",
        ),
    ]

    @api.constrains("price")
    def _check_price(self):
        for departure_price in self:
            if departure_price.price < 0:
                raise ValidationError(_("Harga keberangkatan tidak boleh negatif."))

    def write(self, values):
        if {"departure_id", "room_type"} & values.keys():
            departures = self.mapped("departure_id")
            if values.get("departure_id"):
                departures |= self.env["travel.departure"].browse(
                    values["departure_id"]
                )
            self._ensure_departures_allow_price_structure_changes(departures)
        return super().write(values)

    def unlink(self):
        self._ensure_departures_allow_price_structure_changes(
            self.mapped("departure_id")
        )
        return super().unlink()

    def _ensure_departures_allow_price_structure_changes(self, departures):
        if departures.filtered(lambda departure: departure.state != "draft"):
            raise UserError(
                _(
                    "Struktur harga hanya dapat diubah saat keberangkatan masih Draft."
                )
            )
