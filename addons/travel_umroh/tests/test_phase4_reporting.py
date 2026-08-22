from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import TravelAccountingCase


@tagged("post_install", "-at_install")
class TestPhaseFourReporting(TravelAccountingCase):
    def _view_root(self, xmlid):
        return etree.fromstring(self.env.ref(xmlid).arch_db.encode())

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

    def test_booking_reporting_action_is_travel_only_and_analytical(self):
        action = self.env.ref("travel_umroh.action_travel_booking_report")
        self.assertEqual(action.res_model, "sale.order")
        self.assertEqual(action.view_mode, "list,pivot,graph,form")
        self.assertEqual(
            safe_eval(action.domain),
            [("is_travel_booking", "=", True)],
        )

        list_root = self._view_root(
            "travel_umroh.view_travel_booking_report_list"
        )
        self.assertEqual(list_root.get("create"), "0")
        self.assertEqual(list_root.get("edit"), "0")
        self.assertEqual(list_root.get("delete"), "0")
        for name in (
            "name",
            "date_order",
            "partner_id",
            "departure_id",
            "travel_package_id",
            "participant_count",
            "amount_total",
            "travel_payment_state",
            "travel_state",
            "seat_reserved",
            "state",
            "user_id",
        ):
            self.assertTrue(list_root.xpath(f"//field[@name='{name}']"), name)

        pivot = self._view_root(
            "travel_umroh.view_travel_booking_report_pivot"
        )
        for measure in ("amount_total", "participant_count"):
            self.assertTrue(
                pivot.xpath(
                    f"//field[@name='{measure}' and @type='measure']"
                ),
                measure,
            )
        for dimension in (
            "departure_id",
            "travel_package_id",
            "travel_payment_state",
        ):
            self.assertTrue(
                pivot.xpath(f"//field[@name='{dimension}']"),
                dimension,
            )

        search = self._view_root(
            "travel_umroh.view_travel_booking_report_search"
        )
        for filter_name in (
            "quotation",
            "confirmed",
            "cancelled",
            "unpaid",
            "dp",
            "paid",
            "refunded",
            "reserved_only",
            "group_package",
            "group_departure",
            "group_payment",
            "group_sales_state",
            "group_salesperson",
            "group_order_month",
        ):
            self.assertTrue(
                search.xpath(f"//filter[@name='{filter_name}']"),
                filter_name,
            )

    def test_reporting_menus_keep_operational_and_receivable_roles_separate(self):
        staff = self.env.ref("travel_umroh.group_travel_staff")
        finance = self.env.ref("travel_umroh.group_travel_finance")
        manager = self.env.ref("travel_umroh.group_travel_manager")
        system = self.env.ref("base.group_system")

        reporting_menu = self.env.ref("travel_umroh.menu_travel_reporting")
        booking_menu = self.env.ref(
            "travel_umroh.menu_travel_booking_report"
        )
        for menu in (reporting_menu, booking_menu):
            self.assertEqual(
                set(menu.groups_id.ids),
                {staff.id, finance.id, manager.id, system.id},
            )

        receivable_menu = self.env.ref(
            "travel_umroh.menu_travel_receivable_report"
        )
        self.assertEqual(
            set(receivable_menu.groups_id.ids),
            {finance.id, manager.id, system.id},
        )
        self.assertEqual(
            receivable_menu.action,
            self.env.ref("account.action_move_out_invoice_type"),
        )

    def test_capacity_report_uses_stored_departure_measures(self):
        action = self.env.ref("travel_umroh.action_travel_capacity_report")
        self.assertEqual(action.res_model, "travel.departure")
        self.assertEqual(action.view_mode, "list,pivot,graph,form")

        pivot = self._view_root("travel_umroh.view_travel_capacity_pivot")
        for name in ("quota", "reserved_seats", "remaining_seats"):
            self.assertTrue(
                pivot.xpath(f"//field[@name='{name}' and @type='measure']"),
                name,
            )

        order = self._confirmed_booking(
            "PHASE4-CAPACITY",
            participant_count=2,
        )
        self._post_and_pay(self._create_downpayment_invoice(order))
        self.departure.invalidate_recordset(
            ["reserved_seats", "remaining_seats"]
        )

        groups = self.env["travel.departure"].with_user(
            self.staff
        ).read_group(
            [("id", "=", self.departure.id)],
            ["quota:sum", "reserved_seats:sum", "remaining_seats:sum"],
            ["package_id"],
            lazy=False,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["reserved_seats"], 2)
        self.assertEqual(
            groups[0]["remaining_seats"],
            self.departure.quota - 2,
        )

    def test_document_report_groups_jamaah_by_real_status(self):
        action = self.env.ref("travel_umroh.action_travel_document_report")
        self.assertEqual(action.res_model, "travel.jamaah")
        self.assertEqual(action.view_mode, "list,pivot,graph,form")

        jamaah = self._create_jamaah("PHASE4-DOCUMENT")
        grouped = self.env["travel.jamaah"].with_user(self.staff).read_group(
            [("id", "=", jamaah.id)],
            ["id:count"],
            ["document_status"],
            lazy=False,
        )
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["document_status"], "incomplete")
        self.assertEqual(grouped[0]["__count"], 1)

        pivot = self._view_root("travel_umroh.view_travel_document_pivot")
        self.assertTrue(pivot.xpath("//field[@name='document_status']"))
        graph = self._view_root("travel_umroh.view_travel_document_graph")
        self.assertEqual(graph.get("type"), "pie")

    def test_operational_report_menus_are_visible_to_all_travel_roles(self):
        group_ids = {
            self.env.ref("travel_umroh.group_travel_staff").id,
            self.env.ref("travel_umroh.group_travel_finance").id,
            self.env.ref("travel_umroh.group_travel_manager").id,
            self.env.ref("base.group_system").id,
        }
        for xmlid in (
            "travel_umroh.menu_travel_capacity_report",
            "travel_umroh.menu_travel_document_report",
        ):
            self.assertEqual(set(self.env.ref(xmlid).groups_id.ids), group_ids)

    def test_manifest_is_noneditable_and_scoped_to_travel_participants(self):
        action = self.env.ref("travel_umroh.action_travel_manifest")
        self.assertEqual(action.res_model, "travel.booking.participant")
        self.assertEqual(action.view_mode, "list")
        action_domain = safe_eval(action.domain)
        self.assertEqual(
            action_domain,
            [("order_id.is_travel_booking", "=", True)],
        )
        self.assertEqual(
            safe_eval(action.context).get("search_default_active_manifest"),
            1,
        )

        root = self._view_root("travel_umroh.view_travel_manifest_list")
        self.assertEqual(root.get("create"), "0")
        self.assertEqual(root.get("edit"), "0")
        self.assertEqual(root.get("delete"), "0")
        for field_name in (
            "departure_id",
            "travel_package_id",
            "order_id",
            "jamaah_id",
            "jamaah_nik",
            "jamaah_phone",
            "jamaah_gender",
            "room_type",
            "passport_number",
            "passport_expiry",
            "document_status",
            "travel_payment_state",
            "seat_reserved",
        ):
            self.assertTrue(
                root.xpath(f"//field[@name='{field_name}']"),
                field_name,
            )
        self.assertFalse(root.xpath("//field[@name='ktp_file']"))
        self.assertFalse(root.xpath("//field[@name='passport_file']"))

        search = self._view_root("travel_umroh.view_travel_manifest_search")
        for filter_name in (
            "active_manifest",
            "reserved_only",
            "documents_incomplete",
            "documents_pending",
            "documents_verified",
            "group_departure",
            "group_package",
            "group_booking",
            "group_room_type",
            "group_document_status",
            "group_payment_status",
        ):
            self.assertTrue(
                search.xpath(f"//filter[@name='{filter_name}']"),
                filter_name,
            )

    def test_manifest_default_filter_hides_cancelled_but_keeps_history(self):
        active_order = self._confirmed_booking("PHASE4-MANIFEST-ACTIVE")
        cancelled_order = self._confirmed_booking("PHASE4-MANIFEST-CANCEL")
        result = cancelled_order.with_user(self.staff).action_cancel()
        if isinstance(result, dict) and result.get("res_model") == (
            "sale.order.cancel"
        ):
            self.env["sale.order.cancel"].with_user(self.staff).with_context(
                **result["context"]
            ).create({"order_id": cancelled_order.id}).action_cancel()
        cancelled_order.invalidate_recordset(["state"])
        self.assertEqual(cancelled_order.state, "cancel")

        action = self.env.ref("travel_umroh.action_travel_manifest")
        action_domain = safe_eval(action.domain)
        all_participants = self.env[
            "travel.booking.participant"
        ].with_user(self.staff).search(
            action_domain
            + [("order_id", "in", (active_order.id, cancelled_order.id))]
        )
        self.assertEqual(
            set(all_participants.ids),
            set((active_order | cancelled_order).participant_ids.ids),
        )

        search = self._view_root("travel_umroh.view_travel_manifest_search")
        active_domain = safe_eval(
            search.xpath("//filter[@name='active_manifest']")[0].get(
                "domain"
            )
        )
        active_participants = self.env[
            "travel.booking.participant"
        ].with_user(self.staff).search(
            action_domain
            + active_domain
            + [("order_id", "in", (active_order.id, cancelled_order.id))]
        )
        self.assertEqual(
            active_participants.ids,
            active_order.participant_ids.ids,
        )

    def test_manifest_read_access_does_not_grant_mutation(self):
        order = self._confirmed_booking("PHASE4-MANIFEST-SECURITY")
        participant = order.participant_ids.ensure_one()
        for user in (self.staff, self.finance, self.manager):
            self.assertIn(
                participant,
                self.env["travel.booking.participant"]
                .with_user(user)
                .search([("id", "=", participant.id)]),
            )

        with self.assertRaises(AccessError):
            participant.with_user(self.staff).write({"room_type": "triple"})
        with self.assertRaises(AccessError):
            participant.with_user(self.finance).write({"room_type": "triple"})
        with self.assertRaises(AccessError):
            participant.with_user(self.finance).unlink()

        manifest_menu = self.env.ref("travel_umroh.menu_travel_manifest")
        self.assertEqual(
            set(manifest_menu.groups_id.ids),
            {
                self.env.ref("travel_umroh.group_travel_staff").id,
                self.env.ref("travel_umroh.group_travel_finance").id,
                self.env.ref("travel_umroh.group_travel_manager").id,
                self.env.ref("base.group_system").id,
            },
        )
