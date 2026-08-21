from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelItinerary(TravelUmrohCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.airline = cls.env["travel.airline"].create(
            {"name": "Saudia Airlines", "iata_code": "SV"}
        )
        cls.cgk = cls.env["travel.airport"].create(
            {
                "name": "Soekarno-Hatta International Airport",
                "iata_code": "CGK",
                "city": "Tangerang",
                "country_id": cls.env.ref("base.id").id,
            }
        )
        cls.jed = cls.env["travel.airport"].create(
            {
                "name": "King Abdulaziz International Airport",
                "iata_code": "JED",
                "city": "Jeddah",
                "country_id": cls.env.ref("base.sa").id,
            }
        )
        cls.hotel = cls.env["travel.hotel"].create(
            {
                "name": "Makkah Hotel",
                "city": "Makkah",
                "star_rating": 4,
            }
        )

    def _create_departure(self):
        return self.env["travel.departure"].create(
            {
                "package_id": self.package.id,
                "departure_date": "2027-03-15",
                "return_date": "2027-03-24",
                "quota": 45,
                "company_id": self.env.company.id,
            }
        )

    def _flight_values(self, departure, **overrides):
        values = {
            "departure_id": departure.id,
            "airline_id": self.airline.id,
            "flight_number": "SV-001",
            "origin_airport_id": self.cgk.id,
            "destination_airport_id": self.jed.id,
            "departure_datetime": "2027-03-15 01:00:00",
            "arrival_datetime": "2027-03-15 10:00:00",
        }
        values.update(overrides)
        return values

    def _add_complete_prices(self, departure):
        for room_type, price in (
            ("quad", 30_000_000),
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

    def test_flight_arrival_must_be_after_departure(self):
        departure = self._create_departure()

        with self.assertRaises(ValidationError):
            self.env["travel.departure.flight"].create(
                self._flight_values(
                    departure,
                    arrival_datetime="2027-03-15 01:00:00",
                )
            )

    def test_flight_origin_and_destination_must_differ(self):
        departure = self._create_departure()

        with self.assertRaises(ValidationError):
            self.env["travel.departure.flight"].create(
                self._flight_values(departure, destination_airport_id=self.cgk.id)
            )

    def test_flight_legs_are_ordered_by_sequence_datetime_and_id(self):
        departure = self._create_departure()
        late_sequence = self.env["travel.departure.flight"].create(
            self._flight_values(
                departure,
                sequence=20,
                flight_number="SV-003",
                departure_datetime="2027-03-16 01:00:00",
                arrival_datetime="2027-03-16 10:00:00",
            )
        )
        later_time = self.env["travel.departure.flight"].create(
            self._flight_values(
                departure,
                sequence=10,
                flight_number="SV-002",
                departure_datetime="2027-03-15 03:00:00",
                arrival_datetime="2027-03-15 12:00:00",
            )
        )
        earlier_time = self.env["travel.departure.flight"].create(
            self._flight_values(departure, sequence=10, flight_number="SV-001")
        )

        legs = self.env["travel.departure.flight"].search(
            [("departure_id", "=", departure.id)]
        )

        self.assertEqual(legs, earlier_time | later_time | late_sequence)

    def test_accommodation_checkout_must_be_after_checkin(self):
        departure = self._create_departure()

        with self.assertRaises(ValidationError):
            self.env["travel.departure.accommodation"].create(
                {
                    "departure_id": departure.id,
                    "hotel_id": self.hotel.id,
                    "check_in": "2027-03-17",
                    "check_out": "2027-03-17",
                }
            )

    def test_draft_allows_accommodation_outside_trip_window(self):
        departure = self._create_departure()

        stay = self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-14",
                "check_out": "2027-03-17",
            }
        )

        self.assertEqual(stay.departure_id.state, "draft")

    def test_open_rejects_accommodation_outside_trip_window(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-14",
                "check_out": "2027-03-17",
            }
        )

        with self.assertRaises(UserError):
            departure.action_open()

    def test_open_accepts_accommodation_inside_trip_window(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-15",
                "check_out": "2027-03-24",
            }
        )

        departure.action_open()

        self.assertEqual(departure.state, "open")

    def test_open_departure_rejects_new_accommodation_outside_trip_window(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_open()

        with self.assertRaises(ValidationError):
            self.env["travel.departure.accommodation"].create(
                {
                    "departure_id": departure.id,
                    "hotel_id": self.hotel.id,
                    "check_in": "2027-03-14",
                    "check_out": "2027-03-17",
                }
            )

    def test_open_departure_rejects_accommodation_moved_outside_trip_window(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        stay = self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-15",
                "check_out": "2027-03-20",
            }
        )
        departure.action_open()

        with self.assertRaises(ValidationError):
            stay.write({"check_in": "2027-03-14"})

    def test_open_departure_rejects_date_change_that_invalidates_accommodation(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-15",
                "check_out": "2027-03-24",
            }
        )
        departure.action_open()

        with self.assertRaises(ValidationError):
            departure.write({"return_date": "2027-03-23"})

    def test_accommodations_are_ordered_by_sequence(self):
        departure = self._create_departure()
        second = self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "sequence": 20,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-19",
                "check_out": "2027-03-24",
            }
        )
        first = self.env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "sequence": 10,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-15",
                "check_out": "2027-03-19",
            }
        )

        stays = self.env["travel.departure.accommodation"].search(
            [("departure_id", "=", departure.id)]
        )

        self.assertEqual(stays, first | second)
