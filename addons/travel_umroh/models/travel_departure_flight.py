from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelDepartureFlight(models.Model):
    _name = "travel.departure.flight"
    _description = "Penerbangan Keberangkatan Travel Umroh"
    _order = "sequence, departure_datetime, id"

    departure_id = fields.Many2one(
        "travel.departure",
        string="Keberangkatan",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Urutan", default=10)
    airline_id = fields.Many2one(
        "travel.airline",
        string="Maskapai",
        required=True,
        ondelete="restrict",
    )
    flight_number = fields.Char(string="Nomor Penerbangan", required=True)
    origin_airport_id = fields.Many2one(
        "travel.airport",
        string="Bandara Asal",
        required=True,
        ondelete="restrict",
    )
    origin_terminal = fields.Char(string="Terminal Asal")
    destination_airport_id = fields.Many2one(
        "travel.airport",
        string="Bandara Tujuan",
        required=True,
        ondelete="restrict",
    )
    destination_terminal = fields.Char(string="Terminal Tujuan")
    departure_datetime = fields.Datetime(
        string="Waktu Keberangkatan",
        required=True,
    )
    arrival_datetime = fields.Datetime(string="Waktu Kedatangan", required=True)

    @api.constrains("departure_datetime", "arrival_datetime")
    def _check_flight_times(self):
        for flight in self:
            if (
                flight.departure_datetime
                and flight.arrival_datetime
                and flight.arrival_datetime <= flight.departure_datetime
            ):
                raise ValidationError(
                    _("Waktu kedatangan harus setelah waktu keberangkatan.")
                )

    @api.constrains("origin_airport_id", "destination_airport_id")
    def _check_distinct_airports(self):
        for flight in self:
            if (
                flight.origin_airport_id
                and flight.origin_airport_id == flight.destination_airport_id
            ):
                raise ValidationError(
                    _("Bandara asal dan bandara tujuan harus berbeda.")
                )
