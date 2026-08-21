from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelDepartureAccommodation(models.Model):
    _name = "travel.departure.accommodation"
    _description = "Akomodasi Keberangkatan Travel Umroh"
    _order = "sequence, check_in, id"

    departure_id = fields.Many2one(
        "travel.departure",
        string="Keberangkatan",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Urutan", default=10)
    hotel_id = fields.Many2one(
        "travel.hotel",
        string="Hotel",
        required=True,
        ondelete="restrict",
    )
    check_in = fields.Date(string="Check-in", required=True)
    check_out = fields.Date(string="Check-out", required=True)

    @api.constrains("check_in", "check_out")
    def _check_stay_dates(self):
        for accommodation in self:
            if (
                accommodation.check_in
                and accommodation.check_out
                and accommodation.check_out <= accommodation.check_in
            ):
                raise ValidationError(_("Tanggal check-out harus setelah check-in."))

    @api.constrains("departure_id", "check_in", "check_out")
    def _check_open_departure_trip_window(self):
        for accommodation in self:
            departure = accommodation.departure_id
            if departure.state not in {"open", "departed", "done"}:
                continue
            if (
                accommodation.check_in < departure.departure_date
                or accommodation.check_out > departure.return_date
            ):
                raise ValidationError(
                    _(
                        "Akomodasi keberangkatan yang sudah dibuka harus berada "
                        "dalam rentang perjalanan."
                    )
                )
