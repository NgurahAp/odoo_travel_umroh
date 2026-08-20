from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class TravelDeparture(models.Model):
    _name = "travel.departure"
    _description = "Keberangkatan Travel Umroh"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "departure_date desc, id desc"

    name = fields.Char(
        string="Nama Keberangkatan",
        compute="_compute_name",
        store=True,
    )
    package_id = fields.Many2one(
        "travel.package",
        string="Paket",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    departure_date = fields.Date(
        string="Tanggal Keberangkatan",
        required=True,
        tracking=True,
    )
    return_date = fields.Date(
        string="Tanggal Kepulangan",
        required=True,
        tracking=True,
    )
    quota = fields.Integer(string="Kuota", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Perusahaan",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Mata Uang",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Dibuka"),
            ("departed", "Berangkat"),
            ("done", "Selesai"),
            ("cancelled", "Dibatalkan"),
        ],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    price_ids = fields.One2many(
        "travel.departure.price",
        "departure_id",
        string="Harga per Tipe Kamar",
    )
    flight_ids = fields.One2many(
        "travel.departure.flight",
        "departure_id",
        string="Itinerary Penerbangan",
    )
    accommodation_ids = fields.One2many(
        "travel.departure.accommodation",
        "departure_id",
        string="Itinerary Akomodasi",
    )
    active = fields.Boolean(string="Aktif", default=True)

    @api.depends("package_id.code", "departure_date")
    def _compute_name(self):
        for departure in self:
            if departure.package_id and departure.departure_date:
                date_label = fields.Date.to_date(departure.departure_date).strftime(
                    "%d %b %Y"
                )
                departure.name = f"{departure.package_id.code} — {date_label}"
            elif departure.package_id:
                departure.name = departure.package_id.code
            else:
                departure.name = _("Keberangkatan Baru")

    @api.constrains("departure_date", "return_date")
    def _check_trip_dates(self):
        for departure in self:
            if (
                departure.departure_date
                and departure.return_date
                and departure.return_date <= departure.departure_date
            ):
                raise ValidationError(
                    _("Tanggal kepulangan harus setelah tanggal keberangkatan.")
                )
            if (
                departure.state in {"open", "departed", "done"}
                and departure._get_out_of_range_accommodations()
            ):
                raise ValidationError(
                    _(
                        "Akomodasi keberangkatan yang sudah dibuka harus tetap berada "
                        "dalam rentang perjalanan."
                    )
                )

    @api.constrains("quota")
    def _check_quota(self):
        for departure in self:
            if departure.quota < 0:
                raise ValidationError(_("Kuota keberangkatan tidak boleh negatif."))

    def write(self, values):
        if "state" in values:
            raise UserError(
                _("Gunakan aksi status keberangkatan untuk mengubah status.")
            )
        return super().write(values)

    def action_open(self):
        required_room_types = {"quad", "triple", "double"}
        for departure in self:
            if departure.state != "draft":
                raise UserError(_("Hanya keberangkatan Draft yang dapat dibuka."))
            configured_room_types = set(departure.price_ids.mapped("room_type"))
            missing_room_types = required_room_types - configured_room_types
            if missing_room_types:
                labels = dict(
                    self.env["travel.departure.price"]._fields["room_type"].selection
                )
                missing_labels = ", ".join(
                    labels[room_type] for room_type in sorted(missing_room_types)
                )
                raise UserError(
                    _(
                        "Harga kamar belum lengkap. Tambahkan harga untuk: %(rooms)s.",
                        rooms=missing_labels,
                    )
                )
            invalid_stays = departure._get_out_of_range_accommodations()
            if invalid_stays:
                raise UserError(
                    _(
                        "Akomodasi harus berada dalam rentang %(start)s sampai %(end)s.",
                        start=departure.departure_date,
                        end=departure.return_date,
                    )
                )
        super(TravelDeparture, self).write({"state": "open"})
        return True

    def _get_out_of_range_accommodations(self):
        self.ensure_one()
        if not self.departure_date or not self.return_date:
            return self.env["travel.departure.accommodation"]
        return self.accommodation_ids.filtered(
            lambda stay: stay.check_in < self.departure_date
            or stay.check_out > self.return_date
        )

    def action_cancel(self):
        for departure in self:
            if departure.state not in {"draft", "open"}:
                raise UserError(
                    _("Hanya keberangkatan Draft atau Dibuka yang dapat dibatalkan.")
                )
        super(TravelDeparture, self).write({"state": "cancelled"})
        return True
