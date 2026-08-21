from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelDeparture(TravelUmrohCase):
    def _create_departure(self, **overrides):
        values = {
            "package_id": self.package.id,
            "departure_date": "2027-03-15",
            "return_date": "2027-03-24",
            "quota": 45,
            "company_id": self.env.company.id,
        }
        values.update(overrides)
        return self.env["travel.departure"].create(values)

    def _add_complete_prices(self, departure, quad_price=30_000_000):
        for room_type, price in (
            ("quad", quad_price),
            ("triple", 32_000_000),
            ("double", 35_000_000),
        ):
            self.env["travel.departure.price"].create(
                {
                    "departure_id": departure.id,
                    "room_type": room_type,
                    "price": price,
                }
            )

    def test_return_must_be_after_departure(self):
        with self.assertRaises(ValidationError):
            self._create_departure(return_date="2027-03-15")

    def test_quota_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._create_departure(quota=-1)

    def test_departure_name_and_currency_follow_package_date_and_company(self):
        departure = self._create_departure()

        self.assertEqual(departure.name, "REG-09 — 15 Mar 2027")
        self.assertEqual(departure.currency_id, self.company_currency)

    def test_price_cannot_be_negative(self):
        departure = self._create_departure()

        with self.assertRaises(ValidationError):
            self.env["travel.departure.price"].create(
                {
                    "departure_id": departure.id,
                    "room_type": "quad",
                    "price": -1,
                }
            )

    @mute_logger("odoo.sql_db")
    def test_room_type_is_unique_per_departure(self):
        departure = self._create_departure()
        values = {
            "departure_id": departure.id,
            "room_type": "quad",
            "price": 30_000_000,
        }
        self.env["travel.departure.price"].create(values)

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["travel.departure.price"].create(values)

    def test_open_requires_quad_triple_and_double_prices(self):
        departure = self._create_departure()
        self.env["travel.departure.price"].create(
            {
                "departure_id": departure.id,
                "room_type": "quad",
                "price": 30_000_000,
            }
        )

        with self.assertRaises(UserError):
            departure.action_open()

    def test_open_succeeds_with_complete_prices_including_zero(self):
        departure = self._create_departure()
        self._add_complete_prices(departure, quad_price=0)

        departure.action_open()

        self.assertEqual(departure.state, "open")

    def test_state_cannot_be_opened_by_direct_write(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)

        with self.assertRaises(UserError):
            departure.write({"state": "open"})

    def test_client_context_cannot_bypass_open_action(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)

        with self.assertRaises(UserError):
            departure.with_context(_travel_allow_state_change=True).write(
                {"state": "open"}
            )

        self.assertEqual(departure.state, "draft")

    def test_direct_write_cannot_enter_other_workflow_states(self):
        departure = self._create_departure()

        for target_state in ("departed", "done", "cancelled"):
            with self.subTest(target_state=target_state), self.assertRaises(UserError):
                departure.write({"state": target_state})

        self.assertEqual(departure.state, "draft")

    def test_open_departure_required_price_cannot_be_deleted(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_open()
        quad_price = departure.price_ids.filtered(lambda line: line.room_type == "quad")

        with self.assertRaises(UserError):
            quad_price.unlink()

        self.assertTrue(quad_price.exists())

    def test_open_departure_price_structure_cannot_be_changed(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_open()
        quad_price = departure.price_ids.filtered(lambda line: line.room_type == "quad")

        with self.assertRaises(UserError):
            quad_price.write({"room_type": "triple"})

    def test_cancelled_departure_cannot_be_reopened(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_cancel()

        with self.assertRaises(UserError):
            departure.action_open()
