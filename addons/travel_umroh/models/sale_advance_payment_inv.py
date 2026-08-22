from contextlib import contextmanager
from contextvars import ContextVar

from odoo import _, models
from odoo.exceptions import AccessError, UserError


_travel_downpayment_line_creation = ContextVar(
    "travel_umroh_downpayment_line_creation", default=False
)
_travel_downpayment_line_posting = ContextVar(
    "travel_umroh_downpayment_line_posting", default=False
)


@contextmanager
def _allow_travel_downpayment_line_creation():
    token = _travel_downpayment_line_creation.set(True)
    try:
        yield
    finally:
        _travel_downpayment_line_creation.reset(token)


def is_travel_downpayment_line_creation_allowed():
    return _travel_downpayment_line_creation.get()


@contextmanager
def allow_travel_downpayment_line_posting():
    token = _travel_downpayment_line_posting.set(True)
    try:
        yield
    finally:
        _travel_downpayment_line_posting.reset(token)


def is_travel_downpayment_line_posting_allowed():
    return _travel_downpayment_line_posting.get()


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _create_invoices(self, sale_orders):
        travel_orders = sale_orders.filtered("is_travel_booking")
        if not travel_orders:
            return super()._create_invoices(sale_orders)
        if len(travel_orders) != len(sale_orders):
            raise UserError(
                _(
                    "Booking Travel dan Sales Order biasa tidak dapat "
                    "ditagihkan dalam satu proses."
                )
            )
        if not self.env.is_admin() and not self.env.user.has_group(
            "travel_umroh.group_travel_finance"
        ):
            raise AccessError(
                _(
                    "Hanya Finance atau Manager Travel Umroh yang dapat "
                    "membuat invoice booking."
                )
            )
        if self.advance_payment_method in ("percentage", "fixed"):
            with _allow_travel_downpayment_line_creation():
                return super()._create_invoices(sale_orders)
        return super()._create_invoices(sale_orders)
