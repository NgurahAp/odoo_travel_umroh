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
