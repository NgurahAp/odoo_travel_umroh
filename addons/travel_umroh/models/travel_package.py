from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TravelPackage(models.Model):
    _name = "travel.package"
    _description = "Paket Travel Umroh"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code, name, id"

    name = fields.Char(string="Nama Paket", required=True, tracking=True)
    code = fields.Char(
        string="Kode Paket",
        required=True,
        index=True,
        copy=False,
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Produk Jasa",
        required=True,
        tracking=True,
        ondelete="restrict",
        domain="[('type', '=', 'service'), ('invoice_policy', '=', 'order')]",
    )
    duration_days = fields.Integer(
        string="Durasi (hari)",
        required=True,
        default=9,
        tracking=True,
    )
    description = fields.Html(string="Deskripsi dan Fasilitas")
    active = fields.Boolean(string="Aktif", default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Kode paket harus unik."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if "code" in values:
                values["code"] = self._normalize_code(values["code"])
        return super().create(vals_list)

    def write(self, values):
        if "code" in values:
            values["code"] = self._normalize_code(values["code"])
        return super().write(values)

    @api.constrains("product_id")
    def _check_product_is_ordered_service(self):
        for package in self:
            if package.product_id.type != "service":
                raise ValidationError(_("Produk paket harus bertipe jasa."))
            if package.product_id.invoice_policy != "order":
                raise ValidationError(
                    _("Produk paket harus ditagihkan berdasarkan kuantitas pesanan.")
                )

    @api.constrains("duration_days")
    def _check_duration_days(self):
        for package in self:
            if package.duration_days <= 0:
                raise ValidationError(_("Durasi paket harus lebih dari 0 hari."))

    @staticmethod
    def _normalize_code(value):
        return value.strip().upper() if value else False
