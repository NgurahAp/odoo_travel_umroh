import base64

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseFourInternalAcceptance(TravelAccountingCase):
    def _travel_quotation(self, reference, suffix):
        order = self.env["sale.order"].with_user(self.staff).create(
            {
                "partner_id": self.buyer.id,
                "user_id": self.staff.id,
                "client_order_ref": reference,
                "is_travel_booking": True,
                "departure_id": self.departure.id,
            }
        )
        for index, room_type in enumerate(("quad", "triple"), start=1):
            self.env["travel.booking.participant"].with_user(
                self.staff
            ).create(
                {
                    "order_id": order.id,
                    "jamaah_id": self._create_jamaah(
                        f"{suffix}-{index}"
                    ).id,
                    "room_type": room_type,
                }
            )
        return order

    def _create_final_invoice(self, order):
        before = order.invoice_ids
        self._create_invoice_wizard(
            order, "delivered", deduct_down_payments=True
        ).create_invoices()
        order.invalidate_recordset(["invoice_ids", "invoice_status"])
        return (order.invoice_ids - before).ensure_one()

    def _pay_posted_invoice(self, invoice):
        self.assertEqual(invoice.state, "posted")
        (
            self.env["account.payment.register"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "journal_id": self.company_data[
                        "default_journal_bank"
                    ].id,
                }
            )
            .action_create_payments()
        )
        invoice.invalidate_recordset(["amount_residual", "payment_state"])
        return invoice

    def _reverse_and_pay(self, invoice, reason):
        reversal = (
            self.env["account.move.reversal"]
            .with_user(self.finance)
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .create(
                {
                    "reason": reason,
                    "journal_id": invoice.journal_id.id,
                }
            )
        )
        reversal.refund_moves()
        refund = reversal.new_move_ids.ensure_one()
        if refund.state == "draft":
            refund.with_user(self.finance).action_post()
        self._pay_posted_invoice(refund)
        return refund

    def _fully_pay(self, order):
        downpayment = self._create_downpayment_invoice(order)
        downpayment.with_user(self.finance).action_post()
        self._pay_posted_invoice(downpayment)
        final_invoice = self._create_final_invoice(order)
        final_invoice.with_user(self.finance).action_post()
        self._pay_posted_invoice(final_invoice)
        order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        return downpayment | final_invoice

    def _verify_jamaah(self, jamaah, suffix):
        jamaah.with_user(self.staff).write(
            {
                "passport_number": f"ACCEPT-PASS-{suffix}",
                "passport_expiry": "2035-01-01",
                "ktp_file": base64.b64encode(
                    f"acceptance-ktp-{suffix}".encode()
                ),
                "ktp_filename": f"acceptance-ktp-{suffix}.pdf",
                "passport_file": base64.b64encode(
                    f"acceptance-passport-{suffix}".encode()
                ),
                "passport_filename": f"acceptance-passport-{suffix}.pdf",
            }
        )
        jamaah.with_user(self.staff).action_submit_documents()
        jamaah.with_user(self.manager).action_verify_documents()

    def test_complete_internal_travel_flow_and_reporting_boundaries(self):
        paid_order = self._travel_quotation(
            "PH4-ACCEPT-PAID", "PH4-ACCEPT-PAID"
        )
        paid_order.with_user(self.staff).action_confirm()
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(paid_order.travel_payment_state, "unpaid")
        self.assertEqual(self.departure.reserved_seats, 0)

        downpayment = self._create_downpayment_invoice(paid_order)
        downpayment.with_user(self.finance).action_post()
        paid_order.invalidate_recordset(["travel_payment_state"])
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(paid_order.travel_payment_state, "dp")
        self.assertEqual(self.departure.reserved_seats, 0)

        self._pay_posted_invoice(downpayment)
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(self.departure.reserved_seats, 2)

        final_invoice = self._create_final_invoice(paid_order)
        final_invoice.with_user(self.finance).action_post()
        self._pay_posted_invoice(final_invoice)
        paid_order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        self.assertEqual(paid_order.travel_payment_state, "paid")

        refunded_order = self._travel_quotation(
            "PH4-ACCEPT-REFUND", "PH4-ACCEPT-REFUND"
        )
        refunded_order.with_user(self.staff).action_confirm()
        refunded_invoices = self._fully_pay(refunded_order).filtered(
            lambda move: move.state == "posted"
            and move.move_type == "out_invoice"
        )
        self.assertEqual(len(refunded_invoices), 2)
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(self.departure.reserved_seats, 4)

        (
            self.env["travel.booking.cancel.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "order_id": refunded_order.id,
                    "reason": "DEMO acceptance refund",
                }
            )
            .action_confirm_cancel()
        )
        refunded_order.invalidate_recordset(["state", "seat_reserved"])
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(refunded_order.state, "cancel")
        self.assertFalse(refunded_order.seat_reserved)
        self.assertEqual(self.departure.reserved_seats, 2)
        cancel_audit = " ".join(refunded_order.message_ids.mapped("body"))
        self.assertIn("DEMO acceptance refund", cancel_audit)
        self.assertIn("kursi dilepas", cancel_audit)

        refunds = self.env["account.move"]
        for invoice in refunded_invoices:
            refunds |= self._reverse_and_pay(
                invoice,
                f"DEMO acceptance refund {invoice.name}",
            )
        refunded_order.invalidate_recordset(
            ["invoice_ids", "travel_payment_state", "seat_reserved"]
        )
        refunds.invalidate_recordset(["amount_residual", "payment_state"])
        self.departure.invalidate_recordset(["reserved_seats"])
        self.assertEqual(refunded_order.travel_payment_state, "refunded")
        self.assertTrue(
            all(
                refund.move_type == "out_refund"
                and not refund.amount_residual
                for refund in refunds
            )
        )
        self.assertEqual(self.departure.reserved_seats, 2)

        for index, jamaah in enumerate(
            paid_order.participant_ids.jamaah_id, start=1
        ):
            self._verify_jamaah(jamaah, index)
        self.departure.with_user(self.manager).action_depart()
        self.departure.with_user(self.manager).action_done()
        self.assertEqual(self.departure.state, "done")

        actions_and_records = (
            ("travel_umroh.action_travel_booking_report", paid_order),
            ("travel_umroh.action_travel_capacity_report", self.departure),
            (
                "travel_umroh.action_travel_document_report",
                paid_order.participant_ids[0].jamaah_id,
            ),
            (
                "travel_umroh.action_travel_manifest",
                paid_order.participant_ids[0],
            ),
        )
        for user in (self.staff, self.finance, self.manager):
            for xmlid, expected_record in actions_and_records:
                with self.subTest(user=user.login, action=xmlid):
                    action = self.env.ref(xmlid)
                    visible = self.env[action.res_model].with_user(user).search(
                        [("id", "=", expected_record.id)]
                    )
                    self.assertEqual(visible.ids, expected_record.ids)

        booking_action = self.env.ref(
            "travel_umroh.action_travel_booking_report"
        )
        manifest_action = self.env.ref("travel_umroh.action_travel_manifest")
        booking_domain = safe_eval(booking_action.domain)
        manifest_domain = safe_eval(manifest_action.domain)
        self.assertIn(
            paid_order,
            self.env["sale.order"].with_user(self.staff).search(
                booking_domain + [("id", "=", paid_order.id)]
            ),
        )
        self.assertEqual(
            set(
                self.env["travel.booking.participant"]
                .with_user(self.staff)
                .search(
                    manifest_domain
                    + [("order_id", "=", paid_order.id)]
                )
                .ids
            ),
            set(paid_order.participant_ids.ids),
        )

        receivable_menu = self.env.ref(
            "travel_umroh.menu_travel_receivable_report"
        )
        self.assertEqual(
            set(receivable_menu.groups_id.ids),
            {
                self.env.ref("travel_umroh.group_travel_finance").id,
                self.env.ref("travel_umroh.group_travel_manager").id,
            },
        )
        self.assertFalse(
            self.staff.has_group("account.group_account_invoice")
        )
        with self.assertRaises(AccessError):
            final_invoice.with_user(self.staff).write({"ref": "DENIED"})

        ordinary_order = self.env["sale.order"].with_user(self.staff).create(
            {
                "partner_id": self.buyer.id,
                "user_id": self.staff.id,
                "client_order_ref": "PH4-ORDINARY-SALE",
            }
        )
        self.assertFalse(
            self.env["sale.order"].with_user(self.staff).search(
                booking_domain + [("id", "=", ordinary_order.id)]
            )
        )
        self.assertFalse(
            self.env["travel.booking.participant"].with_user(
                self.staff
            ).search(
                manifest_domain + [("order_id", "=", ordinary_order.id)]
            )
        )
