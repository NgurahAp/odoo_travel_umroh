import ast
from pathlib import Path

from odoo.modules.module import get_module_resource
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseFourDemoData(TravelAccountingCase):
    def test_demo_accounting_helper_uses_standard_states_and_is_idempotent(self):
        dp_order = self._confirmed_booking("DEMO-HELPER-DP")
        paid_order = self._confirmed_booking(
            "DEMO-HELPER-PAID", participant_count=2
        )
        demo = self.env["travel.demo"]

        demo._complete_demo_accounting(dp_order, paid_order)
        dp_order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )
        paid_order.invalidate_recordset(
            ["invoice_ids", "invoice_status", "travel_payment_state"]
        )

        self.assertEqual(dp_order.travel_payment_state, "dp")
        self.assertFalse(dp_order.seat_reserved)
        self.assertTrue(
            dp_order.invoice_ids.filtered(
                lambda move: move.state == "posted"
                and move.move_type == "out_invoice"
            )
        )
        self.assertEqual(paid_order.travel_payment_state, "paid")
        self.assertTrue(paid_order.seat_reserved)
        self.assertEqual(paid_order.departure_id.reserved_seats, 2)
        first_invoice_ids = (dp_order | paid_order).invoice_ids.ids
        first_payment_ids = self.env["account.payment"].search(
            [("reconciled_invoice_ids", "in", (dp_order | paid_order).invoice_ids.ids)]
        ).ids

        demo._complete_demo_accounting(dp_order, paid_order)
        (dp_order | paid_order).invalidate_recordset(["invoice_ids"])

        self.assertEqual((dp_order | paid_order).invoice_ids.ids, first_invoice_ids)
        self.assertEqual(
            self.env["account.payment"].search(
                [
                    (
                        "reconciled_invoice_ids",
                        "in",
                        (dp_order | paid_order).invoice_ids.ids,
                    )
                ]
            ).ids,
            first_payment_ids,
        )

    def test_demo_file_is_registered_only_as_demo_and_is_synthetic(self):
        manifest_path = Path(
            get_module_resource("travel_umroh", "__manifest__.py")
        )
        manifest = ast.literal_eval(manifest_path.read_text())
        demo_path = "demo/travel_umroh_demo.xml"

        self.assertIn(demo_path, manifest.get("demo", []))
        self.assertNotIn(demo_path, manifest.get("data", []))

        xml_path = Path(
            get_module_resource("travel_umroh", "demo", "travel_umroh_demo.xml")
        )
        xml_text = xml_path.read_text()
        self.assertIn("DEMO-NIK-01", xml_text)
        self.assertIn("DEMO-PASS-05", xml_text)
        self.assertIn(".example.test", xml_text)
        self.assertNotIn("password", xml_text.lower())
        self.assertLess(
            xml_text.rfind('name="_open_demo_departures"'),
            xml_text.rfind('name="_load_demo_accounting_states"'),
        )
        self.assertGreater(
            xml_text.rfind('name="_load_demo_accounting_states"'), 0
        )
