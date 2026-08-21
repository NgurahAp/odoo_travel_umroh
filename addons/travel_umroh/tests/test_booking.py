from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError

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

    def test_each_participant_creates_one_service_order_line_and_snapshot(self):
        order = self._create_order()
        jamaah = self._create_jamaah("101")
        participant = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": jamaah.id,
                "room_type": "quad",
                "unit_price": 1,
            }
        )
        self.assertEqual(participant.unit_price, 30_000_000)
        self.assertTrue(participant.sale_line_id)
        self.assertEqual(
            participant.sale_line_id.travel_participant_id, participant
        )
        self.assertEqual(
            participant.sale_line_id.product_id, self.package.product_id
        )
        self.assertEqual(participant.sale_line_id.product_uom_qty, 1)
        self.assertEqual(
            participant.sale_line_id.price_unit, participant.unit_price
        )
        self.assertIn(jamaah.name, participant.sale_line_id.name)
        self.assertEqual(order.participant_count, 1)

    def test_multi_participant_total_equals_snapshot_sum_for_tax_free_fixture(self):
        self.assertFalse(self.package.product_id.taxes_id)
        order = self._create_order()
        first = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah("102").id,
                "room_type": "quad",
            }
        )
        second = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah("103").id,
                "room_type": "double",
            }
        )
        self.assertEqual(
            order.amount_total, first.unit_price + second.unit_price
        )
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(order.participant_count, 2)

    @mute_logger("odoo.sql_db")
    def test_jamaah_cannot_be_duplicated_in_one_booking(self):
        order = self._create_order()
        jamaah = self._create_jamaah("104")
        values = {
            "order_id": order.id,
            "jamaah_id": jamaah.id,
            "room_type": "triple",
        }
        self.env["travel.booking.participant"].create(values)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["travel.booking.participant"].create(values)

    def test_removing_participant_removes_only_its_generated_line(self):
        order = self._create_order()
        first = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah("105").id,
                "room_type": "triple",
            }
        )
        second = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah("106").id,
                "room_type": "quad",
            }
        )
        first_line = first.sale_line_id
        second_line = second.sale_line_id

        first.unlink()

        self.assertFalse(first.exists())
        self.assertFalse(first_line.exists())
        self.assertTrue(second.exists())
        self.assertTrue(second_line.exists())

    def test_participant_requires_travel_order_departure_and_room_price(self):
        regular_order = self.env["sale.order"].create(
            {"partner_id": self.buyer.id}
        )
        with self.assertRaises(UserError):
            self.env["travel.booking.participant"].create(
                {
                    "order_id": regular_order.id,
                    "jamaah_id": self._create_jamaah("107").id,
                    "room_type": "quad",
                }
            )
        travel_without_departure = self._create_order(departure_id=False)
        with self.assertRaises(UserError):
            self.env["travel.booking.participant"].create(
                {
                    "order_id": travel_without_departure.id,
                    "jamaah_id": self._create_jamaah("108").id,
                    "room_type": "quad",
                }
            )

    def test_generated_line_cannot_be_created_or_mutated_directly(self):
        order = self._create_order()
        participant = self.env["travel.booking.participant"].create(
            {
                "order_id": order.id,
                "jamaah_id": self._create_jamaah("109").id,
                "room_type": "quad",
            }
        )
        with self.assertRaises(UserError):
            self.env["sale.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": self.package.product_id.id,
                    "product_uom_qty": 1,
                    "travel_participant_id": participant.id,
                }
            )
        with self.assertRaises(UserError):
            participant.sale_line_id.write({"price_unit": 1})
        with self.assertRaises(UserError):
            participant.sale_line_id.unlink()
