from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelBooking(TravelBookingCase):
    def _create_order(self, **overrides):
        values = {
            "partner_id": self.buyer.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        }
        values.update(overrides)
        return self.env["sale.order"].create(values)

    def test_travel_booking_reuses_sale_order_and_departure_package(self):
        order = self._create_order()
        self.assertTrue(order.is_travel_booking)
        self.assertEqual(order.departure_id, self.departure)
        self.assertEqual(order.travel_package_id, self.package)
        self.assertIn(order, self.departure.booking_ids)
        self.assertEqual(self.departure.booking_count, 1)

    def test_buyer_is_not_required_to_be_a_jamaah(self):
        order = self._create_order()
        self.assertFalse(
            self.env["travel.jamaah"].search(
                [("partner_id", "=", order.partner_id.id)]
            )
        )

    def test_travel_booking_can_be_saved_before_departure_is_selected(self):
        order = self._create_order(departure_id=False)
        self.assertTrue(order.is_travel_booking)
        self.assertFalse(order.departure_id)

    def test_draft_or_cancelled_departure_cannot_be_selected(self):
        invalid_departure = self.env["travel.departure"].create(
            {
                "package_id": self.package.id,
                "departure_date": "2027-10-01",
                "return_date": "2027-10-10",
                "quota": 20,
                "company_id": self.env.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self._create_order(departure_id=invalid_departure.id)
        invalid_departure.action_cancel()
        with self.assertRaises(ValidationError):
            self._create_order(departure_id=invalid_departure.id)

    def test_departure_cannot_be_assigned_to_regular_sale_order(self):
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(
                {
                    "partner_id": self.buyer.id,
                    "departure_id": self.departure.id,
                }
            )

    def test_travel_flag_cannot_be_removed_after_departure_is_set(self):
        order = self._create_order()
        with self.assertRaises(ValidationError):
            order.write({"is_travel_booking": False})

    def test_departure_currency_must_match_sale_pricelist_currency(self):
        foreign_currency = self.env["res.currency"].with_context(
            active_test=False
        ).search(
            [("id", "!=", self.env.company.currency_id.id)], limit=1
        )
        if not foreign_currency.active:
            foreign_currency.active = True
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Synthetic Foreign Pricelist",
                "currency_id": foreign_currency.id,
            }
        )
        with self.assertRaises(ValidationError):
            self._create_order(pricelist_id=pricelist.id)

    def test_regular_sale_order_remains_unaffected(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self.assertFalse(order.is_travel_booking)
        self.assertFalse(order.departure_id)

    def test_staff_role_implies_standard_sales_user(self):
        staff = self.env["res.users"].create(
            {
                "name": "Phase 2 Booking Staff",
                "login": "phase2-booking-shell-staff",
                "email": "phase2-booking-shell-staff@example.test",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "travel_umroh.group_travel_staff"
                            ).id,
                        ]
                    )
                ],
            }
        )
        self.assertTrue(staff.has_group("sales_team.group_sale_salesman"))
