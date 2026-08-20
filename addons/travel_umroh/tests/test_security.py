from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelSecurity(TravelUmrohCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls._create_user("staff", "group_travel_staff")
        cls.finance = cls._create_user("finance", "group_travel_finance")
        cls.manager = cls._create_user("manager", "group_travel_manager")
        cls.internal_user = cls._create_user("internal", None)

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
        cls.departure = cls.env["travel.departure"].create(
            {
                "package_id": cls.package.id,
                "departure_date": "2027-03-15",
                "return_date": "2027-03-24",
                "quota": 45,
                "company_id": cls.env.company.id,
            }
        )
        cls.price = cls.env["travel.departure.price"].create(
            {
                "departure_id": cls.departure.id,
                "room_type": "quad",
                "price": 30_000_000,
            }
        )
        cls.flight = cls.env["travel.departure.flight"].create(
            {
                "departure_id": cls.departure.id,
                "airline_id": cls.airline.id,
                "flight_number": "SV-001",
                "origin_airport_id": cls.cgk.id,
                "destination_airport_id": cls.jed.id,
                "departure_datetime": "2027-03-15 01:00:00",
                "arrival_datetime": "2027-03-15 10:00:00",
            }
        )
        cls.accommodation = cls.env["travel.departure.accommodation"].create(
            {
                "departure_id": cls.departure.id,
                "hotel_id": cls.hotel.id,
                "check_in": "2027-03-15",
                "check_out": "2027-03-20",
            }
        )
        cls.records_by_model = {
            "travel.airline": cls.airline,
            "travel.airport": cls.cgk,
            "travel.hotel": cls.hotel,
            "travel.package": cls.package,
            "travel.departure": cls.departure,
            "travel.departure.price": cls.price,
            "travel.departure.flight": cls.flight,
            "travel.departure.accommodation": cls.accommodation,
        }

    @classmethod
    def _create_user(cls, login, travel_group_xmlid):
        group_ids = [cls.env.ref("base.group_user").id]
        if travel_group_xmlid:
            group_ids.append(cls.env.ref(f"travel_umroh.{travel_group_xmlid}").id)
        return cls.env["res.users"].create(
            {
                "name": login.title(),
                "login": f"phase1-{login}",
                "email": f"phase1-{login}@example.test",
                "groups_id": [Command.set(group_ids)],
            }
        )

    def _create_values(self, suffix):
        return {
            "travel.airline": {"name": f"Airline {suffix}", "iata_code": "XY"},
            "travel.airport": {
                "name": f"Airport {suffix}",
                "iata_code": "XYZ",
                "city": "Test City",
                "country_id": self.env.ref("base.id").id,
            },
            "travel.hotel": {
                "name": f"Hotel {suffix}",
                "city": "Makkah",
                "star_rating": 4,
            },
            "travel.package": {
                "name": f"Package {suffix}",
                "code": f"PKG-{suffix}",
                "product_id": self.service_product.id,
                "duration_days": 9,
            },
            "travel.departure": {
                "package_id": self.package.id,
                "departure_date": "2027-04-01",
                "return_date": "2027-04-10",
                "quota": 40,
                "company_id": self.env.company.id,
            },
            "travel.departure.price": {
                "departure_id": self.departure.id,
                "room_type": "triple",
                "price": 32_000_000,
            },
            "travel.departure.flight": {
                "departure_id": self.departure.id,
                "airline_id": self.airline.id,
                "flight_number": f"{suffix}-001",
                "origin_airport_id": self.cgk.id,
                "destination_airport_id": self.jed.id,
                "departure_datetime": "2027-03-16 01:00:00",
                "arrival_datetime": "2027-03-16 10:00:00",
            },
            "travel.departure.accommodation": {
                "departure_id": self.departure.id,
                "hotel_id": self.hotel.id,
                "check_in": "2027-03-20",
                "check_out": "2027-03-24",
            },
        }

    def _write_values(self):
        return {
            "travel.airline": {"name": "Updated Airline"},
            "travel.airport": {"city": "Updated City"},
            "travel.hotel": {"city": "Updated Makkah"},
            "travel.package": {"name": "Updated Package"},
            "travel.departure": {"quota": 46},
            "travel.departure.price": {"price": 31_000_000},
            "travel.departure.flight": {"flight_number": "SV-002"},
            "travel.departure.accommodation": {"sequence": 20},
        }

    def test_staff_and_finance_are_read_only_on_all_phase_one_models(self):
        create_values = self._create_values("READONLY")
        write_values = self._write_values()

        for user in (self.staff, self.finance):
            for model_name, record in self.records_by_model.items():
                with self.subTest(user=user.login, model=model_name, operation="read"):
                    data = record.with_user(user).read(["display_name"])
                    self.assertEqual(data[0]["id"], record.id)

                with self.subTest(user=user.login, model=model_name, operation="create"):
                    with self.assertRaises(AccessError):
                        self.env[model_name].with_user(user).create(
                            create_values[model_name]
                        )

                with self.subTest(user=user.login, model=model_name, operation="write"):
                    with self.assertRaises(AccessError):
                        record.with_user(user).write(write_values[model_name])

                with self.subTest(user=user.login, model=model_name, operation="unlink"):
                    with self.assertRaises(AccessError):
                        record.with_user(user).unlink()

    def test_internal_user_without_travel_role_cannot_read_phase_one_models(self):
        for model_name, record in self.records_by_model.items():
            with self.subTest(model=model_name):
                with self.assertRaises(AccessError):
                    record.with_user(self.internal_user).read(["display_name"])

    def test_unauthorized_unlink_does_not_delete_chatter(self):
        for record in (self.package, self.departure):
            record.message_post(body="Pesan audit yang harus tetap tersimpan.")
            message_domain = [("model", "=", record._name), ("res_id", "=", record.id)]
            message_ids_before = self.env["mail.message"].search(message_domain).ids
            self.assertTrue(message_ids_before)

            with self.subTest(model=record._name), self.assertRaises(AccessError):
                record.with_user(self.staff).unlink()

            message_ids_after = self.env["mail.message"].search(message_domain).ids
            self.assertEqual(message_ids_after, message_ids_before)

    def test_manager_can_create_write_archive_and_unlink_phase_one_models(self):
        manager_env = self.env(user=self.manager)
        airline = manager_env["travel.airline"].create(
            {"name": "Manager Airline", "iata_code": "MA"}
        )
        origin = manager_env["travel.airport"].create(
            {
                "name": "Manager Origin",
                "iata_code": "MOR",
                "city": "Origin City",
                "country_id": self.env.ref("base.id").id,
            }
        )
        destination = manager_env["travel.airport"].create(
            {
                "name": "Manager Destination",
                "iata_code": "MDS",
                "city": "Destination City",
                "country_id": self.env.ref("base.sa").id,
            }
        )
        hotel = manager_env["travel.hotel"].create(
            {"name": "Manager Hotel", "city": "Makkah", "star_rating": 5}
        )
        package = manager_env["travel.package"].create(
            {
                "name": "Manager Package",
                "code": "MANAGER-PKG",
                "product_id": self.service_product.id,
                "duration_days": 10,
            }
        )
        departure = manager_env["travel.departure"].create(
            {
                "package_id": package.id,
                "departure_date": "2027-05-01",
                "return_date": "2027-05-11",
                "quota": 30,
                "company_id": self.env.company.id,
            }
        )
        price = manager_env["travel.departure.price"].create(
            {
                "departure_id": departure.id,
                "room_type": "double",
                "price": 35_000_000,
            }
        )
        flight = manager_env["travel.departure.flight"].create(
            {
                "departure_id": departure.id,
                "airline_id": airline.id,
                "flight_number": "MA-001",
                "origin_airport_id": origin.id,
                "destination_airport_id": destination.id,
                "departure_datetime": "2027-05-01 01:00:00",
                "arrival_datetime": "2027-05-01 10:00:00",
            }
        )
        accommodation = manager_env["travel.departure.accommodation"].create(
            {
                "departure_id": departure.id,
                "hotel_id": hotel.id,
                "check_in": "2027-05-01",
                "check_out": "2027-05-05",
            }
        )

        records = {
            "travel.airline": airline,
            "travel.airport": origin,
            "travel.hotel": hotel,
            "travel.package": package,
            "travel.departure": departure,
            "travel.departure.price": price,
            "travel.departure.flight": flight,
            "travel.departure.accommodation": accommodation,
        }
        for model_name, values in self._write_values().items():
            with self.subTest(model=model_name, operation="write"):
                self.assertTrue(records[model_name].write(values))

        for record in (airline, origin, destination, hotel, package, departure):
            with self.subTest(model=record._name, operation="archive"):
                record.write({"active": False})
                self.assertFalse(record.active)

        for record in (
            price,
            flight,
            accommodation,
            departure,
            package,
            airline,
            origin,
            destination,
            hotel,
        ):
            with self.subTest(model=record._name, operation="unlink"):
                self.assertTrue(record.unlink())
