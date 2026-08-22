# Phase 3 Accounting, Quota, Cancellation, and Refund Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect confirmed Travel Umroh bookings to standard Odoo 18 down-payment, invoicing, payment, credit-note, and refund flows while reserving and releasing departure seats exactly once, preventing concurrent overbooking, and enforcing the verified-document departure gate.

**Architecture:** Keep `sale.order` as the booking and standard `account.move` records as the accounting source of truth. A paid, posted, down-payment-only customer invoice triggers an idempotent reservation through the standard reconciliation path; reservation serializes on the `travel.departure` database row before counting reserved participants. Seat usage remains derived from `sale.order.seat_reserved`, cancellation remains the standard Sales cancellation state plus a Manager-only reason wizard after a posted DP exists, and refunds remain standard Odoo credit notes/payments. No custom payment, invoice, quota-ledger, or refund transaction model is introduced.

**Tech Stack:** Odoo 18 Community, Python ORM, PostgreSQL row locking, XML views/security, Odoo `TransactionCase` and `BaseCase`, Docker Compose, standard `sale_management` and `account` modules.

**Spec:** `Requirement_Modul_Travel_Umroh.md`, `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md`, `docs/superpowers/plans/2026-08-20-travel-umroh-roadmap.md` Phase 3, and the Phase 2 checkpoint in `docs/superpowers/plans/2026-08-21-phase-2-jamaah-booking-quotation.md`.

## Global Constraints

- Implement only roadmap Phase 3. Do not add Phase 4 reports/demo data, Phase 5 portal, WhatsApp, payment gateway, manifest processing, custom accounting ledgers, or any other deferred feature.
- Preserve the actual Phase 2 architecture: `sale.order` is the booking, `travel.booking.participant` owns participant snapshots, and each participant mirrors to one protected standard `sale.order.line`.
- Use standard Odoo `sale.advance.payment.inv`, `account.move`, `account.payment.register`, and `account.move.reversal`. Do not create custom invoice, payment, credit-note, or refund models.
- A quotation in `draft`/`sent` and a confirmed Sales Order in `sale` consume zero seats until a posted down-payment-only invoice has zero residual through a real Odoo reconciliation/payment flow.
- A final invoice that happens to contain a deducted down-payment line is not a DP trigger. A valid trigger invoice has at least one linked `sale.order.line.is_downpayment`, no linked non-down-payment product line, is `posted`, is `out_invoice`, has zero residual, and is not reversed.
- `seat_reserved` is the idempotency marker. `travel.departure.reserved_seats` is derived from participant counts of non-cancelled bookings whose `seat_reserved` is true; do not decrement a mutable quota counter.
- Reservation and release are private underscore methods only. Do not expose a public RPC method or trust a client-supplied context key to bypass guards.
- Use a Python `ContextVar` only for the trusted call stack in which the standard down-payment wizard creates `is_downpayment` Sales lines. A request context dictionary is not an authorization boundary.
- Before checking availability, reservation must acquire `SELECT ... FOR UPDATE` on the exact `travel_departure` row and recalculate usage inside that transaction. Do not use an unlocked computed field as the final overbooking check.
- The post-DP cancellation boundary is the existence of at least one linked posted customer invoice. Before that boundary, standard Sales cancellation remains available; after it, only Manager can initiate cancellation through the reason wizard. Seat release happens only when `seat_reserved` is true.
- `travel_payment_state` is computed and read-only: `unpaid`, `dp`, `paid`, or `refunded`. Only linked, non-cancelled customer invoices/credit notes are considered; draft accounting moves cannot make a booking paid or refunded.
- A booking is `paid` only when standard Sales reports the original lines fully invoiced, the posted invoice total net of posted refunds equals the order total, and every posted invoice/refund residual is zero.
- A booking is `refunded` only when posted refunds fully offset posted invoices and every posted invoice/refund residual is zero. Creating an unpaid credit note alone is insufficient.
- `travel_state` is computed from the departure lifecycle to avoid a second independently writable workflow: `departed` and `done` mirror those departure states; every other active booking state displays `registered`. Sales cancellation remains `sale.order.state = cancel`.
- Active participants for the departure document gate are participants on bookings in `sale` with `seat_reserved = True`. Cancelled or unreserved quotations must not block departure.
- Manager implies Staff and Finance. Finance must imply standard `account.group_account_invoice`, but Finance must remain unable to mutate bookings, participants, Jamaah, prices, departures, or ordinary Sales Orders. Add server checks because standard accounting ACLs grant write access to `sale.order` and `sale.order.line`.
- Preserve System Administrator behavior through Odoo's normal admin bypass; do not create a duplicate custom administrator role.
- All business checks must run server-side and use Indonesian-friendly business errors/audit messages. Button visibility is usability, not security.
- Never drop a database, Docker volume, or development data. Commands below use dedicated test databases. If a named acceptance database already exists, choose the next unused suffix instead of deleting it.
- Follow test-first order in every task: add/import the test, run it and capture the expected RED failure, implement the minimum behavior, rerun targeted tests, then run the full module suite before the focused commit.

## Actual Phase 2 Baseline and File Map

The implementation agent must verify these facts before editing:

- `addons/travel_umroh/__manifest__.py` is version `18.0.2.0.0` and already depends on `sale_management` and `account`.
- `addons/travel_umroh/models/sale_order.py` already protects direct Sales state writes with a `ContextVar`, validates participant-generated lines at confirmation, keeps confirmation quota-neutral, and blocks cancelled travel bookings from returning to draft.
- `addons/travel_umroh/models/sale_order_line.py` blocks every ordinary line creation on a travel order. Phase 3 must narrowly allow only the trusted standard DP wizard call stack.
- `addons/travel_umroh/models/travel_departure.py` already declares `draft/open/departed/done/cancelled`, but only implements `action_open()` and `action_cancel()`; no seat fields or departed/done actions exist.
- `addons/travel_umroh/security/travel_security.xml` makes Staff a standard Sales User, Finance only an internal user, and Manager imply Staff plus Finance.
- `addons/travel_umroh/security/ir.model.access.csv` gives Finance custom read-only access to travel Sales Orders/lines. Standard `account.group_account_invoice`, when added, also grants Sales Order/line write ACLs, so model guards are mandatory.
- Standard Odoo 18 `sale.advance.payment.inv` creates `is_downpayment=True` section/product Sales lines and has an ACL only for `sales_team.group_sale_salesman`.
- Standard Odoo 18 payment registration reconciles move lines. `account.move.line.reconcile()` is therefore the integration seam for detecting a paid DP without writing side effects inside a computed field.
- The current Phase 2 suite has 120 post-install test methods (140 Odoo test stats at its checkpoint). Record the actual baseline again before Phase 3 work; do not hard-code a new final count until implementation is complete.

## Verification Database Convention

Use one persistent implementation test database and one unused clean-install acceptance database:

```bash
docker compose exec -T db psql -U odoo -d postgres -Atc \
  "SELECT datname FROM pg_database WHERE datname IN ('travel_umroh_phase3_test', 'travel_umroh_phase3_acceptance');"
```

Expected: either no rows or only databases that already exist. Do not drop them. If `travel_umroh_phase3_test` does not exist, initialize it once:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -i base,travel_umroh \
  --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: module installs, Phase 2 suite reports `0 failed, 0 error`, and the database remains available for `-u travel_umroh` runs. If it already exists, use `-u travel_umroh` and first prove the Phase 2 baseline remains green.

---

## Task 1: Secure the Standard Odoo Accounting Entry Point for Travel Finance

**Purpose:** Give Finance the standard invoice/payment capability required by the design without reopening Phase 2 booking mutations or letting Staff create travel invoices.

**Files:**

- Modify: `addons/travel_umroh/__manifest__.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/models/sale_advance_payment_inv.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/sale_order_line.py`
- Modify: `addons/travel_umroh/models/res_users.py`
- Modify: `addons/travel_umroh/security/travel_security.xml`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/tests/common.py`
- Create: `addons/travel_umroh/tests/test_phase3_security.py`

- [ ] **Step 1: Add reusable accounting fixtures and role users**

Add `TravelAccountingCase` after `TravelBookingCase` in `tests/common.py` using Odoo's own accounting fixture mixin:

```python
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TravelAccountingCase(AccountTestInvoicingCommon, TravelBookingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ProductCommon also owns a service_product fixture. Always configure
        # the actual product already linked to the travel package.
        cls.travel_service_product = cls.package.product_id
        cls.travel_service_product.product_tmpl_id.property_account_income_id = (
            cls.company_data["default_account_revenue"]
        )
        cls.staff = cls._create_role_user("phase3-staff", "group_travel_staff")
        cls.finance = cls._create_role_user("phase3-finance", "group_travel_finance")
        cls.manager = cls._create_role_user("phase3-manager", "group_travel_manager")

    @classmethod
    def _create_role_user(cls, login, group_xmlid):
        return cls.env["res.users"].create({
            "name": login,
            "login": login,
            "email": f"{login}@example.test",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
            "groups_id": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref(f"travel_umroh.{group_xmlid}").id,
            ])],
        })

    def _confirmed_booking(self, suffix, participant_count=1):
        order = self.env["sale.order"].with_user(self.staff).create({
            "partner_id": self.buyer.id,
            "user_id": self.staff.id,
            "is_travel_booking": True,
            "departure_id": self.departure.id,
        })
        for index in range(participant_count):
            self.env["travel.booking.participant"].with_user(self.staff).create({
                "order_id": order.id,
                "jamaah_id": self._create_jamaah(f"{suffix}-{index}").id,
                "room_type": "quad",
            })
        order.with_user(self.staff).action_confirm()
        return order
```

Also add helpers in this class in Task 2 for standard down payment and payment registration; do not duplicate accounting setup in individual test files.

- [ ] **Step 2: Write failing role and wizard security tests**

Create `test_phase3_security.py`, import it from `tests/__init__.py`, and add `TestPhaseThreeAccountingSecurity(TravelAccountingCase)` tagged `post_install`, `-at_install`.

Tests must prove:

```python
def test_finance_gets_standard_billing_but_not_sales_user(self):
    self.assertTrue(self.finance.has_group("account.group_account_invoice"))
    self.assertFalse(self.finance.has_group("sales_team.group_sale_salesman"))
    self.env["sale.advance.payment.inv"].with_user(self.finance).check_access("create")

def test_staff_cannot_run_accounting_wizard_for_travel_booking(self):
    order = self._confirmed_booking("SEC-STAFF")
    wizard = self.env["sale.advance.payment.inv"].with_user(self.staff).with_context(
        active_model="sale.order", active_id=order.id, active_ids=order.ids
    ).create({"advance_payment_method": "percentage", "amount": 20})
    with self.assertRaises(AccessError):
        wizard.create_invoices()

def test_finance_cannot_mutate_booking_despite_standard_account_acl(self):
    order = self._confirmed_booking("SEC-FIN")
    line = order.order_line.filtered(lambda item: not item.display_type)
    with self.assertRaises(AccessError):
        order.with_user(self.finance).write({"client_order_ref": "DENIED"})
    with self.assertRaises(AccessError):
        line.with_user(self.finance).write({"price_unit": 1})
    with self.assertRaises(AccessError):
        line.with_user(self.finance).unlink()

def test_finance_cannot_create_sales_order_or_ordinary_line(self):
    with self.assertRaises(AccessError):
        self.env["sale.order"].with_user(self.finance).create({
            "partner_id": self.buyer.id,
        })
```

Retain the existing Phase 2 assertions that Finance cannot read unrelated ordinary Sales Orders and cannot mutate Jamaah/participants/master data.

- [ ] **Step 3: Run RED security tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseThreeAccountingSecurity \
  --log-level=test
```

Expected RED: Finance lacks the accounting group/wizard ACL; or, once that group is provisionally added, Finance can mutate Sales Orders through Odoo's standard accounting ACL. The test must fail for the missing behavior, not because fixtures cannot create accounts/journals.

- [ ] **Step 4: Add accounting role implication and inverse regression coverage**

In `travel_security.xml`, make `group_travel_finance` imply both `base.group_user` and `account.group_account_invoice`. Keep Manager implying Staff and Finance.

Extend existing role-selector tests in `test_security.py` or the new Phase 3 security file to prove:

- selecting Finance adds `account.group_account_invoice` and does not add Sales User;
- selecting Manager adds both accounting and Sales capabilities through implied groups;
- switching Finance to Staff removes the accounting implication when no unrelated group grants it;
- an unrelated explicitly assigned Odoo group remains intact.

Do not manually link/unlink every accounting sub-group in `res_users.py`; rely on the XML implication and test the inverse's resulting membership.

- [ ] **Step 5: Grant Finance access only to the standard transient invoice wizard**

Add this ACL, matching the standard wizard's transient behavior:

```csv
access_sale_advance_payment_inv_travel_finance,sale.advance.payment.inv.travel.finance,sale.model_sale_advance_payment_inv,group_travel_finance,1,1,1,0
```

Do not grant Staff any custom accounting ACL.

- [ ] **Step 6: Implement a non-spoofable standard wizard bridge**

In `models/sale_advance_payment_inv.py`:

- inherit `sale.advance.payment.inv`;
- define a module-level `ContextVar(default=False)` plus context manager for trusted DP Sales-line creation;
- override `_create_invoices(self, sale_orders)`;
- leave all-non-travel invocations unchanged;
- reject mixed travel/non-travel batches with `UserError`;
- for any travel order, require Travel Finance, Travel Manager (via Finance implication), or System Administrator, otherwise raise `AccessError`;
- wrap only `super()._create_invoices(sale_orders)` in the trusted `ContextVar` when the method is `percentage` or `fixed`;
- allow the `delivered` method through the same role check but without enabling Sales-line creation.

In `sale_order_line.create()`:

- continue calling `check_access("create")`;
- permit a travel-order line only when the trusted `ContextVar` is set and every value has `is_downpayment=True`, no `travel_participant_id`, and belongs to a confirmed travel order;
- do not inspect a context key supplied by RPC;
- retain the Phase 2 error for every other ordinary line.

Add a test that `.with_context(_travel_allow_downpayment_line=True)` still cannot forge a line.

- [ ] **Step 7: Restore Finance read-only booking semantics at model level**

Add a helper in `sale_order.py` and `sale_order_line.py` that identifies a Finance-only actor:

```python
def _is_travel_finance_only(self):
    user = self.env.user
    return (
        not user._is_admin()
        and user.has_group("travel_umroh.group_travel_finance")
        and not user.has_group("travel_umroh.group_travel_staff")
    )
```

For that actor:

- reject public `sale.order.create`, `write`, and `unlink` with `AccessError`;
- reject public `sale.order.line.create`, `write`, and `unlink`, except the trusted DP line creation path;
- leave Manager unchanged because Manager also has Staff;
- leave non-travel Sales users unchanged;
- make no `sudo()` escape hatch.

Add `unlink()` overrides because the standard accounting ACL does not grant Sales unlink today, but the server contract must stay safe if upstream ACLs change.

- [ ] **Step 8: Bump the module version and run GREEN tests**

Bump manifest version from `18.0.2.0.0` to `18.0.3.0.0` and import the new model/test.

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseThreeAccountingSecurity \
  --log-level=test

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelBookingSecurity,/travel_umroh:TestPhaseTwoHardening \
  --log-level=test
```

Expected GREEN: Finance has Billing access and can instantiate the standard invoice wizard, Staff is rejected for travel accounting, Manager remains operational, Finance cannot mutate any Sales/travel business record, the context spoof test is rejected, and all Phase 2 security tests remain green.

- [ ] **Step 9: Checkpoint and focused commit**

```bash
git status --short
git diff --check
git add addons/travel_umroh
git commit -m "feat: secure travel accounting entry points"
```

Checkpoint: the accounting entry point is authorized and hardened, but payment state and quota behavior do not exist yet.

---

## Task 2: Compute Read-only Travel Payment State from Standard Accounting Records

**Files:**

- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/tests/common.py`
- Create: `addons/travel_umroh/tests/test_phase3_accounting.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

- [ ] **Step 1: Add exact standard-flow test helpers**

Add these helpers to `TravelAccountingCase`:

```python
def _create_invoice_wizard(self, order, method, **values):
    return self.env["sale.advance.payment.inv"].with_user(self.finance).with_context(
        active_model="sale.order",
        active_id=order.id,
        active_ids=order.ids,
        default_journal_id=self.company_data["default_journal_sale"].id,
    ).create({"advance_payment_method": method, **values})

def _create_downpayment_invoice(self, order, method="percentage", amount=20):
    values = {"amount": amount} if method == "percentage" else {"fixed_amount": amount}
    self._create_invoice_wizard(order, method, **values).create_invoices()
    return order.invoice_ids.sorted("id")[-1]

def _post_and_pay(self, invoice):
    invoice.with_user(self.finance).action_post()
    self.env["account.payment.register"].with_user(self.finance).with_context(
        active_model="account.move",
        active_ids=invoice.ids,
    ).create({
        "journal_id": self.company_data["default_journal_bank"].id,
    }).action_create_payments()
    invoice.invalidate_recordset(["amount_residual", "payment_state"])
    return invoice
```

The helpers must call public standard Odoo methods. Do not mark invoice residuals or payment state manually.

- [ ] **Step 2: Write failing payment-state tests**

Create and import `test_phase3_accounting.py` with `TestTravelPaymentState(TravelAccountingCase)` and tests for:

1. A confirmed booking with no posted customer invoice is `unpaid`.
2. A draft DP invoice remains `unpaid`.
3. A posted unpaid percentage DP invoice is `dp`.
4. A partial payment remains `dp`.
5. A fully paid DP invoice remains `dp` because original participant lines are not fully invoiced.
6. A fixed down payment follows the same state rules.
7. An ordinary Sales Order has `travel_payment_state = False`.
8. Public `write({"travel_payment_state": "paid"})` raises `UserError` for Staff, Finance, and Manager.

For the partial-payment case, instantiate `account.payment.register` with an amount strictly below `invoice.amount_residual` and call `action_create_payments()`.

- [ ] **Step 3: Run RED payment-state tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState \
  --log-level=test
```

Expected RED: `sale.order` has no `travel_payment_state` field. Accounting fixtures and the secure wizard bridge must already work.

- [ ] **Step 4: Implement the computed selection and explicit write protection**

Add a non-stored, read-only selection on `sale.order`:

```python
travel_payment_state = fields.Selection(
    [
        ("unpaid", "Belum Bayar"),
        ("dp", "DP / Bayar Sebagian"),
        ("paid", "Lunas"),
        ("refunded", "Refunded"),
    ],
    string="Status Pembayaran Travel",
    compute="_compute_travel_payment_state",
    readonly=True,
)
```

The compute must:

- return `False` for non-travel orders;
- ignore moves in `draft` or `cancel`;
- split linked `order.invoice_ids` into posted `out_invoice` and posted `out_refund`;
- calculate invoice and refund totals separately in the booking currency;
- use `currency_id.is_zero()` / `compare_amounts()`, never raw float equality;
- set `refunded` when invoices and refunds exist, their net total is zero, and every posted move residual is zero;
- otherwise set `paid` when `invoice_status == "invoiced"`, posted invoice total net of refunds equals `amount_total`, and every posted move residual is zero;
- otherwise set `dp` when a posted customer invoice exists;
- otherwise set `unpaid`.

Depend on the linked invoice state, move type, amount total, amount residual/payment state, and Sales invoice status so a posted payment, credit note, or final invoice invalidates the UI value.

Add `travel_payment_state` to the explicitly protected Phase 3 fields in public `sale.order.write()` before calling `super()`.

- [ ] **Step 5: Run GREEN payment-state and regression tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState \
  --log-level=test

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected GREEN: all unpaid/DP scenarios match actual invoice and residual state; the field cannot be forged; the whole module suite has zero failures/errors.

- [ ] **Step 6: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/tests/common.py \
  addons/travel_umroh/tests/test_phase3_accounting.py \
  addons/travel_umroh/tests/__init__.py
git commit -m "feat: compute travel payment status"
```

Checkpoint: payment status is accounting-derived, but paying DP does not reserve seats until Task 3.

---

## Task 3: Derive Departure Capacity and Reserve Seats after a Paid DP

**Files:**

- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/models/account_move_line.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/travel_departure.py`
- Create: `addons/travel_umroh/tests/test_phase3_quota.py`
- Modify: `addons/travel_umroh/tests/test_phase3_accounting.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

- [ ] **Step 1: Write failing derived-capacity tests**

In `test_phase3_quota.py`, create `TestTravelQuota(TravelAccountingCase)` and prove:

- `reserved_seats == 0`, `remaining_seats == quota`, and `is_full is False` initially;
- draft and confirmed bookings do not alter any capacity field;
- creating or posting a DP invoice does not reserve;
- a partial DP payment does not reserve;
- full standard payment of a DP reserves all booking participants once;
- `seat_reserved_at` is populated on first reservation;
- replaying `_travel_reserve_seats()` returns false/no-op and does not change capacity or timestamp;
- a final invoice containing a deducted DP line is not itself classified as a DP-only trigger;
- lowering quota below `reserved_seats` raises `ValidationError`.

Also test direct writes to `seat_reserved` and `seat_reserved_at` are rejected for Staff, Finance, and Manager.

- [ ] **Step 2: Run RED capacity tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelQuota \
  --log-level=test
```

Expected RED: reservation/capacity fields and reconcile hook do not exist.

- [ ] **Step 3: Add idempotency fields and derived departure capacity**

On `sale.order`, add stored, read-only, copy-disabled fields:

```python
seat_reserved = fields.Boolean(default=False, readonly=True, copy=False, tracking=True)
seat_reserved_at = fields.Datetime(readonly=True, copy=False, tracking=True)
```

Protect both from public `write()`.

On `travel.departure`, add stored computed fields:

```python
reserved_seats = fields.Integer(compute="_compute_seat_capacity", store=True)
remaining_seats = fields.Integer(compute="_compute_seat_capacity", store=True)
is_full = fields.Boolean(compute="_compute_seat_capacity", store=True)
```

The compute sums `participant_count` only for bookings with `seat_reserved=True` and `state != "cancel"`; it sets `remaining_seats = quota - reserved_seats` and `is_full = remaining_seats <= 0`. Depend directly on `quota`, `booking_ids.seat_reserved`, `booking_ids.state`, and `booking_ids.participant_ids`.

Extend `_check_quota` so `quota < reserved_seats` is rejected. Keep the existing non-negative check.

- [ ] **Step 4: Implement the locked, private reservation primitive**

Add `sale.order._travel_reserve_seats()` with this exact contract:

- `ensure_one()`;
- require a travel order in `sale` with a departure and at least one participant;
- return `False` immediately if already reserved;
- flush `travel.departure.quota`, `sale.order.departure_id/seat_reserved/state`, and participant `order_id` before SQL;
- lock the exact departure row using a parameterized `SELECT id FROM travel_departure WHERE id = %s FOR UPDATE`;
- invalidate `seat_reserved` and recheck it after obtaining the lock;
- calculate current usage with one SQL `COUNT(travel_booking_participant.id)` joined to `sale_order`, filtered by the same departure, `seat_reserved = TRUE`, and `state != 'cancel'`;
- compare `needed = len(order.participant_ids)` to `available = departure.quota - current_usage`;
- if insufficient, raise `UserError` containing departure display name, available seats, and needed seats;
- otherwise call `super(SaleOrder, order).write({"seat_reserved": True, "seat_reserved_at": fields.Datetime.now()})` so no public bypass flag exists;
- post one Chatter note with participant count and departure;
- return `True` only for the first reservation.

The row lock and fresh SQL count are authoritative. `remaining_seats` is display data and must not be used as the final check.

- [ ] **Step 5: Detect a paid DP through standard reconciliation**

Create `models/account_move_line.py` and inherit `account.move.line.reconcile()`:

1. Capture `self.move_id` before `super()`.
2. Call and retain the standard reconciliation result.
3. From affected moves, keep posted customer invoices only.
4. For each invoice, derive linked Sales lines through `invoice_line_ids.sale_line_ids`.
5. Treat it as DP-only only if it has a non-display down-payment Sales line and no non-down-payment product Sales line.
6. Require zero residual and `payment_state != "reversed"`.
7. For each linked confirmed travel order, call `_travel_reserve_seats()`.
8. Return the untouched standard reconciliation result.

Do not add side effects to `_compute_payment_state()` and do not infer DP from invoice names or product names.

- [ ] **Step 6: Run GREEN quota tests and full regression**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelQuota,/travel_umroh:TestTravelPaymentState \
  --log-level=test

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected GREEN: draft/confirmation/posting/partial payment consume zero seats; a fully reconciled DP consumes participant count exactly once; quota cannot be lowered under actual usage; final invoice classification does not create a false DP trigger.

- [ ] **Step 7: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models addons/travel_umroh/tests
git commit -m "feat: reserve travel seats after paid down payment"
```

Checkpoint: sequential reservation is correct and already uses a lock; Task 4 proves the lock under concurrent transactions and completes full-departure selection guards.

---

## Task 4: Prove Concurrent Overbooking Prevention and Close Capacity Selection Gaps

**Files:**

- Create: `addons/travel_umroh/tests/test_phase3_concurrency.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/views/travel_booking_views.xml`

- [ ] **Step 1: Write the dedicated two-cursor concurrency test first**

Follow Odoo's `onboarding/tests/test_onboarding_concurrency.py` pattern. Create `TestTravelQuotaConcurrency(BaseCase)` tagged `-standard`, `-at_install`, `post_install`, `database_breaking`.

In `setUpClass`, use `Registry(get_db_name()).cursor()` and `api.Environment(..., SUPERUSER_ID, {})` to create and commit only synthetic Phase 3 records:

- one service product/package/open departure with `quota = 1` and all three prices;
- two buyers, Jamaah, confirmed travel orders, and one participant per order;
- store every created ID for exact cleanup.

The test uses `ThreadPoolExecutor(max_workers=2)` and `threading.Barrier(2)`. Each worker opens its own registry cursor, browses one order, waits at the barrier, calls `_travel_reserve_seats()`, and lets the cursor commit on clean context exit. Catch the expected business `UserError` in the losing worker.

Assertions in a third fresh cursor:

```python
self.assertEqual(success_count, 1)
self.assertEqual(overbooking_error_count, 1)
self.assertEqual(departure.reserved_seats, 1)
self.assertEqual(departure.remaining_seats, 0)
self.assertTrue(departure.is_full)
self.assertEqual(orders.filtered("seat_reserved").__len__(), 1)
```

Assert the losing error states `available=0` and `needed=1` in the Indonesian message.

Register a class cleanup that deletes only the stored synthetic IDs in dependency order inside a fresh cursor. Never drop the test database and never use a broad domain or wildcard cleanup.

- [ ] **Step 2: Run RED/validation concurrency test**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelQuotaConcurrency \
  --log-level=test
```

Expected: the concurrency assertion is already GREEN when Task 3's lock is correct. The new server-side full-departure selection assertion added before Step 3 is RED until the model constraint is implemented. Do not weaken or temporarily remove the lock to manufacture a failure.

- [ ] **Step 3: Reject new selection of a full departure**

Extend the travel `departure_id` view domain to:

```xml
domain="[('state', '=', 'open'), ('active', '=', True), ('is_full', '=', False)]"
```

Extend `_check_travel_booking_configuration` so creating or changing a draft/sent booking to a currently full departure raises `ValidationError`. Do not invalidate an already-confirmed booking merely because another transaction fills the departure; final reservation remains the authoritative overbooking gate.

Add model tests proving RPC creation with a full departure is rejected even when the view domain is bypassed, while already-confirmed unreserved orders remain intact and fail only when they attempt reservation.

- [ ] **Step 4: Run GREEN concurrency/capacity/full suite**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelQuotaConcurrency,/travel_umroh:TestTravelQuota \
  --log-level=test

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected GREEN: only one concurrent reservation can consume the last seat; new full-departure selection is blocked in both UI and server; no Phase 1/2 regression.

- [ ] **Step 5: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/views/travel_booking_views.xml \
  addons/travel_umroh/tests/test_phase3_concurrency.py \
  addons/travel_umroh/tests/test_phase3_quota.py \
  addons/travel_umroh/tests/__init__.py
git commit -m "test: prove travel quota concurrency safety"
```

Checkpoint: the quota exit criteria are automated, including real independent database transactions.

---

## Task 5: Complete Standard Final Invoicing and the Paid State

**Files:**

- Modify: `addons/travel_umroh/tests/test_phase3_accounting.py`
- Modify: `addons/travel_umroh/models/sale_advance_payment_inv.py`
- Modify: `addons/travel_umroh/models/sale_order.py`

- [ ] **Step 1: Write the failing quotation-to-paid integration test**

Add a test that performs only public standard actions:

1. Staff creates a two-participant quotation and confirms it.
2. Finance creates a 20% standard percentage down payment.
3. Finance posts it; seats remain zero.
4. Finance registers full payment; exactly two seats reserve and state remains `dp`.
5. Finance runs `sale.advance.payment.inv` with `advance_payment_method="delivered"` and `deduct_down_payments=True`.
6. Assert the final invoice includes the participant Sales lines and the standard deducted DP line, and its total equals `order.amount_total - dp_invoice.amount_total`.
7. Finance posts and pays the final invoice.
8. Assert `order.invoice_status == "invoiced"`, every posted invoice residual is zero, `travel_payment_state == "paid"`, and reserved seats remain exactly two.
9. Re-read the order in a fresh environment/cache invalidation and assert the same values.

Add a companion test where the final invoice is posted but unpaid; state must remain `dp`.

- [ ] **Step 2: Run RED final-invoice integration**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState \
  --log-level=test
```

Expected RED if the secure wizard bridge blocks `delivered`, the payment compute marks a paid DP as fully paid too early, or standard final invoicing touches a protected line path. The failure must identify the actual incompatibility.

- [ ] **Step 3: Apply only the minimum compatibility correction**

Allowed corrections:

- let Finance's authorized `delivered` wizard call standard `_create_invoices(final=True)` without enabling the DP-line `ContextVar`;
- adjust the computed `paid` branch to require both `invoice_status == "invoiced"` and net posted invoice value equal to the order total;
- allow only technical standard Odoo relationship/recompute writes proven necessary by the failing test, without permitting Finance to edit line business fields.

Do not add a custom “Pelunasan” invoice generator or direct `account.move` creation.

- [ ] **Step 4: Run GREEN accounting and security regression**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState,/travel_umroh:TestPhaseThreeAccountingSecurity \
  --log-level=test
```

Expected GREEN: standard final invoicing reaches `paid`, unpaid final residual remains `dp`, reservation is not duplicated, and Finance still cannot edit Sales data.

- [ ] **Step 5: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/tests/test_phase3_accounting.py \
  addons/travel_umroh/models/sale_advance_payment_inv.py \
  addons/travel_umroh/models/sale_order.py
git commit -m "test: cover standard travel final settlement"
```

Checkpoint: confirmed booking through full settlement uses only standard invoice/payment transactions.

---

## Task 6: Add Manager-only Post-DP Cancellation with Idempotent Seat Release

**Files:**

- Modify: `addons/travel_umroh/__init__.py`
- Modify: `addons/travel_umroh/__manifest__.py`
- Create: `addons/travel_umroh/wizards/__init__.py`
- Create: `addons/travel_umroh/wizards/travel_booking_cancel_wizard.py`
- Create: `addons/travel_umroh/views/travel_booking_cancel_views.xml`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`
- Modify: `addons/travel_umroh/views/travel_booking_views.xml`
- Create: `addons/travel_umroh/tests/test_phase3_cancellation.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

- [ ] **Step 1: Write failing cancellation boundary tests**

Create `TestTravelCancellation(TravelAccountingCase)` with tests for:

- no posted invoice: Staff can use standard `action_cancel()`; no seat release note and capacity stays unchanged;
- posted DP exists: Staff and Finance cannot invoke `action_cancel()` or open the reason wizard;
- paid DP/reserved booking: only Manager can open and confirm the wizard;
- blank/whitespace reason is rejected;
- successful Manager cancellation sets standard `sale.order.state = "cancel"`, records the exact reason in Chatter, sets `seat_reserved=False`, and restores capacity once;
- calling private `_travel_release_seats()` again returns false/no-op and does not add capacity;
- cancelled travel booking still cannot be reset to draft;
- Manager cannot cancel the same booking twice;
- a posted but unpaid DP still crosses the Manager-cancellation boundary but releases zero seats.

The last case makes the boundary explicit: posted accounting documents require managed cancellation/credit-note handling even if reservation has not occurred.

- [ ] **Step 2: Run RED cancellation tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelCancellation \
  --log-level=test
```

Expected RED: current Phase 2 `action_cancel()` lets Staff cancel a confirmed travel order regardless of DP and no cancellation wizard/release method exists.

- [ ] **Step 3: Implement cancellation state helper and idempotent release**

On `sale.order`, add computed boolean `travel_requires_manager_cancel` that is true only for travel bookings with at least one linked posted `out_invoice`.

Add `_travel_release_seats()`:

- `ensure_one()`;
- acquire the same departure `FOR UPDATE` row lock as reservation;
- invalidate and recheck `seat_reserved` after locking;
- return `False` if already released;
- use `super(SaleOrder, order).write({"seat_reserved": False})`;
- retain `seat_reserved_at` as the historical reservation timestamp;
- post one release note;
- return `True` only on the first release.

Protect `travel_requires_manager_cancel` from public writes.

- [ ] **Step 4: Implement the Manager-only reason wizard**

Create transient model `travel.booking.cancel.wizard` with:

- required readonly `order_id` to `sale.order`;
- required `reason = fields.Text`;
- `action_confirm_cancel()` that checks Manager/System Administrator server-side, strips/rejects whitespace, validates one confirmed travel booking with posted invoice, and calls `order._travel_cancel_after_dp(reason)`.

Add Manager-only CRUD ACL for the transient model and a modal form/action view. Import `wizards` in root `__init__.py` and load its view before booking views in the manifest.

On `sale.order`:

- add `action_open_travel_cancel_wizard()` with the same server-side role/state checks;
- override public `action_cancel()` so unposted travel cancellations and ordinary Sales cancellations retain standard behavior, but posted-invoice travel raises an Indonesian error directing Manager to the managed action;
- use a private `ContextVar` for the trusted wizard call stack, never a request context key;
- `_travel_cancel_after_dp(reason)` posts the reason, calls the standard Sales cancel flow with the trusted marker, and releases the seat in the same transaction;
- if any step fails, the transaction must roll back both cancellation and release.

- [ ] **Step 5: Adjust the booking form without relying on UI security**

Inherit the single standard `action_cancel` button's `invisible` expression so it is hidden only when a travel booking requires managed cancellation. Add a Manager-only `Batalkan setelah DP` object button visible only for a confirmed travel booking where `travel_requires_manager_cancel` is true. Keep ordinary Sales view behavior unchanged.

- [ ] **Step 6: Run GREEN cancellation/full security tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelCancellation,/travel_umroh:TestPhaseThreeAccountingSecurity,/travel_umroh:TestPhaseTwoHardening \
  --log-level=test
```

Expected GREEN: standard pre-DP cancellation remains; posted-DP cancellation is Manager-only via reason wizard; one release restores exact participant count; retry is a no-op; Phase 2 reset and role guards remain.

- [ ] **Step 7: Checkpoint and focused commit**

```bash
git add addons/travel_umroh
git commit -m "feat: manage post-DP travel cancellation"
```

Checkpoint: business cancellation and seat release are complete; Finance still performs the accounting reversal in Task 7.

---

## Task 7: Reflect Standard Credit Notes and Refund Payments in Travel State

**Files:**

- Modify: `addons/travel_umroh/tests/test_phase3_accounting.py`
- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/account_move_line.py`

- [ ] **Step 1: Write the full quotation-to-refund integration test**

Add one end-to-end test with this exact public flow:

1. Confirm a two-participant travel quotation.
2. Create/post/pay 20% DP; assert two seats reserved and state `dp`.
3. Create/post/pay the final standard invoice; assert state `paid` and two seats reserved.
4. Manager cancels through `travel.booking.cancel.wizard` with a reason; assert state `cancel`, zero reserved seats, and original invoices remain linked.
5. As Finance, run standard `account.move.reversal` for each posted customer invoice with `reason` and `journal_id`; use `refund_moves()`.
6. Post each created `out_refund` if the selected standard reversal mode leaves it draft.
7. Before refund payment, assert `travel_payment_state != "refunded"` because refund residual remains.
8. Register the outgoing refund for every credit note with standard `account.payment.register.action_create_payments()`.
9. Invalidate invoice/order caches; assert posted refund total equals posted invoice total, all residuals are zero, `travel_payment_state == "refunded"`, and seats stay released.
10. Re-run cache reads/reconciliation-sensitive code and prove seats are not re-reserved.

Add negative tests:

- a partial credit note or partially paid refund falls back to `dp` (the available non-final settlement state), never `paid` or `refunded`;
- a full unpaid credit note is not `refunded`;
- direct travel payment-state writes remain blocked.

- [ ] **Step 2: Run RED refund integration**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState \
  --log-level=test
```

Expected RED if refund totals/residuals are not handled, if the original paid DP is incorrectly treated as a new reservation during credit-note reconciliation, or if Finance lacks a standard reversal/payment permission.

- [ ] **Step 3: Make only accounting-derived corrections**

If needed:

- ensure `_compute_travel_payment_state` evaluates `refunded` before `paid` and requires exact zero net total plus zero residuals;
- ensure the reconcile hook ignores `out_refund`, reversed invoices, and cancelled Sales Orders;
- do not set `travel_payment_state` from the cancellation wizard;
- do not auto-create credit notes or refund payments;
- do not introduce a refund boolean or custom ledger.

- [ ] **Step 4: Run GREEN integration, accounting security, and quota tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelPaymentState,/travel_umroh:TestTravelCancellation,/travel_umroh:TestTravelQuota \
  --log-level=test
```

Expected GREEN: quotation-to-refund completes using standard Odoo transactions, status matches actual residual/net value, and refund reconciliation cannot re-reserve cancelled seats.

- [ ] **Step 5: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models/sale_order.py \
  addons/travel_umroh/models/account_move_line.py \
  addons/travel_umroh/tests/test_phase3_accounting.py
git commit -m "test: cover standard travel credit note and refund"
```

Checkpoint: the accounting and cancellation/refund exit criteria are complete without custom accounting records.

---

## Task 8: Add Departure `departed`/`done`, Verified-document Gate, and Phase 3 UI

**Files:**

- Modify: `addons/travel_umroh/models/sale_order.py`
- Modify: `addons/travel_umroh/models/travel_departure.py`
- Modify: `addons/travel_umroh/views/travel_booking_views.xml`
- Modify: `addons/travel_umroh/views/travel_departure_views.xml`
- Create: `addons/travel_umroh/tests/test_phase3_departure.py`
- Create: `addons/travel_umroh/tests/test_phase3_views.py`
- Modify: `addons/travel_umroh/tests/__init__.py`

- [ ] **Step 1: Write failing lifecycle and document-gate tests**

Create `TestPhaseThreeDepartureWorkflow(TravelAccountingCase)` and prove:

- Staff and Finance cannot invoke departed/done actions through RPC;
- Manager cannot move a state other than `open` to `departed`;
- an unreserved quotation or confirmed booking does not block departure;
- a reserved booking with any participant whose Jamaah `document_status != "verified"` blocks `action_depart()` and the error names/counts the affected Jamaah;
- after all active Jamaah documents are submitted and Manager-verified through existing actions, `action_depart()` succeeds;
- cancelled/released bookings do not block departure;
- only `departed` can move to `done`;
- direct `write({"state": "departed"})` remains blocked;
- booking `travel_state` computes `registered -> departed -> done` from its departure and cannot be edited directly.

Use the existing document upload/submit/verify flow; do not write `document_status="verified"` directly in the test.

- [ ] **Step 2: Write failing composed-view tests**

Create `TestPhaseThreeViews` using `lxml.etree` and composed views for Staff, Finance, and Manager. Assert:

- booking form contains read-only `travel_payment_state`, `travel_state`, `seat_reserved`, and `seat_reserved_at` only in travel context;
- standard invoice smart button remains present;
- standard Create Invoice action is usable by Finance/Manager according to model/action access, while Staff's server call is rejected;
- managed cancellation button is Manager-only;
- full departure is excluded by the booking `departure_id` domain;
- departure list/form show `quota`, `reserved_seats`, `remaining_seats`, and `is_full`;
- `action_depart` and `action_done` buttons are Manager-only and have correct state invisibility;
- booking rows on the departure page show payment/travel/seat state;
- no `<tree>` tag is introduced; Odoo 18 uses `<list>`.

- [ ] **Step 3: Run RED lifecycle/view tests**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseThreeDepartureWorkflow,/travel_umroh:TestPhaseThreeViews \
  --log-level=test
```

Expected RED: departed/done actions, computed travel state, and Phase 3 presentation are absent.

- [ ] **Step 4: Implement one authoritative departure lifecycle**

On `sale.order`, add read-only computed selection `travel_state`:

- non-travel: `False`;
- departure state `departed`: `departed`;
- departure state `done`: `done`;
- otherwise: `registered`.

Depend on `is_travel_booking` and `departure_id.state`; explicitly protect it from public writes.

On `travel.departure`:

- add private helper returning participants of bookings where `state == "sale"` and `seat_reserved=True`;
- `action_depart()` permits only Manager/System Administrator, requires `state == "open"`, rejects any active Jamaah not `verified`, and then writes `departed` through `super()`;
- `action_done()` permits only Manager/System Administrator, requires `state == "departed"`, and then writes `done` through `super()`;
- keep direct state writes blocked and existing cancel/open transitions intact;
- post normal tracked state changes; do not create per-booking duplicated state transitions.

- [ ] **Step 5: Implement the Phase 3 interface**

Booking form:

- show payment/travel state as read-only badges or status widgets for travel bookings;
- show reservation boolean/time as read-only audit information;
- retain standard Invoices smart button and standard Create Invoice action rather than duplicating them;
- keep all new content invisible on ordinary Sales Orders.

Departure list/form:

- show quota, reserved, remaining, and full status;
- add Manager-only `Tandai Berangkat` in `open` and `Tandai Selesai` in `departed`;
- show payment state, travel state, and seat reservation in the readonly booking page;
- keep the statusbar `draft,open,departed,done,cancelled`.

- [ ] **Step 6: Run GREEN lifecycle, view, and full regression**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseThreeDepartureWorkflow,/travel_umroh:TestPhaseThreeViews \
  --log-level=test

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected GREEN: verified active participants allow departure; incomplete active participants block it; lifecycle and booking display synchronize; ordinary Sales views/flows and all Phase 1/2 tests remain green.

- [ ] **Step 7: Checkpoint and focused commit**

```bash
git add addons/travel_umroh/models \
  addons/travel_umroh/views \
  addons/travel_umroh/tests
git commit -m "feat: complete travel departure lifecycle"
```

Checkpoint: all Phase 3 business behavior and interfaces are implemented; Task 9 is verification and review only.

---

## Task 9: Full Phase 3 Verification, Clean Install, Upgrade, Security Review, and Checkpoint

**Files:**

- Modify only if verification finds an in-scope defect: the exact Phase 3 source/test file responsible
- Update verification evidence in the implementation handoff or commit message; do not create Phase 4 code/data

- [ ] **Step 1: Static and source-scope review**

```bash
git status --short
git diff --check
python3 -m compileall -q addons/travel_umroh
rg -n "sudo\(|_travel_.*context|travel_payment_state|seat_reserved|FOR UPDATE|refund|departed|done" addons/travel_umroh
```

Expected:

- no whitespace or Python syntax error;
- no client-context authorization bypass;
- no unexpected `sudo()` in booking/quota/cancellation code;
- one reservation lock path and one release lock path;
- no Phase 4/5 files or demo data.

- [ ] **Step 2: Run the complete Phase 3 test suite on the implementation database**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: `0 failed, 0 error`. Record the actual method/stat count from the log and confirm it is greater than the Phase 2 baseline because Phase 3 tests were added.

- [ ] **Step 3: Run the dedicated concurrency proof separately**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_test \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestTravelQuotaConcurrency \
  --log-level=test
```

Expected: exactly one transaction reserves the last seat, the other receives the capacity business error, and cleanup removes only synthetic test records.

- [ ] **Step 4: Prove clean install on a never-used database**

Check the proposed name first:

```bash
docker compose exec -T db psql -U odoo -d postgres -Atc \
  "SELECT 1 FROM pg_database WHERE datname = 'travel_umroh_phase3_acceptance';"
```

Expected: empty. If not empty, use `travel_umroh_phase3_acceptance_02`, then `_03`, without dropping anything.

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_acceptance \
  -i base,travel_umroh \
  --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: clean install succeeds, module is `installed` at `18.0.3.0.0`, and all tests including accounting/concurrency pass with zero failures/errors.

- [ ] **Step 5: Prove module upgrade on the same acceptance database**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_acceptance \
  -u travel_umroh \
  --without-demo=all \
  --test-enable \
  --test-tags /travel_umroh \
  --log-level=test
```

Expected: upgrade succeeds idempotently, XML IDs/ACLs load without duplicates, and the full suite remains green. Do not recreate or delete the database between install and upgrade.

- [ ] **Step 6: Run focused Staff, Finance, and Manager security evidence**

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase3_acceptance \
  -u travel_umroh \
  --test-enable \
  --test-tags /travel_umroh:TestPhaseThreeAccountingSecurity,/travel_umroh:TestTravelCancellation,/travel_umroh:TestPhaseThreeDepartureWorkflow \
  --log-level=test
```

Review and report this matrix:

| Operation | Staff | Finance | Manager |
|---|---|---|---|
| Read all travel bookings | allow | allow | allow |
| Create/edit quotation | allow before lock | deny | allow |
| Create/post DP/final invoice and payment | deny | allow | allow |
| Directly edit booking/order lines | constrained by Phase 2 | deny | constrained/audited |
| Cancel before posted DP | allow standard | deny mutation | allow standard |
| Initiate cancellation after posted DP | deny | deny | allow with reason |
| Create credit note/refund | deny | allow standard Accounting | allow |
| Mark departure departed/done | deny | deny | allow with document gate |

Expected: both XML/ACL and server-method enforcement match the matrix; hiding a button is never the only protection.

- [ ] **Step 7: Review complete acceptance traceability**

| Phase 3 acceptance criterion | Automated evidence |
|---|---|
| Draft and confirmed SO do not reduce quota | `TestTravelQuota` |
| Unpaid/partial DP does not reserve | `TestTravelQuota` |
| Paid DP reduces quota once | `TestTravelQuota` |
| Concurrent transactions cannot exceed quota | `TestTravelQuotaConcurrency` |
| Cancellation releases once | `TestTravelCancellation` |
| Payment state is actual and read-only | `TestTravelPaymentState` |
| Standard final invoice reaches paid | quotation-to-paid integration in `TestTravelPaymentState` |
| Standard credit note/refund reaches refunded | quotation-to-refund integration in `TestTravelPaymentState` |
| Departure requires verified active documents | `TestPhaseThreeDepartureWorkflow` |
| Staff/Finance/Manager accounting security | `TestPhaseThreeAccountingSecurity` plus focused workflow tests |
| UI exposes Phase 3 without changing ordinary Sales | `TestPhaseThreeViews` plus Phase 2 view regression |

Every row must be green before claiming Phase 3 complete.

- [ ] **Step 8: Manual demo flow for the handoff**

Use only synthetic records on a test database:

1. Login as Staff; create a buyer, two Jamaah, and a two-participant quotation; confirm it and show departure reserved remains zero.
2. Login as Finance; use standard **Create Invoice** to make a percentage DP, post it, then register only a partial payment; show state `DP` and zero reservation.
3. Complete the DP payment; show `seat_reserved`, timestamp, reserved/remaining capacity, and unchanged count after refresh.
4. Create the standard final invoice with deducted DP, post and pay it; show state `Lunas`.
5. Attempt post-DP cancellation as Staff and Finance; show both are rejected.
6. Login as Manager; cancel through **Batalkan setelah DP**, enter a reason, and show Sales state cancelled plus seats released once.
7. Login as Finance; create standard credit notes, post them, and register outgoing refunds; show state `Refunded` only after all residuals reach zero.
8. On a separate reserved booking, attempt **Tandai Berangkat** with incomplete documents and show the gate; complete submit/verification as Staff/Manager and show `Berangkat -> Selesai`.
9. Open an ordinary Sales Order and demonstrate its standard customer/order-line/cancel/invoice UI remains unchanged.

- [ ] **Step 9: Final focused verification commit if needed**

If verification required an in-scope fix, list the exact changed paths with `git diff --name-only`, stage those paths individually, rerun the exact failing target and the full suite, then commit only that correction:

```bash
git diff --name-only
git commit -m "fix: close Phase 3 acceptance gap"
```

Run `git commit` only after the exact paths printed by `git diff --name-only` have been staged individually with `git add path/to/file`; do not use `git add .`.

If no source changed, do not create an empty commit.

- [ ] **Step 10: Stop at the Phase 3 checkpoint**

Report:

- commits created;
- exact files created/modified;
- full-suite, clean-install, upgrade, concurrency, and focused-security results with actual test counts;
- Staff/Finance/Manager review;
- manual demo result;
- remaining risks, especially PostgreSQL lock contention, accounting localization/journal configuration, and operational handling of a payment transaction rolled back because the last seat was lost;
- explicit confirmation that no database/volume/development data was deleted;
- explicit confirmation that Phase 4 and later were not started.

Do not begin reports, demo XML data, portal, or any Phase 4/5 work. Stop for review.

## Planned File Inventory

**Create:**

- `addons/travel_umroh/models/account_move_line.py`
- `addons/travel_umroh/models/sale_advance_payment_inv.py`
- `addons/travel_umroh/wizards/__init__.py`
- `addons/travel_umroh/wizards/travel_booking_cancel_wizard.py`
- `addons/travel_umroh/views/travel_booking_cancel_views.xml`
- `addons/travel_umroh/tests/test_phase3_accounting.py`
- `addons/travel_umroh/tests/test_phase3_cancellation.py`
- `addons/travel_umroh/tests/test_phase3_concurrency.py`
- `addons/travel_umroh/tests/test_phase3_departure.py`
- `addons/travel_umroh/tests/test_phase3_quota.py`
- `addons/travel_umroh/tests/test_phase3_security.py`
- `addons/travel_umroh/tests/test_phase3_views.py`

**Modify:**

- `addons/travel_umroh/__init__.py`
- `addons/travel_umroh/__manifest__.py`
- `addons/travel_umroh/models/__init__.py`
- `addons/travel_umroh/models/res_users.py`
- `addons/travel_umroh/models/sale_order.py`
- `addons/travel_umroh/models/sale_order_line.py`
- `addons/travel_umroh/models/travel_departure.py`
- `addons/travel_umroh/security/ir.model.access.csv`
- `addons/travel_umroh/security/travel_security.xml`
- `addons/travel_umroh/tests/__init__.py`
- `addons/travel_umroh/tests/common.py`
- `addons/travel_umroh/tests/test_security.py` only if role-selector regression coverage is kept with the existing tests
- `addons/travel_umroh/views/travel_booking_views.xml`
- `addons/travel_umroh/views/travel_departure_views.xml`

## Explicitly Deferred after Phase 3

- Dashboards, graph/pivot reporting, overdue/expiry/occupancy operational reports, and management summaries.
- Demo master/booking/accounting data and scripted stakeholder demo dataset.
- Internal reporting hardening that belongs to roadmap Phase 4.
- Portal pages, record rules, download flows, and portal document submission.
- WhatsApp integration, payment gateway, manifest airline, room assignment, visa API, mobile application, multi-currency complexity, or custom accounting ledgers.

These items must not appear in Phase 3 commits even if implementation makes them seem convenient.
