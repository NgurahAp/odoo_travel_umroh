from datetime import timedelta

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
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
