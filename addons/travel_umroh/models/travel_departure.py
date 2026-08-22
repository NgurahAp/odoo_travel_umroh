from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


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
    booking_ids = fields.One2many(
        "sale.order", "departure_id", string="Booking"
    )
    booking_count = fields.Integer(
        string="Jumlah Booking", compute="_compute_booking_count"
    )
    reserved_seats = fields.Integer(
        string="Kursi Direservasi",
        compute="_compute_seat_capacity",
        store=True,
    )
    remaining_seats = fields.Integer(
        string="Sisa Kursi",
        compute="_compute_seat_capacity",
        store=True,
    )
    is_full = fields.Boolean(
        string="Kuota Penuh",
        compute="_compute_seat_capacity",
        store=True,
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

    @api.depends("booking_ids")
    def _compute_booking_count(self):
        for departure in self:
            departure.booking_count = len(departure.booking_ids)

    @api.depends(
        "quota",
        "booking_ids.seat_reserved",
        "booking_ids.state",
        "booking_ids.participant_ids",
    )
    def _compute_seat_capacity(self):
        for departure in self:
            reserved_bookings = departure.booking_ids.filtered(
                lambda booking: booking.seat_reserved
                and booking.state != "cancel"
            )
            departure.reserved_seats = sum(
                len(booking.participant_ids) for booking in reserved_bookings
            )
            departure.remaining_seats = (
                departure.quota - departure.reserved_seats
            )
            departure.is_full = departure.remaining_seats <= 0

    def action_view_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("departure_id", "=", self.id)],
            "context": {
                "default_is_travel_booking": True,
                "default_departure_id": self.id,
            },
        }

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
            if departure.quota < departure.reserved_seats:
                raise ValidationError(
                    _(
                        "Kuota tidak boleh lebih kecil dari %(reserved)s "
                        "kursi yang sudah direservasi.",
                        reserved=departure.reserved_seats,
                    )
                )

    def write(self, values):
        if "state" in values:
            raise UserError(
                _("Gunakan aksi status keberangkatan untuk mengubah status.")
            )
        return super().write(values)

    def action_open(self):
        self._check_travel_manager_access()
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

    def _check_travel_manager_access(self):
        if not (
            self.env.is_admin()
            or self.env.user.has_group(
                "travel_umroh.group_travel_manager"
            )
        ):
            raise AccessError(
                _(
                    "Hanya Manager Travel Umroh yang dapat mengubah "
                    "siklus keberangkatan."
                )
            )

    def _reserved_active_participants(self):
        self.ensure_one()
        return self.booking_ids.filtered(
            lambda booking: booking.state == "sale"
            and booking.seat_reserved
        ).participant_ids

    def action_depart(self):
        self._check_travel_manager_access()
        for departure in self:
            if departure.state != "open":
                raise UserError(
                    _(
                        "Hanya keberangkatan berstatus Dibuka yang dapat "
                        "ditandai Berangkat."
                    )
                )
            incomplete_jamaah = (
                departure._reserved_active_participants()
                .jamaah_id.filtered(
                    lambda jamaah: jamaah.document_status != "verified"
                )
            )
            if incomplete_jamaah:
                raise UserError(
                    _(
                        "%(count)s Jamaah belum memiliki dokumen "
                        "terverifikasi: %(names)s.",
                        count=len(incomplete_jamaah),
                        names=", ".join(
                            incomplete_jamaah.mapped("display_name")
                        ),
                    )
                )
        super(TravelDeparture, self).write({"state": "departed"})
        return True

    def action_done(self):
        self._check_travel_manager_access()
        for departure in self:
            if departure.state != "departed":
                raise UserError(
                    _(
                        "Hanya keberangkatan berstatus Berangkat yang dapat "
                        "ditandai Selesai."
                    )
                )
        super(TravelDeparture, self).write({"state": "done"})
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
        self._check_travel_manager_access()
        for departure in self:
            if departure.state not in {"draft", "open"}:
                raise UserError(
                    _("Hanya keberangkatan Draft atau Dibuka yang dapat dibatalkan.")
                )
        super(TravelDeparture, self).write({"state": "cancelled"})
        return True
