from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class TravelBookingParticipant(models.Model):
    _name = "travel.booking.participant"
    _description = "Participant Booking Travel Umroh"
    _order = "order_id, id"

    order_id = fields.Many2one(
        "sale.order",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
    )
    jamaah_id = fields.Many2one(
        "travel.jamaah",
        string="Jamaah",
        required=True,
        ondelete="restrict",
        index=True,
    )
    room_type = fields.Selection(
        [
            ("quad", "Quad"),
            ("triple", "Triple"),
            ("double", "Double"),
        ],
        string="Tipe Kamar",
        required=True,
    )
    unit_price = fields.Monetary(
        string="Harga Snapshot", required=True, copy=False
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.currency_id",
        store=True,
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Baris Sales Order",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    can_override_price = fields.Boolean(
        compute="_compute_can_override_price"
    )

    _sql_constraints = [
        (
            "order_jamaah_uniq",
            "unique(order_id, jamaah_id)",
            "Jamaah tidak boleh didaftarkan dua kali dalam satu booking.",
        ),
        (
            "sale_line_uniq",
            "unique(sale_line_id)",
            "Baris Sales Order participant harus unik.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        prepared_values = []
        for incoming_values in vals_list:
            values = dict(incoming_values)
            order = self.env["sale.order"].browse(values.get("order_id"))
            self._ensure_order_mutation_allowed(order)
            room_type = values.get("room_type")
            departure_price = self._get_departure_price(order, room_type)
            values["unit_price"] = departure_price.price
            prepared_values.append(values)

        participants = super().create(prepared_values)
        for participant in participants:
            line = self.env[
                "sale.order.line"
            ]._travel_create_participant_lines(
                [participant._prepare_sale_line_values()]
            )
            super(TravelBookingParticipant, participant).write(
                {"sale_line_id": line.id}
            )
            if participant.order_id.state not in ("draft", "sent"):
                participant.order_id.message_post(
                    body=_(
                        "Koreksi participant oleh Manager: %(jamaah)s "
                        "ditambahkan dengan kamar %(room)s dan harga %(price)s.",
                        jamaah=participant.jamaah_id.name,
                        room=participant._room_label(),
                        price=participant._price_label(),
                    )
                )
        return participants

    def unlink(self):
        for participant in self:
            self._ensure_order_mutation_allowed(participant.order_id)
            if participant.order_id.state not in ("draft", "sent"):
                participant.order_id.message_post(
                    body=_(
                        "Koreksi participant oleh Manager: %(jamaah)s "
                        "dihapus (kamar %(room)s, harga %(price)s).",
                        jamaah=participant.jamaah_id.name,
                        room=participant._room_label(),
                        price=participant._price_label(),
                    )
                )
        lines = self.mapped("sale_line_id")
        result = super().unlink()
        if lines:
            lines._travel_unlink_from_participant()
        return result

    def write(self, values):
        if "order_id" in values:
            raise UserError(
                _("Participant tidak dapat dipindahkan ke booking lain.")
            )
        is_manager = self.env.user.has_group(
            "travel_umroh.group_travel_manager"
        )
        for participant in self:
            self._ensure_order_mutation_allowed(participant.order_id)
        if "unit_price" in values and not is_manager:
            raise AccessError(
                _("Hanya Manager Travel Umroh yang dapat override harga.")
            )

        old_values = {
            participant.id: {
                "jamaah": participant.jamaah_id.name,
                "room": participant._room_label(),
                "price": participant._price_label(),
                "confirmed": participant.order_id.state
                not in ("draft", "sent"),
            }
            for participant in self
        }

        result = super().write(values)
        if "unit_price" in values:
            self._sync_sale_line()
        elif "room_type" in values:
            self._refresh_from_departure_price()
        elif "jamaah_id" in values:
            self._sync_sale_line()

        audited_fields = {"jamaah_id", "room_type", "unit_price"}
        if audited_fields.intersection(values):
            for participant in self:
                previous = old_values[participant.id]
                if previous["confirmed"] or "unit_price" in values:
                    operation_label = (
                        _("Override harga participant")
                        if "unit_price" in values
                        else _("Koreksi participant")
                    )
                    participant.order_id.message_post(
                        body=_(
                            "%(operation)s oleh Manager: %(old_jamaah)s / "
                            "%(old_room)s / %(old_price)s menjadi "
                            "%(new_jamaah)s / %(new_room)s / %(new_price)s.",
                            operation=operation_label,
                            old_jamaah=previous["jamaah"],
                            old_room=previous["room"],
                            old_price=previous["price"],
                            new_jamaah=participant.jamaah_id.name,
                            new_room=participant._room_label(),
                            new_price=participant._price_label(),
                        )
                    )
        return result

    @api.depends_context("uid")
    def _compute_can_override_price(self):
        is_manager = self.env.user.has_group(
            "travel_umroh.group_travel_manager"
        )
        for participant in self:
            participant.can_override_price = is_manager

    @api.model
    def _ensure_order_mutation_allowed(self, order):
        if not order.exists():
            raise UserError(_("Booking participant tidak ditemukan."))
        if order.state not in ("draft", "sent") and not self.env.user.has_group(
            "travel_umroh.group_travel_manager"
        ):
            raise AccessError(
                _(
                    "Participant terkunci setelah konfirmasi. Hanya Manager "
                    "Travel Umroh yang dapat melakukan koreksi."
                )
            )

    def _room_label(self):
        self.ensure_one()
        return dict(self._fields["room_type"].selection).get(
            self.room_type, self.room_type or "-"
        )

    def _price_label(self):
        self.ensure_one()
        return self.currency_id.format(self.unit_price)

    @api.model
    def _get_departure_price(self, order, room_type):
        if not order.exists() or not order.is_travel_booking:
            raise UserError(_("Participant harus berada pada Booking Travel."))
        departure = order.departure_id
        if not departure or departure.state != "open" or not departure.active:
            raise UserError(
                _("Pilih keberangkatan aktif yang berstatus Dibuka terlebih dahulu.")
            )
        prices = departure.price_ids.filtered(
            lambda price: price.room_type == room_type
        )
        if len(prices) != 1:
            room_label = dict(self._fields["room_type"].selection).get(
                room_type, room_type or _("belum dipilih")
            )
            raise UserError(
                _(
                    "Harga kamar %(room)s belum tersedia untuk keberangkatan ini.",
                    room=room_label,
                )
            )
        return prices

    def _prepare_sale_line_values(self):
        self.ensure_one()
        product = self.order_id.travel_package_id.product_id
        room_label = dict(self._fields["room_type"].selection)[self.room_type]
        return {
            "order_id": self.order_id.id,
            "product_id": product.id,
            "product_uom_qty": 1,
            "product_uom": product.uom_id.id,
            "price_unit": self.unit_price,
            "name": _(
                "%(jamaah)s — %(room)s — %(departure)s",
                jamaah=self.jamaah_id.name,
                room=room_label,
                departure=self.order_id.departure_id.display_name,
            ),
            "travel_participant_id": self.id,
        }

    def _sync_sale_line(self):
        for participant in self:
            if not participant.sale_line_id:
                continue
            line_values = participant._prepare_sale_line_values()
            line_values.pop("order_id")
            line_values.pop("travel_participant_id")
            participant.sale_line_id._travel_write_from_participant(line_values)

    def _refresh_from_departure_price(self):
        for participant in self:
            departure_price = self._get_departure_price(
                participant.order_id, participant.room_type
            )
            super(TravelBookingParticipant, participant).write(
                {"unit_price": departure_price.price}
            )
            participant._sync_sale_line()
