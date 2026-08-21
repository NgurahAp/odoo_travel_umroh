from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelJamaah(models.Model):
    _name = "travel.jamaah"
    _description = "Profil Jamaah Travel Umroh"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "partner_id"
    _order = "partner_id, id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Kontak",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    name = fields.Char(related="partner_id.name", readonly=False)
    phone = fields.Char(related="partner_id.phone", readonly=False)
    email = fields.Char(related="partner_id.email", readonly=False)
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    city = fields.Char(related="partner_id.city", readonly=False)
    state_id = fields.Many2one(related="partner_id.state_id", readonly=False)
    zip = fields.Char(related="partner_id.zip", readonly=False)
    country_id = fields.Many2one(related="partner_id.country_id", readonly=False)
    nik = fields.Char(string="NIK", required=True, index=True, tracking=True)
    birth_place = fields.Char(
        string="Tempat Lahir", required=True, tracking=True
    )
    birth_date = fields.Date(
        string="Tanggal Lahir", required=True, tracking=True
    )
    age = fields.Integer(compute="_compute_age", string="Umur")
    gender = fields.Selection(
        [("male", "Laki-laki"), ("female", "Perempuan")],
        string="Jenis Kelamin",
        required=True,
        tracking=True,
    )
    passport_number = fields.Char(
        string="Nomor Paspor", index=True, tracking=True
    )
    passport_expiry = fields.Date(
        string="Masa Berlaku Paspor", tracking=True
    )
    emergency_contact_name = fields.Char(
        string="Nama Kontak Darurat", required=True, tracking=True
    )
    emergency_contact_phone = fields.Char(
        string="Telepon Kontak Darurat", required=True, tracking=True
    )

    _sql_constraints = [
        ("partner_uniq", "unique(partner_id)", "Kontak sudah memiliki profil Jamaah."),
        ("nik_uniq", "unique(nik)", "NIK Jamaah harus unik."),
        (
            "passport_number_uniq",
            "unique(passport_number)",
            "Nomor paspor Jamaah harus unik.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._normalize_identity_values(values)
        return super().create(vals_list)

    def write(self, values):
        self._normalize_identity_values(values)
        return super().write(values)

    @api.depends("birth_date")
    def _compute_age(self):
        for jamaah in self:
            jamaah.age = (
                relativedelta(
                    fields.Date.context_today(jamaah), jamaah.birth_date
                ).years
                if jamaah.birth_date
                else 0
            )

    @api.constrains("birth_date")
    def _check_birth_date(self):
        for jamaah in self:
            if (
                jamaah.birth_date
                and jamaah.birth_date > fields.Date.context_today(jamaah)
            ):
                raise ValidationError(
                    _("Tanggal lahir tidak boleh berada di masa depan.")
                )

    @staticmethod
    def _normalize_identity_values(values):
        if "nik" in values:
            values["nik"] = values["nik"].strip() if values["nik"] else False
        if "passport_number" in values:
            values["passport_number"] = (
                values["passport_number"].strip().upper()
                if values["passport_number"]
                else False
            )
