# Phase 4 Reporting, Demo Data, and Internal Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the internal Travel Umroh back-office presentation-ready with standard Odoo operational reports, a filterable Jamaah manifest, controlled demo-only records, end-to-end acceptance coverage, internal security hardening, and reproducible developer/demo documentation.

**Architecture:** Keep the existing Phase 1-3 business models as the reporting source of truth. Make only the existing computed dimensions that must participate in grouping/aggregation stored, add non-editable standard Odoo list/search/pivot/graph actions over `sale.order`, `travel.departure`, `travel.jamaah`, and `travel.booking.participant`, and do not introduce a reporting ledger or custom dashboard. Demo XML creates synthetic master and transaction shells only when demo data is enabled; one private, non-RPC abstract-model helper completes the two standard Accounting demo states through public Odoo invoice/payment APIs.

**Tech Stack:** Odoo 18 Community, Python ORM, XML list/search/pivot/graph views, manifest demo data, standard `sale_management` and `account` workflows, Odoo `TransactionCase`, `lxml.etree`, Docker Compose, PostgreSQL 15.

**Spec:** `Requirement_Modul_Travel_Umroh.md`, `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md` Sections 8-13, `docs/superpowers/plans/2026-08-20-travel-umroh-roadmap.md` Phase 4, and the actual Phase 3 checkpoint in `docs/superpowers/plans/2026-08-22-phase-3-accounting-quota-cancellation-refund.md`.

## Global Constraints

- Implement roadmap Phase 4 only. Do not add Phase 5 portal routes/templates/rules, WhatsApp, payment gateway, waitlist, room allocation, visa workflow/API, migration, multi-company behavior, mobile features, custom accounting ledgers, or custom OWL/JavaScript dashboards.
- Keep `sale.order` as Booking/Quotation and standard Odoo `account.move`, payment, credit-note, and refund records as accounting truth. Reporting must never copy transaction totals into a custom ledger.
- Use standard Odoo `list`, `search`, `pivot`, and `graph` views. Odoo 18 XML uses `<list>`, never `<tree>`.
- IDR/company currency remains the only supported reporting currency. Do not add cross-currency conversion or multi-company consolidation.
- Reporting actions are read-oriented entry points over existing models. Their XML visibility does not replace the Phase 1-3 ACL, record-rule, and server-method protections.
- Staff, Finance, and Manager may read internal operational reports because all three already read travel transactions/master data. Reporting must not grant new create/write/unlink permissions.
- Store only grouping dimensions and numeric measures required by Odoo pivot/graph. Do not duplicate NIK, passport, phone, attachments, invoice totals, payment residuals, or other sensitive/source-of-truth values into a new table.
- The Manifest is a standard, non-editable participant list filtered/grouped by departure. A printable QWeb/PDF manifest is not required because the technical design says to use the simplest standard view/report.
- Demo data must be synthetic, deterministic, recognizable by `DEMO-` codes/logins/names, and declared under the manifest's `demo` key. A database installed with `--without-demo=all` must receive zero Travel Umroh demo records.
- Demo accounting states must use standard `sale.advance.payment.inv`, `account.move.action_post()`, and `account.payment.register.action_create_payments()`. Do not seed `travel_payment_state`, residuals, `seat_reserved`, or invoice state directly.
- The demo helper must be an `AbstractModel`, expose no menu/ACL, use an underscore-prefixed method, resolve only known demo XML IDs, and be idempotent on module upgrade.
- Preserve Phase 3 reservation, cancellation, refund, verified-document, and concurrency behavior. Phase 4 may harden an identified authorization gap, but may not redesign those workflows.
- Preserve normal System Administrator behavior. Every Manager-only Python guard reviewed in Phase 4 must explicitly accept `env.is_admin()` while still rejecting Staff and Finance.
- All automated data uses synthetic identities and `.example.test` email addresses. No real NIK, passport, phone, credential, or customer record may enter the repository.
- Never drop a database, Docker volume, or development data. If a proposed acceptance database exists, choose the next unused `_02`, `_03`, and so on.
- For every behavior task: add/import the failing test first, run the exact target and record RED for the intended missing behavior, implement the minimum change, rerun the target to GREEN, run the stated regression target, then stage exact paths and create one focused commit.
- Verification-only assertions that deliberately consolidate already-green Phase 1-3 behavior must not be made artificially RED by weakening production code. They still run before documentation/checkpoint completion and must be green.

## Actual Phase 3 Baseline and File Map

Verify these facts again before editing:

- `main` and `origin/main` point to `13a8d41`; the Phase 3 module version is `18.0.3.0.0`.
- The latest standard module suite is 169 post-install test methods / 201 Odoo test stats, 0 failed, 0 errors. `database_breaking` concurrency remains a separate 1-method / 3-stat test.
- `sale.order.travel_package_id` is already a stored related field, but `participant_count`, `travel_payment_state`, and `travel_state` are non-stored and therefore cannot be reliable pivot measures/grouping dimensions.
- `travel.departure.reserved_seats`, `remaining_seats`, and `is_full` are already stored computed fields and are suitable for capacity pivot/graph measures.
- `travel.jamaah.document_status` is stored and already has list/search views.
- `travel.booking.participant` has no stored `departure_id`, package, payment, booking-state, or document-status reporting dimensions; its form is currently embedded only inside Booking.
- The current Booking action is `list,form` with no dedicated search/pivot/graph views. The root menu has no Reporting submenu.
- `README.md` currently contains only the repository title.
- Manager-only departure/cancellation checks already accept System Administrator, but verified Jamaah, verified partner/attachment, and post-confirmation participant checks contain direct `has_group(group_travel_manager)` checks that can reject System Administrator. Phase 4 hardening must close this actual gap without broadening Staff/Finance.
- Existing report source records are protected by Phase 1-3 ACLs/record rules. No new persistent reporting model or ACL row is planned.

## Planned File Structure

**Create:**

- `addons/travel_umroh/views/travel_reporting_booking_views.xml` — Booking/sales list, search, pivot, graph, and report action.
- `addons/travel_umroh/views/travel_reporting_operations_views.xml` — Capacity and document-status pivots/graphs/actions.
- `addons/travel_umroh/views/travel_manifest_views.xml` — Non-editable participant Manifest list/search/action.
- `addons/travel_umroh/models/travel_demo.py` — private demo departure-opening and Accounting completion helpers only.
- `addons/travel_umroh/models/travel_security.py` — shared Manager-or-System-Administrator predicate for internal server guards.
- `addons/travel_umroh/demo/travel_umroh_demo.xml` — synthetic demo masters, Jamaah, departures, and bookings.
- `addons/travel_umroh/tests/test_phase4_reporting.py` — stored dimensions, aggregates, view/action/menu, and report security.
- `addons/travel_umroh/tests/test_phase4_demo.py` — demo accounting helper and manifest placement contract.
- `addons/travel_umroh/tests/test_phase4_hardening.py` — System Administrator and role-boundary regression.
- `addons/travel_umroh/tests/test_phase4_acceptance.py` — one consolidated internal end-to-end acceptance flow.
- `docs/phase4-demo-flow.md` — role-by-role stakeholder demo and expected checkpoints.

**Modify:**

- `addons/travel_umroh/__manifest__.py` — version `18.0.4.0.0`, report view data, and demo file registration.
- `addons/travel_umroh/models/__init__.py` — import `travel_demo`.
- `addons/travel_umroh/models/sale_order.py` — stored reporting fields and admin helper semantics only.
- `addons/travel_umroh/models/travel_booking_participant.py` — reporting dimensions and non-stored related display fields.
- `addons/travel_umroh/models/travel_jamaah.py` — System Administrator compatibility in verified-profile workflows.
- `addons/travel_umroh/models/res_partner.py` — System Administrator business-correction compatibility while retaining the technical `signup_type` exception.
- `addons/travel_umroh/models/ir_attachment.py` — System Administrator compatibility for verified documents.
- `addons/travel_umroh/tests/__init__.py` — import Phase 4 test modules.
- `addons/travel_umroh/tests/common.py` — only reusable Phase 4 reporting/demo fixture helpers that are actually shared.
- `addons/travel_umroh/views/travel_menus.xml` — Reporting parent, four Travel report entries, and one Finance/Manager link to Odoo's standard customer-invoice action.
- `README.md` — developer setup, install/upgrade/test, roles, database safety, and documentation links.
- Phase 1-3 source/test files only if a RED Phase 4 hardening/acceptance test proves an in-scope defect.

## Verification Database Convention

Use three dedicated databases and never delete/recreate them:

- `travel_umroh_phase4_test`: persistent implementation/upgrades with demo disabled.
- `travel_umroh_phase4_acceptance`: first unused no-demo clean install.
- `travel_umroh_phase4_demo`: first unused demo-enabled clean install.

Check names before use:

```bash
docker compose exec -T db psql -U odoo -d postgres -Atc \
  "SELECT datname FROM pg_database WHERE datname LIKE 'travel_umroh_phase4%';"
```

Expected: only previously created databases are listed. Choose unused suffixes instead of dropping anything.

---

## Task 1: Make Existing Booking and Participant Dimensions Reportable

**Purpose:** Supply Odoo pivot/graph with stored grouping dimensions and measures without introducing a report ledger or duplicating sensitive identity data.

**Files:**

- Modify: `addons/travel_umroh/__manifest__.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/travel_booking_participant.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Create: `addons/travel_umroh/tests/test_phase4_reporting.py`

**Interfaces:**

- Consumes: existing `sale.order.departure_id`, stored `travel_package_id`, `participant_ids`, computed payment/travel state, participant `order_id`, and `jamaah_id`.
- Produces on `sale.order`: stored `participant_count: Integer`, stored `travel_payment_state: Selection`, and stored `travel_state: Selection` with their existing values and compute methods unchanged.
- Produces on `travel.booking.participant`: stored/read-only `departure_id`, `travel_package_id`, `booking_state`, `travel_payment_state`, `travel_state`, `seat_reserved`, and `document_status`; non-stored/read-only display relations `jamaah_nik`, `jamaah_phone`, `jamaah_gender`, `passport_number`, and `passport_expiry`.

- [ ] **Step 1: Import the Phase 4 reporting test and write RED field-contract tests**

Create `TestPhaseFourReporting(TravelAccountingCase)` tagged `post_install`, `-at_install`. Assert the groupable fields exist and are stored while identity display fields are not stored:

```python
def test_reporting_dimensions_are_stored_without_copying_identity_data(self):
    order_fields = self.env["sale.order"]._fields
    for name in ("participant_count", "travel_payment_state", "travel_state"):
        self.assertTrue(order_fields[name].store, name)

    participant_fields = self.env["travel.booking.participant"]._fields
    for name in (
        "departure_id", "travel_package_id", "booking_state",
        "travel_payment_state", "travel_state", "seat_reserved",
        "document_status",
    ):
        self.assertTrue(participant_fields[name].store, name)
        self.assertTrue(participant_fields[name].readonly, name)
    for name in (
        "jamaah_nik", "jamaah_phone", "jamaah_gender",
        "passport_number", "passport_expiry",
    ):
        self.assertFalse(participant_fields[name].store, name)
```

Add a second test that creates one confirmed two-participant booking, calls `read_group()` by `departure_id` and `travel_payment_state`, and expects count `1`, `participant_count == 2`, and `amount_total` equal to the booking total. Add participant `read_group()` by `departure_id`/`document_status` and expect two participant rows.

- [ ] **Step 2: Run RED reporting-dimension test**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test \
  -u travel_umroh \
  --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting.test_reporting_dimensions_are_stored_without_copying_identity_data \
  --log-level=test
```

Expected RED: `sale.order` reporting fields report `store=False` and participant reporting fields do not exist. Fixtures must load successfully; the failure must not come from accounting configuration.

- [ ] **Step 3: Store only required order dimensions/measures**

Change the existing fields, without changing selections/compute bodies:

```python
participant_count = fields.Integer(
    string="Jumlah Participant",
    compute="_compute_participant_count",
    store=True,
)
travel_payment_state = fields.Selection(
    [
        ("unpaid", "Belum Bayar"),
        ("dp", "DP / Bayar Sebagian"),
        ("paid", "Lunas"),
        ("refunded", "Refunded"),
    ],
    string="Status Pembayaran Travel",
    compute="_compute_travel_payment_state",
    store=True,
    readonly=True,
)
travel_state = fields.Selection(
    [
        ("registered", "Terdaftar"),
        ("departed", "Berangkat"),
        ("done", "Selesai"),
    ],
    string="Status Perjalanan",
    compute="_compute_travel_state",
    store=True,
    readonly=True,
)
```

Retain the existing `@api.depends` lists. Do not make role-dependent `can_*` helpers or `travel_requires_manager_cancel` stored.

- [ ] **Step 4: Add participant reporting relations**

Add these fields to `travel.booking.participant`:

```python
departure_id = fields.Many2one(
    "travel.departure", related="order_id.departure_id",
    string="Keberangkatan", store=True, readonly=True,
)
travel_package_id = fields.Many2one(
    "travel.package", related="order_id.travel_package_id",
    string="Paket", store=True, readonly=True,
)
booking_state = fields.Selection(
    related="order_id.state", string="Status Booking",
    store=True, readonly=True,
)
travel_payment_state = fields.Selection(
    related="order_id.travel_payment_state", string="Status Pembayaran",
    store=True, readonly=True,
)
travel_state = fields.Selection(
    related="order_id.travel_state", string="Status Perjalanan",
    store=True, readonly=True,
)
seat_reserved = fields.Boolean(
    related="order_id.seat_reserved", string="Kursi Direservasi",
    store=True, readonly=True,
)
document_status = fields.Selection(
    related="jamaah_id.document_status", string="Status Dokumen",
    store=True, readonly=True,
)
jamaah_nik = fields.Char(
    related="jamaah_id.nik", string="NIK", readonly=True,
)
jamaah_phone = fields.Char(
    related="jamaah_id.phone", string="Telepon", readonly=True,
)
jamaah_gender = fields.Selection(
    related="jamaah_id.gender", string="Jenis Kelamin", readonly=True,
)
passport_number = fields.Char(
    related="jamaah_id.passport_number", string="Nomor Paspor", readonly=True,
)
passport_expiry = fields.Date(
    related="jamaah_id.passport_expiry", string="Masa Berlaku Paspor",
    readonly=True,
)
```

Do not add inverse methods and do not add these fields to participant mutation/audit logic; they are derived reporting/display fields.

- [ ] **Step 5: Bump Phase version and run GREEN plus accounting regression**

Set manifest version to `18.0.4.0.0`, import `test_phase4_reporting`, then run:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test \
  -u travel_umroh \
  --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting,/travel_umroh:TestTravelPaymentState,/travel_umroh:TestTravelQuota \
  --log-level=test
```

Expected GREEN: stored fields recompute existing records during upgrade, read-group totals match source records, and Phase 3 payment/quota results remain unchanged.

- [ ] **Step 6: Checkpoint and focused commit**

```bash
git diff --check
git add addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/travel_booking_participant.py \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/tests/test_phase4_reporting.py
git commit -m "feat: add travel reporting dimensions"
```

Checkpoint: reportable dimensions exist and aggregate correctly; no Reporting menu/view exists until Tasks 2-4.

---

## Task 2: Add Booking and Sales Operational Reporting

**Purpose:** Provide Booking per departure, payment status, and sales per package/departure through one read-only standard list/pivot/graph action.

**Files:**

- Create: `addons/travel_umroh/views/travel_reporting_booking_views.xml`
- Modify: `addons/travel_umroh/views/travel_menus.xml`
- Modify: `addons/travel_umroh/__manifest__.py`
- Modify: `addons/travel_umroh/tests/test_phase4_reporting.py`

**Interfaces:**

- Consumes: Task 1 stored `sale.order.participant_count`, `travel_payment_state`, `travel_state`, `travel_package_id`; existing `departure_id`, `amount_total`, `state`, `seat_reserved`, `date_order`, `partner_id`, and `user_id`.
- Produces XML IDs: `view_travel_booking_report_list`, `view_travel_booking_report_search`, `view_travel_booking_report_pivot`, `view_travel_booking_report_graph`, `action_travel_booking_report`, `menu_travel_reporting`, `menu_travel_booking_report`, and `menu_travel_receivable_report`.
- Reuses verified standard action `account.action_move_out_invoice_type` for outstanding customer invoices; no duplicate receivable model/action is created.

- [ ] **Step 1: Write RED view/action/menu contract tests**

Extend `TestPhaseFourReporting`:

```python
def test_booking_reporting_action_is_travel_only_and_analytical(self):
    action = self.env.ref("travel_umroh.action_travel_booking_report")
    self.assertEqual(action.res_model, "sale.order")
    self.assertEqual(action.view_mode, "list,pivot,graph,form")
    self.assertIn("('is_travel_booking', '=', True)", action.domain)

    pivot = etree.fromstring(
        self.env.ref("travel_umroh.view_travel_booking_report_pivot")
        .arch_db.encode()
    )
    for measure in ("amount_total", "participant_count"):
        self.assertTrue(pivot.xpath(f"//field[@name='{measure}' and @type='measure']"))
    for dimension in (
        "departure_id", "travel_package_id", "travel_payment_state"
    ):
        self.assertTrue(pivot.xpath(f"//field[@name='{dimension}']"))
```

Also assert the list has `create="0"`, `edit="0"`, `delete="0"`; the search view has named filters for draft/confirmed/cancelled, unpaid/DP/paid/refunded, reserved, package, departure, payment, Sales state, salesperson, and order month; and the Booking report menu is restricted to all three Travel groups. Resolve `account.action_move_out_invoice_type`, assert `menu_travel_receivable_report.action` points to it, and assert that menu is restricted to Finance and Manager (Staff must not receive Accounting invoice access through Reporting).

- [ ] **Step 2: Run RED Booking report target**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting.test_booking_reporting_action_is_travel_only_and_analytical \
  --log-level=test
```

Expected RED: external ID `travel_umroh.action_travel_booking_report` is missing.

- [ ] **Step 3: Create the dedicated Booking reporting views**

Create `travel_reporting_booking_views.xml` with:

- `view_travel_booking_report_list`: non-editable columns `name`, `date_order`, `partner_id`, `departure_id`, `travel_package_id`, `participant_count`, `amount_total`, `currency_id`, `travel_payment_state`, `travel_state`, `seat_reserved`, `state`, and `user_id`;
- `view_travel_booking_report_search`: searchable Booking/customer/departure/package/staff plus the exact named filters tested in Step 1;
- `view_travel_booking_report_pivot`: rows `travel_package_id`, `departure_id`, `travel_payment_state`; column `date_order:month`; measures `amount_total` and `participant_count`;
- `view_travel_booking_report_graph`: bar graph grouped by `departure_id` with `amount_total` measure;
- `action_travel_booking_report`: `res_model="sale.order"`, fixed domain `[('is_travel_booking', '=', True)]`, `view_mode="list,pivot,graph,form"`, explicit view bindings in that order, and search view `view_travel_booking_report_search`.

Do not reuse the ordinary Sales quotation list as the reporting list and do not alter `action_travel_booking`.

- [ ] **Step 4: Register data and Reporting menu**

Load `travel_reporting_booking_views.xml` after booking/departure business views and before `travel_menus.xml`. Add:

```xml
<menuitem id="menu_travel_reporting" name="Laporan"
          parent="menu_travel_root" sequence="80"
          groups="travel_umroh.group_travel_staff,travel_umroh.group_travel_finance,travel_umroh.group_travel_manager"/>
<menuitem id="menu_travel_booking_report" name="Booking &amp; Penjualan"
          parent="menu_travel_reporting" action="action_travel_booking_report"
          sequence="10"
          groups="travel_umroh.group_travel_staff,travel_umroh.group_travel_finance,travel_umroh.group_travel_manager"/>
<menuitem id="menu_travel_receivable_report" name="Sisa Tagihan"
          parent="menu_travel_reporting" action="account.action_move_out_invoice_type"
          sequence="50"
          groups="travel_umroh.group_travel_finance,travel_umroh.group_travel_manager"/>
```

`Sisa Tagihan` deliberately opens the standard customer-invoice list/report so residual, payment state, credit notes, and reconciliation remain owned by Accounting. Do not create a copied residual field or a custom receivable action. Staff validates payment status in `Booking & Penjualan`; Finance/Manager validate residuals in `Sisa Tagihan`.

- [ ] **Step 5: Run GREEN view and role-access regression**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting,/travel_umroh:TestPhaseThreeViews,/travel_umroh:TestTravelPhaseTwoViews \
  --log-level=test
```

Expected GREEN: the report is travel-only, non-editable, visible to all three Travel roles, uses stored measures/dimensions, and ordinary Sales/Booking views remain unchanged.

- [ ] **Step 6: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/views/travel_reporting_booking_views.xml \
  addons/travel_umroh/views/travel_menus.xml \
  addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/tests/test_phase4_reporting.py
git commit -m "feat: add travel booking sales reports"
```

Checkpoint: Booking/payment/sales analysis exists; capacity, documents, and manifest follow separately.

---

## Task 3: Add Capacity and Document-status Operational Reports

**Purpose:** Expose departure quota usage and Jamaah document readiness through standard Odoo analytical views.

**Files:**

- Create: `addons/travel_umroh/views/travel_reporting_operations_views.xml`
- Modify: `addons/travel_umroh/views/travel_menus.xml`
- Modify: `addons/travel_umroh/__manifest__.py`
- Modify: `addons/travel_umroh/tests/test_phase4_reporting.py`

**Interfaces:**

- Consumes: stored `travel.departure.quota`, `reserved_seats`, `remaining_seats`, `is_full`, `state`, `package_id`, `departure_date`; stored `travel.jamaah.document_status`, `gender`, `verified_by`, and existing Jamaah search/list.
- Produces XML IDs: `view_travel_capacity_pivot`, `view_travel_capacity_graph`, `action_travel_capacity_report`, `view_travel_document_pivot`, `view_travel_document_graph`, `action_travel_document_report`, `menu_travel_capacity_report`, and `menu_travel_document_report`.

- [ ] **Step 1: Write RED capacity/document report tests**

Add tests which resolve both actions, verify models/view modes, parse all views, and exercise the actual measures:

```python
def test_capacity_report_uses_stored_departure_measures(self):
    action = self.env.ref("travel_umroh.action_travel_capacity_report")
    self.assertEqual(action.res_model, "travel.departure")
    self.assertEqual(action.view_mode, "list,pivot,graph,form")
    pivot = etree.fromstring(
        self.env.ref("travel_umroh.view_travel_capacity_pivot").arch_db.encode()
    )
    for name in ("quota", "reserved_seats", "remaining_seats"):
        self.assertTrue(pivot.xpath(f"//field[@name='{name}' and @type='measure']"))

def test_document_report_groups_jamaah_by_real_status(self):
    action = self.env.ref("travel_umroh.action_travel_document_report")
    self.assertEqual(action.res_model, "travel.jamaah")
    self.assertEqual(action.view_mode, "list,pivot,graph,form")
    grouped = self.env["travel.jamaah"].read_group(
        [], ["id:count"], ["document_status"], lazy=False
    )
    self.assertTrue(any(row["document_status"] == "incomplete" for row in grouped))
```

Add an integration assertion: after fully paying a two-participant DP, departure `read_group()` returns `reserved_seats == 2` and `remaining_seats == quota - 2`. The report must reflect existing computed capacity rather than calculating a second usage definition.

- [ ] **Step 2: Run RED operations-report tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting.test_capacity_report_uses_stored_departure_measures,/travel_umroh:TestPhaseFourReporting.test_document_report_groups_jamaah_by_real_status \
  --log-level=test
```

Expected RED: the new action/view external IDs are absent.

- [ ] **Step 3: Implement capacity list/pivot/graph action**

In `travel_reporting_operations_views.xml` define:

- `view_travel_capacity_pivot`: rows `package_id`, `state`; column `departure_date:month`; measures `quota`, `reserved_seats`, `remaining_seats`;
- `view_travel_capacity_graph`: stacked bar by `name` with `reserved_seats` and `remaining_seats` measures;
- `action_travel_capacity_report`: `travel.departure`, `list,pivot,graph,form`, existing `view_travel_departure_list` and `view_travel_departure_search` plus the new analytical views.

Do not sum `booking_count` as a seat measure. Do not recompute quota from bookings in a report model.

- [ ] **Step 4: Implement document-status list/pivot/graph action**

In the same file define:

- `view_travel_document_pivot`: row `document_status`, column `gender`, implicit record count only;
- `view_travel_document_graph`: pie graph grouped by `document_status`, implicit record count;
- `action_travel_document_report`: `travel.jamaah`, `list,pivot,graph,form`, existing Jamaah list/search/form plus the new analytical views.

The action must not expose binary `ktp_file`/`passport_file` in pivot/graph and must not use `sudo()`.

- [ ] **Step 5: Register actions and report menus**

Load the XML before menus and add under `menu_travel_reporting`:

```xml
<menuitem id="menu_travel_capacity_report" name="Kapasitas Keberangkatan"
          parent="menu_travel_reporting" action="action_travel_capacity_report"
          sequence="20"
          groups="travel_umroh.group_travel_staff,travel_umroh.group_travel_finance,travel_umroh.group_travel_manager"/>
<menuitem id="menu_travel_document_report" name="Status Dokumen"
          parent="menu_travel_reporting" action="action_travel_document_report"
          sequence="30"
          groups="travel_umroh.group_travel_staff,travel_umroh.group_travel_finance,travel_umroh.group_travel_manager"/>
```

- [ ] **Step 6: Run GREEN operations and quota/document regression**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting,/travel_umroh:TestTravelQuota,/travel_umroh:TestTravelJamaah \
  --log-level=test
```

Expected GREEN: capacity reports match reserved-seat source fields after payment, document reports match actual Jamaah workflow status, and no business workflow changes.

- [ ] **Step 7: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/views/travel_reporting_operations_views.xml \
  addons/travel_umroh/views/travel_menus.xml \
  addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/tests/test_phase4_reporting.py
git commit -m "feat: add travel operational reports"
```

Checkpoint: Booking sales, quota usage, and document readiness are visible through standard analytical views.

---

## Task 4: Add the Standard Jamaah Manifest

**Purpose:** Give operations a simple, filterable, exportable participant manifest per departure without adding a printable report engine.

**Files:**

- Create: `addons/travel_umroh/views/travel_manifest_views.xml`
- Modify: `addons/travel_umroh/views/travel_menus.xml`
- Modify: `addons/travel_umroh/__manifest__.py`
- Modify: `addons/travel_umroh/tests/test_phase4_reporting.py`

**Interfaces:**

- Consumes: Task 1 participant report fields plus existing `order_id`, `jamaah_id`, `room_type`, `unit_price`, and `currency_id`.
- Produces XML IDs: `view_travel_manifest_list`, `view_travel_manifest_search`, `action_travel_manifest`, and `menu_travel_manifest`.

- [ ] **Step 1: Write RED manifest scope, field, and security tests**

Add:

```python
def test_manifest_is_noneditable_and_scoped_to_travel_participants(self):
    action = self.env.ref("travel_umroh.action_travel_manifest")
    self.assertEqual(action.res_model, "travel.booking.participant")
    self.assertEqual(action.view_mode, "list")
    self.assertIn("('order_id.is_travel_booking', '=', True)", action.domain)
    root = etree.fromstring(
        self.env.ref("travel_umroh.view_travel_manifest_list").arch_db.encode()
    )
    self.assertEqual(root.get("create"), "0")
    self.assertEqual(root.get("edit"), "0")
    self.assertEqual(root.get("delete"), "0")
    for field_name in (
        "departure_id", "travel_package_id", "order_id", "jamaah_id",
        "jamaah_nik", "jamaah_phone", "jamaah_gender", "room_type",
        "passport_number", "passport_expiry", "document_status",
        "travel_payment_state", "seat_reserved",
    ):
        self.assertTrue(root.xpath(f"//field[@name='{field_name}']"), field_name)
```

Create a cancelled participant and an active confirmed participant. Prove the fixed action domain includes only travel participants, while a named default search filter `active_manifest` excludes cancelled bookings and a named `reserved_only` filter can restrict to reserved seats. Do not hard-code cancellation into the action domain because users must be able to inspect history by clearing the default filter.

For each of Staff, Finance, and Manager, call `search()` through `with_user()` and assert the active participant is readable. Then reassert Finance cannot write/unlink the participant and Staff cannot edit it after confirmation.

- [ ] **Step 2: Run RED manifest target**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting.test_manifest_is_noneditable_and_scoped_to_travel_participants \
  --log-level=test
```

Expected RED: external ID `action_travel_manifest` is missing.

- [ ] **Step 3: Implement the non-editable Manifest list**

Create `view_travel_manifest_list` with `create="0" edit="0" delete="0"`, default order by departure/booking/Jamaah, and the exact columns tested in Step 1. Mark `jamaah_nik`, phone, gender, passport, and expiry `optional="show"`; keep price/currency optional and do not show attachments.

- [ ] **Step 4: Implement the Manifest search/action/menu**

The search view must include searchable `departure_id`, `travel_package_id`, `order_id`, `jamaah_id`, `jamaah_nik`, and `passport_number`; filters:

- `active_manifest`: `[('booking_state', '!=', 'cancel')]`;
- `reserved_only`: `[('seat_reserved', '=', True)]`;
- `documents_incomplete`, `documents_pending`, `documents_verified`;
- group by departure, package, booking, room type, document status, and payment status. Keep gender as a visible/searchable non-stored related value; do not group by it because Odoo analytical grouping requires a stored field and Phase 4 intentionally avoids duplicating identity attributes.

Define `action_travel_manifest` with fixed domain `[('order_id.is_travel_booking', '=', True)]`, `view_mode="list"`, explicit Manifest list/search views, and context `{'search_default_active_manifest': 1}`. Add `menu_travel_manifest` sequence 40 under Reporting with the same explicit Staff, Finance, and Manager groups as the other operational reports.

- [ ] **Step 5: Run GREEN manifest/report/security tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting,/travel_umroh:TestTravelBookingSecurity,/travel_umroh:TestPhaseThreeAccountingSecurity \
  --log-level=test
```

Expected GREEN: operations can filter/group/export the list by departure, default view excludes cancelled bookings, historical records remain discoverable, and report UI grants no mutation authority.

- [ ] **Step 6: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/views/travel_manifest_views.xml \
  addons/travel_umroh/views/travel_menus.xml \
  addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/tests/test_phase4_reporting.py
git commit -m "feat: add travel jamaah manifest"
```

Checkpoint: all reporting items in technical design Section 9 are covered without custom JavaScript or printable QWeb scope.

---

## Task 5: Add Controlled Demo-only Master and Transaction Data

**Purpose:** Load a deterministic presentation dataset only when Odoo demo data is enabled, including Draft, DP, and Paid Booking states produced through standard workflows.

**Files:**

- Create: `addons/travel_umroh/models/travel_demo.py`
- Create: `addons/travel_umroh/demo/travel_umroh_demo.xml`
- Create: `addons/travel_umroh/tests/test_phase4_demo.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/__manifest__.py`

**Interfaces:**

- Consumes: existing public package/departure/participant/Sales methods and standard Phase 3 Accounting helpers through the production Odoo models.
- Produces abstract model `travel.demo` with private methods `_open_demo_departures()`, `_load_demo_accounting_states()`, `_complete_demo_accounting(dp_order, paid_order)`, `_create_demo_downpayment(order, percentage)`, `_create_demo_final_invoice(order)`, and `_pay_demo_invoice(invoice)`.
- Produces stable XML IDs with prefix `demo_`: three airlines, four airports, two hotels, one service product/package, two open departures, six prices, flight/accommodation legs, five Jamaah, three buyers, and three bookings named by customer reference `DEMO-DRAFT`, `DEMO-DP`, and `DEMO-PAID`.

- [ ] **Step 1: Write RED demo workflow and idempotency tests**

Create `TestPhaseFourDemoData(TravelAccountingCase)` and build three synthetic bookings through existing test fixtures. Leave one Draft; pass a confirmed-ready DP order and Paid order to the missing helper:

```python
def test_demo_accounting_helper_uses_standard_states_and_is_idempotent(self):
    dp_order = self._confirmed_booking("DEMO-HELPER-DP")
    paid_order = self._confirmed_booking("DEMO-HELPER-PAID", participant_count=2)
    demo = self.env["travel.demo"]

    demo._complete_demo_accounting(dp_order, paid_order)
    dp_order.invalidate_recordset(["invoice_ids", "travel_payment_state"])
    paid_order.invalidate_recordset(["invoice_ids", "travel_payment_state"])

    self.assertEqual(dp_order.travel_payment_state, "dp")
    self.assertFalse(dp_order.seat_reserved)
    self.assertTrue(dp_order.invoice_ids.filtered(
        lambda move: move.state == "posted" and move.move_type == "out_invoice"
    ))
    self.assertEqual(paid_order.travel_payment_state, "paid")
    self.assertTrue(paid_order.seat_reserved)
    self.assertEqual(paid_order.departure_id.reserved_seats, 2)
    first_invoice_ids = (dp_order | paid_order).invoice_ids.ids

    demo._complete_demo_accounting(dp_order, paid_order)
    self.assertEqual((dp_order | paid_order).invoice_ids.ids, first_invoice_ids)
```

Add a static manifest/data contract test using `odoo.modules.module.get_module_resource()` and `ast.literal_eval()` for `__manifest__.py`: `demo/travel_umroh_demo.xml` must appear only under `demo`, never under `data`; all names/NIK/passport/email values in the XML must contain recognizable synthetic `DEMO`/`.example.test` values; the XML must end by calling `_load_demo_accounting_states`.

- [ ] **Step 2: Run RED demo target**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourDemoData \
  --log-level=test
```

Expected RED: model `travel.demo` and manifest `demo` entry are absent. The failure must not be an Accounting fixture error.

- [ ] **Step 3: Implement a private, idempotent demo Accounting helper**

Create an `AbstractModel`:

```python
class TravelDemo(models.AbstractModel):
    _name = "travel.demo"
    _description = "Travel Umroh Demo Data Loader"

    @api.model
    def _open_demo_departures(self):
        for xmlid in (
            "travel_umroh.demo_departure_reg_01",
            "travel_umroh.demo_departure_reg_02",
        ):
            departure = self.env.ref(xmlid)
            if departure.state == "draft":
                departure.action_open()
        return True

    @api.model
    def _load_demo_accounting_states(self):
        return self._complete_demo_accounting(
            self.env.ref("travel_umroh.demo_booking_dp"),
            self.env.ref("travel_umroh.demo_booking_paid"),
        )
```

`_complete_demo_accounting(dp_order, paid_order)` must:

1. ensure both are Travel bookings with different IDs;
2. confirm each only if still `draft`/`sent`;
3. if the DP order has no invoices, create a 20% standard down-payment invoice and post it, but do not register payment;
4. if the DP order already has invoices, require it to be a valid `dp` demo state and create nothing;
5. if the Paid order has no invoices, create/post/pay a 20% DP, create the standard delivered/final invoice with deducted down payments, then post/pay it;
6. if the Paid order already has invoices, require `travel_payment_state == "paid"` and create nothing;
7. return `True` and never write computed state, residual, reservation, or Sales state directly.

The invoice helpers must search the order company's Sales and Bank journals, raise an Indonesian `UserError` naming the missing journal/accounting prerequisite, and call the same public APIs used by `TravelAccountingCase`. If the demo product lacks an income account, select one company income account and assign it only to the demo product template before creating invoices. Do not alter non-demo products or company-wide defaults.

Import `travel_demo` from `models/__init__.py`. Add no ACL/menu because it is an underscore-only abstract helper.

- [ ] **Step 4: Create exact synthetic demo XML**

Create `demo/travel_umroh_demo.xml` in dependency-safe order:

1. airlines `DEMO Saudia`, `DEMO Garuda`, `DEMO Emirates`;
2. airports `DEMO Jakarta/CGK`, `DEMO Jeddah/JED`, `DEMO Madinah/MED`, `DEMO Dubai/DXB` using real `res.country` references but synthetic names;
3. hotels `DEMO Makkah Hotel` and `DEMO Madinah Hotel`;
4. tax-free service product `DEMO Umroh Service` with ordered-quantity invoice policy;
5. package code `DEMO-REG-09` (`duration_days=9`) and departure XML IDs `demo_departure_reg_01` for 10-18 February 2030 with quota 20 and `demo_departure_reg_02` for 5-13 September 2030 with quota 25; let the existing computed `travel.departure.name` generate each display name;
6. Quad/Triple/Double prices of IDR 30,000,000/33,000,000/36,000,000 for departure 01 and IDR 32,000,000/35,000,000/38,000,000 for departure 02;
7. CGK-JED outbound and MED-CGK return legs plus one Makkah and one Madinah accommodation inside each departure's exact date range;
8. after all required prices/accommodations exist, call the idempotent private helper exactly as `<function model="travel.demo" name="_open_demo_departures"/>`; the helper resolves both known demo XML IDs and calls public `action_open()` only while each departure is Draft;
9. buyer contacts `DEMO Buyer Draft`, `DEMO Buyer DP`, and `DEMO Buyer Paid` with matching `.example.test` emails; five separate Jamaah partner contacts plus `travel.jamaah` profiles `DEMO Jamaah 01` through `DEMO Jamaah 05` with unique `DEMO-NIK-01` through `DEMO-NIK-05`, `DEMO-PASS-01` through `DEMO-PASS-05`, synthetic emergency contacts, and no binary identity documents;
10. three Draft Travel `sale.order` records using `client_order_ref` `DEMO-DRAFT`, `DEMO-DP`, `DEMO-PAID`; assign Jamaah 01 to Draft and Jamaah 02 to DP on departure 01, assign Jamaah 03 Quad plus Jamaah 04 Triple to Paid on departure 02, and leave Jamaah 05 unbooked as a document-status reporting sample;
11. call `travel.demo._load_demo_accounting_states()` as the final XML operation.

Use only XML IDs from this module/standard modules. Do not create internal users/passwords, payments by raw XML, or hard-code database numeric IDs.

- [ ] **Step 5: Register demo and run GREEN helper/manifest tests**

Add only:

```python
"demo": ["demo/travel_umroh_demo.xml"],
```

Do not add the file to `data`. Then run:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourDemoData,/travel_umroh:TestTravelPaymentState,/travel_umroh:TestTravelQuota \
  --log-level=test
```

Expected GREEN: helper produces posted unpaid DP and fully paid standard settlement, replay creates no invoice/payment duplicates, and Phase 3 accounting/quota tests remain green.

- [ ] **Step 6: Prove controlled loading on fresh no-demo and demo databases**

First use an unused no-demo name:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_acceptance \
  -i base,travel_umroh --without-demo=all --log-level=info
docker compose exec -T db psql -U odoo -d travel_umroh_phase4_acceptance -Atc \
  "SELECT count(*) FROM travel_package WHERE code LIKE 'DEMO-%';"
```

Expected: install succeeds and count is exactly `0`.

Then use an unused demo name and deliberately omit `--without-demo=all`:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_demo \
  -i base,travel_umroh --log-level=info
docker compose exec -T db psql -U odoo -d travel_umroh_phase4_demo -Atc \
  "SELECT client_order_ref || '|' || travel_payment_state FROM sale_order WHERE client_order_ref LIKE 'DEMO-%' ORDER BY client_order_ref;"
```

Expected exactly:

```text
DEMO-DP|dp
DEMO-DRAFT|unpaid
DEMO-PAID|paid
```

Also query two departures, six prices, five Jamaah, DP `seat_reserved=false`, Paid `seat_reserved=true`, and `reserved_seats=2` on the Paid departure. If the Docker image configuration suppresses demo by default, rerun only the unused demo database with Odoo's explicit demo-enabled option after checking `odoo --help`; do not modify the no-demo database and do not drop either database.

- [ ] **Step 7: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models/travel_demo.py \
  addons/travel_umroh/models/__init__.py \
  addons/travel_umroh/demo/travel_umroh_demo.xml \
  addons/travel_umroh/tests/test_phase4_demo.py \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/__manifest__.py
git commit -m "feat: add controlled travel demo data"
```

Checkpoint: no-demo install stays clean; demo-enabled install contains deterministic Draft/DP/Paid records built through standard workflows.

---

## Task 6: Harden Manager Boundaries and Preserve System Administrator

**Purpose:** Close the actual Phase 3 inconsistency where some direct `has_group(Manager)` checks reject System Administrator, without granting Staff or Finance any new mutation right.

**Files:**

- Create: `addons/travel_umroh/models/travel_security.py`
- Create: `addons/travel_umroh/tests/test_phase4_hardening.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Modify: `addons/travel_umroh/models/res_partner.py`
- Modify: `addons/travel_umroh/models/ir_attachment.py`
- Modify: `addons/travel_umroh/models/travel_jamaah.py`
- Modify: `addons/travel_umroh/models/travel_booking_participant.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

**Interfaces:**

- Produces `is_travel_manager_or_admin(env) -> bool`, true exactly for `env.is_admin()` or membership in `travel_umroh.group_travel_manager`.
- Consumes this predicate in all reviewed verified-contact/document and participant override checks; it does not alter ACLs, record rules, role implication, or Finance-only checks.

- [ ] **Step 1: Write RED System Administrator and negative-role tests**

Create `TestPhaseFourInternalHardening(TravelAccountingCase)`. Through existing submit/verify flows, prove:

- System Administrator can verify a pending Jamaah;
- after verification, System Administrator can correct one Jamaah profile field, one linked partner contact field, and one KTP/passport attachment and each correction produces the existing audit message;
- after unlocking a confirmed booking, System Administrator can correct participant room/price and the existing Chatter audit remains;
- Staff and Finance still fail the same verified-profile/partner/attachment and confirmed-participant mutations;
- Manager behavior remains green;
- System Administrator still cannot forge computed `travel_payment_state`, `seat_reserved`, or departure state through direct `write()` because those are workflow integrity guards, not role ACLs.

Use `self.env.ref("base.user_admin")` for the normal Odoo Administrator and do not rely only on UID 1. Reuse synthetic uploaded document bytes; never use real identity files.

- [ ] **Step 2: Run RED hardening target**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourInternalHardening \
  --log-level=test
```

Expected RED: Administrator is rejected by at least `action_verify_documents()` and verified-contact/attachment or participant Manager-only checks. Staff/Finance negative assertions must already pass.

- [ ] **Step 3: Add the shared predicate and apply it narrowly**

Create:

```python
def is_travel_manager_or_admin(env):
    return env.is_admin() or env.user.has_group(
        "travel_umroh.group_travel_manager"
    )
```

Import `travel_security` from `models/__init__.py` before importing the model modules that consume the predicate. Keep the helper as a plain internal Python function; do not register a new Odoo model or ACL for it.

Import/use it only in:

- `travel.jamaah.write()` verified-profile correction and `action_verify_documents()`;
- `res.partner.write()` verified-Jamaah business correction; retain `trusted_signup_metadata_write` solely to suppress audit for Odoo's technical `signup_type` write;
- `ir.attachment._travel_check_verified_document_mutation()`;
- `travel.booking.participant.write()`, `_compute_can_override_price()`, and `_ensure_order_mutation_allowed()`;
- `sale.order._compute_travel_edit_helpers()` so Administrator UI helpers reflect the same server capability.

Do not use the helper in Finance-only checks. Do not convert workflow-integrity errors into admin bypasses. Existing departure/cancellation checks may keep their equivalent explicit `env.is_admin() or has_group()` form.

- [ ] **Step 4: Run GREEN hardening plus all focused role tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourInternalHardening,/travel_umroh:TestPhaseTwoHardening,/travel_umroh:TestPhaseThreeAccountingSecurity,/travel_umroh:TestTravelBookingSecurity,/travel_umroh:TestTravelSecurity \
  --log-level=test
```

Expected GREEN: Administrator performs Manager-authorized corrections with audit, Staff/Finance remain denied, and all Phase 1-3 role-selector/ACL/server-boundary tests pass.

- [ ] **Step 5: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models/travel_security.py \
  addons/travel_umroh/models/__init__.py \
  addons/travel_umroh/models/res_partner.py \
  addons/travel_umroh/models/ir_attachment.py \
  addons/travel_umroh/models/travel_jamaah.py \
  addons/travel_umroh/models/travel_booking_participant.py \
  addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/tests/test_phase4_hardening.py \
  addons/travel_umroh/tests/__init__.py
git commit -m "fix: preserve admin travel management access"
```

Checkpoint: all internal management boundaries now consistently include Odoo Administrator without weakening Staff/Finance.

---

## Task 7: Add End-to-End Internal Acceptance and Reproducible Documentation

**Purpose:** Consolidate the complete internal flow into one acceptance test and document exact developer/demo operations for a zero-context reviewer.

**Files:**

- Create: `addons/travel_umroh/tests/test_phase4_acceptance.py`
- Create: `docs/phase4-demo-flow.md`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `README.md`

**Interfaces:**

- Consumes: public Phase 1-3 master, Booking, document, Accounting, cancellation/refund methods; Phase 4 report actions; controlled demo XML IDs.
- Produces `TestPhaseFourInternalAcceptance`, a developer README, and a role-by-role demo script. No new production model/field/action is planned in this task.

- [ ] **Step 1: Write the consolidated acceptance test before documentation**

Create `TestPhaseFourInternalAcceptance(TravelAccountingCase)` tagged `post_install`, `-at_install`. One method must execute this exact flow with public Odoo APIs:

1. use the open fixture departure and create a two-participant Travel quotation as Staff;
2. confirm it and assert zero reserved seats/unpaid;
3. as Finance create/post a 20% down-payment invoice and assert DP/zero reserved;
4. register the full DP payment and assert exactly two reserved seats;
5. create the standard delivered/final invoice with `deduct_down_payments=True`, post/pay it, and assert `paid`;
6. while the departure is still Open, create and fully pay a separate two-participant booking on the same departure, snapshot its posted `out_invoice` records, then Manager uses `travel.booking.cancel.wizard` with reason `DEMO acceptance refund`; assert capacity falls from four reserved seats back to two plus the exact reason/release Chatter notes;
7. Finance reverses only that snapshot of original customer invoices with `account.move.reversal.refund_moves()`, posts all resulting `out_refund` moves, pays each outgoing refund through `account.payment.register`, and asserts `refunded` with capacity still at two (no re-reservation);
8. verify both Jamaah of the original paid booking through existing Staff submit + Manager verify actions, then Manager moves the departure `departed -> done`;
9. resolve all four custom Phase 4 report actions and prove Staff, Finance, and Manager can read the involved records from their respective source models; evaluate the fixed Booking and Manifest domains explicitly, and additionally prove the standard-invoice menu is assigned only to Finance/Manager while Staff receives no new Accounting group or invoice mutation capability;
10. assert an ordinary Sales Order remains outside `action_travel_booking_report` and cannot appear in the participant Manifest because it has no Travel participants.

Use small private test helpers inside the test class with explicit signatures:

```python
def _create_final_invoice(self, order):
    before = order.invoice_ids
    self._create_invoice_wizard(
        order, "delivered", deduct_down_payments=True
    ).create_invoices()
    order.invalidate_recordset(["invoice_ids"])
    return (order.invoice_ids - before).ensure_one()

def _reverse_and_pay(self, invoice, reason):
    reversal = self.env["account.move.reversal"].with_user(
        self.finance
    ).with_context(
        active_model="account.move", active_ids=invoice.ids
    ).create({
        "reason": reason,
        "journal_id": invoice.journal_id.id,
    })
    reversal.refund_moves()
    refund = reversal.new_move_ids.ensure_one()
    if refund.state == "draft":
        refund.with_user(self.finance).action_post()
    self._pay_posted_invoice(refund)
    return refund

def _pay_posted_invoice(self, invoice):
    self.assertEqual(invoice.state, "posted")
    (
        self.env["account.payment.register"]
        .with_user(self.finance)
        .with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        )
        .create({
            "journal_id": self.company_data["default_journal_bank"].id,
        })
        .action_create_payments()
    )
    invoice.invalidate_recordset(["amount_residual", "payment_state"])
    return invoice
```

Before looping, snapshot only the cancelled order's posted `out_invoice` recordset and iterate that immutable recordset. Do not iterate `order.invoice_ids` after credit notes are created, and do not search all company refunds by name/date.

- [ ] **Step 2: Run the acceptance test and handle only real in-scope defects**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourInternalAcceptance \
  --log-level=test
```

Expected: this may be GREEN immediately because it consolidates already implemented behavior. If RED, classify the exact root cause and return to the earlier task that owns that explicit file before editing. Only Phase 4 reporting/demo/internal-hardening gaps are authorized; do not redesign Phase 3 or weaken a business guard to make the scenario pass.

- [ ] **Step 3: Expand `README.md` with executable developer setup**

Replace the one-line README with these exact sections:

- project purpose and Odoo 18/PostgreSQL 15 architecture;
- prerequisites: Docker Desktop/Compose and Git;
- `docker compose up -d`, `docker compose ps`, and `http://localhost:8069`;
- separate development/test database policy and explicit warning never to drop volumes/databases without approval;
- module install command using an unused database and `-i base,travel_umroh --without-demo=all`;
- module upgrade command using `-u travel_umroh --without-demo=all`;
- full standard suite and separate `database_breaking` concurrency command;
- Staff/Finance/Manager permission summary;
- how to install with controlled demo enabled and expected `DEMO-DRAFT`, `DEMO-DP`, `DEMO-PAID` states;
- links to PRD, technical design, roadmap, Phase 1-4 plans, and `docs/phase4-demo-flow.md`;
- explicit deferred Phase 5 Portal and excluded integrations.

Use commands from this plan verbatim except that database-name examples must be replaced with a confirmed unused name; do not include credentials beyond the repository's Docker development defaults.

- [ ] **Step 4: Write the exact stakeholder demo flow**

Create `docs/phase4-demo-flow.md` containing:

1. environment preflight and demo record checks;
2. Manager walkthrough of package, two departures, three room prices, flights, hotels, capacity list/pivot/graph;
3. Staff walkthrough of `DEMO-DRAFT`, Jamaah document status, and Manifest filters;
4. Finance walkthrough of `DEMO-DP` invoice/residual and report payment grouping;
5. Finance/Manager walkthrough of `DEMO-PAID`, reserved capacity and full Booking report;
6. a synthetic manual refund flow on a copy/new test booking, including expected state before/after refund;
7. Reporting menu walkthrough: Booking & Penjualan, Kapasitas Keberangkatan, Status Dokumen, Manifest Jamaah, plus Finance/Manager `Sisa Tagihan` using the standard customer-invoice action;
8. ordinary Sales regression check;
9. expected errors for Staff invoice, Finance booking edit, unverified departure, and insufficient quota;
10. cleanup guidance limited to cancelling/archiving synthetic records—never deleting databases/volumes.

For every step state the role, navigation path, input, expected UI state, and what screenshot/evidence to capture. Clearly mark that `.example.test` email cannot deliver real mail without SMTP configuration.

- [ ] **Step 5: Run documentation/static validation and full acceptance regression**

```bash
rg -n "docker compose|without-demo|database_breaking|Staff|Finance|Manager|Phase 5" README.md docs/phase4-demo-flow.md
rg -n "DEMO-DRAFT|DEMO-DP|DEMO-PAID|Booking & Penjualan|Manifest Jamaah" docs/phase4-demo-flow.md
git diff --check
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourInternalAcceptance,/travel_umroh:TestPhaseFourReporting,/travel_umroh:TestPhaseFourDemoData,/travel_umroh:TestPhaseFourInternalHardening \
  --log-level=test
```

Expected: both documents contain all required executable sections; Phase 4 acceptance/report/demo/hardening tests report 0 failed, 0 errors.

- [ ] **Step 6: Checkpoint and focused commit**

If the acceptance test required no production correction:

```bash
git add addons/travel_umroh/tests/test_phase4_acceptance.py \
  addons/travel_umroh/tests/__init__.py \
  README.md docs/phase4-demo-flow.md
git commit -m "docs: add travel acceptance demo guide"
```

If Task 7 initially exposed a production defect, finish and commit the correction under its owning earlier task, rerun the exact failure and full Phase 4 target, then make this documentation commit separately.

Checkpoint: internal acceptance is automated and a reviewer can reproduce setup/demo without reading implementation code.

---

## Task 8: Full Phase 4 Verification, Security Review, Install/Upgrade Proof, and Stop

**Purpose:** Produce final evidence that reporting/demo/hardening are complete, no-demo production installation stays clean, demo upgrade is idempotent, and Phase 5 has not started.

**Files:**

- Modify: `docs/superpowers/plans/2026-08-22-phase-4-reporting-demo-hardening.md` only to append actual checkpoint evidence after all commands pass
- No production/test file is modified inside Task 8; a failure returns to the earlier task with the explicit owning file list

**Interfaces:**

- Consumes all Phase 1-4 tests/actions/data/docs.
- Produces verification logs/counts, acceptance traceability, security matrix, manual demo evidence, and the Phase 4 stop checkpoint.

- [ ] **Step 1: Static scope and syntax review**

```bash
git status --short
git diff --check
PYTHONPYCACHEPREFIX=/private/tmp/travel_umroh_phase4_pycache \
  python3 -m compileall -q addons/travel_umroh
rg -n "<tree|sudo\(|portal|http\.route|javascript|owl|payment.gateway|whatsapp" addons/travel_umroh README.md docs/phase4-demo-flow.md
rg -n "store=True|read_group|pivot|graph|DEMO-|is_travel_manager_or_admin" addons/travel_umroh
```

Expected:

- no syntax/whitespace errors and no `<tree>`;
- no controller/portal/OWL/JavaScript/payment gateway/WhatsApp implementation;
- `sudo()` occurrences are only pre-existing verified-document lookups or tightly reviewed demo/test setup, never report access bypass;
- no new persistent reporting ledger/model;
- demo XML is referenced only by the manifest `demo` key.

- [ ] **Step 2: Run the full standard module suite**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable --test-tags /travel_umroh --log-level=test
```

Expected: 0 failed, 0 errors; method/stat totals exceed the Phase 3 baseline of 169/201. Record actual counts rather than predicting them in advance.

- [ ] **Step 3: Run the real PostgreSQL concurrency proof separately**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable --test-tags database_breaking --log-level=test
```

Expected: one method / three Odoo stats, 0 failed, 0 errors; one last-seat reservation succeeds and the losing transaction receives the existing capacity outcome after retry. Reporting storage changes must not affect locking/idempotency.

- [ ] **Step 4: Prove a never-used no-demo clean install**

Resolve an unused suffix first, then:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_acceptance_02 \
  -i base,travel_umroh --without-demo=all \
  --test-enable --test-tags /travel_umroh --log-level=test
docker compose exec -T db psql -U odoo -d travel_umroh_phase4_acceptance_02 -Atc \
  "SELECT state || '|' || latest_version FROM ir_module_module WHERE name='travel_umroh'; SELECT count(*) FROM travel_package WHERE code LIKE 'DEMO-%';"
```

Expected: `installed|18.0.4.0.0`, full suite 0/0, and demo count `0`.

- [ ] **Step 5: Prove idempotent no-demo module upgrade**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_acceptance_02 \
  -u travel_umroh --without-demo=all \
  --test-enable --test-tags /travel_umroh --log-level=test
```

Expected: all XML IDs, stored-field recomputations, actions, and menus upgrade without duplicate/error; suite stays 0/0; demo count remains zero.

- [ ] **Step 6: Prove demo-enabled install and upgrade remain deterministic**

Use a never-used demo database and omit `--without-demo=all`:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_demo_02 \
  -i base,travel_umroh \
  --test-enable --test-tags /travel_umroh --log-level=test
docker compose exec -T db psql -U odoo -d travel_umroh_phase4_demo_02 -Atc \
  "SELECT client_order_ref || '|' || travel_payment_state FROM sale_order WHERE client_order_ref LIKE 'DEMO-%' ORDER BY client_order_ref;"
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_demo_02 \
  -u travel_umroh \
  --test-enable --test-tags /travel_umroh --log-level=test
```

Expected before and after upgrade: exactly three demo bookings; Draft/DP/Paid states unchanged; invoice/payment counts unchanged; full tests 0/0. If demo loading is disabled by container defaults, use the explicit option discovered from `docker compose run --rm odoo --help` on a new unused database—never reuse/drop the failed name.

- [ ] **Step 7: Focused reporting and Staff/Finance/Manager/System Administrator review**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_acceptance_02 -u travel_umroh --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseFourReporting,/travel_umroh:TestPhaseFourInternalHardening,/travel_umroh:TestPhaseThreeAccountingSecurity,/travel_umroh:TestTravelBookingSecurity,/travel_umroh:TestTravelSecurity \
  --log-level=test
```

Review and report:

| Operation | Staff | Finance | Manager | System Administrator |
|---|---:|---:|---:|---:|
| Open four operational Travel reports | allow | allow | allow | allow |
| See Travel menu `Sisa Tagihan` | hidden | allow | allow | allow |
| Read/export Manifest | allow | allow | allow | allow |
| Edit via report list | denied/non-editable | denied/non-editable | denied via report list | denied via report list |
| Mutate Booking | constrained Phase 2 | deny | constrained/audited | workflow integrity retained |
| Invoice/payment/refund | deny | allow | allow | allow |
| Verify/correct verified Jamaah | deny | deny | allow/audited | allow/audited |
| Change verified attachment | deny | deny | allow/audited | allow/audited |
| Manage master/departure | read | read | allow | allow |

Expected: XML visibility, ACL/record rules, and server guards agree. No report uses `sudo()` to manufacture visibility.

- [ ] **Step 8: Acceptance traceability review**

| Phase 4 criterion | Automated/manual evidence |
|---|---|
| Booking per departure and payment status | `TestPhaseFourReporting`, Booking list/pivot/graph |
| Sales per package/departure | Booking pivot/graph using `amount_total` |
| Outstanding amount | Finance/Manager `Sisa Tagihan` menu linked to `account.action_move_out_invoice_type` and standard residual/payment-state UI |
| Quota total/used/remaining | capacity pivot/graph and paid-DP integration assertion |
| Jamaah by document status | document pivot/graph and real document workflow |
| Manifest per departure | non-editable participant Manifest list/search |
| Controlled demo data | `TestPhaseFourDemoData`, paired no-demo/demo clean installs |
| Draft/DP/Paid demo states | standard-flow demo helper and SQL readback |
| End-to-end paid/refund flow | `TestPhaseFourInternalAcceptance` |
| Staff/Finance/Manager security | focused Phase 1-4 suite and matrix |
| Administrator preserved | `TestPhaseFourInternalHardening` |
| Audit/error hardening | acceptance Chatter and existing Indonesian business-error assertions |
| Install and upgrade | no-demo and demo acceptance database proofs |
| Developer/demo documentation | README/doc static checks plus manual walkthrough |

Every row must have green evidence before Phase 4 is declared complete.

- [ ] **Step 9: Manual demo checkpoint**

On the demo database, follow `docs/phase4-demo-flow.md` and capture:

1. package/departure configuration;
2. Draft/DP/Paid Booking list;
3. Booking sales pivot/graph;
4. capacity pivot/graph with two reserved seats;
5. document-status pivot/graph;
6. Manifest filtered by departure;
7. one copied/new synthetic refund flow;
8. Staff/Finance negative permissions and Manager/Admin positive audited correction;
9. ordinary Sales regression.

Expected: no traceback, no record from another domain in fixed Travel actions, and no real email/data is required.

- [ ] **Step 10: Route any verification defect back to its owning task**

If verification discovers an in-scope defect, stop this verification task and return to the first task above that owns the exact source/test/doc file. Add a new RED regression assertion there, use that task's explicit `git add` path list and focused commit, then restart Task 8 from Step 1. Do not create a generic catch-all or empty correction commit.

- [ ] **Step 11: Stop at Phase 4 checkpoint**

Report:

- every focused commit and exact file created/modified;
- standard full-suite and separate concurrency counts;
- no-demo clean install/upgrade proof and zero demo records;
- demo clean install/upgrade proof and stable Draft/DP/Paid records;
- Staff/Finance/Manager/System Administrator review;
- reporting and manual demo evidence;
- remaining risks: large-data pivot performance, spreadsheet export handling of sensitive Manifest columns, demo dependence on a configured chart/journals, SMTP being intentionally unconfigured, and accounting localization differences;
- explicit confirmation that no database/volume/development data was deleted;
- explicit confirmation that Portal/Phase 5 and all excluded integrations were not started.

Do not implement or plan Phase 5 in the Phase 4 execution session. Stop for user review.

## Explicitly Deferred after Phase 4

- Portal controllers, routes, templates, access tokens, portal record rules, portal document upload, and self-service profile edits.
- Printable QWeb/PDF Manifest unless a later requirement explicitly selects it over the standard list/export.
- Custom OWL/JavaScript dashboard, KPI tiles, or bespoke chart widgets.
- WhatsApp, payment gateway, bank synchronization, waitlist, room/roommate allocation, visa processing/API, airline manifest API, mobile application, legacy migration, multi-company consolidation, and multi-currency reporting.
- Production SMTP, Indonesian localization/chart configuration, and real customer/demo identities.
