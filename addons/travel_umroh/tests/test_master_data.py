from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTravelMasterData(TransactionCase):
    def test_hotel_rejects_star_rating_outside_one_to_five(self):
        for star_rating in (0, 6):
            with self.subTest(star_rating=star_rating), self.assertRaises(ValidationError):
                self.env["travel.hotel"].create(
                    {
                        "name": "Invalid Rating",
                        "city": "Makkah",
                        "star_rating": star_rating,
                    }
                )

    def test_hotel_rejects_negative_distance(self):
        with self.assertRaises(ValidationError):
            self.env["travel.hotel"].create(
                {
                    "name": "Invalid Distance",
                    "city": "Madinah",
                    "star_rating": 4,
                    "distance_to_mosque_km": -1,
                }
            )

    def test_airport_uses_odoo_country(self):
        airport = self.env["travel.airport"].create(
            {
                "name": "Soekarno-Hatta International Airport",
                "iata_code": "CGK",
                "city": "Tangerang",
                "country_id": self.env.ref("base.id").id,
            }
        )

        self.assertEqual(airport.country_id.code, "ID")

    def test_iata_codes_are_trimmed_and_uppercased_on_create_and_write(self):
        airline = self.env["travel.airline"].create(
            {"name": "Garuda Indonesia", "iata_code": " ga "}
        )
        airport = self.env["travel.airport"].create(
            {
                "name": "King Abdulaziz International Airport",
                "iata_code": " jed ",
                "city": "Jeddah",
                "country_id": self.env.ref("base.sa").id,
            }
        )

        self.assertEqual(airline.iata_code, "GA")
        self.assertEqual(airport.iata_code, "JED")

        airline.write({"iata_code": " sv "})
        airport.write({"iata_code": " med "})

        self.assertEqual(airline.iata_code, "SV")
        self.assertEqual(airport.iata_code, "MED")

    def test_iata_codes_reject_values_longer_than_three_characters(self):
        with self.assertRaises(ValidationError):
            self.env["travel.airline"].create(
                {"name": "Invalid Airline", "iata_code": "LONG"}
            )

        with self.assertRaises(ValidationError):
            self.env["travel.airport"].create(
                {
                    "name": "Invalid Airport",
                    "iata_code": "LONG",
                    "city": "Nowhere",
                    "country_id": self.env.ref("base.id").id,
                }
            )
