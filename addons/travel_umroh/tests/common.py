from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
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
                "taxes_id": [Command.clear()],
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
        partner = cls.env["res.partner"].sudo().create(
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
        return cls.env["travel.jamaah"].sudo().create(values)


class TravelAccountingCase(AccountTestInvoicingCommon, TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.departure.company_id = cls.env.company
        cls.travel_service_product = cls.package.product_id
        cls.travel_service_product.product_tmpl_id.property_account_income_id = (
            cls.company_data["default_account_revenue"]
        )
        cls.staff = cls._create_role_user("phase3-staff", "group_travel_staff")
        cls.finance = cls._create_role_user(
            "phase3-finance", "group_travel_finance"
        )
        cls.manager = cls._create_role_user(
            "phase3-manager", "group_travel_manager"
        )

    @classmethod
    def _create_role_user(cls, login, group_xmlid):
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set(cls.env.company.ids)],
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(
                                f"travel_umroh.{group_xmlid}"
                            ).id,
                        ]
                    )
                ],
            }
        )

    def _confirmed_booking(self, suffix, participant_count=1):
        order = self.env["sale.order"].with_user(self.staff).create(
            {
                "partner_id": self.buyer.id,
                "user_id": self.staff.id,
                "is_travel_booking": True,
                "departure_id": self.departure.id,
            }
        )
        for index in range(participant_count):
            self.env["travel.booking.participant"].with_user(self.staff).create(
                {
                    "order_id": order.id,
                    "jamaah_id": self._create_jamaah(
                        f"{suffix}-{index}"
                    ).id,
                    "room_type": "quad",
                }
            )
        order.with_user(self.staff).action_confirm()
        return order
