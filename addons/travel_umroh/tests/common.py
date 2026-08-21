from odoo.tests.common import TransactionCase


class TravelUmrohCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Umroh Service Fixture",
                "type": "service",
                "invoice_policy": "order",
            }
        )
        cls.package = cls.env["travel.package"].create(
            {
                "name": "Umroh Reguler 9 Hari",
                "code": "REG-09",
                "product_id": cls.service_product.id,
                "duration_days": 9,
            }
        )
        cls.company_currency = cls.env.company.currency_id


class TravelBookingCase(TravelUmrohCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.departure = cls.env["travel.departure"].create(
            {
                "package_id": cls.package.id,
                "departure_date": "2027-09-01",
                "return_date": "2027-09-10",
                "quota": 45,
                "company_id": cls.env.company.id,
            }
        )
        for room_type, price in (
            ("quad", 30_000_000),
            ("triple", 32_000_000),
            ("double", 35_000_000),
        ):
            cls.env["travel.departure.price"].create(
                {
                    "departure_id": cls.departure.id,
                    "room_type": room_type,
                    "price": price,
                }
            )
        cls.departure.action_open()
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Synthetic Booking Buyer",
                "email": "buyer@example.test",
            }
        )

    @classmethod
    def _create_jamaah(cls, suffix="001", **overrides):
        partner = cls.env["res.partner"].create(
            {
                "name": f"Synthetic Jamaah {suffix}",
                "phone": f"+62812000{suffix}",
            }
        )
        values = {
            "partner_id": partner.id,
            "nik": f"SYNTH-NIK-{suffix}",
            "birth_place": "Denpasar",
            "birth_date": "1995-01-01",
            "gender": "male",
            "emergency_contact_name": "Synthetic Emergency",
            "emergency_contact_phone": "+628129990000",
        }
        values.update(overrides)
        return cls.env["travel.jamaah"].create(values)
