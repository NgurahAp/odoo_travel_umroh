from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestTravelPackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Umroh Service",
                "type": "service",
                "invoice_policy": "order",
            }
        )

    def _package_values(self, **overrides):
        values = {
            "name": "Umroh Reguler 9 Hari",
            "code": "REG-09",
            "product_id": self.service_product.id,
            "duration_days": 9,
        }
        values.update(overrides)
        return values

    def test_package_accepts_ordered_quantity_service(self):
        package = self.env["travel.package"].create(self._package_values())

        self.assertEqual(package.product_id.type, "service")
        self.assertEqual(package.product_id.invoice_policy, "order")

    def test_package_rejects_non_service_product(self):
        product = self.env["product.product"].create(
            {"name": "Physical Item", "type": "consu"}
        )

        with self.assertRaises(ValidationError):
            self.env["travel.package"].create(
                self._package_values(code="INVALID-TYPE", product_id=product.id)
            )

    def test_package_rejects_service_invoiced_on_delivery(self):
        product = self.env["product.product"].create(
            {
                "name": "Delivered Service",
                "type": "service",
                "invoice_policy": "delivery",
            }
        )

        with self.assertRaises(ValidationError):
            self.env["travel.package"].create(
                self._package_values(code="INVALID-POLICY", product_id=product.id)
            )

    def test_package_rejects_non_positive_duration(self):
        for duration_days in (0, -1):
            with self.subTest(duration_days=duration_days), self.assertRaises(
                ValidationError
            ):
                self.env["travel.package"].create(
                    self._package_values(
                        code=f"DURATION-{duration_days}",
                        duration_days=duration_days,
                    )
                )

    def test_package_normalizes_code_on_create_and_write(self):
        package = self.env["travel.package"].create(
            self._package_values(code=" reg-09 ")
        )

        self.assertEqual(package.code, "REG-09")

        package.write({"code": " ramadan-12 "})

        self.assertEqual(package.code, "RAMADAN-12")

    @mute_logger("odoo.sql_db")
    def test_package_code_is_unique_after_normalization(self):
        self.env["travel.package"].create(self._package_values(code=" UNIQUE "))

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["travel.package"].create(
                self._package_values(name="Package B", code="unique")
            )
