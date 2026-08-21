from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelAirport(models.Model):
    _name = "travel.airport"
    _description = "Bandara Travel Umroh"
    _order = "city, name, id"

    name = fields.Char(string="Nama Bandara", required=True)
    iata_code = fields.Char(string="Kode IATA", required=True, help="Kode IATA bandara, maksimal 3 karakter.")
    city = fields.Char(string="Kota", required=True)
    country_id = fields.Many2one(
        "res.country",
        string="Negara",
        required=True,
        ondelete="restrict",
    )
    active = fields.Boolean(string="Aktif", default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if "iata_code" in values:
                values["iata_code"] = self._normalize_iata_code(values["iata_code"])
        return super().create(vals_list)

    def write(self, values):
        if "iata_code" in values:
            values["iata_code"] = self._normalize_iata_code(values["iata_code"])
        return super().write(values)

    @api.constrains("iata_code")
    def _check_iata_code_length(self):
        for airport in self:
            if airport.iata_code and len(airport.iata_code) > 3:
                raise ValidationError(_("Kode IATA bandara maksimal 3 karakter."))

    @staticmethod
    def _normalize_iata_code(value):
        return value.strip().upper() if value else False
