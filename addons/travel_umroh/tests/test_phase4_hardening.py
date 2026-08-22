import base64

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseFourInternalHardening(TravelAccountingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.administrator = cls.env.ref("base.user_admin")
        cls.administrator.sudo().write(
            {
                "company_id": cls.env.company.id,
                "company_ids": [Command.link(cls.env.company.id)],
            }
        )

    def _pending_jamaah(self, suffix):
        jamaah = self._create_jamaah(
            suffix,
            passport_number=f"PH4-PASS-{suffix}",
            passport_expiry="2035-01-01",
            ktp_file=base64.b64encode(b"phase4-synthetic-ktp"),
            ktp_filename=f"phase4-ktp-{suffix}.pdf",
            passport_file=base64.b64encode(b"phase4-synthetic-passport"),
            passport_filename=f"phase4-passport-{suffix}.pdf",
        )
        jamaah.with_user(self.staff).action_submit_documents()
        return jamaah

    def _ktp_attachment(self, jamaah):
        return self.env["ir.attachment"].sudo().search(
            [
                ("res_model", "=", "travel.jamaah"),
                ("res_id", "=", jamaah.id),
                ("res_field", "=", "ktp_file"),
            ],
            limit=1,
        )

    def test_administrator_performs_manager_corrections_with_audit(self):
        self.assertFalse(
            self.administrator.has_group(
                "travel_umroh.group_travel_manager"
            )
        )
        jamaah = self._pending_jamaah("ADMIN")

        jamaah.with_user(self.administrator).action_verify_documents()
        jamaah.with_user(self.administrator).write(
            {"birth_place": "Phase 4 Admin Correction"}
        )
        jamaah.partner_id.with_user(self.administrator).write(
            {"phone": "+628120004000"}
        )
        attachment = self._ktp_attachment(jamaah)
        self.assertTrue(attachment)
        attachment.with_user(self.administrator).write(
            {"datas": base64.b64encode(b"phase4-admin-ktp-correction")}
        )

        order = self._confirmed_booking("PH4-ADMIN")
        participant = order.participant_ids.ensure_one()
        if order.locked:
            order.with_user(self.administrator).action_unlock()
        self.assertTrue(
            order.with_user(self.administrator).can_edit_travel_participants
        )
        self.assertTrue(
            participant.with_user(self.administrator).can_override_price
        )
        participant.with_user(self.administrator).write(
            {"room_type": "double", "unit_price": 34_500_000}
        )

        jamaah_audit = " ".join(jamaah.message_ids.mapped("body"))
        self.assertIn("Dokumen jamaah diverifikasi", jamaah_audit)
        self.assertIn("Data Jamaah terverifikasi dikoreksi", jamaah_audit)
        self.assertIn(
            "Kontak Jamaah terverifikasi dikoreksi", jamaah_audit
        )
        self.assertIn(
            "Lampiran dokumen Jamaah terverifikasi dikoreksi", jamaah_audit
        )
        order_audit = " ".join(order.message_ids.mapped("body"))
        self.assertIn("Override harga participant", order_audit)

    def test_staff_and_finance_remain_denied_after_verification(self):
        jamaah = self._pending_jamaah("NEGATIVE")
        jamaah.with_user(self.manager).action_verify_documents()
        attachment = self._ktp_attachment(jamaah)
        self.assertTrue(attachment)
        order = self._confirmed_booking("PH4-NEGATIVE")
        participant = order.participant_ids.ensure_one()

        for user in (self.staff, self.finance):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    jamaah.with_user(user).write(
                        {"birth_place": "Denied Correction"}
                    )
                with self.assertRaises(AccessError):
                    jamaah.partner_id.with_user(user).write(
                        {"phone": "+628120004999"}
                    )
                with self.assertRaises(AccessError):
                    attachment.with_user(user).write(
                        {"datas": base64.b64encode(b"denied")}
                    )
                with self.assertRaises(AccessError):
                    participant.with_user(user).write(
                        {"room_type": "double"}
                    )

    def test_administrator_cannot_forge_workflow_integrity_fields(self):
        order = self._confirmed_booking("PH4-INTEGRITY")

        for values in (
            {"travel_payment_state": "paid"},
            {"seat_reserved": True},
        ):
            with self.subTest(values=values), self.assertRaises(UserError):
                order.with_user(self.administrator).write(values)

        with self.assertRaises(UserError):
            self.departure.with_user(self.administrator).write(
                {"state": "done"}
            )

    def test_administrator_can_read_all_reports_and_report_menus(self):
        order = self._confirmed_booking("PH4-ADMIN-REPORT")
        participant = order.participant_ids.ensure_one()
        reports = (
            ("travel_umroh.action_travel_booking_report", order),
            ("travel_umroh.action_travel_capacity_report", self.departure),
            (
                "travel_umroh.action_travel_document_report",
                participant.jamaah_id,
            ),
            ("travel_umroh.action_travel_manifest", participant),
        )
        for xmlid, expected_record in reports:
            with self.subTest(action=xmlid):
                action = self.env.ref(xmlid)
                visible = self.env[action.res_model].with_user(
                    self.administrator
                ).search([("id", "=", expected_record.id)])
                self.assertEqual(visible.ids, expected_record.ids)

        visible_menu_ids = (
            self.env["ir.ui.menu"]
            .with_user(self.administrator)
            ._visible_menu_ids()
        )
        for xmlid in (
            "travel_umroh.menu_travel_booking_report",
            "travel_umroh.menu_travel_capacity_report",
            "travel_umroh.menu_travel_document_report",
            "travel_umroh.menu_travel_manifest",
            "travel_umroh.menu_travel_receivable_report",
            "travel_umroh.menu_travel_configuration",
        ):
            with self.subTest(menu=xmlid):
                self.assertIn(self.env.ref(xmlid).id, visible_menu_ids)

        for model_name in (
            "travel.airline",
            "travel.airport",
            "travel.hotel",
            "travel.package",
            "travel.departure",
            "travel.departure.price",
            "travel.departure.flight",
            "travel.departure.accommodation",
            "travel.jamaah",
            "travel.booking.participant",
            "travel.booking.cancel.wizard",
        ):
            model = self.env[model_name].with_user(self.administrator)
            for operation in ("read", "write", "create", "unlink"):
                with self.subTest(model=model_name, operation=operation):
                    model.check_access(operation)
