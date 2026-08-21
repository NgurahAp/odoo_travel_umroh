from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelHotel(models.Model):
    _name = "travel.hotel"
    _description = "Hotel Travel Umroh"
    _order = "city, name, id"

    name = fields.Char(string="Nama Hotel", required=True)
    city = fields.Char(string="Kota", required=True)
    star_rating = fields.Integer(string="Rating Bintang", required=True)
    distance_to_mosque_km = fields.Float(
        string="Jarak ke Masjid (km)",
        help="Informasi opsional jarak hotel ke masjid dalam kilometer.",
    )
    active = fields.Boolean(string="Aktif", default=True)

    @api.constrains("star_rating")
    def _check_star_rating(self):
        for hotel in self:
            if not 1 <= hotel.star_rating <= 5:
                raise ValidationError(_("Rating hotel harus antara 1 dan 5 bintang."))

    @api.constrains("distance_to_mosque_km")
    def _check_distance_to_mosque(self):
        for hotel in self:
            if hotel.distance_to_mosque_km < 0:
                raise ValidationError(_("Jarak hotel ke masjid tidak boleh negatif."))
