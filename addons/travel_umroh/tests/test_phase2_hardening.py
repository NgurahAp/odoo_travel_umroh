import base64

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestPhaseTwoHardening(TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls._role_user("phase2-hardening-staff", "group_travel_staff")
        cls.manager = cls._role_user(
            "phase2-hardening-manager", "group_travel_manager"
        )

    @classmethod
    def _role_user(cls, login, group_xmlid):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(f"travel_umroh.{group_xmlid}").id,
                        ]
                    )
                ],
            }
        )

    def _order(self, user=None, **overrides):
        user = user or self.env.user
        values = {
            "partner_id": self.buyer.id,
            "user_id": user.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        }
        values.update(overrides)
        return self.env["sale.order"].with_user(user).create(values)

    def _participant(self, order, suffix, user=None):
        user = user or self.env.user
        return self.env["travel.booking.participant"].with_user(user).create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah(suffix).id,
                "room_type": "quad",
            }
        )

    def _verified_jamaah(self, suffix):
        partner = self.env["res.partner"].with_user(self.staff).create(
            {
                "name": f"Verified Jamaah {suffix}",
                "phone": f"+6281555{suffix}",
            }
        )
        jamaah = self.env["travel.jamaah"].with_user(self.staff).create(
            {
                "partner_id": partner.id,
                "nik": f"HARD-NIK-{suffix}",
                "birth_place": "Jakarta",
                "birth_date": "1990-01-01",
                "gender": "male",
                "emergency_contact_name": "Hardening Emergency",
                "emergency_contact_phone": "+628155500000",
                "passport_number": f"HARD-PASS-{suffix}",
                "passport_expiry": "2032-01-01",
                "ktp_file": base64.b64encode(b"original-ktp"),
                "ktp_filename": f"ktp-{suffix}.pdf",
                "passport_file": base64.b64encode(b"original-passport"),
                "passport_filename": f"passport-{suffix}.pdf",
            }
        )
        jamaah.with_user(self.staff).action_submit_documents()
        jamaah.with_user(self.manager).action_verify_documents()
        return jamaah

    def test_public_sale_line_create_is_blocked_for_travel_orders(self):
        order = self._order(self.staff)
        values = {
            "order_id": order.id,
            "product_id": self.package.product_id.id,
            "product_uom_qty": 1,
            "price_unit": 1,
        }

        with self.assertRaises(UserError):
            self.env["sale.order.line"].with_user(self.staff).create(values)
        with self.assertRaises(UserError):
            order.with_user(self.staff).write(
                {"order_line": [Command.create(dict(values, order_id=False))]}
            )

        participant = self._participant(order, "901", self.staff)
        order.with_user(self.staff).action_confirm()
        with self.assertRaises(UserError):
            self.env["sale.order.line"].with_user(self.staff).create(values)
        order.with_user(self.manager).action_lock()
        with self.assertRaises(UserError):
            self.env["sale.order.line"].with_user(self.manager).create(values)
        self.assertTrue(participant.sale_line_id.exists())

    def test_regular_sale_line_cannot_be_moved_into_travel_order(self):
        travel_order = self._order(self.staff)
        self._participant(travel_order, "916", self.staff)
        regular_order = self.env["sale.order"].with_user(self.staff).create(
            {"partner_id": self.buyer.id, "user_id": self.staff.id}
        )
        regular_line = self.env["sale.order.line"].with_user(self.staff).create(
            {
                "order_id": regular_order.id,
                "product_id": self.service_product.id,
                "product_uom_qty": 1,
            }
        )

        with self.assertRaises(UserError):
            regular_line.with_user(self.staff).write(
                {"order_id": travel_order.id}
            )
        travel_order.with_user(self.staff).action_confirm()
        with self.assertRaises(UserError):
            regular_line.with_user(self.staff).write(
                {"order_id": travel_order.id}
            )

    def test_confirmation_rejects_any_extra_non_display_line(self):
        order = self._order()
        self._participant(order, "902")
        self.env["sale.order.line"]._travel_create_participant_lines(
            [
                {
                    "order_id": order.id,
                    "product_id": self.package.product_id.id,
                    "product_uom_qty": 1,
                    "price_unit": 1,
                }
            ]
        )

        with self.assertRaises(UserError):
            order.action_confirm()

    def test_direct_state_create_and_write_cannot_bypass_confirmation(self):
        with self.assertRaises(UserError):
            self._order(self.staff, state="sale")

        order = self._order(self.staff, departure_id=False)
        with self.assertRaises(UserError):
            order.with_user(self.staff).write({"state": "sale"})
        with self.assertRaises(UserError):
            order.with_user(self.staff).with_context(
                _travel_allow_state_transition=True
            ).write({"state": "sale"})

    def test_confirmed_order_cannot_be_reopened_through_direct_state_write(self):
        order = self._order(self.staff)
        participant = self._participant(order, "912", self.staff)
        order.with_user(self.staff).action_confirm()

        with self.assertRaises(UserError):
            order.with_user(self.staff).write({"state": "draft"})
        with self.assertRaises(UserError):
            order.with_user(self.staff).write({"state": "cancel"})
        with self.assertRaises(AccessError):
            participant.with_user(self.staff).write({"room_type": "double"})

    def test_only_draft_regular_order_without_lines_can_become_travel(self):
        regular = self.env["sale.order"].with_user(self.staff).create(
            {"partner_id": self.buyer.id, "user_id": self.staff.id}
        )
        self.env["sale.order.line"].with_user(self.staff).create(
            {
                "order_id": regular.id,
                "product_id": self.service_product.id,
                "product_uom_qty": 1,
            }
        )
        with self.assertRaises(UserError):
            regular.with_user(self.staff).write(
                {
                    "is_travel_booking": True,
                    "departure_id": self.departure.id,
                }
            )

        confirmed = self.env["sale.order"].with_user(self.staff).create(
            {"partner_id": self.buyer.id, "user_id": self.staff.id}
        )
        self.env["sale.order.line"].with_user(self.staff).create(
            {
                "order_id": confirmed.id,
                "product_id": self.service_product.id,
                "product_uom_qty": 1,
            }
        )
        confirmed.with_user(self.staff).action_confirm()
        with self.assertRaises(UserError):
            confirmed.with_user(self.staff).write(
                {
                    "is_travel_booking": True,
                    "departure_id": self.departure.id,
                }
            )

    def test_confirm_and_cancel_work_but_cancelled_travel_cannot_reset(self):
        order = self._order(self.manager)
        participant = self._participant(order, "913", self.manager)

        order.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, "sale")
        order.with_user(self.staff).with_context(
            disable_cancel_warning=True
        ).action_cancel()
        self.assertEqual(order.state, "cancel")
        with self.assertRaises(UserError):
            order.with_user(self.staff).action_draft()
        with self.assertRaises(UserError):
            order.with_user(self.manager).action_draft()
        with self.assertRaises(AccessError):
            participant.with_user(self.staff).write({"room_type": "double"})

    def test_participant_sale_line_pointer_is_internal_only(self):
        order = self._order(self.staff)
        participant = self._participant(order, "903", self.staff)
        regular_order = self.env["sale.order"].create(
            {"partner_id": self.buyer.id}
        )
        other_line = self.env["sale.order.line"].create(
            {
                "order_id": regular_order.id,
                "product_id": self.service_product.id,
                "product_uom_qty": 1,
            }
        )

        for user in (self.staff, self.manager):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                participant.with_user(user).write({"sale_line_id": other_line.id})
        with self.assertRaises(UserError):
            self.env["travel.booking.participant"].with_user(self.staff).create(
                {
                    "order_id": order.id,
                    "jamaah_id": self._create_jamaah("904").id,
                    "room_type": "double",
                    "sale_line_id": other_line.id,
                }
            )
        self.assertEqual(participant.sale_line_id.travel_participant_id, participant)

    def test_manager_cannot_mutate_participants_while_order_is_locked(self):
        order = self._order(self.manager)
        participant = self._participant(order, "905", self.manager)
        order.with_user(self.manager).action_confirm()
        order.with_user(self.manager).action_lock()

        with self.assertRaises(UserError):
            participant.with_user(self.manager).write({"room_type": "double"})
        with self.assertRaises(UserError):
            participant.with_user(self.manager).unlink()
        with self.assertRaises(UserError):
            self._participant(order, "906", self.manager)

        order.with_user(self.manager).action_unlock()
        participant.with_user(self.manager).write({"room_type": "double"})
        self.assertEqual(participant.room_type, "double")

    def test_generated_line_discount_is_zero_and_validated_on_confirm(self):
        order = self._order()
        participant = self._participant(order, "907")
        self.assertEqual(participant.sale_line_id.discount, 0)

        participant.sale_line_id._travel_write_from_participant({"discount": 10})
        with self.assertRaises(UserError):
            order.action_confirm()

        participant.write({"room_type": "triple"})
        self.assertEqual(participant.sale_line_id.discount, 0)
        order.action_confirm()

    def test_same_currency_discount_pricelist_cannot_discount_snapshot(self):
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Hardening Discount Pricelist",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": pricelist.id,
                "applied_on": "3_global",
                "compute_price": "percentage",
                "percent_price": 25,
            }
        )
        order = self._order(pricelist_id=pricelist.id)
        participant = self._participant(order, "914")

        self.assertEqual(participant.sale_line_id.discount, 0)
        self.assertEqual(participant.sale_line_id.price_unit, 30_000_000)
        self.assertEqual(order.amount_total, participant.unit_price)
        order.action_confirm()

    def test_refresh_rejects_inactive_or_non_open_departure(self):
        order = self._order()
        self.departure.active = False
        with self.assertRaises(UserError):
            order.action_refresh_travel_prices()

    def test_staff_can_manage_ordinary_and_unverified_partner_contact(self):
        partner = self.env["res.partner"].with_user(self.staff).create(
            {"name": "Staff Contact"}
        )
        partner.with_user(self.staff).write({"phone": "+628111111111"})
        jamaah = self.env["travel.jamaah"].with_user(self.staff).create(
            {
                "partner_id": partner.id,
                "nik": "HARD-NIK-CONTACT",
                "birth_place": "Solo",
                "birth_date": "1990-01-01",
                "gender": "female",
                "emergency_contact_name": "Emergency",
                "emergency_contact_phone": "+628122222222",
            }
        )
        partner.with_user(self.staff).write({"city": "Semarang"})
        self.assertEqual(jamaah.city, "Semarang")
        unrelated = self.env["res.partner"].with_user(self.staff).create(
            {"name": "Unrelated Contact"}
        )
        with self.assertRaises(AccessError):
            unrelated.with_user(self.staff).unlink()
        with self.assertRaises(AccessError):
            self.env["res.partner.bank"].with_user(self.staff).create(
                {"partner_id": partner.id, "acc_number": "1234567890"}
            )

    def test_staff_cannot_mutate_other_internal_or_archive_verified_partner(self):
        internal_user = self._role_user(
            "phase2-protected-internal", "group_travel_finance"
        )
        with self.assertRaises(AccessError):
            internal_user.partner_id.with_user(self.staff).write(
                {"name": "Compromised Internal User"}
            )

        jamaah = self._verified_jamaah("917")
        with self.assertRaises(AccessError):
            jamaah.partner_id.with_user(self.staff).write({"active": False})

        jamaah.partner_id.with_user(self.manager).write({"active": False})
        self.assertFalse(jamaah.partner_id.active)
        audit_messages = jamaah.message_ids.filtered(
            lambda message: "Kontak Jamaah terverifikasi dikoreksi"
            in (message.body or "")
        )
        self.assertTrue(audit_messages)
        self.assertNotIn("False", " ".join(audit_messages.mapped("body")))

    def test_role_switch_removes_travel_derived_standard_permissions(self):
        cases = (
            ("group_travel_staff", "finance"),
            ("group_travel_manager", "finance"),
            ("group_travel_staff", False),
        )
        for index, (source_group, destination_role) in enumerate(cases):
            with self.subTest(
                source_group=source_group, destination_role=destination_role
            ):
                user = self._role_user(
                    f"phase2-role-transition-{index}", source_group
                )
                self.assertTrue(user.has_group("sales_team.group_sale_salesman"))
                user.write({"travel_umroh_role": destination_role})

                self.assertFalse(
                    user.has_group("sales_team.group_sale_salesman")
                )
                self.assertFalse(user.has_group("base.group_partner_manager"))
                with self.assertRaises(AccessError):
                    self.env["sale.order"].with_user(user).create(
                        {"partner_id": self.buyer.id}
                    )
                with self.assertRaises(AccessError):
                    self.env["res.partner"].with_user(user).create(
                        {"name": "Denied Transition Contact"}
                    )

    def test_verified_partner_contact_requires_manager_and_is_audited(self):
        jamaah = self._verified_jamaah("908")
        with self.assertRaises(AccessError):
            jamaah.partner_id.with_user(self.staff).write({"phone": "+628100000001"})

        jamaah.partner_id.with_user(self.manager).write(
            {"phone": "+628100000002"}
        )
        self.assertEqual(jamaah.phone, "+628100000002")
        self.assertTrue(
            jamaah.message_ids.filtered(
                lambda message: "Kontak Jamaah terverifikasi dikoreksi"
                in (message.body or "")
            )
        )

    def test_verified_attachments_require_manager_for_all_mutations(self):
        jamaah = self._verified_jamaah("909")
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "travel.jamaah"),
                ("res_id", "=", jamaah.id),
                ("res_field", "=", "ktp_file"),
            ],
            limit=1,
        )
        self.assertTrue(attachment)

        with self.assertRaises(AccessError):
            attachment.with_user(self.staff).write(
                {"datas": base64.b64encode(b"tampered")}
            )
        with self.assertRaises(AccessError):
            attachment.with_user(self.staff).unlink()
        with self.assertRaises(AccessError):
            attachment.with_user(self.staff).write(
                {"res_id": self._create_jamaah("910").id}
            )
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].with_user(self.staff).create(
                {
                    "name": "replacement.pdf",
                    "datas": base64.b64encode(b"replacement"),
                    "res_model": "travel.jamaah",
                    "res_id": jamaah.id,
                    "res_field": "ktp_file",
                }
            )

        attachment.with_user(self.manager).write(
            {"datas": base64.b64encode(b"manager-correction")}
        )
        audit_messages = jamaah.message_ids.filtered(
            lambda message: "Lampiran dokumen Jamaah terverifikasi dikoreksi"
            in (message.body or "")
        )
        self.assertTrue(audit_messages)
        manager_attachment = self.env["ir.attachment"].with_user(
            self.manager
        ).create(
            {
                "name": "manager-addition.pdf",
                "datas": base64.b64encode(b"manager-addition"),
                "res_model": "travel.jamaah",
                "res_id": jamaah.id,
                "res_field": "passport_file",
            }
        )
        manager_attachment.with_user(self.manager).write(
            {"res_id": self._create_jamaah("915").id}
        )
        disposable_attachment = self.env["ir.attachment"].with_user(
            self.manager
        ).create(
            {
                "name": "manager-removal.pdf",
                "datas": base64.b64encode(b"manager-removal"),
                "res_model": "travel.jamaah",
                "res_id": jamaah.id,
                "res_field": "ktp_file",
            }
        )
        disposable_attachment.with_user(self.manager).unlink()

        audit_body = " ".join(
            jamaah.message_ids.filtered(
                lambda message: "Lampiran dokumen Jamaah terverifikasi dikoreksi"
                in (message.body or "")
            ).mapped("body")
        )
        for operation in ("diperbarui", "ditambahkan", "dipindahkan", "dihapus"):
            self.assertIn(operation, audit_body)
        for raw_value in (
            "manager-correction",
            "manager-addition",
            "manager-removal",
        ):
            self.assertNotIn(raw_value, audit_body)

    def test_sensitive_identity_values_are_not_stored_in_mail_tracking(self):
        jamaah = self._verified_jamaah("911")
        old_nik = jamaah.nik
        old_passport = jamaah.passport_number
        new_nik = "HARD-NIK-911-UPDATED"
        new_passport = "HARD-PASS-911-UPDATED"

        jamaah.with_user(self.manager).write(
            {"nik": new_nik, "passport_number": new_passport}
        )

        tracking_values = jamaah.message_ids.mapped("tracking_value_ids")
        serialized = " ".join(
            str(value or "")
            for tracking in tracking_values
            for value in (
                tracking.old_value_char,
                tracking.new_value_char,
                tracking.old_value_text,
                tracking.new_value_text,
            )
        )
        for sensitive_value in (old_nik, old_passport, new_nik, new_passport):
            self.assertNotIn(sensitive_value, serialized)
            self.assertNotIn(
                sensitive_value,
                " ".join(jamaah.message_ids.mapped("body")),
            )
