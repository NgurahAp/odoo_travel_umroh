# Travel Umroh Phase 2: Jamaah and Booking/Quotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Travel Staff to maintain secure Jamaah profiles and create multi-participant travel quotations whose participant price snapshots stay synchronized with one protected Sales Order line per participant.

**Architecture:** Keep contact data on `res.partner`, add a one-to-one `travel.jamaah` domain profile, and extend the standard `sale.order` instead of creating a parallel booking transaction. `travel.booking.participant` is the source of truth for participant identity, room type, and snapshot price; a guarded `sale.order.line` mirrors each participant so Odoo computes quotation totals and preserves the standard quotation-to-Sales-Order workflow.

**Tech Stack:** Odoo 18 Community, Python 3, PostgreSQL 15, `sale_management`, `mail`, XML views/data, Odoo `TransactionCase`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md`

**Roadmap:** `docs/superpowers/plans/2026-08-20-travel-umroh-roadmap.md`

**Previous phase:** `docs/superpowers/plans/2026-08-20-phase-1-foundation-master-data.md`

## Global Constraints

- Work only inside `addons/travel_umroh` plus this Phase 2 plan when implementation evidence requires a documentation correction.
- Treat the roadmap definition of Phase 2 as authoritative: implement Jamaah and Booking/Quotation only.
- Do not implement portal routes, portal users, QWeb portal templates, or portal record rules; those belong to Phase 5.
- Do not implement payment state, down payment logic, invoice/payment hooks, seat reservation, remaining-seat computation, overbooking, cancellation/refund, or departure `departed`/`done`; those belong to Phase 3.
- Confirming a travel quotation must not change departure quota and must not create a seat-reservation field or record.
- Reuse standard `res.partner`, `sale.order`, `sale.order.line`, product, tax, currency, Chatter, and quotation confirmation behavior. Do not create a separate `travel.booking` transaction model.
- Keep tax behavior standard. Tests proving `amount_total == sum(participant.unit_price)` must use the existing tax-free service-product fixture; do not silently clear configured product taxes in business code.
- Initial implementation remains single-company and uses the departure/company currency. Reject a travel order whose Sales pricelist currency differs from its departure currency; do not add currency conversion.
- Use Odoo 18 `<list>` roots, not `<tree>`.
- Enforce every lock and permission in Python/ACL/record rules. XML `readonly`, `invisible`, domains, and hidden menus are usability only.
- Do not use a client-provided context flag as an authorization bypass. Internal synchronization must call private underscore-prefixed helpers that invoke `super()` directly; Odoo RPC does not expose private methods.
- Avoid `sudo()` in business flows. It is allowed only for narrowly scoped test inspection or Odoo metadata access where the acting user is not being authorized by that `sudo()`.
- Store `ktp_file` and `passport_file` as Odoo attachments using `fields.Binary(attachment=True)`, not inline business-table blobs.
- Do not store real NIK, passport, contact, credential, or customer data in source or demo fixtures. Use visibly synthetic values under `example.test`.
- Use English technical identifiers and Indonesian-friendly labels, help text, audit messages, and business errors.
- Preserve every Phase 1 test and behavior, including protected departure state changes, price structure locks, and the current Travel role selector.

---

## Current Baseline and Integration Boundaries

The implementation starts from `main` after Phase 1 merge commit `42788df`. The current add-on has:

- `travel.package.product_id` pointing to an ordered-quantity service product.
- `travel.departure` with `draft/open/cancelled` actions, complete room prices, flight legs, and accommodations.
- Room-price structure locked after departure opens, while the numeric `price` remains editable by Manager; this makes an explicit quotation snapshot refresh meaningful.
- Travel Staff, Finance, and Manager groups; Manager implies Staff and Finance.
- Staff and Finance read-only on all Phase 1 travel models; Manager has full CRUD.
- No `travel.jamaah`, participant, `sale.order` extension, or `sale.order.line` extension.
- 45 Phase 1 test methods (55 in Odoo test statistics) passing on install and upgrade.

Odoo 18 contracts verified from the running image:

- Sales form external ID: `sale.view_order_form`.
- Order-line notebook page: `//page[@name='order_lines']`.
- Confirmation hook: `sale.order.action_confirm()` validates, writes `state='sale'`, then calls `_action_confirm()`.
- Standard Sales User ACL: `sales_team.group_sale_salesman` can read/write/create `sale.order` and CRUD `sale.order.line`, but its record rule normally limits orders to its own/unassigned records.
- Group record rules are additive within a model; a Travel-specific rule can grant all Travel Staff visibility over `is_travel_booking=True` without exposing unrelated Sales Orders.

## Planned File Map

```text
addons/travel_umroh/
├── __manifest__.py                              # bump to 18.0.2.0.0; load Phase 2 views
├── models/
│   ├── __init__.py                              # import new Phase 2 models
│   ├── sale_order.py                            # booking fields, eligibility, refresh, confirm gates
│   ├── sale_order_line.py                       # participant reverse link and anti-bypass guards
│   ├── travel_booking_participant.py            # participant snapshot and line synchronization
│   ├── travel_departure.py                      # booking relation/count/action
│   └── travel_jamaah.py                         # partner profile, documents, verification, booking action
├── security/
│   ├── ir.model.access.csv                      # Jamaah/participant/Finance Sales read ACLs
│   └── travel_security.xml                      # Sales implication and Travel booking record rules
├── tests/
│   ├── __init__.py                              # import Phase 2 test modules
│   ├── common.py                                # TravelBookingCase fixture and helper factories
│   ├── test_booking.py                          # booking, snapshot, synchronization, confirmation
│   ├── test_booking_security.py                 # Staff/Finance/Manager server-side matrix
│   ├── test_jamaah.py                           # identity, attachment, verification workflow
│   └── test_views.py                            # composed views, actions, menus, debug=False smoke
└── views/
    ├── travel_booking_views.xml                 # Sales form extension and Booking action
    ├── travel_departure_views.xml               # Bookings smart button/tab
    ├── travel_jamaah_views.xml                  # list/form/search/action
    └── travel_menus.xml                         # Bookings and Jamaah menu entries
```

No controller, wizard, report, demo-data, accounting model, or portal file is created in Phase 2.

## Test Database and Commands

Before editing implementation code, create an isolated worktree with `superpowers:using-git-worktrees` and branch name `codex/phase-2-jamaah-booking`. Run all commands from that worktree.

Prepare a Phase 1 baseline in a new test database:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_test \
  -i travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: exit `0`; the existing 45 Phase 1 test methods pass before Phase 2 edits.

Focused test form used by each task:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TEST_CLASS \
  --log-level=test
```

Full regression form:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected successful ending for every green run: process exit `0`, no registry/XML/ACL error, and `0 failed, 0 error(s)`.

If a RED install leaves the test database unusable, do not delete it. Continue with a newly named database such as `travel_umroh_phase2_test_02`, or ask before dropping anything.

---

### Task 1: Add the One-to-One Jamaah Identity Profile

**Files:**

- Create: `addons/travel_umroh/models/travel_jamaah.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Modify: `addons/travel_umroh/__manifest__.py`
- Create: `addons/travel_umroh/tests/test_jamaah.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/tests/common.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`

**Interfaces:**

- Consumes: standard `res.partner`; existing `TravelUmrohCase` and Travel groups.
- Produces: model `travel.jamaah`; helper `TravelBookingCase._create_jamaah(suffix)`; fields used later by `travel.booking.participant.jamaah_id`.

- [ ] **Step 1: Write failing identity and uniqueness tests**

Add `TestTravelJamaah` with concrete cases:

```python
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelJamaah(TravelUmrohCase):
    def _values(self, suffix="001", **overrides):
        partner = self.env["res.partner"].create({
            "name": f"Jamaah Synthetic {suffix}",
            "phone": f"+62812000{suffix}",
            "email": f"jamaah-{suffix}@example.test",
        })
        values = {
            "partner_id": partner.id,
            "nik": f"SYNTHETIC-NIK-{suffix}",
            "birth_place": "Denpasar",
            "birth_date": fields.Date.context_today(self) - relativedelta(years=30),
            "gender": "male",
            "emergency_contact_name": "Synthetic Family",
            "emergency_contact_phone": "+628129999000",
        }
        values.update(overrides)
        return values

    def test_jamaah_reuses_partner_contact_and_computes_current_age(self):
        jamaah = self.env["travel.jamaah"].create(self._values())
        self.assertEqual(jamaah.name, jamaah.partner_id.name)
        self.assertEqual(jamaah.phone, jamaah.partner_id.phone)
        self.assertEqual(jamaah.age, 30)

    def test_future_birth_date_is_rejected(self):
        tomorrow = fields.Date.context_today(self) + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.env["travel.jamaah"].create(self._values(birth_date=tomorrow))

    @mute_logger("odoo.sql_db")
    def test_partner_nik_and_nonempty_passport_are_unique(self):
        first = self.env["travel.jamaah"].create(
            self._values("001", passport_number="SYNTH-P001")
        )
        for overrides in (
            {"partner_id": first.partner_id.id, "nik": "SYNTHETIC-NIK-002"},
            {"nik": first.nik},
            {"passport_number": first.passport_number},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(IntegrityError), self.cr.savepoint():
                self.env["travel.jamaah"].create(self._values("002", **overrides))

    def test_multiple_empty_passports_are_allowed(self):
        first = self.env["travel.jamaah"].create(self._values("003"))
        second = self.env["travel.jamaah"].create(self._values("004"))
        self.assertFalse(first.passport_number)
        self.assertFalse(second.passport_number)
```

Import `test_jamaah` in `tests/__init__.py` before running.

- [ ] **Step 2: Run the test to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelJamaah --log-level=test
```

Expected: non-zero exit because `travel.jamaah` is not registered.

- [ ] **Step 3: Implement the minimal Jamaah identity model**

Implement this exact field contract:

```python
class TravelJamaah(models.Model):
    _name = "travel.jamaah"
    _description = "Profil Jamaah Travel Umroh"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "partner_id"
    _order = "partner_id, id"

    partner_id = fields.Many2one(
        "res.partner", required=True, ondelete="restrict", index=True, tracking=True
    )
    name = fields.Char(related="partner_id.name", readonly=False)
    phone = fields.Char(related="partner_id.phone", readonly=False)
    email = fields.Char(related="partner_id.email", readonly=False)
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    city = fields.Char(related="partner_id.city", readonly=False)
    state_id = fields.Many2one(related="partner_id.state_id", readonly=False)
    zip = fields.Char(related="partner_id.zip", readonly=False)
    country_id = fields.Many2one(related="partner_id.country_id", readonly=False)
    nik = fields.Char(required=True, index=True, tracking=True)
    birth_place = fields.Char(required=True, tracking=True)
    birth_date = fields.Date(required=True, tracking=True)
    age = fields.Integer(compute="_compute_age", string="Umur")
    gender = fields.Selection(
        [("male", "Laki-laki"), ("female", "Perempuan")],
        required=True,
        tracking=True,
    )
    passport_number = fields.Char(index=True, tracking=True)
    passport_expiry = fields.Date(tracking=True)
    emergency_contact_name = fields.Char(required=True, tracking=True)
    emergency_contact_phone = fields.Char(required=True, tracking=True)
```

Use SQL constraints named `partner_uniq`, `nik_uniq`, and `passport_number_uniq`. Normalize `nik` with `.strip()` and a nonempty passport with `.strip().upper()` in both `create()` and `write()`; leave an empty passport as `False` so PostgreSQL permits multiple missing passports. Do not add a 16-digit NIK rule because neither PRD nor technical design specifies it.

Compute non-stored `age` with `relativedelta(fields.Date.context_today(record), record.birth_date).years`, and reject a future `birth_date` with `ValidationError("Tanggal lahir tidak boleh berada di masa depan.")`.

Add initial ACL rows:

```csv
access_travel_jamaah_staff,travel.jamaah.staff,model_travel_jamaah,group_travel_staff,1,1,1,0
access_travel_jamaah_finance,travel.jamaah.finance,model_travel_jamaah,group_travel_finance,1,0,0,0
access_travel_jamaah_manager,travel.jamaah.manager,model_travel_jamaah,group_travel_manager,1,1,1,1
```

Bump the manifest version from `18.0.1.0.0` to `18.0.2.0.0`.

- [ ] **Step 4: Add a reusable Phase 2 fixture**

Extend `tests/common.py` without changing `TravelUmrohCase` setup used by Phase 1:

```python
class TravelBookingCase(TravelUmrohCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.departure = cls.env["travel.departure"].create({
            "package_id": cls.package.id,
            "departure_date": "2027-09-01",
            "return_date": "2027-09-10",
            "quota": 45,
            "company_id": cls.env.company.id,
        })
        for room_type, price in (
            ("quad", 30_000_000),
            ("triple", 32_000_000),
            ("double", 35_000_000),
        ):
            cls.env["travel.departure.price"].create({
                "departure_id": cls.departure.id,
                "room_type": room_type,
                "price": price,
            })
        cls.departure.action_open()
        cls.buyer = cls.env["res.partner"].create({
            "name": "Synthetic Booking Buyer",
            "email": "buyer@example.test",
        })

    @classmethod
    def _create_jamaah(cls, suffix="001", **overrides):
        partner = cls.env["res.partner"].create({
            "name": f"Synthetic Jamaah {suffix}",
            "phone": f"+62812000{suffix}",
        })
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
```

- [ ] **Step 5: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelJamaah --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: all Jamaah identity tests pass; all 45 Phase 1 test methods remain green; no model-access warning for `travel.jamaah`.

- [ ] **Step 6: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/models/__init__.py \
  addons/travel_umroh/models/travel_jamaah.py \
  addons/travel_umroh/security/ir.model.access.csv \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/tests/common.py \
  addons/travel_umroh/tests/test_jamaah.py
git commit -m "feat: add jamaah identity profiles"
```

Checkpoint: a synthetic partner can have exactly one Jamaah profile; NIK and nonempty passport are unique; no Booking code exists yet.

---

### Task 2: Add Attachment-Backed Documents and Verification Workflow

**Files:**

- Modify: `addons/travel_umroh/models/travel_jamaah.py`
- Modify: `addons/travel_umroh/tests/test_jamaah.py`

**Interfaces:**

- Consumes: `travel.jamaah` from Task 1 and existing Travel groups.
- Produces: `action_submit_documents() -> True`; `action_verify_documents() -> True`; immutable status metadata `document_status`, `verified_by`, and `verified_at` for Booking/security/UI tasks.

- [ ] **Step 1: Write failing attachment and transition tests**

Add these methods to `TestTravelJamaah`:

```python
from odoo import Command
from odoo.exceptions import AccessError
from odoo.exceptions import AccessError, UserError

def _complete_document_values(self):
    return {
        "passport_number": "SYNTH-PASSPORT-001",
        "passport_expiry": "2030-01-01",
        "ktp_file": b"synthetic-ktp-content",
        "ktp_filename": "synthetic-ktp.txt",
        "passport_file": b"synthetic-passport-content",
        "passport_filename": "synthetic-passport.txt",
    }

def _role_user(self, login, group_xmlid):
    return self.env["res.users"].create({
        "name": login,
        "login": login,
        "email": f"{login}@example.test",
        "groups_id": [Command.set([
            self.env.ref("base.group_user").id,
            self.env.ref(f"travel_umroh.{group_xmlid}").id,
        ])],
    })

def test_binary_documents_are_stored_as_ir_attachments(self):
    jamaah = self.env["travel.jamaah"].create(
        self._values(**self._complete_document_values())
    )
    attachments = self.env["ir.attachment"].search([
        ("res_model", "=", "travel.jamaah"),
        ("res_id", "=", jamaah.id),
        ("res_field", "in", ["ktp_file", "passport_file"]),
    ])
    self.assertEqual(len(attachments), 2)

def test_incomplete_documents_cannot_be_submitted(self):
    jamaah = self.env["travel.jamaah"].create(self._values())
    with self.assertRaises(UserError):
        jamaah.action_submit_documents()

def test_submit_then_manager_verify_records_audit_identity_and_time(self):
    jamaah = self.env["travel.jamaah"].create(
        self._values(**self._complete_document_values())
    )
    jamaah.action_submit_documents()
    self.assertEqual(jamaah.document_status, "pending")
    manager = self._role_user("phase2-document-manager", "group_travel_manager")
    jamaah.with_user(manager).action_verify_documents()
    self.assertEqual(jamaah.document_status, "verified")
    self.assertEqual(jamaah.verified_by, manager)
    self.assertTrue(jamaah.verified_at)
    self.assertTrue(jamaah.message_ids.filtered(
        lambda message: "Dokumen jamaah diverifikasi" in (message.body or "")
    ))

def test_staff_cannot_verify_or_edit_a_verified_profile(self):
    staff = self._role_user("phase2-document-staff", "group_travel_staff")
    manager = self._role_user("phase2-document-lock-manager", "group_travel_manager")
    jamaah = self.env["travel.jamaah"].create(
        self._values(suffix="002", **self._complete_document_values())
    )
    jamaah.action_submit_documents()
    with self.assertRaises(AccessError):
        jamaah.with_user(staff).action_verify_documents()
    jamaah.with_user(manager).action_verify_documents()
    with self.assertRaises(AccessError):
        jamaah.with_user(staff).write({"birth_place": "Bandung"})

def test_document_status_and_verifier_cannot_be_written_directly(self):
    jamaah = self.env["travel.jamaah"].create(self._values())
    for values in (
        {"document_status": "verified"},
        {"verified_by": self.env.user.id},
        {"verified_at": "2027-01-01 00:00:00"},
    ):
        with self.subTest(values=values), self.assertRaises(UserError):
            jamaah.write(values)
```

Task 7 repeats these denials inside the complete cross-model role matrix; the behavior itself is test-first in this task.

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelJamaah --log-level=test
```

Expected: failures because the binary/status fields and actions do not exist.

- [ ] **Step 3: Implement attachment fields and protected transitions**

Add this contract:

```text
ktp_file: Binary(attachment=True, copy=False)
ktp_filename: Char(copy=False)
passport_file: Binary(attachment=True, copy=False)
passport_filename: Char(copy=False)
document_status: Selection(incomplete/pending/verified, default incomplete, tracking, copy=False, readonly)
verified_by: Many2one(res.users, readonly, copy=False)
verified_at: Datetime(readonly, copy=False)
```

`action_submit_documents()` must:

1. Accept only `document_status == 'incomplete'`.
2. Require `ktp_file`, `passport_number`, `passport_expiry`, and `passport_file`.
3. Raise `UserError("Lengkapi file KTP, nomor dan masa berlaku paspor, serta file paspor sebelum diajukan.")` when incomplete.
4. Call `super(TravelJamaah, jamaah).write({'document_status': 'pending', 'verified_by': False, 'verified_at': False})` directly for each record and return `True`.

`action_verify_documents()` must:

1. Require `group_travel_manager` with `has_group`; otherwise raise `AccessError`.
2. Accept only `pending`.
3. Write `verified`, current user, and `fields.Datetime.now()` through `super()`.
4. Post `"Dokumen jamaah diverifikasi oleh <display name>."` to the Jamaah Chatter.
5. Return `True`.

Override public `write()` so direct writes to `document_status`, `verified_by`, or `verified_at` raise `UserError("Gunakan aksi dokumen Jamaah untuk mengubah status verifikasi.")`. Do not use a context bypass.

For verified records, block Staff changes to identity/contact/document fields. Permit Manager correction and post a Chatter note listing changed field labels; keep the verification state unchanged because the technical design requires Manager correction with audit but does not define an automatic reset transition.

- [ ] **Step 4: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelJamaah --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: two `ir.attachment` records are linked through `res_field`; incomplete submission and direct status writes fail; verification records user/time and Chatter; Phase 1 remains green.

- [ ] **Step 5: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/models/travel_jamaah.py \
  addons/travel_umroh/tests/test_jamaah.py
git commit -m "feat: add jamaah document verification"
```

Checkpoint: internal document verification exists, but no portal upload and no departure-travel gate is implemented.

---

### Task 3: Extend Sales Orders as Travel Booking Quotations

**Files:**

- Create: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Modify: `addons/travel_umroh/models/travel_departure.py`
- Modify: `addons/travel_umroh/security/travel_security.xml`
- Create: `addons/travel_umroh/tests/test_booking.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/tests/common.py`

**Interfaces:**

- Consumes: open `travel.departure`, its package/service product, current company/currency, standard `sale.order`.
- Produces: the Travel Booking shell on `sale.order` (`is_travel_booking`, `departure_id`, `travel_package_id`) plus departure `booking_ids`, `booking_count`, and `action_view_bookings()`. Participant relations are added only after their comodel exists in Task 4.

- [ ] **Step 1: Write failing booking-shell tests**

Create `TestTravelBooking`:

```python
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelBooking(TravelBookingCase):
    def _create_order(self, **overrides):
        values = {
            "partner_id": self.buyer.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        }
        values.update(overrides)
        return self.env["sale.order"].create(values)

    def test_travel_booking_reuses_sale_order_and_departure_package(self):
        order = self._create_order()
        self.assertTrue(order.is_travel_booking)
        self.assertEqual(order.departure_id, self.departure)
        self.assertEqual(order.travel_package_id, self.package)
        self.assertIn(order, self.departure.booking_ids)
        self.assertEqual(self.departure.booking_count, 1)

    def test_buyer_is_not_required_to_be_a_jamaah(self):
        order = self._create_order()
        self.assertFalse(self.env["travel.jamaah"].search([
            ("partner_id", "=", order.partner_id.id)
        ]))

    def test_draft_or_cancelled_departure_cannot_be_selected(self):
        invalid_departure = self.env["travel.departure"].create({
            "package_id": self.package.id,
            "departure_date": "2027-10-01",
            "return_date": "2027-10-10",
            "quota": 20,
            "company_id": self.env.company.id,
        })
        with self.assertRaises(ValidationError):
            self._create_order(departure_id=invalid_departure.id)

    def test_regular_sale_order_remains_unaffected(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self.assertFalse(order.is_travel_booking)
        self.assertFalse(order.departure_id)
```

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test
```

Expected: failures because `sale.order` and `travel.departure` lack Phase 2 fields.

- [ ] **Step 3: Implement the Sales Order booking shell**

Add to `sale.order`:

```text
is_travel_booking: Boolean(default False, index=True, copy=False, tracking=True)
departure_id: Many2one(travel.departure, tracking=True, ondelete=restrict, check_company=True)
travel_package_id: Many2one(related=departure_id.package_id, store=True, readonly=True)
```

Do not register `participant_ids`, participant counts, or participant-specific UI helper fields in this commit. The participant comodel and order relations arrive together in Task 4; role-aware UI helper fields arrive with the lock rules in Task 6.

Allow creating a new Travel Booking without a departure so the form can be saved incrementally. Once a nonempty `departure_id` is assigned to a travel order, enforce:

- departure `state == 'open'`;
- departure `active == True`;
- order `company_id == departure.company_id`;
- order `currency_id == departure.currency_id`, otherwise raise `ValidationError("Mata uang pricelist Sales Order harus sama dengan mata uang keberangkatan.")`.

Reject setting `departure_id` on a non-travel order. Reject changing `is_travel_booking` to false after a departure exists. These checks belong in `create()`/`write()` and a server constraint so RPC/import cannot bypass them. Task 4 extends the toggle guard once participants exist.

- [ ] **Step 4: Add departure-side booking interfaces**

Extend the existing class in `travel_departure.py`:

```text
booking_ids: One2many(sale.order, departure_id, string="Booking")
booking_count: Integer(compute="_compute_booking_count")
action_view_bookings(): returns ir.actions.act_window action_travel_booking with domain departure_id=self.id
```

`action_view_bookings()` is referenced by XML in Task 8; until that action exists, return a plain action dictionary with `res_model='sale.order'`, `view_mode='list,form'`, domain, and `context={'default_is_travel_booking': True, 'default_departure_id': self.id}`. Task 8 replaces the name/action reference without changing the signature.

- [ ] **Step 5: Enable Staff's standard quotation engine without broad all-order access**

Add `sales_team.group_sale_salesman` to `group_travel_staff.implied_ids`. Do not imply Sales Manager. Existing Sales personal rules continue to govern non-travel orders; Task 7 adds a group rule that grants all Travel Staff access only to travel bookings.

- [ ] **Step 6: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: Travel Sales Orders link to open departures; ordinary Sales Orders still work; departure count updates; no participant, price, or quota behavior exists yet.

- [ ] **Step 7: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/models/__init__.py \
  addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/travel_departure.py \
  addons/travel_umroh/security/travel_security.xml \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/tests/common.py \
  addons/travel_umroh/tests/test_booking.py
git commit -m "feat: extend quotations as travel bookings"
```

Checkpoint: booking identity/departure eligibility works; no participant line or confirmation override exists.

---

### Task 4: Generate One Protected Sales Line per Participant

**Files:**

- Create: `addons/travel_umroh/models/travel_booking_participant.py`
- Create: `addons/travel_umroh/models/sale_order_line.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`
- Modify: `addons/travel_umroh/tests/test_booking.py`

**Interfaces:**

- Consumes: `sale.order.departure_id`, `travel.departure.price`, `travel.package.product_id`, `travel.jamaah`.
- Produces: `travel.booking.participant`; `sale.order.line.travel_participant_id`; private line helpers `_travel_create_participant_lines`, `_travel_write_from_participant`, and `_travel_unlink_from_participant`.

- [ ] **Step 1: Write failing participant-to-line tests**

Add:

```python
from psycopg2 import IntegrityError
from odoo.tools import mute_logger

def test_each_participant_creates_one_service_order_line_and_snapshot(self):
    order = self._create_order()
    jamaah = self._create_jamaah("101")
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": jamaah.id,
        "room_type": "quad",
        "unit_price": 1,
    })
    self.assertEqual(participant.unit_price, 30_000_000)
    self.assertTrue(participant.sale_line_id)
    self.assertEqual(participant.sale_line_id.travel_participant_id, participant)
    self.assertEqual(participant.sale_line_id.product_id, self.package.product_id)
    self.assertEqual(participant.sale_line_id.product_uom_qty, 1)
    self.assertEqual(participant.sale_line_id.price_unit, participant.unit_price)

def test_multi_participant_total_equals_snapshot_sum_for_tax_free_fixture(self):
    order = self._create_order()
    first = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("102").id,
        "room_type": "quad",
    })
    second = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("103").id,
        "room_type": "double",
    })
    self.assertEqual(order.amount_total, first.unit_price + second.unit_price)
    self.assertEqual(len(order.order_line), 2)

@mute_logger("odoo.sql_db")
def test_jamaah_cannot_be_duplicated_in_one_booking(self):
    order = self._create_order()
    jamaah = self._create_jamaah("104")
    values = {"order_id": order.id, "jamaah_id": jamaah.id, "room_type": "triple"}
    self.env["travel.booking.participant"].create(values)
    with self.assertRaises(IntegrityError), self.cr.savepoint():
        self.env["travel.booking.participant"].create(values)

def test_removing_participant_removes_only_its_generated_line(self):
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("105").id,
        "room_type": "triple",
    })
    line = participant.sale_line_id
    participant.unlink()
    self.assertFalse(participant.exists())
    self.assertFalse(line.exists())
```

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test
```

Expected: `travel.booking.participant` is absent.

- [ ] **Step 3: Implement the participant model and price lookup**

Exact fields:

```text
order_id: Many2one(sale.order, required, cascade, index, copy=False)
jamaah_id: Many2one(travel.jamaah, required, restrict, index)
room_type: Selection(quad/triple/double, required)
unit_price: Monetary(required, copy=False)
currency_id: Many2one(related=order_id.currency_id, store=True, readonly=True)
sale_line_id: Many2one(sale.order.line, readonly=True, copy=False, ondelete=set null)
can_override_price: Boolean(non-stored, compute from current Manager group)
```

Add SQL constraints `order_jamaah_uniq` on `(order_id, jamaah_id)` and `sale_line_uniq` on `sale_line_id`.

Private helper signatures:

```python
def _get_departure_price(self, order, room_type):
    """Return exactly one travel.departure.price or raise UserError."""

def _prepare_sale_line_values(self):
    """Return order_id, product_id, product_uom_qty=1, product_uom,
    price_unit, name, and travel_participant_id."""

def _sync_sale_line(self):
    """Create or update the one mirrored Sales line; return None."""
```

On public `create()`:

1. Require `order.is_travel_booking`, open departure, and room price.
2. Ignore any caller-supplied `unit_price` and replace it with the current departure price.
3. Create the participant first.
4. Call the private Sales-line creation helper.
5. Link both `sale_line_id` and `travel_participant_id` through direct `super()` calls.

The line description format is `"<Jamaah name> — <Room label> — <Departure name>"`.

On `unlink()`, retain the line recordset, unlink participants through `super()`, then call the private line unlink helper. This order avoids a dangling participant relation while preserving standard order deletion cascades.

- [ ] **Step 4: Implement the Sales-line reverse link and private synchronization API**

Add:

```python
travel_participant_id = fields.Many2one(
    "travel.booking.participant", copy=False, readonly=True, ondelete="set null", index=True
)
```

Add SQL unique constraint `travel_participant_uniq` on `travel_participant_id`.

Private helpers call `super(SaleOrderLine, self).create/write/unlink` directly. Public `create()` rejects a caller-supplied `travel_participant_id`; public `write()` and `unlink()` reject participant-backed lines with `UserError("Ubah baris harga melalui Participant Booking Travel.")`. Do not trust a context key.

Regular Sales lines with no `travel_participant_id` must continue through standard `super()` unchanged.

- [ ] **Step 5: Complete order relation, travel-flag guard, and ACLs**

Now add `sale.order.participant_ids` and compute `participant_count`. Extend `sale.order.write()` so an order with any participant cannot be changed to `is_travel_booking=False`, including an RPC/import write. Add ACLs:

```csv
access_travel_booking_participant_staff,travel.booking.participant.staff,model_travel_booking_participant,group_travel_staff,1,1,1,1
access_travel_booking_participant_finance,travel.booking.participant.finance,model_travel_booking_participant,group_travel_finance,1,0,0,0
access_travel_booking_participant_manager,travel.booking.participant.manager,model_travel_booking_participant,group_travel_manager,1,1,1,1
```

- [ ] **Step 6: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: each participant has one line and vice versa; caller price `1` becomes departure snapshot; total equals snapshot sum in the tax-free fixture; regular Sales lines and all Phase 1 tests remain green.

- [ ] **Step 7: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/models/__init__.py \
  addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/sale_order_line.py \
  addons/travel_umroh/models/travel_booking_participant.py \
  addons/travel_umroh/security/ir.model.access.csv \
  addons/travel_umroh/tests/test_booking.py
git commit -m "feat: generate booking participant order lines"
```

Checkpoint: multi-participant quotation totals work; confirmation and post-confirmation locks are not yet claimed.

---

### Task 5: Preserve Snapshots, Refresh Draft Prices, and Block Line Bypasses

**Files:**

- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/sale_order_line.py`
- Modify: `addons/travel_umroh/models/travel_booking_participant.py`
- Modify: `addons/travel_umroh/tests/test_booking.py`

**Interfaces:**

- Consumes: participant-line one-to-one contract from Task 4.
- Produces: `sale.order.action_refresh_travel_prices() -> True`; participant `_refresh_from_departure_price()`; safe update behavior for room, Jamaah, departure, and current price.

- [ ] **Step 1: Write failing snapshot and anti-bypass tests**

```python
def test_departure_price_change_does_not_mutate_existing_snapshot_until_refresh(self):
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("201").id,
        "room_type": "quad",
    })
    quad = self.departure.price_ids.filtered(lambda price: price.room_type == "quad")
    quad.write({"price": 31_000_000})
    self.assertEqual(participant.unit_price, 30_000_000)
    order.action_refresh_travel_prices()
    self.assertEqual(participant.unit_price, 31_000_000)
    self.assertEqual(participant.sale_line_id.price_unit, 31_000_000)

def test_room_change_refreshes_snapshot_and_line_description(self):
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("202").id,
        "room_type": "quad",
    })
    participant.write({"room_type": "double"})
    self.assertEqual(participant.unit_price, 35_000_000)
    self.assertEqual(participant.sale_line_id.price_unit, 35_000_000)
    self.assertIn("Double", participant.sale_line_id.name)

def test_changing_draft_departure_refreshes_participant_snapshots(self):
    second_departure = self.env["travel.departure"].create({
        "package_id": self.package.id,
        "departure_date": "2027-11-01",
        "return_date": "2027-11-10",
        "quota": 30,
        "company_id": self.env.company.id,
    })
    for room_type, price in (
        ("quad", 40_000_000),
        ("triple", 42_000_000),
        ("double", 45_000_000),
    ):
        self.env["travel.departure.price"].create({
            "departure_id": second_departure.id,
            "room_type": room_type,
            "price": price,
        })
    second_departure.action_open()
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("204").id,
        "room_type": "quad",
    })
    order.write({"departure_id": second_departure.id})
    self.assertEqual(participant.unit_price, 40_000_000)
    self.assertEqual(participant.sale_line_id.price_unit, 40_000_000)

def test_direct_generated_line_price_write_and_unlink_are_rejected(self):
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("203").id,
        "room_type": "triple",
    })
    with self.assertRaises(UserError):
        participant.sale_line_id.write({"price_unit": 1})
    with self.assertRaises(UserError):
        participant.sale_line_id.with_context(_travel_participant_sync=True).write(
            {"price_unit": 1}
        )
    with self.assertRaises(UserError):
        participant.sale_line_id.unlink()

def test_public_participant_price_write_is_rejected_before_role_override(self):
    order = self._create_order()
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("205").id,
        "room_type": "quad",
    })
    with self.assertRaises(UserError):
        participant.write({"unit_price": 1})

def test_regular_sales_line_can_still_be_edited_and_deleted(self):
    order = self.env["sale.order"].create({"partner_id": self.buyer.id})
    line = self.env["sale.order.line"].create({
        "order_id": order.id,
        "product_id": self.service_product.id,
        "product_uom_qty": 1,
        "price_unit": 100,
    })
    line.write({"price_unit": 200})
    self.assertEqual(line.price_unit, 200)
    self.assertTrue(line.unlink())
```

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test
```

Expected: snapshot refresh method is absent or room/departure edits leave stale values.

- [ ] **Step 3: Implement draft refresh and synchronization**

`action_refresh_travel_prices()` must:

- accept only travel orders in `draft` or `sent`;
- require a valid open departure;
- invoke each participant's private `_refresh_from_departure_price()`;
- update participant `unit_price`, mirrored line `price_unit`, product, UoM, and description atomically;
- post one order Chatter note summarizing the number of refreshed participants;
- return `True`.

Participant public `write()` behavior while quotation is `draft/sent`:

- `room_type` change selects the current matching departure price and synchronizes the line;
- `jamaah_id` change synchronizes the description;
- `order_id` change is rejected; move by delete/recreate is not needed by the requirements;
- public explicit `unit_price` writes raise `UserError` for every user in this task. Task 6 replaces this temporary all-user guard with the final role-aware rule: Manager may override through the participant; Staff remains denied.

When draft/sent `sale.order.departure_id` changes, call `action_refresh_travel_prices()` after `super().write()` so all participant product/price snapshots follow the new departure. Reject departure changes after confirmation for every role; Manager correction is limited to participant/price, as specified.

- [ ] **Step 4: Expand public Sales-line guards**

Protect `product_id`, `product_uom`, `product_uom_qty`, `price_unit`, `discount`, `tax_id`, `order_id`, `name`, and `travel_participant_id` on participant-backed lines. Public `write()` or `unlink()` raises regardless of user role; Manager edits through the participant source of truth. Keep private helper methods as the only synchronization path.

- [ ] **Step 5: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: snapshots remain stable until explicit refresh, draft refresh is atomic, room/departure changes synchronize, line RPC bypasses fail, standard Sales lines remain unaffected.

- [ ] **Step 6: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/sale_order_line.py \
  addons/travel_umroh/models/travel_booking_participant.py \
  addons/travel_umroh/tests/test_booking.py
git commit -m "feat: protect and refresh booking price snapshots"
```

Checkpoint: draft quotation snapshots are safe; confirmation locking and Manager audit are next.

---

### Task 6: Confirm Without Reserving Seats and Lock Staff Corrections

**Files:**

- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/travel_booking_participant.py`
- Modify: `addons/travel_umroh/tests/test_booking.py`

**Interfaces:**

- Consumes: standard Odoo `sale.order.action_confirm()` and protected participant/line contract.
- Produces: confirmation preconditions; Staff post-confirm lock; Manager audited participant/price correction; explicit Phase 2 non-reservation guarantee.

- [ ] **Step 1: Write failing confirmation and audit tests**

```python
from odoo import Command


def test_travel_order_requires_departure_and_participant_before_confirmation(self):
    no_departure = self.env["sale.order"].create({
        "partner_id": self.buyer.id,
        "is_travel_booking": True,
    })
    with self.assertRaises(UserError):
        no_departure.action_confirm()
    no_participant = self._create_order()
    with self.assertRaises(UserError):
        no_participant.action_confirm()

def test_confirmation_keeps_departure_quota_unchanged(self):
    order = self._create_order()
    self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("301").id,
        "room_type": "quad",
    })
    quota_before = self.departure.quota
    order.action_confirm()
    self.assertEqual(order.state, "sale")
    self.assertEqual(self.departure.quota, quota_before)
    self.assertNotIn("seat_reserved", order._fields)
    self.assertNotIn("reserved_seats", self.departure._fields)

def test_confirmed_order_cannot_refresh_snapshot(self):
    order = self._create_order()
    self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("302").id,
        "room_type": "triple",
    })
    order.action_confirm()
    with self.assertRaises(UserError):
        order.action_refresh_travel_prices()

def test_manager_price_override_after_confirmation_syncs_line_and_chatter(self):
    manager = self.env["res.users"].create({
        "name": "Synthetic Booking Manager",
        "login": "phase2-booking-manager",
        "email": "phase2-booking-manager@example.test",
        "groups_id": [Command.set([
            self.env.ref("base.group_user").id,
            self.env.ref("travel_umroh.group_travel_manager").id,
        ])],
    })
    order = self._create_order(user_id=manager.id)
    participant = self.env["travel.booking.participant"].create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("303").id,
        "room_type": "double",
    })
    order.action_confirm()
    participant.with_user(manager).write({"unit_price": 36_000_000})
    self.assertEqual(participant.sale_line_id.price_unit, 36_000_000)
    self.assertTrue(order.message_ids.filtered(
        lambda message: "Override harga participant" in (message.body or "")
    ))

def test_staff_cannot_override_price_or_correct_after_confirmation(self):
    staff = self.env["res.users"].create({
        "name": "Synthetic Booking Staff",
        "login": "phase2-booking-staff",
        "email": "phase2-booking-staff@example.test",
        "groups_id": [Command.set([
            self.env.ref("base.group_user").id,
            self.env.ref("travel_umroh.group_travel_staff").id,
        ])],
    })
    order = self._create_order(user_id=staff.id)
    participant = self.env["travel.booking.participant"].with_user(staff).create({
        "order_id": order.id,
        "jamaah_id": self._create_jamaah("304").id,
        "room_type": "quad",
    })
    with self.assertRaises(AccessError):
        participant.with_user(staff).write({"unit_price": 1})
    order.with_user(staff).action_confirm()
    with self.assertRaises(AccessError):
        participant.with_user(staff).write({"room_type": "double"})
```

The functional tests use real Manager and Staff users assigned as order salespeople, so standard Sales record rules do not hide the mutation behavior under test. Task 7 repeats these guards in the complete cross-role matrix.

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test
```

Expected: incomplete travel orders confirm or Manager changes are not audited/guarded.

- [ ] **Step 3: Add travel confirmation preconditions**

Override `sale.order.action_confirm()`:

1. For non-travel orders, call `super()` unchanged.
2. For each travel order, require open/active departure, at least one participant, and for every participant exactly one existing linked Sales line with matching product, quantity 1, and price.
3. Raise a business `UserError` naming the broken invariant.
4. Call standard `super().action_confirm()`.
5. Do not override `_action_confirm()`, write quota, or add reservation fields.

- [ ] **Step 4: Implement role-aware post-confirm participant corrections**

Private guard:

```python
def _ensure_mutation_allowed(self, operation, values=None):
    """Allow Staff in draft/sent; require Manager after confirmation;
    always require Manager for explicit unit_price override."""
```

Rules:

- Staff may create/write/unlink participants while order state is `draft` or `sent`.
- A caller-supplied `unit_price` during participant creation is always discarded and replaced by the departure snapshot, as defined in Task 4. Staff cannot explicitly write `unit_price` afterward.
- Once state is not `draft/sent`, only Manager may create/write/unlink participants.
- Manager `unit_price` write synchronizes line price.
- Manager corrections after confirmation post one Chatter note with old and new Jamaah/room/price labels.
- If standard Odoo has locked the Sales Order, Manager must use the standard **Unlock** action before correcting it; the module must not bypass Odoo's `locked` protection.
- Never log raw NIK, passport bytes, or attachment content.

Block `sale.order.departure_id`, `is_travel_booking`, and participant command changes after confirmation except participant operations already authorized by the participant model. Do not create a cancel/refund path in this task.

Add the non-stored UI helper fields consumed by Task 8:

```text
sale.order.can_edit_travel_participants: true in draft/sent, or for Manager
sale.order.can_override_travel_price: true only for Manager
travel.booking.participant.can_override_price: true only for Manager
```

These are presentation helpers only. The ORM guards above remain authoritative.

- [ ] **Step 5: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBooking --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: incomplete travel booking cannot confirm; a valid multi-participant order becomes standard state `sale`; quota is unchanged; refresh is locked; Manager correction updates the mirrored line and Chatter.

- [ ] **Step 6: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/travel_booking_participant.py \
  addons/travel_umroh/tests/test_booking.py
git commit -m "feat: lock confirmed travel quotation snapshots"
```

Checkpoint: Phase 2 transaction behavior is complete; server-level role proof remains.

---

### Task 7: Prove Staff, Finance, Manager, and Internal-User Security

**Files:**

- Modify: `addons/travel_umroh/security/travel_security.xml`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`
- Create: `addons/travel_umroh/tests/test_booking_security.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

**Interfaces:**

- Consumes: all Phase 2 models and existing Travel role selector.
- Produces: complete server-side Phase 2 access matrix and Travel-only Sales record rules.

- [ ] **Step 1: Write role-user fixtures and failing security tests**

Create users with only their intended Travel role; Staff receives Sales User only through the XML implication from Task 3. Do not test as Administrator.

Required test code structure:

```python
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelBookingSecurity(TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls._create_user("phase2-staff", "group_travel_staff")
        cls.finance = cls._create_user("phase2-finance", "group_travel_finance")
        cls.manager = cls._create_user("phase2-manager", "group_travel_manager")
        cls.internal = cls._create_user("phase2-internal", None)

    @classmethod
    def _create_user(cls, login, group_xmlid):
        group_ids = [cls.env.ref("base.group_user").id]
        if group_xmlid:
            group_ids.append(cls.env.ref(f"travel_umroh.{group_xmlid}").id)
        return cls.env["res.users"].create({
            "name": login,
            "login": login,
            "email": f"{login}@example.test",
            "groups_id": [Command.set(group_ids)],
        })

    def _jamaah_as(self, user, suffix):
        partner = self.env["res.partner"].create({
            "name": f"Security Jamaah {suffix}",
            "phone": f"+6281300{suffix}",
        })
        return self.env["travel.jamaah"].with_user(user).create({
            "partner_id": partner.id,
            "nik": f"SEC-NIK-{suffix}",
            "birth_place": "Jakarta",
            "birth_date": "1990-01-01",
            "gender": "male",
            "emergency_contact_name": "Security Emergency",
            "emergency_contact_phone": "+628139990000",
        })

    def _draft_booking_as(self, user, suffix):
        order = self.env["sale.order"].with_user(user).create({
            "partner_id": self.buyer.id,
            "user_id": user.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        })
        participant = self.env["travel.booking.participant"].with_user(user).create({
            "order_id": order.id,
            "jamaah_id": self._jamaah_as(user, suffix).id,
            "room_type": "quad",
            "unit_price": 1,
        })
        return order, participant
```

Write the concrete role tests before changing ACLs/rules:

```python
def test_staff_gets_sales_user_and_can_open_another_staff_travel_booking(self):
    self.assertTrue(self.staff.has_group("sales_team.group_sale_salesman"))
    own_order, own_participant = self._draft_booking_as(self.staff, "400")
    own_order.with_user(self.staff).write({"client_order_ref": "STAFF-DRAFT"})
    own_participant.jamaah_id.with_user(self.staff).write({"birth_place": "Bogor"})
    other = self._create_user("phase2-other-staff", "group_travel_staff")
    other_order, _participant = self._draft_booking_as(other, "401")
    self.assertEqual(
        self.env["sale.order"].with_user(self.staff).browse(other_order.id).name,
        other_order.name,
    )

def test_staff_cannot_override_snapshot_or_mutate_after_confirmation(self):
    order, participant = self._draft_booking_as(self.staff, "402")
    self.assertEqual(participant.unit_price, 30_000_000)
    with self.assertRaises(AccessError):
        participant.with_user(self.staff).write({"unit_price": 1})
    order.with_user(self.staff).action_confirm()
    with self.assertRaises(AccessError):
        participant.with_user(self.staff).write({"room_type": "double"})
    with self.assertRaises(AccessError):
        participant.with_user(self.staff).unlink()
    with self.assertRaises(AccessError):
        self.env["travel.booking.participant"].with_user(self.staff).create({
            "order_id": order.id,
            "jamaah_id": self._jamaah_as(self.staff, "403").id,
            "room_type": "triple",
        })

def test_staff_cannot_verify_or_edit_verified_jamaah(self):
    jamaah = self._jamaah_as(self.staff, "404")
    jamaah.with_user(self.staff).write({
        "passport_number": "SEC-PASSPORT-404",
        "passport_expiry": "2030-01-01",
        "ktp_file": b"synthetic-ktp",
        "ktp_filename": "ktp-404.pdf",
        "passport_file": b"synthetic-passport",
        "passport_filename": "passport-404.pdf",
    })
    jamaah.with_user(self.staff).action_submit_documents()
    with self.assertRaises(AccessError):
        jamaah.with_user(self.staff).action_verify_documents()
    jamaah.with_user(self.manager).action_verify_documents()
    with self.assertRaises(AccessError):
        jamaah.with_user(self.staff).write({"birth_place": "Bandung"})

def test_finance_reads_travel_transaction_but_cannot_mutate_it(self):
    order, participant = self._draft_booking_as(self.staff, "405")
    finance_order = order.with_user(self.finance)
    self.assertEqual(finance_order.participant_count, 1)
    self.assertEqual(participant.with_user(self.finance).jamaah_id.nik, "SEC-NIK-405")
    self.assertEqual(participant.sale_line_id.with_user(self.finance).price_unit, 30_000_000)
    self.assertFalse(self.finance.has_group("sales_team.group_sale_salesman"))
    with self.assertRaises(AccessError):
        finance_order.write({"client_order_ref": "DENIED"})
    with self.assertRaises(AccessError):
        participant.with_user(self.finance).write({"room_type": "double"})
    with self.assertRaises(AccessError):
        participant.jamaah_id.with_user(self.finance).unlink()
    with self.assertRaises(AccessError):
        participant.sale_line_id.with_user(self.finance).unlink()

def test_finance_cannot_create_phase_two_records(self):
    order, participant = self._draft_booking_as(self.staff, "408")
    jamaah_values = {
        "partner_id": self.env["res.partner"].create({"name": "Finance Denied"}).id,
        "nik": "SEC-NIK-408-FIN",
        "birth_place": "Jakarta",
        "birth_date": "1990-01-01",
        "gender": "female",
        "emergency_contact_name": "Emergency",
        "emergency_contact_phone": "+628130000408",
    }
    with self.assertRaises(AccessError):
        self.env["travel.jamaah"].with_user(self.finance).create(jamaah_values)
    with self.assertRaises(AccessError):
        self.env["sale.order"].with_user(self.finance).create({
            "partner_id": self.buyer.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        })
    with self.assertRaises(AccessError):
        self.env["travel.booking.participant"].with_user(self.finance).create({
            "order_id": order.id,
            "jamaah_id": participant.jamaah_id.id,
            "room_type": "double",
        })
    with self.assertRaises(AccessError):
        self.env["sale.order.line"].with_user(self.finance).create({
            "order_id": order.id,
            "product_id": self.package.product_id.id,
            "product_uom_qty": 1,
        })

def test_manager_can_correct_confirmed_participant_and_change_is_audited(self):
    order, participant = self._draft_booking_as(self.manager, "406")
    order.with_user(self.manager).action_confirm()
    participant.with_user(self.manager).write({
        "room_type": "double",
        "unit_price": 36_000_000,
    })
    self.assertEqual(participant.sale_line_id.price_unit, 36_000_000)
    self.assertTrue(order.message_ids.filtered(
        lambda message: "Override harga participant" in (message.body or "")
    ))

def test_internal_user_and_finance_do_not_gain_unrelated_sales_access(self):
    travel_order, participant = self._draft_booking_as(self.staff, "407")
    unrelated_owner = self._create_user("phase2-unrelated-owner", "group_travel_staff")
    non_travel = self.env["sale.order"].create({
        "partner_id": self.buyer.id,
        "user_id": unrelated_owner.id,
    })
    with self.assertRaises(AccessError):
        travel_order.with_user(self.internal).read(["name"])
    with self.assertRaises(AccessError):
        participant.with_user(self.internal).read(["jamaah_id"])
    with self.assertRaises(AccessError):
        participant.jamaah_id.with_user(self.internal).read(["nik"])
    self.assertEqual(travel_order.with_user(self.finance).name, travel_order.name)
    self.assertEqual(participant.with_user(self.finance).jamaah_id, participant.jamaah_id)
    with self.assertRaises(AccessError):
        non_travel.with_user(self.finance).read(["name"])
    with self.assertRaises(AccessError):
        non_travel.with_user(self.staff).read(["name"])
```

Coverage that these methods must preserve:

```text
Staff:
- has sales_team.group_sale_salesman through implication;
- creates/reads/writes a draft travel quotation and Jamaah;
- sees another Staff user's travel booking;
- supplied create price cannot affect the snapshot; explicit price write is denied;
- cannot mutate/add/remove participant after confirmation;
- cannot verify Jamaah documents;
- cannot edit a verified Jamaah profile.

Finance:
- reads all travel booking headers, participant, generated lines, and Jamaah;
- cannot create/write/unlink Jamaah, participant, travel sale order, or line;
- does not receive Sales User through group implication in Phase 2.

Manager:
- retains all Phase 1 CRUD;
- verifies documents;
- corrects confirmed participant identity/room/price;
- correction is visible in Chatter.

Ordinary internal user:
- cannot read travel.jamaah or travel.booking.participant;
- cannot read a travel booking through the Travel action/rule.

Scope boundary:
- custom Travel record rules allow all travel bookings only;
- they do not grant Finance or ordinary internal users read access to an unrelated non-travel Sales Order.
```

Use `with_user()` for every positive and negative ORM operation. For all expected denials, assert `AccessError` or the exact custom `UserError`, not a broad exception.

- [ ] **Step 2: Run focused tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBookingSecurity --log-level=test
```

Expected: at least one access/rule assertion fails before final ACL and record-rule corrections.

- [ ] **Step 3: Implement precise ACLs and record rules**

Keep the model ACLs from Tasks 1 and 4. Add Finance read-only ACLs for standard Sales models:

```csv
access_sale_order_travel_finance,sale.order.travel.finance,sale.model_sale_order,group_travel_finance,1,0,0,0
access_sale_order_line_travel_finance,sale.order.line.travel.finance,sale.model_sale_order_line,group_travel_finance,1,0,0,0
```

Add group record rules in `travel_security.xml`:

```xml
<record id="rule_travel_booking_all_roles" model="ir.rule">
    <field name="name">Travel roles: all travel bookings</field>
    <field name="model_id" ref="sale.model_sale_order"/>
    <field name="domain_force">[('is_travel_booking', '=', True)]</field>
    <field name="groups" eval="[(4, ref('group_travel_staff')), (4, ref('group_travel_finance'))]"/>
</record>

<record id="rule_travel_booking_line_all_roles" model="ir.rule">
    <field name="name">Travel roles: all travel booking lines</field>
    <field name="model_id" ref="sale.model_sale_order_line"/>
    <field name="domain_force">[('order_id.is_travel_booking', '=', True)]</field>
    <field name="groups" eval="[(4, ref('group_travel_staff')), (4, ref('group_travel_finance'))]"/>
</record>
```

Retain Odoo's global multi-company rules. Do not create an "own booking" rule. Do not use a blank `group_id` ACL.

- [ ] **Step 4: Run focused and full GREEN verification**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelBookingSecurity --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh --log-level=test
```

Expected: the exact matrix passes from real role users; Manager implication does not create false failures; ordinary Sales Orders are not exposed by custom Finance/Travel rules; all Phase 1 tests stay green.

- [ ] **Step 5: Review security diff before commit**

```bash
git diff -- addons/travel_umroh/security \
  addons/travel_umroh/tests/test_booking_security.py
git diff --check
```

Expected: no `sudo()` authorization shortcut, no portal rule, no blank-group ACL, and no permission for Finance to mutate transactions.

- [ ] **Step 6: Checkpoint and commit**

```bash
git add addons/travel_umroh/security \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/tests/test_booking_security.py
git commit -m "test: enforce phase two travel role security"
```

Checkpoint: role enforcement is proven on the server before any Phase 2 menu/view is trusted.

---

### Task 8: Add Booking, Jamaah, Smart Buttons, and Standard Views

**Files:**

- Create: `addons/travel_umroh/views/travel_jamaah_views.xml`
- Create: `addons/travel_umroh/views/travel_booking_views.xml`
- Modify: `addons/travel_umroh/models/travel_jamaah.py`
- Modify: `addons/travel_umroh/views/travel_departure_views.xml`
- Modify: `addons/travel_umroh/views/travel_menus.xml`
- Modify: `addons/travel_umroh/__manifest__.py`
- Create: `addons/travel_umroh/tests/test_views.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

**Interfaces:**

- Consumes: all model actions/fields and `sale.view_order_form`.
- Produces: actions `action_travel_booking` and `action_travel_jamaah`; visible menu order Bookings/Jamaah/Paket/Keberangkatan; composed form/list/search interfaces with no custom JavaScript.

- [ ] **Step 1: Write failing composed-view and action tests**

Create `TestTravelPhaseTwoViews` using `lxml.etree` and a real Staff user:

```python
from lxml import etree

from odoo import Command
from odoo.tests import tagged

from .common import TravelBookingCase


@tagged("post_install", "-at_install")
class TestTravelPhaseTwoViews(TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env["res.users"].create({
            "name": "Phase 2 View Staff",
            "login": "phase2-view-staff",
            "email": "phase2-view-staff@example.test",
            "groups_id": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref("travel_umroh.group_travel_staff").id,
            ])],
        })
```

Required assertions:

```python
def test_booking_action_is_scoped_and_defaults_travel_flag(self):
    action = self.env.ref("travel_umroh.action_travel_booking").read()[0]
    self.assertIn("is_travel_booking", action["domain"])
    self.assertIn("default_is_travel_booking", action["context"])

def test_staff_composed_sale_form_contains_one_participant_page_without_debug(self):
    arch = self.env["sale.order"].with_user(self.staff).with_context(debug=False).get_view(
        view_id=self.env.ref("sale.view_order_form").id,
        view_type="form",
    )["arch"]
    root = etree.fromstring(arch.encode())
    self.assertEqual(len(root.xpath("//page[@name='travel_participants']")), 1)
    self.assertEqual(len(root.xpath("//field[@name='participant_ids']")), 1)

def test_jamaah_binary_fields_use_filename_attributes(self):
    arch = self.env.ref("travel_umroh.view_travel_jamaah_form").arch_db
    root = etree.fromstring(arch.encode())
    self.assertEqual(
        root.xpath("//field[@name='ktp_file']/@filename"),
        ["ktp_filename"],
    )
    self.assertEqual(
        root.xpath("//field[@name='passport_file']/@filename"),
        ["passport_filename"],
    )
```

Also assert:

- `action_travel_jamaah` opens `list,form`.
- Booking participant page is invisible when `is_travel_booking` is false.
- Standard Order Lines page is invisible for travel bookings and remains available for non-travel orders.
- Manager-only verification controls contain `groups="travel_umroh.group_travel_manager"`.
- Departure form contains `booking_count` smart button and a readonly Bookings page.
- XML uses `<list>`, with no `<tree>` root.

- [ ] **Step 2: Run view tests to prove RED**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelPhaseTwoViews --log-level=test
```

Expected: missing external IDs/views/actions.

- [ ] **Step 3: Add Jamaah views**

`travel_jamaah_views.xml` must define:

- list columns: partner, NIK, phone, birth date, age, passport number, document status;
- form sections: contact/address, identity, passport, emergency contact, documents, verification metadata;
- header buttons `action_submit_documents` and Manager-only `action_verify_documents` with state visibility;
- `ktp_file filename="ktp_filename"` and `passport_file filename="passport_filename"`;
- Chatter;
- search by partner/name, NIK, passport, phone; document-status filters and grouping;
- action `action_travel_jamaah` with `view_mode="list,form"`.

In `travel_jamaah.py`, add:

```text
participant_ids: One2many(travel.booking.participant, jamaah_id, readonly)
booking_count: Integer(compute as count of distinct participant_ids.order_id)
action_view_bookings(): sale.order list/form action with domain [('participant_ids.jamaah_id', '=', self.id)]
```

Show `booking_count` as a smart button calling `action_view_bookings()`. No report is added.

- [ ] **Step 4: Add the Booking action and Sales form extension**

`travel_booking_views.xml` must:

- inherit `sale.view_order_form`;
- include hidden `is_travel_booking`, `can_edit_travel_participants`, and `can_override_travel_price` fields;
- insert Departure and related Package after `partner_id`, visible only for travel bookings;
- enforce UI domain `[('state', '=', 'open'), ('active', '=', True)]` on Departure;
- add `travel_participants` notebook page with editable participant list/form fields Jamaah, room type, snapshot price, currency, and line reference;
- set participant page readonly when `not can_edit_travel_participants`;
- make `unit_price` readonly unless `can_override_price` is true; Python remains authoritative;
- add `action_refresh_travel_prices` button visible only in draft/sent travel quotations;
- hide the standard `order_lines` page when `is_travel_booking` is true so users cannot edit generated lines through the UI;
- show `amount_total` on the travel participant page;
- retain standard quotation Send/Confirm/Cancel buttons and Chatter;
- define `action_travel_booking` on `sale.order` with domain `[('is_travel_booking', '=', True)]` and context `{'default_is_travel_booking': True}`.

Do not clone the Sales form. Inherit it so standard Odoo confirmation, taxes, totals, invoices, and Chatter remain available.

- [ ] **Step 5: Extend Departure views and the menu tree**

Add to the existing Departure form:

- smart button calling `action_view_bookings` with `booking_count`;
- readonly Bookings notebook page listing Sales Order reference, buyer, participant count, amount total, salesperson, and Sales state.

Update menus, preserving external IDs and existing sequences:

```text
Travel Umroh
├── Booking          sequence 10, all Travel roles
├── Jamaah           sequence 20, all Travel roles
├── Paket            sequence 30
├── Keberangkatan    sequence 40
└── Konfigurasi      sequence 90, Manager only
```

Load view files in manifest dependency order:

```python
"views/res_users_views.xml",
"views/travel_master_views.xml",
"views/travel_package_views.xml",
"views/travel_jamaah_views.xml",
"views/travel_booking_views.xml",
"views/travel_departure_views.xml",
"views/travel_menus.xml",
```

- [ ] **Step 6: Run focused view, full suite, and upgrade tests**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable \
  --test-tags /travel_umroh:TestTravelPhaseTwoViews --log-level=test

docker compose run --rm odoo --stop-after-init -d travel_umroh_phase2_test \
  -u travel_umroh --test-enable --test-tags /travel_umroh --log-level=test
```

Expected: view inheritance resolves under Odoo 18; no missing field/external ID; Staff and Manager composed forms contain the Phase 2 interface with `debug=False`; full suite has zero failures.

- [ ] **Step 7: Perform manual UI smoke on the development database**

Upgrade `travel_umroh_dev` and restart Odoo without deleting or recreating the database:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_dev \
  -u travel_umroh \
  --log-level=info
docker compose up -d odoo
docker compose ps
```

Expected: upgrade exits `0`; the long-running `odoo` and `db` services are healthy/running. Then validate without Developer Mode:

1. Manager creates two synthetic Jamaah profiles, uploads synthetic text files, submits, and verifies documents.
2. Staff opens **Travel Umroh → Booking**, selects a buyer who is not a participant, selects an open departure, and adds both Jamaah with different room types.
3. Confirm two generated snapshot prices and quotation total.
4. Manager changes one departure numeric room price; quotation remains unchanged until Staff clicks **Refresh Harga** while draft.
5. Staff confirms the quotation; state becomes Sales Order and departure quota is unchanged.
6. Staff cannot edit participant/price after confirmation.
7. Manager corrects one participant snapshot; generated line and Chatter update.
8. Finance can read Booking/Jamaah but cannot edit.
9. Regular Sales quotation remains visually and behaviorally unchanged.

Use only synthetic data and do not delete existing development data.

- [ ] **Step 8: Checkpoint and commit**

```bash
git diff --check
git add addons/travel_umroh/__manifest__.py \
  addons/travel_umroh/models/travel_jamaah.py \
  addons/travel_umroh/tests/__init__.py \
  addons/travel_umroh/tests/test_views.py \
  addons/travel_umroh/views/travel_booking_views.xml \
  addons/travel_umroh/views/travel_departure_views.xml \
  addons/travel_umroh/views/travel_jamaah_views.xml \
  addons/travel_umroh/views/travel_menus.xml
git commit -m "feat: add phase two booking and jamaah views"
```

Checkpoint: complete Phase 2 back-office flow is demonstrable; no Phase 3/5 interface appears.

---

## Phase 2 Final Verification and Review Checkpoint

This is a verification checkpoint, not another implementation task. Do not add behavior while performing it.

- [ ] **Create a brand-new acceptance database and prove clean install**

First prove the database name is absent without deleting anything:

```bash
docker compose exec -T db psql -U odoo -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = 'travel_umroh_phase2_acceptance';"
```

Expected: empty output. If it already exists, choose `travel_umroh_phase2_acceptance_02`; do not drop it.

Run:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_acceptance \
  -i travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: exit `0`; zero failed/error tests; no registry, XML, ACL, constraint, or external-ID error.

- [ ] **Prove module upgrade with the final tree**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_acceptance \
  -u travel_umroh \
  --log-level=info
```

Expected: exit `0`; module version `18.0.2.0.0` is installed.

- [ ] **Run focused security regression once more**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase2_acceptance \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelBookingSecurity \
  --log-level=test
```

Expected: Staff, Finance, Manager, and ordinary-internal negative/positive cases all pass.

- [ ] **Review scope and repository state**

```bash
git status --short
git diff --check
git log --oneline --decorate -15
rg -n "seat_reserved|reserved_seats|remaining_seats|travel_payment_state|account\.move|http\.route|request\.env|portal" addons/travel_umroh
```

Expected:

- clean worktree after focused commits;
- no whitespace errors;
- no implementation of reservation/payment/accounting/portal;
- any `portal` match is only an existing dependency comment/test assertion, not a model/controller/view;
- no real identity data or credentials.

- [ ] **Request code and security review**

Review the full Phase 2 diff against the pre-Phase-2 base. Required review questions:

1. Can Staff change snapshot price through participant, generated line, order-line commands, RPC, import, or a spoofed context?
2. Can Finance mutate Sales/Jamaah data despite read-only requirements?
3. Can ordinary internal users or unrelated Sales users read `travel.jamaah` or participant records?
4. Does Manager correction always synchronize participant and line and write a non-sensitive Chatter note?
5. Can confirmation change quota or introduce Phase 3 behavior?
6. Are standard non-travel Sales Orders unaffected?
7. Are binary documents stored as attachments and excluded from audit bodies?

Resolve validated findings with a failing regression test first, then rerun the full acceptance suite.

- [ ] **Report Phase 2 evidence and stop**

Report:

- files created/modified;
- focused and full test counts/results;
- clean install and upgrade evidence;
- Staff/Finance/Manager matrix;
- manual demo result;
- remaining risks;
- explicit proof that quotation confirmation did not reserve seats;
- explicit statement that payment, quota, cancellation/refund, reporting, demo data, and portal remain unimplemented.

Stop at the Phase 2 checkpoint. Do not start Phase 3 and do not draft Phase 3 code. A Phase 3 implementation plan must be written later against the code that actually survives this checkpoint.

## Phase 2 Requirement-to-Task Traceability

| Roadmap/Design requirement | Implemented and proven in |
|---|---|
| One-to-one Jamaah profile over `res.partner` | Task 1 |
| Identity, emergency contact, optional passport | Task 1 |
| KTP/passport attachments and verification metadata | Task 2 |
| `sale.order` as Booking/Quotation | Task 3 |
| Open departure selection and package/service-product reuse | Tasks 3–4 |
| Multi-participant booking; buyer may differ from Jamaah | Task 4 |
| One participant creates one Sales line | Task 4 |
| Automatic room price and quotation total | Task 4 |
| Stable snapshot and draft refresh | Task 5 |
| Generated-line anti-bypass | Task 5 |
| Confirmation does not reserve a seat | Task 6 |
| Staff lock and Manager audited correction | Task 6 |
| Staff/Finance/Manager server security | Task 7 |
| Booking/Jamaah forms, menus, smart buttons, Chatter | Task 8 |
| Clean install, upgrade, full tests, security review | Final checkpoint |

## Explicitly Deferred Beyond Phase 2

- `travel_payment_state`, DP invoice, posted-payment detection, and paid/refunded computation.
- `seat_reserved`, `seat_reserved_at`, `reserved_seats`, `remaining_seats`, `is_full`, concurrency locks, and overbooking.
- Post-DP cancellation, seat release, Credit Note, and refund.
- Departure `departed`/`done` document gate.
- Reporting/pivot/graph, manifest, demo data, and end-to-end accounting acceptance.
- Portal controllers, QWeb, portal upload, portal record rules, public/self-registration, WhatsApp, payment gateway, waitlist, room allocation, multi-company, and OWL dashboards.
