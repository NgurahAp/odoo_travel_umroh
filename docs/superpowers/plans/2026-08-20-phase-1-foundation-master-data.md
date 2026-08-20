# Travel Umroh Phase 1: Foundation and Master Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Build an installable Odoo 18 Community add-on that provides secure Travel roles, reference masters, reusable packages, sellable departures, room-type pricing, and travel itineraries.

**Architecture:** Keep business-specific records in `travel.*` models while reusing Odoo product, company, country, and currency models. Phase 1 deliberately stops before jamaah and booking models so it produces a small, testable configuration subsystem without fake transaction logic.

**Tech Stack:** Odoo 18 Community, Python 3, PostgreSQL 15, XML views/data, Odoo `TransactionCase`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md`

**Roadmap:** `docs/superpowers/plans/2026-08-20-travel-umroh-roadmap.md`

---

## Global Constraints

- Work only inside `addons/travel_umroh` plus documentation explicitly named by this plan.
- Use `_inherit = ['mail.thread', 'mail.activity.mixin']` only on Package and Departure, where change history is useful; do not add chatter to every lookup table.
- Use Odoo 18 `<list>` view roots, not the older `<tree>` form.
- Validate business invariants on the server. XML visibility is not security.
- Avoid `sudo()` in business methods and tests except narrowly scoped test setup.
- Do not implement Jamaah, Booking, `sale.order` extension, payment, quota reservation, reporting, demo data, or portal in this phase.
- Do not store real customer data or credentials in source files.
- Use English for technical identifiers and Indonesian-friendly labels/help text in the UI.

## Planned File Map

```text
addons/travel_umroh/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── travel_airline.py
│   ├── travel_airport.py
│   ├── travel_departure.py
│   ├── travel_departure_accommodation.py
│   ├── travel_departure_flight.py
│   ├── travel_departure_price.py
│   ├── travel_hotel.py
│   └── travel_package.py
├── security/
│   ├── ir.model.access.csv
│   └── travel_security.xml
├── tests/
│   ├── __init__.py
│   ├── common.py
│   ├── test_departure.py
│   ├── test_itinerary.py
│   ├── test_master_data.py
│   ├── test_package.py
│   └── test_security.py
└── views/
    ├── travel_departure_views.xml
    ├── travel_master_views.xml
    ├── travel_menus.xml
    └── travel_package_views.xml
```

## Test Commands

Use a dedicated test database. On its first run:

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_test -i travel_umroh --test-enable --test-tags /travel_umroh --log-level=test
```

For later runs after the module is installed:

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_test -u travel_umroh --test-enable --test-tags /travel_umroh --log-level=test
```

Expected successful ending: process exit code `0`, no `ERROR`/`CRITICAL` log, and Odoo reports zero failed tests.

If a failed install leaves the test database unusable, do not silently delete it. Create a new explicitly named test database or ask before dropping the old database.

## Task 0: Establish a Safe Version-Control Baseline

**Files:**

- Verify: project root and current files
- Create after user approval: `.git/`
- Create if absent: `.gitignore`

- [ ] **Step 1: Verify the folder is not already a repository**

Run:

```bash
git rev-parse --is-inside-work-tree
```

Expected now: non-zero exit with `not a git repository`.

- [ ] **Step 2: Request explicit approval, then initialize Git**

Run only after approval:

```bash
git init
```

Expected: an initialized empty Git repository in the project folder.

- [ ] **Step 3: Add a minimal `.gitignore`**

Create:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
*.log
.venv/
```

Do not ignore `addons/`, documentation, or Docker Compose files.

- [ ] **Step 4: Commit the planning baseline**

```bash
git add .gitignore Requirement_Modul_Travel_Umroh.md compose.yaml docs
git commit -m "docs: define travel umroh requirements and implementation roadmap"
```

Expected: clean baseline commit before module code is introduced.

## Task 1: Scaffold an Installable Odoo Add-on

**Files:**

- Create: `addons/travel_umroh/__init__.py`
- Create: `addons/travel_umroh/__manifest__.py`
- Create: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/tests/__init__.py`
- Create: `addons/travel_umroh/security/travel_security.xml`
- Create: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Create the package entry points**

`addons/travel_umroh/__init__.py` imports `models`. `models/__init__.py` remains ready for explicit model imports added by later tasks. `tests/__init__.py` imports each test module only when that module exists.

- [ ] **Step 2: Create a minimal manifest**

Use this contract:

```python
{
    "name": "Travel Umroh",
    "summary": "Manage Umroh packages, departures, jamaah, and bookings",
    "version": "18.0.1.0.0",
    "category": "Services",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "mail",
        "product",
        "sale_management",
        "account",
    ],
    "data": [
        "security/travel_security.xml",
        "security/ir.model.access.csv",
    ],
    "application": True,
    "installable": True,
}
```

Do not add `portal` yet; Phase 5 owns portal behavior.

- [ ] **Step 3: Define the three role groups**

Create external IDs:

- `group_travel_staff`
- `group_travel_finance`
- `group_travel_manager`

All three imply `base.group_user`. Manager additionally implies Staff and Finance. Put the roles in one Travel Umroh application category so they are understandable on the user form.

- [ ] **Step 4: Add only the CSV header initially**

`ir.model.access.csv` begins with:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

Model access rows are added together with each model; never reference model external IDs that do not exist yet.

- [ ] **Step 5: Prove the empty module installs**

Run the first-run test command above without `--test-tags` if there are no tests yet.

Expected: module registry loads and exits with code `0`.

- [ ] **Step 6: Commit**

```bash
git add addons/travel_umroh
git commit -m "feat: scaffold travel umroh addon and roles"
```

## Task 2: Build Airline, Airport, and Hotel Masters

**Files:**

- Create: `addons/travel_umroh/models/travel_airline.py`
- Create: `addons/travel_umroh/models/travel_airport.py`
- Create: `addons/travel_umroh/models/travel_hotel.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/tests/test_master_data.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Write failing master-data tests**

Cover these behaviors in `test_master_data.py` using `TransactionCase`:

```python
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTravelMasterData(TransactionCase):
    def test_hotel_rejects_star_rating_outside_one_to_five(self):
        with self.assertRaises(ValidationError):
            self.env["travel.hotel"].create({"name": "Invalid", "city": "Makkah", "star_rating": 6})

    def test_hotel_rejects_negative_distance(self):
        with self.assertRaises(ValidationError):
            self.env["travel.hotel"].create({
                "name": "Invalid Distance",
                "city": "Madinah",
                "star_rating": 4,
                "distance_to_mosque_km": -1,
            })

    def test_airport_uses_odoo_country(self):
        airport = self.env["travel.airport"].create({
            "name": "Soekarno-Hatta International Airport",
            "iata_code": "CGK",
            "city": "Tangerang",
            "country_id": self.env.ref("base.id").id,
        })
        self.assertEqual(airport.country_id.code, "ID")
```

Run the module test command.

Expected failure: registry/test errors because the three models do not exist.

- [ ] **Step 2: Implement complete model interfaces**

Required fields:

```text
travel.airline: name(required), iata_code(optional, max 3), active(default True)
travel.airport: name(required), iata_code(required, max 3), city(required), country_id(required), active(default True)
travel.hotel: name(required), city(required), star_rating(required Integer), distance_to_mosque_km(optional Float), active(default True)
```

Set useful `_rec_name`/`_order` defaults, trim and uppercase IATA codes in `create`/`write`, and enforce IATA length of three characters when present. Use `@api.constrains` for hotel rating `1..5` and non-negative distance. Do not invent terminal fields on Airline; terminals belong to flight legs.

- [ ] **Step 3: Add role-based ACL rows**

For each of the three models:

- Staff: read only.
- Finance: read only.
- Manager: read, write, create, unlink.

Do not grant access to all internal users with a blank `group_id`.

- [ ] **Step 4: Run focused and full tests**

Focused:

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_test -u travel_umroh --test-enable --test-tags /travel_umroh:TestTravelMasterData --log-level=test
```

Then run the full module test command.

Expected: all master-data tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/travel_umroh/models addons/travel_umroh/tests addons/travel_umroh/security/ir.model.access.csv
git commit -m "feat: add travel reference masters"
```

## Task 3: Build Reusable Packages Backed by Service Products

**Files:**

- Create: `addons/travel_umroh/models/travel_package.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/tests/test_package.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Write failing package tests**

Test the full package contract:

```python
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTravelPackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service_product = cls.env["product.product"].create({
            "name": "Umroh Service",
            "type": "service",
            "invoice_policy": "order",
        })

    def test_package_accepts_ordered_quantity_service(self):
        package = self.env["travel.package"].create({
            "name": "Umroh Reguler 9 Hari",
            "code": "REG-09",
            "product_id": self.service_product.id,
            "duration_days": 9,
        })
        self.assertEqual(package.product_id.type, "service")

    def test_package_rejects_non_service_product(self):
        product = self.env["product.product"].create({"name": "Physical Item", "type": "consu"})
        with self.assertRaises(ValidationError):
            self.env["travel.package"].create({
                "name": "Invalid Product",
                "code": "INVALID",
                "product_id": product.id,
                "duration_days": 9,
            })

    def test_package_code_is_unique(self):
        values = {
            "name": "Package A",
            "code": "UNIQUE",
            "product_id": self.service_product.id,
            "duration_days": 9,
        }
        self.env["travel.package"].create(values)
        with self.assertRaises(Exception):
            self.env["travel.package"].create({**values, "name": "Package B"})
```

Prefer asserting the concrete database exception Odoo emits after the first failing run rather than retaining a broad `Exception` assertion.

Expected initial failure: `travel.package` is absent.

- [ ] **Step 2: Implement `travel.package`**

Required interface:

```text
_name = "travel.package"
_inherit = ["mail.thread", "mail.activity.mixin"]
name: Char(required, tracking)
code: Char(required, indexed, copy=False, tracking), unique after normalization
product_id: Many2one(product.product, required, tracking, restrict deletion)
duration_days: Integer(required, default 9, tracking), strictly positive
description: Html
active: Boolean(default True)
```

Normalize `code` by stripping whitespace and converting to uppercase. Constrain `product_id.type == 'service'` and `product_id.invoice_policy == 'order'`. Use a unique SQL constraint for code.

- [ ] **Step 3: Add ACL rows**

- Staff and Finance: read only.
- Manager: full CRUD.

- [ ] **Step 4: Run focused and full tests**

Expected: service-product, duration, normalization, and uniqueness tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/travel_umroh/models addons/travel_umroh/tests addons/travel_umroh/security/ir.model.access.csv
git commit -m "feat: add reusable umroh packages"
```

## Task 4: Build Departures and Room-Type Pricing

**Files:**

- Create: `addons/travel_umroh/models/travel_departure.py`
- Create: `addons/travel_umroh/models/travel_departure_price.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/tests/common.py`
- Create: `addons/travel_umroh/tests/test_departure.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Add a shared test fixture**

`TravelUmrohCase` creates one service product, one package, and exposes the company currency. Keep only immutable/reference setup in `setUpClass`; each test creates its own departure-specific records.

- [ ] **Step 2: Write failing departure tests**

Required cases:

```python
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TravelUmrohCase


@tagged("post_install", "-at_install")
class TestTravelDeparture(TravelUmrohCase):
    def _create_departure(self, **overrides):
        values = {
            "package_id": self.package.id,
            "departure_date": "2027-03-15",
            "return_date": "2027-03-24",
            "quota": 45,
            "company_id": self.env.company.id,
        }
        values.update(overrides)
        return self.env["travel.departure"].create(values)

    def _add_complete_prices(self, departure):
        for room_type, price in (("quad", 30_000_000), ("triple", 32_000_000), ("double", 35_000_000)):
            self.env["travel.departure.price"].create({
                "departure_id": departure.id,
                "room_type": room_type,
                "price": price,
            })

    def test_return_must_be_after_departure(self):
        with self.assertRaises(ValidationError):
            self._create_departure(return_date="2027-03-15")

    def test_quota_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._create_departure(quota=-1)

    def test_price_cannot_be_negative(self):
        departure = self._create_departure()
        with self.assertRaises(ValidationError):
            self.env["travel.departure.price"].create({
                "departure_id": departure.id,
                "room_type": "quad",
                "price": -1,
            })

    def test_room_type_is_unique_per_departure(self):
        departure = self._create_departure()
        values = {"departure_id": departure.id, "room_type": "quad", "price": 30_000_000}
        self.env["travel.departure.price"].create(values)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["travel.departure.price"].create(values)

    def test_open_requires_quad_triple_and_double_prices(self):
        departure = self._create_departure()
        self.env["travel.departure.price"].create({
            "departure_id": departure.id,
            "room_type": "quad",
            "price": 30_000_000,
        })
        with self.assertRaises(UserError):
            departure.action_open()

    def test_open_succeeds_with_complete_prices(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_open()
        self.assertEqual(departure.state, "open")

    def test_state_cannot_be_opened_by_direct_write(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        with self.assertRaises(UserError):
            departure.write({"state": "open"})

    def test_cancelled_departure_cannot_be_reopened(self):
        departure = self._create_departure()
        self._add_complete_prices(departure)
        departure.action_cancel()
        with self.assertRaises(UserError):
            departure.action_open()
```

The opening test must call the public business method, not write `state` directly:

```python
departure.action_open()
self.assertEqual(departure.state, "open")
```

Run the tests and confirm they fail because the models/methods are absent.

- [ ] **Step 3: Implement `travel.departure`**

Phase 1 interface:

```text
_name = "travel.departure"
_inherit = ["mail.thread", "mail.activity.mixin"]
name: Char(compute, stored)
package_id: Many2one(travel.package, required, tracking, restrict deletion)
departure_date: Date(required, tracking)
return_date: Date(required, tracking)
quota: Integer(required, tracking)
company_id: Many2one(res.company, required, default env.company, indexed)
currency_id: Many2one(res.currency, required, related/default from company)
state: Selection(draft/open/departed/done/cancelled, default draft, tracking, copy=False)
price_ids: One2many(travel.departure.price, departure_id)
active: Boolean(default True)
```

Name format must be deterministic and readable, for example `REG-09 — 15 Mar 2027`. Constrain return date after departure date and quota non-negative.

Add explicit state actions:

```text
action_open: draft -> open; require exactly one positive-or-zero price for each room type
action_cancel: draft/open -> cancelled
```

Do not add fake `reserved_seats`, `remaining_seats`, or `is_full` values in Phase 1. Those fields arrive in Phase 3 when their booking source exists.

- [ ] **Step 4: Implement `travel.departure.price`**

Required interface:

```text
departure_id: Many2one(required, cascade deletion, indexed)
room_type: Selection(quad/triple/double, required)
price: Monetary(required)
currency_id: related departure.currency_id, stored, readonly
```

Use a unique SQL constraint on `(departure_id, room_type)` and a Python constraint for `price >= 0`.

- [ ] **Step 5: Protect state changes**

Override `write` narrowly so ordinary callers cannot bypass `action_open` by writing `state='open'`. Business actions set a private context flag and still validate invariants. Keep the mechanism small and test direct invalid writes.

- [ ] **Step 6: Add ACL rows and run tests**

- Staff/Finance: read only.
- Manager: full CRUD.

Run focused departure tests, then the full suite.

- [ ] **Step 7: Commit**

```bash
git add addons/travel_umroh/models addons/travel_umroh/tests addons/travel_umroh/security/ir.model.access.csv
git commit -m "feat: add departures and room pricing"
```

## Task 5: Build Flight and Accommodation Itineraries

**Files:**

- Create: `addons/travel_umroh/models/travel_departure_flight.py`
- Create: `addons/travel_umroh/models/travel_departure_accommodation.py`
- Modify: `addons/travel_umroh/models/__init__.py`
- Create: `addons/travel_umroh/tests/test_itinerary.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Write failing flight tests**

Cover:

- Arrival must be after departure.
- Origin and destination airports must differ.
- Multiple legs are ordered by `(sequence, departure_datetime, id)`.

Example assertion:

```python
with self.assertRaises(ValidationError):
    self.env["travel.departure.flight"].create({
        "departure_id": departure.id,
        "airline_id": airline.id,
        "flight_number": "SV-001",
        "origin_airport_id": cgk.id,
        "destination_airport_id": cgk.id,
        "departure_datetime": "2027-03-15 01:00:00",
        "arrival_datetime": "2027-03-15 10:00:00",
    })
```

- [ ] **Step 2: Write failing accommodation tests**

Cover:

- Check-out must be after check-in.
- Draft departure may temporarily contain an accommodation outside the trip window.
- `action_open()` rejects a departure while any accommodation remains outside the departure/return range.
- Multiple stays are ordered by sequence.

This makes the Manager's correction workflow explicit: incomplete draft data may be saved, but an invalid departure cannot be sold.

- [ ] **Step 3: Implement flight leg interface**

```text
departure_id: Many2one(required, cascade deletion, indexed)
sequence: Integer(default 10)
airline_id: Many2one(required, restrict deletion)
flight_number: Char(required)
origin_airport_id: Many2one(required, restrict deletion)
origin_terminal: Char(optional)
destination_airport_id: Many2one(required, restrict deletion)
destination_terminal: Char(optional)
departure_datetime: Datetime(required)
arrival_datetime: Datetime(required)
```

Use server constraints for time ordering and distinct airports.

- [ ] **Step 4: Implement accommodation interface**

```text
departure_id: Many2one(required, cascade deletion, indexed)
sequence: Integer(default 10)
hotel_id: Many2one(required, restrict deletion)
check_in: Date(required)
check_out: Date(required)
```

Always constrain check-out after check-in. Extend `travel.departure.action_open()` to validate that each stay fits within the trip dates.

- [ ] **Step 5: Add ACL rows and run tests**

- Staff/Finance: read only.
- Manager: full CRUD.

Run focused itinerary tests followed by the full suite.

- [ ] **Step 6: Commit**

```bash
git add addons/travel_umroh/models addons/travel_umroh/tests addons/travel_umroh/security/ir.model.access.csv
git commit -m "feat: add departure itineraries"
```

## Task 6: Prove the Role Matrix at Server Level

**Files:**

- Create: `addons/travel_umroh/tests/test_security.py`
- Modify: `addons/travel_umroh/tests/__init__.py`
- Modify if tests expose gaps: `addons/travel_umroh/security/travel_security.xml`
- Modify if tests expose gaps: `addons/travel_umroh/security/ir.model.access.csv`

- [ ] **Step 1: Create isolated internal users**

Create Staff, Finance, and Manager users with only their intended Travel group plus the implied internal-user group. Do not test with the administrator because administrator access masks ACL errors.

- [ ] **Step 2: Write failing negative and positive tests**

At minimum:

```text
Staff can read airline/package/departure but cannot create, write, or unlink them.
Finance can read airline/package/departure but cannot create, write, or unlink them.
Manager can create, write, and archive every Phase 1 model.
An ordinary internal user without a Travel role cannot read Phase 1 business records.
```

Use `record.with_user(user)` and `self.env[model].with_user(user)` so access is evaluated by the ORM.

- [ ] **Step 3: Run focused security tests**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_test -u travel_umroh --test-enable --test-tags /travel_umroh:TestTravelSecurity --log-level=test
```

Expected before ACL corrections: at least one assertion exposes the permission gap. After minimal ACL/group corrections: all security tests pass.

- [ ] **Step 4: Run the full module suite**

Expected: no access regression in other tests.

- [ ] **Step 5: Commit**

```bash
git add addons/travel_umroh/security addons/travel_umroh/tests
git commit -m "test: enforce travel master role permissions"
```

## Task 7: Add Standard Odoo Views and Menus

**Files:**

- Create: `addons/travel_umroh/views/travel_master_views.xml`
- Create: `addons/travel_umroh/views/travel_package_views.xml`
- Create: `addons/travel_umroh/views/travel_departure_views.xml`
- Create: `addons/travel_umroh/views/travel_menus.xml`
- Modify: `addons/travel_umroh/__manifest__.py`

- [ ] **Step 1: Add XML files to the manifest in dependency order**

Load actions/views before menus that reference them:

```python
"data": [
    "security/travel_security.xml",
    "security/ir.model.access.csv",
    "views/travel_master_views.xml",
    "views/travel_package_views.xml",
    "views/travel_departure_views.xml",
    "views/travel_menus.xml",
],
```

- [ ] **Step 2: Build master views and actions**

For Airline, Airport, and Hotel, provide:

- `<list>` view with useful identifying columns.
- Form view with all fields grouped logically.
- Search view with archived filter and common grouping where useful.
- Window action.

Configuration menu items must use `groups="travel_umroh.group_travel_manager"`.

- [ ] **Step 3: Build Package views**

Provide list, form with chatter, and search views. Package form shows product, duration, description, and archive state. Creation/edit controls remain secured by ACL even if the menu is visible to Staff/Finance.

- [ ] **Step 4: Build Departure views**

Departure form includes:

- Header state/status and `Open`/`Cancel` buttons with correct group and state visibility.
- Core dates, package, quota, company, and currency.
- Notebook tabs for Pricing, Flights, and Accommodations with editable inline lists for Manager.
- Chatter.

Departure list includes package, dates, quota, currency, and state. Search includes state, package, departure month, and archived filter.

- [ ] **Step 5: Build the Phase 1 menu tree**

```text
Travel Umroh
├── Packages
├── Departures
└── Configuration (Manager only)
    ├── Airlines
    ├── Airports
    └── Hotels
```

Reserve menu sequence ranges so later phases can insert Bookings, Jamaah, and Reporting without renaming existing external IDs.

- [ ] **Step 6: Run install/upgrade verification**

Run the full test command. XML parse errors, missing external IDs, and invalid view fields must produce a non-zero result and be corrected before continuing.

- [ ] **Step 7: Perform a manual UI smoke check**

In the development database as Manager:

1. Upgrade or install Travel Umroh.
2. Confirm the menu loads.
3. Create Airline, Airport, Hotel, and service Product.
4. Create Package.
5. Create Departure with three prices, flight legs, and hotel stays.
6. Open the Departure.
7. Confirm invalid dates and missing prices display understandable errors.

Repeat read-only navigation as Staff and Finance; confirm Configuration is hidden and direct ORM security is already covered by tests.

- [ ] **Step 8: Commit**

```bash
git add addons/travel_umroh/__manifest__.py addons/travel_umroh/views
git commit -m "feat: add travel master and departure views"
```

## Task 8: Phase 1 Final Verification and Handoff

**Files:**

- Verify: all files in `addons/travel_umroh`
- Modify if implementation changed the contract: this plan and roadmap

- [ ] **Step 1: Run the complete automated suite from a clean test database**

Use a new database name so the result proves clean installation rather than relying on earlier registry state:

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_acceptance -i travel_umroh --test-enable --test-tags /travel_umroh --log-level=test
```

Expected: exit `0`, no failed test, no XML/ACL/registry error.

- [ ] **Step 2: Prove upgrade compatibility**

```bash
docker compose run --rm odoo --stop-after-init -d travel_umroh_phase1_acceptance -u travel_umroh --log-level=info
```

Expected: exit `0` and module upgrade completes.

- [ ] **Step 3: Review scope and repository state**

```bash
git status --short
git diff --check
git log --oneline --decorate -10
```

Expected: no accidental secrets, generated data, unrelated files, whitespace errors, or uncommitted implementation changes.

- [ ] **Step 4: Review against exit criteria**

Report evidence for:

- Install and upgrade.
- Master data constraints.
- Package service product.
- Complete pricing before departure opens.
- Itinerary validation.
- Staff/Finance read-only and Manager CRUD.
- Manual UI smoke flow.

- [ ] **Step 5: Commit documentation corrections if needed**

```bash
git add docs/superpowers/plans
git commit -m "docs: align phase one plan with implementation"
```

- [ ] **Step 6: Stop at the checkpoint**

Do not start Phase 2 automatically. First present the Phase 1 verification evidence, then write the detailed Phase 2 plan against the code that actually exists.
