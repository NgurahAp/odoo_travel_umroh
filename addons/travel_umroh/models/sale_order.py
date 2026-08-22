from contextlib import contextmanager
from contextvars import ContextVar

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_travel_state_transition = ContextVar(
    "travel_umroh_sale_state_transition", default=False
)


@contextmanager
def _allow_travel_state_transition():
    token = _travel_state_transition.set(True)
    try:
        yield
    finally:
        _travel_state_transition.reset(token)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_travel_booking = fields.Boolean(
        string="Booking Travel Umroh",
        default=False,
        index=True,
        copy=False,
        tracking=True,
    )
    departure_id = fields.Many2one(
        "travel.departure",
        string="Keberangkatan",
        ondelete="restrict",
        check_company=True,
        tracking=True,
    )
    travel_package_id = fields.Many2one(
        "travel.package",
        string="Paket Travel",
        related="departure_id.package_id",
        store=True,
        readonly=True,
    )
    participant_ids = fields.One2many(
        "travel.booking.participant",
        "order_id",
        string="Participant",
        copy=False,
    )
    participant_count = fields.Integer(
        string="Jumlah Participant", compute="_compute_participant_count"
    )
    travel_payment_state = fields.Selection(
        [
            ("unpaid", "Belum Bayar"),
            ("dp", "DP / Bayar Sebagian"),
            ("paid", "Lunas"),
            ("refunded", "Refunded"),
        ],
        string="Status Pembayaran Travel",
        compute="_compute_travel_payment_state",
        readonly=True,
    )
    seat_reserved = fields.Boolean(
        string="Kursi Direservasi",
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
    )
    seat_reserved_at = fields.Datetime(
        string="Waktu Reservasi Kursi",
        readonly=True,
        copy=False,
        tracking=True,
    )
    can_edit_travel_participants = fields.Boolean(
        compute="_compute_travel_edit_helpers"
    )
    can_override_travel_price = fields.Boolean(
        compute="_compute_travel_edit_helpers"
    )

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for order in self:
            order.participant_count = len(order.participant_ids)

    @api.depends(
        "is_travel_booking",
        "invoice_status",
        "amount_total",
        "currency_id",
        "invoice_ids.state",
        "invoice_ids.move_type",
        "invoice_ids.amount_total",
        "invoice_ids.amount_residual",
        "invoice_ids.payment_state",
    )
    def _compute_travel_payment_state(self):
        for order in self:
            if not order.is_travel_booking:
                order.travel_payment_state = False
                continue

            posted_moves = order.invoice_ids.filtered(
                lambda move: move.state == "posted"
                and move.move_type in ("out_invoice", "out_refund")
            )
            invoices = posted_moves.filtered(
                lambda move: move.move_type == "out_invoice"
            )
            refunds = posted_moves.filtered(
                lambda move: move.move_type == "out_refund"
            )
            invoice_total = sum(invoices.mapped("amount_total"))
            refund_total = sum(refunds.mapped("amount_total"))
            net_total = invoice_total - refund_total
            all_settled = bool(posted_moves) and all(
                order.currency_id.is_zero(move.amount_residual)
                for move in posted_moves
            )

            if (
                invoices
                and refunds
                and order.currency_id.is_zero(net_total)
                and all_settled
            ):
                order.travel_payment_state = "refunded"
            elif (
                invoices
                and order.invoice_status == "invoiced"
                and order.currency_id.compare_amounts(
                    net_total, order.amount_total
                )
                == 0
                and all_settled
            ):
                order.travel_payment_state = "paid"
            elif invoices:
                order.travel_payment_state = "dp"
            else:
                order.travel_payment_state = "unpaid"

    @api.depends("state", "locked")
    @api.depends_context("uid")
    def _compute_travel_edit_helpers(self):
        is_manager = self.env.user.has_group(
            "travel_umroh.group_travel_manager"
        )
        for order in self:
            order.can_edit_travel_participants = (
                not order.locked
                and (order.state in ("draft", "sent") or is_manager)
            )
            order.can_override_travel_price = is_manager

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_travel_finance_only():
            raise AccessError(
                _("Finance Travel Umroh tidak dapat membuat Sales Order.")
            )
        for values in vals_list:
            if (
                values.get("is_travel_booking")
                and values.get("state", "draft") != "draft"
            ):
                raise UserError(
                    _(
                        "Booking Travel harus dibuat sebagai quotation Draft "
                        "dan dikonfirmasi melalui aksi Confirm."
                    )
                )
        return super().create(vals_list)

    def write(self, values):
        protected_phase_three_fields = {
            "travel_payment_state",
            "seat_reserved",
            "seat_reserved_at",
        }
        if protected_phase_three_fields.intersection(values):
            raise UserError(
                _(
                    "Status pembayaran Travel dihitung otomatis dari "
                    "invoice dan pembayaran Accounting."
                )
            )
        if self._is_travel_finance_only():
            raise AccessError(
                _("Finance Travel Umroh hanya dapat membaca booking.")
            )
        if values.get("is_travel_booking") is True:
            invalid_conversions = self.filtered(
                lambda order: not order.is_travel_booking
                and (
                    order.state not in ("draft", "sent")
                    or order.order_line.filtered(
                        lambda line: not line.display_type
                    )
                )
            )
            if invalid_conversions:
                raise UserError(
                    _(
                        "Hanya quotation Draft/Sent tanpa baris Sales yang "
                        "dapat diubah menjadi Booking Travel."
                    )
                )
        if "state" in values and not _travel_state_transition.get():
            new_state = values["state"]
            invalid_state_changes = self.filtered(
                lambda order: (
                    order.is_travel_booking
                    or values.get("is_travel_booking") is True
                )
                and new_state != order.state
                and not (
                    order.state in ("draft", "sent")
                    and new_state in ("draft", "sent")
                )
            )
            if invalid_state_changes:
                raise UserError(
                    _(
                        "Ubah status Booking Travel melalui aksi quotation "
                        "standar, bukan dengan menulis field status langsung."
                    )
                )
        protected_travel_fields = {
            "departure_id",
            "is_travel_booking",
        }
        if protected_travel_fields.intersection(values) and self.filtered(
            lambda order: order.is_travel_booking
            and order.state not in ("draft", "sent")
        ):
            raise UserError(
                _(
                    "Keberangkatan dan status Booking Travel terkunci setelah "
                    "quotation dikonfirmasi."
                )
            )
        if values.get("is_travel_booking") is False and self.filtered(
            lambda order: order.departure_id or order.participant_ids
        ):
            raise ValidationError(
                _(
                    "Status Booking Travel tidak dapat dilepas setelah "
                    "keberangkatan dipilih."
                )
            )
        if values.get("departure_id") is False and self.filtered(
            "participant_ids"
        ):
            raise UserError(
                _(
                    "Keberangkatan tidak dapat dikosongkan selama booking "
                    "masih memiliki participant."
                )
            )

        result = super().write(values)
        if "departure_id" in values:
            travel_orders = self.filtered(
                lambda order: order.is_travel_booking
                and order.departure_id
                and order.participant_ids
            )
            travel_orders.action_refresh_travel_prices()
        return result

    def unlink(self):
        if self._is_travel_finance_only():
            raise AccessError(
                _("Finance Travel Umroh tidak dapat menghapus Sales Order.")
            )
        return super().unlink()

    def _is_travel_finance_only(self):
        user = self.env.user
        return (
            not self.env.is_admin()
            and user.has_group("travel_umroh.group_travel_finance")
            and not user.has_group("travel_umroh.group_travel_staff")
        )

    def _travel_reserve_seats(self):
        self.ensure_one()
        if (
            not self.is_travel_booking
            or self.state != "sale"
            or not self.departure_id
            or not self.participant_ids
        ):
            raise UserError(
                _(
                    "Reservasi kursi hanya tersedia untuk Booking Travel "
                    "terkonfirmasi yang memiliki participant."
                )
            )
        if self.seat_reserved:
            return False

        self.env["travel.departure"].flush_model(["quota"])
        self.env["sale.order"].flush_model(
            ["departure_id", "seat_reserved", "state"]
        )
        self.env["travel.booking.participant"].flush_model(["order_id"])
        self.env.cr.execute(
            "SELECT id FROM travel_departure WHERE id = %s FOR UPDATE",
            [self.departure_id.id],
        )
        self.invalidate_recordset(["seat_reserved"])
        if self.seat_reserved:
            return False

        self.env.cr.execute(
            """
                SELECT COUNT(participant.id)
                  FROM travel_booking_participant AS participant
                  JOIN sale_order AS booking
                    ON booking.id = participant.order_id
                 WHERE booking.departure_id = %s
                   AND booking.seat_reserved = TRUE
                   AND booking.state != 'cancel'
            """,
            [self.departure_id.id],
        )
        current_usage = self.env.cr.fetchone()[0]
        needed = len(self.participant_ids)
        available = self.departure_id.quota - current_usage
        if needed > available:
            raise UserError(
                _(
                    "Keberangkatan %(departure)s tidak memiliki kuota cukup: "
                    "tersedia=%(available)s, dibutuhkan=%(needed)s.",
                    departure=self.departure_id.display_name,
                    available=available,
                    needed=needed,
                )
            )

        super(SaleOrder, self).write(
            {
                "seat_reserved": True,
                "seat_reserved_at": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "%(count)s kursi direservasi pada keberangkatan %(departure)s "
                "setelah uang muka lunas.",
                count=needed,
                departure=self.departure_id.display_name,
            )
        )
        return True

    def action_confirm(self):
        for order in self.filtered("is_travel_booking"):
            departure = order.departure_id
            if not departure or departure.state != "open" or not departure.active:
                raise UserError(
                    _(
                        "Booking Travel harus memiliki keberangkatan aktif "
                        "berstatus Dibuka sebelum dikonfirmasi."
                    )
                )
            if not order.participant_ids:
                raise UserError(
                    _(
                        "Tambahkan minimal satu participant sebelum Booking "
                        "Travel dikonfirmasi."
                    )
                )
            expected_product = order.travel_package_id.product_id
            participant_lines = order.participant_ids.mapped("sale_line_id")
            actual_lines = order.order_line.filtered(
                lambda line: not line.display_type
            )
            if set(actual_lines.ids) != set(participant_lines.ids):
                raise UserError(
                    _(
                        "Booking Travel hanya boleh memiliki baris Sales yang "
                        "dibuat dari Participant."
                    )
                )
            for participant in order.participant_ids:
                line = participant.sale_line_id
                if (
                    not line.exists()
                    or line.order_id != order
                    or line.travel_participant_id != participant
                    or line.product_id != expected_product
                    or line.product_uom != expected_product.uom_id
                    or line.product_uom_qty != 1
                    or line.discount != 0
                    or order.currency_id.compare_amounts(
                        line.price_unit, participant.unit_price
                    )
                    != 0
                ):
                    raise UserError(
                        _(
                            "Baris Sales untuk participant %(participant)s "
                            "tidak sinkron. Perbaiki quotation sebelum "
                            "dikonfirmasi.",
                            participant=participant.jamaah_id.name,
                        )
                    )
        with _allow_travel_state_transition():
            return super().action_confirm()

    def _action_cancel(self):
        with _allow_travel_state_transition():
            return super()._action_cancel()

    def action_draft(self):
        if self.filtered("is_travel_booking"):
            raise UserError(
                _(
                    "Booking Travel yang sudah dibatalkan tidak dapat "
                    "dikembalikan menjadi Draft pada Phase 2."
                )
            )
        return super().action_draft()

    def action_refresh_travel_prices(self):
        for order in self:
            if not order.is_travel_booking:
                raise UserError(
                    _("Harga travel hanya tersedia pada Booking Travel Umroh.")
                )
            if order.state not in ("draft", "sent"):
                raise UserError(
                    _("Harga travel hanya dapat diperbarui pada quotation.")
                )
            if not order.departure_id:
                raise UserError(
                    _("Pilih keberangkatan sebelum memperbarui harga travel.")
                )
            if (
                order.departure_id.state != "open"
                or not order.departure_id.active
            ):
                raise UserError(
                    _(
                        "Harga hanya dapat diperbarui dari keberangkatan aktif "
                        "yang berstatus Dibuka."
                    )
                )
            order.participant_ids._refresh_from_departure_price()
            order.message_post(
                body=_(
                    "Harga %(count)s participant diperbarui dari "
                    "keberangkatan %(departure)s.",
                    count=len(order.participant_ids),
                    departure=order.departure_id.display_name,
                )
            )
        return True

    @api.constrains(
        "is_travel_booking", "departure_id", "company_id", "pricelist_id"
    )
    def _check_travel_booking_configuration(self):
        for order in self:
            departure = order.departure_id
            if not departure:
                continue
            if not order.is_travel_booking:
                raise ValidationError(
                    _(
                        "Keberangkatan hanya dapat dipilih pada Booking Travel "
                        "Umroh."
                    )
                )
            if departure.state != "open" or not departure.active:
                raise ValidationError(
                    _("Pilih keberangkatan aktif yang berstatus Dibuka.")
                )
            if order.state in ("draft", "sent") and departure.is_full:
                raise ValidationError(
                    _(
                        "Keberangkatan %(departure)s sudah penuh. Pilih "
                        "keberangkatan lain.",
                        departure=departure.display_name,
                    )
                )
            if order.company_id != departure.company_id:
                raise ValidationError(
                    _(
                        "Perusahaan Sales Order harus sama dengan perusahaan "
                        "keberangkatan."
                    )
                )
            if order.currency_id != departure.currency_id:
                raise ValidationError(
                    _(
                        "Mata uang pricelist Sales Order harus sama dengan "
                        "mata uang keberangkatan."
                    )
                )
