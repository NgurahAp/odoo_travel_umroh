from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .ir_attachment import suppress_travel_attachment_audit
from .travel_security import is_travel_manager_or_admin


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
    nik = fields.Char(string="NIK", required=True, index=True)
    birth_place = fields.Char(string="Tempat Lahir", required=True)
    birth_date = fields.Date(string="Tanggal Lahir", required=True)
    age = fields.Integer(compute="_compute_age", string="Umur")
    gender = fields.Selection(
        [("male", "Laki-laki"), ("female", "Perempuan")],
        string="Jenis Kelamin",
        required=True,
    )
    passport_number = fields.Char(string="Nomor Paspor", index=True)
    passport_expiry = fields.Date(string="Masa Berlaku Paspor")
    emergency_contact_name = fields.Char(
        string="Nama Kontak Darurat", required=True
    )
    emergency_contact_phone = fields.Char(
        string="Telepon Kontak Darurat", required=True
    )
    ktp_file = fields.Binary(
        string="File KTP", attachment=True, copy=False
    )
    ktp_filename = fields.Char(string="Nama File KTP", copy=False)
    passport_file = fields.Binary(
        string="File Paspor", attachment=True, copy=False
    )
    passport_filename = fields.Char(string="Nama File Paspor", copy=False)
    document_status = fields.Selection(
        [
            ("incomplete", "Belum Lengkap"),
            ("pending", "Menunggu Verifikasi"),
            ("verified", "Terverifikasi"),
        ],
        string="Status Dokumen",
        required=True,
        default="incomplete",
        tracking=True,
        copy=False,
        readonly=True,
    )
    verified_by = fields.Many2one(
        "res.users",
        string="Diverifikasi Oleh",
        readonly=True,
        copy=False,
    )
    verified_at = fields.Datetime(
        string="Waktu Verifikasi", readonly=True, copy=False
    )
    participant_ids = fields.One2many(
        "travel.booking.participant",
        "jamaah_id",
        string="Participant Booking",
        readonly=True,
    )
    booking_count = fields.Integer(
        string="Jumlah Booking", compute="_compute_booking_count"
    )

    _verification_metadata_fields = {
        "document_status",
        "verified_by",
        "verified_at",
    }
    _verified_profile_fields = {
        "partner_id",
        "name",
        "phone",
        "email",
        "street",
        "street2",
        "city",
        "state_id",
        "zip",
        "country_id",
        "nik",
        "birth_place",
        "birth_date",
        "gender",
        "passport_number",
        "passport_expiry",
        "emergency_contact_name",
        "emergency_contact_phone",
        "ktp_file",
        "ktp_filename",
        "passport_file",
        "passport_filename",
    }

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
            if self._verification_metadata_fields.intersection(values):
                raise UserError(
                    _(
                        "Gunakan aksi dokumen Jamaah untuk mengubah status "
                        "verifikasi."
                    )
                )
            self._normalize_identity_values(values)
        return super().create(vals_list)

    def write(self, values):
        if self._verification_metadata_fields.intersection(values):
            raise UserError(
                _(
                    "Gunakan aksi dokumen Jamaah untuk mengubah status "
                    "verifikasi."
                )
            )
        changed_profile_fields = self._verified_profile_fields.intersection(
            values
        )
        verified_records = self.filtered(
            lambda jamaah: jamaah.document_status == "verified"
        )
        if (
            verified_records
            and changed_profile_fields
            and not is_travel_manager_or_admin(self.env)
        ):
            raise AccessError(
                _(
                    "Hanya Manager Travel Umroh yang dapat mengoreksi data "
                    "Jamaah terverifikasi."
                )
            )
        self._normalize_identity_values(values)
        write_records = self.sudo() if self.env.is_admin() else self
        with suppress_travel_attachment_audit():
            result = super(TravelJamaah, write_records).write(values)
        if verified_records and changed_profile_fields:
            field_labels = ", ".join(
                self._fields[field_name].string
                for field_name in sorted(changed_profile_fields)
            )
            audit_records = (
                verified_records.sudo()
                if self.env.is_admin()
                else verified_records
            )
            for jamaah in audit_records:
                jamaah.message_post(
                    body=_(
                        "Data Jamaah terverifikasi dikoreksi oleh "
                        "%(user)s. Field: %(fields)s.",
                        user=self.env.user.display_name,
                        fields=field_labels,
                    )
                )
        return result

    def action_submit_documents(self):
        for jamaah in self:
            if jamaah.document_status != "incomplete":
                raise UserError(
                    _("Hanya dokumen yang belum lengkap yang dapat diajukan.")
                )
            if not all(
                (
                    jamaah.ktp_file,
                    jamaah.passport_number,
                    jamaah.passport_expiry,
                    jamaah.passport_file,
                )
            ):
                raise UserError(
                    _(
                        "Lengkapi file KTP, nomor dan masa berlaku paspor, "
                        "serta file paspor sebelum diajukan."
                    )
                )
            super(TravelJamaah, jamaah).write(
                {
                    "document_status": "pending",
                    "verified_by": False,
                    "verified_at": False,
                }
            )
        return True

    def action_verify_documents(self):
        if not is_travel_manager_or_admin(self.env):
            raise AccessError(
                _("Hanya Manager Travel Umroh yang dapat memverifikasi dokumen.")
            )
        for jamaah in self:
            if jamaah.document_status != "pending":
                raise UserError(
                    _("Hanya dokumen yang menunggu verifikasi yang dapat diverifikasi.")
                )
            write_record = (
                jamaah.sudo() if self.env.is_admin() else jamaah
            )
            super(TravelJamaah, write_record).write(
                {
                    "document_status": "verified",
                    "verified_by": self.env.user.id,
                    "verified_at": fields.Datetime.now(),
                }
            )
            write_record.message_post(
                body=_(
                    "Dokumen jamaah diverifikasi oleh %(user)s.",
                    user=self.env.user.display_name,
                )
            )
        return True

    @api.depends("participant_ids.order_id")
    def _compute_booking_count(self):
        for jamaah in self:
            jamaah.booking_count = len(jamaah.participant_ids.mapped("order_id"))

    def action_view_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking Jamaah"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("participant_ids.jamaah_id", "=", self.id)],
            "context": {"default_is_travel_booking": True},
        }

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
