from base64 import b64encode
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelJamaah(TravelUmrohCase):
    def _values(self, suffix="001", **overrides):
        partner = self.env["res.partner"].create(
            {
                "name": f"Jamaah Synthetic {suffix}",
                "phone": f"+62812000{suffix}",
                "email": f"jamaah-{suffix}@example.test",
            }
        )
        values = {
            "partner_id": partner.id,
            "nik": f"SYNTHETIC-NIK-{suffix}",
            "birth_place": "Denpasar",
            "birth_date": fields.Date.context_today(self.env.user)
            - relativedelta(years=30),
            "gender": "male",
            "emergency_contact_name": "Synthetic Family",
            "emergency_contact_phone": "+628129999000",
        }
        values.update(overrides)
        return values

    def _complete_document_values(self):
        return {
            "passport_number": "SYNTH-PASSPORT-001",
            "passport_expiry": "2030-01-01",
            "ktp_file": b64encode(b"synthetic-ktp-content"),
            "ktp_filename": "synthetic-ktp.txt",
            "passport_file": b64encode(b"synthetic-passport-content"),
            "passport_filename": "synthetic-passport.txt",
        }

    def _role_user(self, login, group_xmlid):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(f"travel_umroh.{group_xmlid}").id,
                        ]
                    )
                ],
            }
        )

    def test_jamaah_reuses_partner_contact_and_computes_current_age(self):
        jamaah = self.env["travel.jamaah"].create(self._values())
        self.assertEqual(jamaah.name, jamaah.partner_id.name)
        self.assertEqual(jamaah.phone, jamaah.partner_id.phone)
        self.assertEqual(jamaah.age, 30)

    def test_future_birth_date_is_rejected(self):
        tomorrow = fields.Date.context_today(self.env.user) + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.env["travel.jamaah"].create(self._values(birth_date=tomorrow))

    @mute_logger("odoo.sql_db")
    def test_partner_nik_and_nonempty_passport_are_unique(self):
        first = self.env["travel.jamaah"].create(
            self._values("001", passport_number="SYNTH-P001")
        )
        for overrides in (
            {"partner_id": first.partner_id.id, "nik": "SYNTHETIC-NIK-002"},
            {"nik": first.nik},
            {"passport_number": first.passport_number},
        ):
            with (
                self.subTest(overrides=overrides),
                self.assertRaises(IntegrityError),
                self.cr.savepoint(),
            ):
                self.env["travel.jamaah"].create(self._values("002", **overrides))

    def test_multiple_empty_passports_are_allowed(self):
        first = self.env["travel.jamaah"].create(self._values("003"))
        second = self.env["travel.jamaah"].create(self._values("004"))
        self.assertFalse(first.passport_number)
        self.assertFalse(second.passport_number)

    def test_identity_numbers_are_normalized_on_create_and_write(self):
        jamaah = self.env["travel.jamaah"].create(
            self._values(
                "005",
                nik="  SYNTHETIC-NIK-005  ",
                passport_number="  synth-p005  ",
            )
        )
        self.assertEqual(jamaah.nik, "SYNTHETIC-NIK-005")
        self.assertEqual(jamaah.passport_number, "SYNTH-P005")

        jamaah.write(
            {
                "nik": "  SYNTHETIC-NIK-005-UPDATED  ",
                "passport_number": "  synth-p005-updated  ",
            }
        )
        self.assertEqual(jamaah.nik, "SYNTHETIC-NIK-005-UPDATED")
        self.assertEqual(jamaah.passport_number, "SYNTH-P005-UPDATED")

    def test_binary_documents_are_stored_as_ir_attachments(self):
        jamaah = self.env["travel.jamaah"].create(
            self._values("010", **self._complete_document_values())
        )
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "travel.jamaah"),
                ("res_id", "=", jamaah.id),
                ("res_field", "in", ["ktp_file", "passport_file"]),
            ]
        )
        self.assertEqual(len(attachments), 2)

    def test_incomplete_documents_cannot_be_submitted(self):
        jamaah = self.env["travel.jamaah"].create(self._values("011"))
        with self.assertRaises(UserError):
            jamaah.action_submit_documents()

    def test_submit_then_manager_verify_records_audit_identity_and_time(self):
        jamaah = self.env["travel.jamaah"].create(
            self._values("012", **self._complete_document_values())
        )
        jamaah.action_submit_documents()
        self.assertEqual(jamaah.document_status, "pending")

        manager = self._role_user(
            "phase2-document-manager", "group_travel_manager"
        )
        jamaah.with_user(manager).action_verify_documents()

        self.assertEqual(jamaah.document_status, "verified")
        self.assertEqual(jamaah.verified_by, manager)
        self.assertTrue(jamaah.verified_at)
        self.assertTrue(
            jamaah.message_ids.filtered(
                lambda message: "Dokumen jamaah diverifikasi"
                in (message.body or "")
            )
        )

    def test_document_status_and_verifier_cannot_be_written_directly(self):
        jamaah = self.env["travel.jamaah"].create(self._values("013"))
        for values in (
            {"document_status": "verified"},
            {"verified_by": self.env.user.id},
            {"verified_at": "2027-01-01 00:00:00"},
        ):
            with self.subTest(values=values), self.assertRaises(UserError):
                jamaah.write(values)

    def test_document_status_cannot_be_seeded_during_create(self):
        with self.assertRaises(UserError):
            self.env["travel.jamaah"].create(
                self._values("016", document_status="verified")
            )

    def test_document_workflow_rejects_invalid_transitions(self):
        manager = self._role_user(
            "phase2-document-transition-manager", "group_travel_manager"
        )
        jamaah = self.env["travel.jamaah"].create(
            self._values("017", **self._complete_document_values())
        )
        with self.assertRaises(UserError):
            jamaah.with_user(manager).action_verify_documents()
        jamaah.action_submit_documents()
        with self.assertRaises(UserError):
            jamaah.action_submit_documents()
        jamaah.with_user(manager).action_verify_documents()
        with self.assertRaises(UserError):
            jamaah.with_user(manager).action_verify_documents()

    def test_staff_cannot_verify_or_edit_a_verified_profile(self):
        staff = self._role_user(
            "phase2-document-staff", "group_travel_staff"
        )
        manager = self._role_user(
            "phase2-document-lock-manager", "group_travel_manager"
        )
        jamaah = self.env["travel.jamaah"].create(
            self._values("014", **self._complete_document_values())
        )
        jamaah.action_submit_documents()
        with self.assertRaises(AccessError):
            jamaah.with_user(staff).action_verify_documents()
        jamaah.with_user(manager).action_verify_documents()
        with self.assertRaises(AccessError):
            jamaah.with_user(staff).write({"birth_place": "Bandung"})

    def test_manager_correction_of_verified_profile_is_audited(self):
        manager = self._role_user(
            "phase2-document-audit-manager", "group_travel_manager"
        )
        jamaah = self.env["travel.jamaah"].create(
            self._values("015", **self._complete_document_values())
        )
        jamaah.action_submit_documents()
        jamaah.with_user(manager).action_verify_documents()

        jamaah.with_user(manager).write({"birth_place": "Mataram"})

        self.assertEqual(jamaah.birth_place, "Mataram")
        self.assertEqual(jamaah.document_status, "verified")
        self.assertTrue(
            jamaah.message_ids.filtered(
                lambda message: "Data Jamaah terverifikasi dikoreksi"
                in (message.body or "")
            )
        )
