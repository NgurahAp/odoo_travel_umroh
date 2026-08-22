import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2.errors

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tests import BaseCase, tagged
from odoo.tests.common import get_db_name


@tagged(
    "-standard",
    "-at_install",
    "post_install",
    "database_breaking",
    "travel_umroh",
)
class TestTravelQuotaConcurrency(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registry = Registry(get_db_name())
        cls.synthetic_ids = {}
        cls.addClassCleanup(cls._cleanup_synthetic_records)
        suffix = uuid.uuid4().hex[:8]

        with cls.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            product = env["product.product"].create(
                {
                    "name": "Phase 3 Concurrency Product",
                    "type": "service",
                    "invoice_policy": "order",
                    "taxes_id": [Command.clear()],
                }
            )
            package = env["travel.package"].create(
                {
                    "name": "Phase 3 Concurrency Package",
                    "code": f"P3-CONCURRENT-{suffix}",
                    "product_id": product.id,
                    "duration_days": 9,
                }
            )
            departure = env["travel.departure"].create(
                {
                    "package_id": package.id,
                    "departure_date": "2028-03-01",
                    "return_date": "2028-03-10",
                    "quota": 1,
                    "company_id": env.company.id,
                }
            )
            prices = env["travel.departure.price"].create(
                [
                    {
                        "departure_id": departure.id,
                        "room_type": room_type,
                        "price": price,
                    }
                    for room_type, price in (
                        ("quad", 30_000_000),
                        ("triple", 32_000_000),
                        ("double", 35_000_000),
                    )
                ]
            )
            departure.action_open()
            buyers = env["res.partner"].create(
                [{"name": f"Concurrent Buyer {index}"} for index in (1, 2)]
            )
            jamaah_partners = env["res.partner"].create(
                [{"name": f"Concurrent Jamaah {index}"} for index in (1, 2)]
            )
            jamaah = env["travel.jamaah"].create(
                [
                    {
                        "partner_id": partner.id,
                        "nik": f"CONCURRENT-NIK-{suffix}-{index}",
                        "birth_place": "Denpasar",
                        "birth_date": "1995-01-01",
                        "gender": "male",
                        "emergency_contact_name": "Concurrent Emergency",
                        "emergency_contact_phone": "+628120000000",
                    }
                    for index, partner in enumerate(jamaah_partners, 1)
                ]
            )
            orders = env["sale.order"]
            participants = env["travel.booking.participant"]
            for index in range(2):
                order = env["sale.order"].create(
                    {
                        "partner_id": buyers[index].id,
                        "is_travel_booking": True,
                        "departure_id": departure.id,
                    }
                )
                participant = env["travel.booking.participant"].create(
                    {
                        "order_id": order.id,
                        "jamaah_id": jamaah[index].id,
                        "room_type": "quad",
                    }
                )
                order.action_confirm()
                orders |= order
                participants |= participant

            cls.departure_id = departure.id
            cls.order_ids = orders.ids
            cls.synthetic_ids = {
                "travel.booking.participant": participants.ids,
                "sale.order": orders.ids,
                "travel.jamaah": jamaah.ids,
                "res.partner": buyers.ids + jamaah_partners.ids,
                "travel.departure.price": prices.ids,
                "travel.departure": departure.ids,
                "travel.package": package.ids,
                "product.product": product.ids,
            }

    @classmethod
    def _cleanup_synthetic_records(cls):
        if not cls.synthetic_ids:
            return
        with cls.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            orders = env["sale.order"].browse(
                cls.synthetic_ids.get("sale.order", [])
            ).exists()
            if orders:
                orders._action_cancel()
            for model_name in (
                "sale.order",
                "travel.jamaah",
                "travel.departure",
                "travel.package",
                "product.product",
                "res.partner",
            ):
                env[model_name].browse(
                    cls.synthetic_ids.get(model_name, [])
                ).exists().unlink()

    def test_last_seat_can_only_be_reserved_once(self):
        barrier = threading.Barrier(2)

        cursors = [self.registry.cursor(), self.registry.cursor()]
        environments = [
            api.Environment(cr, SUPERUSER_ID, {}) for cr in cursors
        ]

        def reserve(env, order_id):
            order = env["sale.order"].browse(order_id)
            barrier.wait(timeout=5)
            try:
                order._travel_reserve_seats()
            except psycopg2.errors.SerializationFailure:
                env.cr.rollback()
                env.invalidate_all()
                order = env["sale.order"].browse(order_id)
                try:
                    order._travel_reserve_seats()
                except UserError as error:
                    env.cr.commit()
                    return "error", str(error)
                raise
            except UserError as error:
                env.cr.commit()
                return "error", str(error)
            env.cr.commit()
            return "success", ""

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(reserve, env, order_id)
                    for env, order_id in zip(environments, self.order_ids)
                ]
                results = [future.result(timeout=10) for future in futures]
        finally:
            for cr in cursors:
                cr.close()

        successes = [result for result in results if result[0] == "success"]
        errors = [result for result in results if result[0] == "error"]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("tersedia=0", errors[0][1])
        self.assertIn("dibutuhkan=1", errors[0][1])

        with self.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            departure = env["travel.departure"].browse(self.departure_id)
            orders = env["sale.order"].browse(self.order_ids)
            self.assertEqual(departure.reserved_seats, 1)
            self.assertEqual(departure.remaining_seats, 0)
            self.assertTrue(departure.is_full)
            self.assertEqual(len(orders.filtered("seat_reserved")), 1)
