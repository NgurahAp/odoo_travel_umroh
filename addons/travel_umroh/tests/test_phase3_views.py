from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseThreeViews(TravelAccountingCase):
    def _composed_sale_form(self, user):
        arch = (
            self.env["sale.order"]
            .with_user(user)
            .get_view(
                view_id=self.env.ref("sale.view_order_form").id,
                view_type="form",
            )["arch"]
        )
        return etree.fromstring(arch.encode())

    def test_travel_audit_fields_and_standard_invoice_controls_remain(self):
        for user in (self.staff, self.finance, self.manager):
            with self.subTest(user=user.login):
                root = self._composed_sale_form(user)
                for field_name in (
                    "travel_payment_state",
                    "travel_state",
                    "seat_reserved",
                    "seat_reserved_at",
                ):
                    fields = root.xpath(
                        f"//field[@name='{field_name}']"
                    )
                    self.assertEqual(len(fields), 1)
                    self.assertEqual(fields[0].get("readonly"), "1")
                    self.assertIn(
                        "not is_travel_booking",
                        fields[0].get("invisible", ""),
                    )
                self.assertTrue(
                    root.xpath("//button[@name='action_view_invoice']")
                )
                self.assertTrue(root.xpath("//button[@id='create_invoice']"))

        self.env["sale.advance.payment.inv"].with_user(
            self.finance
        ).check_access("create")
        self.env["sale.advance.payment.inv"].with_user(
            self.manager
        ).check_access("create")
        order = self._confirmed_booking("VIEW-INVOICE")
        staff_wizard = (
            self.env["sale.advance.payment.inv"]
            .with_user(self.staff)
            .with_context(
                active_model="sale.order",
                active_id=order.id,
                active_ids=order.ids,
            )
            .create({"advance_payment_method": "percentage", "amount": 20})
        )
        with self.assertRaises(AccessError):
            staff_wizard.create_invoices()

    def test_create_invoice_is_hidden_from_staff_only_for_travel_booking(self):
        self.assertIn("can_create_travel_invoice", self.env["sale.order"]._fields)
        self.assertFalse(
            self.env["sale.order"].with_user(self.staff).new(
                {"is_travel_booking": True}
            ).can_create_travel_invoice
        )
        for user in (self.finance, self.manager):
            with self.subTest(user=user.login):
                self.assertTrue(
                    self.env["sale.order"].with_user(user).new(
                        {"is_travel_booking": True}
                    ).can_create_travel_invoice
                )

        root = self._composed_sale_form(self.staff)
        create_invoice_buttons = root.xpath("//button[@id='create_invoice']")
        self.assertTrue(create_invoice_buttons)
        for button in create_invoice_buttons:
            self.assertIn(
                "is_travel_booking and not can_create_travel_invoice",
                button.get("invisible", ""),
            )
        self.assertTrue(root.xpath("//field[@name='can_create_travel_invoice']"))

    def test_booking_view_has_manager_cancel_and_full_departure_domain(self):
        root = etree.fromstring(
            self.env.ref(
                "travel_umroh.view_sale_order_form_travel"
            ).arch_db.encode()
        )
        cancel_button = root.xpath(
            "//button[@name='action_open_travel_cancel_wizard']"
        )
        self.assertEqual(len(cancel_button), 1)
        self.assertEqual(
            cancel_button[0].get("groups"),
            "travel_umroh.group_travel_manager",
        )
        departure_field = root.xpath("//field[@name='departure_id']")[0]
        self.assertIn("('is_full', '=', False)", departure_field.get("domain"))

    def test_departure_views_expose_capacity_lifecycle_and_booking_states(self):
        list_root = etree.fromstring(
            self.env.ref(
                "travel_umroh.view_travel_departure_list"
            ).arch_db.encode()
        )
        form_root = etree.fromstring(
            self.env.ref(
                "travel_umroh.view_travel_departure_form"
            ).arch_db.encode()
        )
        for field_name in (
            "quota",
            "reserved_seats",
            "remaining_seats",
            "is_full",
        ):
            self.assertTrue(list_root.xpath(f"//field[@name='{field_name}']"))
            self.assertTrue(form_root.xpath(f"//field[@name='{field_name}']"))

        depart_button = form_root.xpath("//button[@name='action_depart']")
        done_button = form_root.xpath("//button[@name='action_done']")
        self.assertEqual(len(depart_button), 1)
        self.assertEqual(len(done_button), 1)
        for button, state in ((depart_button[0], "open"), (done_button[0], "departed")):
            self.assertEqual(
                button.get("groups"), "travel_umroh.group_travel_manager"
            )
            self.assertIn(state, button.get("invisible", ""))

        booking_page = form_root.xpath("//page[@name='bookings']")[0]
        for field_name in (
            "travel_payment_state",
            "travel_state",
            "seat_reserved",
        ):
            self.assertTrue(
                booking_page.xpath(f".//field[@name='{field_name}']")
            )

    def test_phase_three_views_use_odoo_eighteen_list_tags(self):
        for xmlid in (
            "travel_umroh.view_sale_order_form_travel",
            "travel_umroh.view_travel_departure_list",
            "travel_umroh.view_travel_departure_form",
            "travel_umroh.view_travel_booking_cancel_wizard_form",
        ):
            root = etree.fromstring(self.env.ref(xmlid).arch_db.encode())
            self.assertFalse(root.xpath("//tree"), xmlid)
