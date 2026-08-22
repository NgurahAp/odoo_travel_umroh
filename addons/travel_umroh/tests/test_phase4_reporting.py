from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseFourReporting(TravelAccountingCase):
    def test_reporting_dimensions_are_stored_without_copying_identity_data(self):
        order_fields = self.env["sale.order"]._fields
        for name in (
            "participant_count",
            "travel_payment_state",
            "travel_state",
        ):
            self.assertTrue(order_fields[name].store, name)

        participant_fields = self.env["travel.booking.participant"]._fields
        for name in (
            "departure_id",
            "travel_package_id",
            "booking_state",
            "travel_payment_state",
            "travel_state",
            "seat_reserved",
            "document_status",
        ):
            self.assertTrue(participant_fields[name].store, name)
            self.assertTrue(participant_fields[name].readonly, name)
        for name in (
            "jamaah_nik",
            "jamaah_phone",
            "jamaah_gender",
            "passport_number",
            "passport_expiry",
        ):
            self.assertFalse(participant_fields[name].store, name)

    def test_reporting_dimensions_aggregate_source_records(self):
        order = self._confirmed_booking("PHASE4-REPORT", participant_count=2)

        order_groups = self.env["sale.order"].with_user(self.staff).read_group(
            [("id", "=", order.id)],
            ["participant_count:sum", "amount_total:sum"],
            ["departure_id", "travel_payment_state"],
            lazy=False,
        )
        self.assertEqual(len(order_groups), 1)
        self.assertEqual(order_groups[0]["__count"], 1)
        self.assertEqual(order_groups[0]["participant_count"], 2)
        self.assertEqual(order_groups[0]["amount_total"], order.amount_total)

        participant_groups = self.env[
            "travel.booking.participant"
        ].with_user(self.staff).read_group(
            [("order_id", "=", order.id)],
            ["id:count"],
            ["departure_id", "document_status"],
            lazy=False,
        )
        self.assertEqual(
            sum(group["__count"] for group in participant_groups),
            2,
        )
