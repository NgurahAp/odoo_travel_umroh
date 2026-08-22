import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseThreeDepartureWorkflow(TravelAccountingCase):
    def _reserve_booking(self, suffix, participant_count=1):
        order = self._confirmed_booking(suffix, participant_count)
        self._post_and_pay(self._create_downpayment_invoice(order))
        return order

    def _verify_documents(self, jamaah):
        jamaah.with_user(self.staff).write(
            {
                "passport_number": f"P3-{jamaah.id}",
                "passport_expiry": "2035-01-01",
                "ktp_file": base64.b64encode(b"phase-3-ktp"),
                "ktp_filename": f"ktp-{jamaah.id}.pdf",
                "passport_file": base64.b64encode(b"phase-3-passport"),
                "passport_filename": f"passport-{jamaah.id}.pdf",
            }
        )
        jamaah.with_user(self.staff).action_submit_documents()
        jamaah.with_user(self.manager).action_verify_documents()

    def _cancel_reserved_booking(self, order):
        (
            self.env["travel.booking.cancel.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "order_id": order.id,
                    "reason": "Tidak ikut keberangkatan",
                }
            )
            .action_confirm_cancel()
        )

    def test_staff_and_finance_cannot_change_departure_lifecycle(self):
        for user in (self.staff, self.finance):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.departure.with_user(user).action_depart()
                with self.assertRaises(AccessError):
                    self.departure.with_user(user).action_done()

    def test_only_open_departure_can_depart(self):
        self.departure.with_user(self.manager).action_cancel()

        with self.assertRaises(UserError):
            self.departure.with_user(self.manager).action_depart()

    def test_unreserved_bookings_do_not_block_departure(self):
        self._confirmed_booking("DEPART-UNRESERVED")

        self.departure.with_user(self.manager).action_depart()

        self.assertEqual(self.departure.state, "departed")

    def test_reserved_unverified_jamaah_blocks_departure_with_names(self):
        order = self._reserve_booking(
            "DEPART-BLOCKED", participant_count=2
        )
        jamaah = order.participant_ids.jamaah_id

        with self.assertRaises(UserError) as error:
            self.departure.with_user(self.manager).action_depart()

        self.assertIn("2", str(error.exception))
        for person in jamaah:
            self.assertIn(person.display_name, str(error.exception))
        self.assertEqual(self.departure.state, "open")

    def test_verified_reserved_jamaah_can_depart_and_finish(self):
        order = self._reserve_booking(
            "DEPART-VERIFIED", participant_count=2
        )
        for jamaah in order.participant_ids.jamaah_id:
            self._verify_documents(jamaah)

        self.departure.with_user(self.manager).action_depart()
        self.assertEqual(self.departure.state, "departed")
        self.departure.with_user(self.manager).action_done()
        self.assertEqual(self.departure.state, "done")

    def test_cancelled_released_booking_does_not_block_departure(self):
        order = self._reserve_booking("DEPART-CANCELLED")
        self._cancel_reserved_booking(order)

        self.departure.with_user(self.manager).action_depart()

        self.assertEqual(self.departure.state, "departed")
        self.assertFalse(order.seat_reserved)

    def test_only_departed_can_be_done_and_direct_write_stays_blocked(self):
        with self.assertRaises(UserError):
            self.departure.with_user(self.manager).action_done()
        with self.assertRaises(UserError):
            self.departure.with_user(self.manager).write(
                {"state": "departed"}
            )

        self.departure.with_user(self.manager).action_depart()
        self.departure.with_user(self.manager).action_done()
        with self.assertRaises(UserError):
            self.departure.with_user(self.manager).action_done()

    def test_booking_travel_state_follows_departure_and_is_readonly(self):
        order = self._confirmed_booking("DEPART-STATE")
        self.assertEqual(order.travel_state, "registered")

        for user in (self.staff, self.finance, self.manager):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                order.with_user(user).write({"travel_state": "departed"})

        self.departure.with_user(self.manager).action_depart()
        order.invalidate_recordset(["travel_state"])
        self.assertEqual(order.travel_state, "departed")

        self.departure.with_user(self.manager).action_done()
        order.invalidate_recordset(["travel_state"])
        self.assertEqual(order.travel_state, "done")
