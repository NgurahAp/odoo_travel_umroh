from lxml import etree

from odoo import Command
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelPhaseTwoViews(TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env["res.users"].create(
            {
                "name": "Phase 2 View Staff",
                "login": "phase2-view-staff",
                "email": "phase2-view-staff@example.test",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(
                                "travel_umroh.group_travel_staff"
                            ).id,
                        ]
                    )
                ],
            }
        )

    def _staff_sale_form(self):
        arch = (
            self.env["sale.order"]
            .with_user(self.staff)
            .with_context(debug=False)
            .get_view(
                view_id=self.env.ref("sale.view_order_form").id,
                view_type="form",
            )["arch"]
        )
        return etree.fromstring(arch.encode())

    def test_booking_action_is_scoped_and_defaults_travel_flag(self):
        action = self.env.ref("travel_umroh.action_travel_booking").read()[0]
        self.assertIn("is_travel_booking", action["domain"])
        self.assertIn("default_is_travel_booking", action["context"])

    def test_jamaah_action_and_booking_smart_action_are_scoped(self):
        action = self.env.ref("travel_umroh.action_travel_jamaah").read()[0]
        self.assertEqual(action["res_model"], "travel.jamaah")
        self.assertEqual(action["view_mode"], "list,form")

        jamaah = self._create_jamaah("501")
        booking_action = jamaah.action_view_bookings()
        self.assertEqual(booking_action["res_model"], "sale.order")
        self.assertIn(
            ("participant_ids.jamaah_id", "=", jamaah.id),
            booking_action["domain"],
        )

    def test_staff_composed_sale_form_contains_one_travel_participant_page(self):
        root = self._staff_sale_form()
        pages = root.xpath("//page[@name='travel_participants']")
        self.assertEqual(len(pages), 1)
        self.assertEqual(
            pages[0].xpath(".//field[@name='participant_ids']").__len__(),
            1,
        )
        self.assertIn("not is_travel_booking", pages[0].get("invisible"))

    def test_standard_order_lines_are_hidden_only_for_travel_booking(self):
        root = self._staff_sale_form()
        order_line_pages = root.xpath("//page[@name='order_lines']")
        self.assertEqual(len(order_line_pages), 1)
        self.assertIn(
            "is_travel_booking", order_line_pages[0].get("invisible", "")
        )

    def test_jamaah_binary_fields_and_manager_verification_controls(self):
        arch = self.env.ref("travel_umroh.view_travel_jamaah_form").arch_db
        root = etree.fromstring(arch.encode())
        self.assertEqual(
            root.xpath("//field[@name='ktp_file']/@filename"),
            ["ktp_filename"],
        )
        self.assertEqual(
            root.xpath("//field[@name='passport_file']/@filename"),
            ["passport_filename"],
        )
        verification_buttons = root.xpath(
            "//button[@name='action_verify_documents']"
        )
        self.assertEqual(len(verification_buttons), 1)
        self.assertEqual(
            verification_buttons[0].get("groups"),
            "travel_umroh.group_travel_manager",
        )

    def test_departure_form_exposes_booking_count_and_readonly_booking_page(self):
        arch = self.env.ref("travel_umroh.view_travel_departure_form").arch_db
        root = etree.fromstring(arch.encode())
        self.assertEqual(
            len(root.xpath("//button[@name='action_view_bookings']")), 1
        )
        self.assertEqual(len(root.xpath("//field[@name='booking_count']")), 1)
        booking_pages = root.xpath("//page[@name='bookings']")
        self.assertEqual(len(booking_pages), 1)
        self.assertEqual(
            booking_pages[0].xpath(".//field[@name='booking_ids']/@readonly"),
            ["1"],
        )

    def test_phase_two_views_use_odoo_eighteen_list_tag(self):
        view_xmlids = (
            "travel_umroh.view_travel_jamaah_list",
            "travel_umroh.view_travel_jamaah_form",
            "travel_umroh.view_travel_jamaah_search",
            "travel_umroh.view_sale_order_form_travel",
            "travel_umroh.view_travel_departure_form",
        )
        for xmlid in view_xmlids:
            root = etree.fromstring(self.env.ref(xmlid).arch_db.encode())
            self.assertFalse(root.xpath("//tree"), xmlid)
