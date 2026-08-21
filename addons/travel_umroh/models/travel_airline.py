from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelAirline(models.Model):
    _name = "travel.airline"
    _description = "Maskapai Travel Umroh"
    _order = "name, id"

    name = fields.Char(string="Nama Maskapai", required=True)
    iata_code = fields.Char(string="Kode IATA", help="Kode IATA maskapai, maksimal 3 karakter.")
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
        for airline in self:
            if airline.iata_code and len(airline.iata_code) > 3:
                raise ValidationError(_("Kode IATA maskapai maksimal 3 karakter."))

    @staticmethod
    def _normalize_iata_code(value):
        return value.strip().upper() if value else False
