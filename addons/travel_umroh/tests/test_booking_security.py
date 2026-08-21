import base64

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelBookingSecurity(TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls._create_user(
            "phase2-security-staff", "group_travel_staff"
        )
        cls.finance = cls._create_user(
            "phase2-security-finance", "group_travel_finance"
        )
        cls.manager = cls._create_user(
            "phase2-security-manager", "group_travel_manager"
        )
        cls.internal = cls._create_user("phase2-security-internal", None)

    @classmethod
    def _create_user(cls, login, group_xmlid):
        group_ids = [cls.env.ref("base.group_user").id]
        if group_xmlid:
            group_ids.append(cls.env.ref(f"travel_umroh.{group_xmlid}").id)
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "groups_id": [Command.set(group_ids)],
            }
        )

    def _jamaah_as(self, user, suffix):
        partner = self.env["res.partner"].create(
            {
                "name": f"Security Jamaah {suffix}",
                "phone": f"+6281300{suffix}",
            }
        )
        return self.env["travel.jamaah"].with_user(user).create(
            {
                "partner_id": partner.id,
                "nik": f"SEC-NIK-{suffix}",
                "birth_place": "Jakarta",
                "birth_date": "1990-01-01",
                "gender": "male",
                "emergency_contact_name": "Security Emergency",
                "emergency_contact_phone": "+628139990000",
            }
        )

    def _draft_booking_as(self, user, suffix):
        order = self.env["sale.order"].with_user(user).create(
            {
                "partner_id": self.buyer.id,
                "user_id": user.id,
                "is_travel_booking": True,
                "departure_id": self.departure.id,
            }
        )
        participant = self.env["travel.booking.participant"].with_user(
            user
        ).create(
            {
                "order_id": order.id,
                "jamaah_id": self._jamaah_as(user, suffix).id,
                "room_type": "quad",
                "unit_price": 1,
            }
        )
        return order, participant

    def test_staff_gets_sales_user_and_can_open_another_staff_travel_booking(self):
        self.assertTrue(
            self.staff.has_group("sales_team.group_sale_salesman")
        )
        own_order, own_participant = self._draft_booking_as(
            self.staff, "400"
        )
        own_order.with_user(self.staff).write(
            {"client_order_ref": "STAFF-DRAFT"}
        )
        own_participant.jamaah_id.with_user(self.staff).write(
            {"birth_place": "Bogor"}
        )
        other = self._create_user(
            "phase2-security-other-staff", "group_travel_staff"
        )
        other_order, _participant = self._draft_booking_as(other, "401")

        visible_order = self.env["sale.order"].with_user(self.staff).browse(
            other_order.id
        )
        self.assertEqual(visible_order.name, other_order.name)

    def test_staff_cannot_override_snapshot_or_mutate_after_confirmation(self):
        order, participant = self._draft_booking_as(self.staff, "402")
        self.assertEqual(participant.unit_price, 30_000_000)
        with self.assertRaises(AccessError):
            participant.with_user(self.staff).write({"unit_price": 1})

        order.with_user(self.staff).action_confirm()

        with self.assertRaises(AccessError):
            participant.with_user(self.staff).write({"room_type": "double"})
        with self.assertRaises(AccessError):
            participant.with_user(self.staff).unlink()
        with self.assertRaises(AccessError):
            self.env["travel.booking.participant"].with_user(
                self.staff
            ).create(
                {
                    "order_id": order.id,
                    "jamaah_id": self._jamaah_as(self.staff, "403").id,
                    "room_type": "triple",
                }
            )

    def test_staff_cannot_verify_or_edit_verified_jamaah(self):
        jamaah = self._jamaah_as(self.staff, "404")
        jamaah.with_user(self.staff).write(
            {
                "passport_number": "SEC-PASSPORT-404",
                "passport_expiry": "2030-01-01",
                "ktp_file": base64.b64encode(b"synthetic-ktp"),
                "ktp_filename": "ktp-404.pdf",
                "passport_file": base64.b64encode(b"synthetic-passport"),
                "passport_filename": "passport-404.pdf",
            }
        )
        jamaah.with_user(self.staff).action_submit_documents()
        with self.assertRaises(AccessError):
            jamaah.with_user(self.staff).action_verify_documents()

        jamaah.with_user(self.manager).action_verify_documents()

        with self.assertRaises(AccessError):
            jamaah.with_user(self.staff).write({"birth_place": "Bandung"})

    def test_finance_reads_travel_transaction_but_cannot_mutate_it(self):
        order, participant = self._draft_booking_as(self.staff, "405")
        finance_order = order.with_user(self.finance)
        self.assertEqual(finance_order.participant_count, 1)
        self.assertEqual(
            participant.with_user(self.finance).jamaah_id.nik,
            "SEC-NIK-405",
        )
        self.assertEqual(
            participant.sale_line_id.with_user(self.finance).price_unit,
            30_000_000,
        )
        self.assertFalse(
            self.finance.has_group("sales_team.group_sale_salesman")
        )
        with self.assertRaises(AccessError):
            finance_order.write({"client_order_ref": "DENIED"})
        with self.assertRaises(AccessError):
            participant.with_user(self.finance).write(
                {"room_type": "double"}
            )
        with self.assertRaises(AccessError):
            participant.jamaah_id.with_user(self.finance).unlink()
        with self.assertRaises(AccessError):
            participant.sale_line_id.with_user(self.finance).unlink()

    def test_finance_cannot_create_phase_two_records(self):
        order, participant = self._draft_booking_as(self.staff, "408")
        jamaah_values = {
            "partner_id": self.env["res.partner"]
            .create({"name": "Finance Denied"})
            .id,
            "nik": "SEC-NIK-408-FIN",
            "birth_place": "Jakarta",
            "birth_date": "1990-01-01",
            "gender": "female",
            "emergency_contact_name": "Emergency",
            "emergency_contact_phone": "+628130000408",
        }
        with self.assertRaises(AccessError):
            self.env["travel.jamaah"].with_user(self.finance).create(
                jamaah_values
            )
        with self.assertRaises(AccessError):
            self.env["sale.order"].with_user(self.finance).create(
                {
                    "partner_id": self.buyer.id,
                    "is_travel_booking": True,
                    "departure_id": self.departure.id,
                }
            )
        with self.assertRaises(AccessError):
            self.env["travel.booking.participant"].with_user(
                self.finance
            ).create(
                {
                    "order_id": order.id,
                    "jamaah_id": participant.jamaah_id.id,
                    "room_type": "double",
                }
            )
        with self.assertRaises(AccessError):
            self.env["sale.order.line"].with_user(self.finance).create(
                {
                    "order_id": order.id,
                    "product_id": self.package.product_id.id,
                    "product_uom_qty": 1,
                }
            )

    def test_manager_can_correct_confirmed_participant_and_change_is_audited(self):
        order, participant = self._draft_booking_as(self.manager, "406")
        order.with_user(self.manager).action_confirm()

        participant.with_user(self.manager).write(
            {"room_type": "double", "unit_price": 36_000_000}
        )

        self.assertEqual(participant.sale_line_id.price_unit, 36_000_000)
        self.assertTrue(
            order.message_ids.filtered(
                lambda message: "Override harga participant"
                in (message.body or "")
            )
        )

    def test_internal_user_and_finance_do_not_gain_unrelated_sales_access(self):
        travel_order, participant = self._draft_booking_as(self.staff, "407")
        unrelated_owner = self._create_user(
            "phase2-security-unrelated-owner", "group_travel_staff"
        )
        non_travel = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "user_id": unrelated_owner.id,
            }
        )
        with self.assertRaises(AccessError):
            travel_order.with_user(self.internal).read(["name"])
        with self.assertRaises(AccessError):
            participant.with_user(self.internal).read(["jamaah_id"])
        with self.assertRaises(AccessError):
            participant.jamaah_id.with_user(self.internal).read(["nik"])
        self.assertEqual(
            travel_order.with_user(self.finance).name, travel_order.name
        )
        self.assertEqual(
            participant.with_user(self.finance).jamaah_id,
            participant.jamaah_id,
        )
        with self.assertRaises(AccessError):
            non_travel.with_user(self.finance).read(["name"])
        with self.assertRaises(AccessError):
            non_travel.with_user(self.staff).read(["name"])
