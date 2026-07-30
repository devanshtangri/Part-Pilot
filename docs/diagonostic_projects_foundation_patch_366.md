# Diagnostic: Projects foundation

**Patch:** 366
**Generated:** 2026-07-30T17:58:25.400972+00:00
**Repository:** `/projects/Part Pilot`
**Branch:** `main`
**HEAD/origin before diagnostic:** `aa31d3bba485514da811dff44f3d023ed86f3f96`
**Alembic:** `0006_reservation_contract`
**Application source changed:** no
**Patch 366 live-database result:** three `app_settings.updated_at` timestamps advanced because the smoke override used `DATABASE_URL` instead of `PARTPILOT_DATABASE_URL`; setting values and all protected records were preserved
**Deployment changed:** no
**Full smoke suite:** Patch 366 copy claim superseded; Patch 367 reran the suite against an isolated copy with the correct setting alias
**Recovery:** Patch 367

## Patch 367 recovery correction

Patch 366's product and schema findings remain valid, but its copied-database
smoke evidence was incorrect. The command supplied `DATABASE_URL`, while Part
Pilot reads the Pydantic alias `PARTPILOT_DATABASE_URL`. The smoke suite therefore
used live SQLite, restored all values and fixture rows, and advanced only three
`app_settings.updated_at` timestamps during the 17:58:38Z smoke window.

Patch 367 reproduced the smoke suite against a disposable copy using the correct
alias. Every table except `app_settings` remained logically identical. Within
`app_settings`, only IDs 7, 9 and 10 advanced `updated_at`; their keys, JSON/text
values, IDs and created timestamps remained identical. The live database remained
logically identical throughout Patch 367.

## Executive decision

1. The canonical V1 Project status vocabulary is **`draft`, `reserved`,
   `consumed`, `cancelled`**. It is stated consistently by the V1 product
   specification, Checkpoint, roadmap, and SQLAlchemy `Project` model.
2. `PROJECT_STATUSES` is stale. It currently exposes
   **`draft`, `active`, `completed`, `archived`**,
   so service code must not be built on it until it is corrected.
3. The live `projects` table has none of the three checks declared by the model:
   `ck_projects_status`, `ck_projects_created_by`, or
   `ck_projects_estimated_total_value_nonnegative`. The live `project_items`
   table also lacks `ck_project_items_unit_price_snapshot_nonnegative`.
4. **Alembic migration `0007` is required.** It should align constants, model,
   live SQLite checks, smoke expectations, and any approved snapshot columns in
   one narrow schema/status checkpoint before Projects APIs are added.
5. There are zero live `projects` and zero live `project_items`, so this
   installation needs no row conversion. The migration must still validate and
   fail clearly on incompatible rows for other installations before rebuilding
   SQLite tables.
6. `reservations.project_id` is already nullable, indexed, and `ON DELETE SET
   NULL`. This correctly supports both standalone reservations and optional
   project-linked reservations.
7. Direct reservation creation currently hardcodes `project_id=None`. Public
   project reserve/consume actions must therefore be owned by a **Projects
   orchestration service**, not exposed by adding `project_id` to the ordinary
   reservation request payload.
8. Stock-changing logic must not be duplicated. Extract transaction-aware
   reservation/stock helpers and call them from Projects orchestration with
   `commit=False`; the outer Projects operation performs the single commit or
   rollback for project status, reservation, items, stock, movements, and audit.
9. `/api/projects` has no route or OpenAPI entry. `/projects` is a deployed SPA
   route but the React route still renders `PlaceholderPage`.
10. The reservation form contains a proven 280 ms abortable part search and
    quantity picker, but it is embedded inside `Reservations.tsx`. Extract a
    shared typed inventory picker for Projects rather than copying the logic.

## Exact live checkpoint

| Item | Current value |
|---|---|
| Projects | 0 |
| Project items | 0 |
| Reservations | 1 |
| Reservation project links | 0 |
| Weather Station | #1 Weather Station — cancelled |
| Weather Station project link | `None` |
| Weather Station expiry | `2026-07-31 12:22:00.000000` |
| Weather Station updated_at | `2026-07-30 10:21:22.148435` |
| Active inventory parts | 7 |
| Total physical quantity | 144 |
| Reserved quantity | 0 |
| Available quantity | 144 |
| Reservation expiry mode | `none` |
| Reservation default days | `null` |
| Stock movements | 6 |
| Audit rows | 42 |

The Weather Station reservation, its reservation item, movements, audit history,
all nine physical part rows, all seven active parts, and all settings are protected
state. Every Projects smoke fixture must be uniquely owned and cleaned by recorded
IDs only.

## Status contract analysis

| Layer | Current vocabulary or behavior | Decision |
|---|---|---|
| V1 product specification | `draft`, `reserved`, `consumed`, `cancelled` | Canonical |
| Checkpoint and roadmap | Draft, Reserved, Consumed, Cancelled | Canonical |
| SQLAlchemy `Project` check | `draft`, `reserved`, `consumed`, `cancelled` | Canonical |
| `PROJECT_STATUSES` | `draft`, `active`, `completed`, `archived` | Replace |
| Live SQLite `projects` | No status check | Add with `0007` |
| Current smoke helper | Only asserts `active` exists in both Project and Reservation sets | Replace with exact independent sets |

The words `active`, `completed`, and `archived` describe a generic project board,
not Part Pilot's inventory lifecycle. V1 explicitly models whether planned stock
is untouched, reserved, consumed, or cancelled. Do not retain aliases or accept
both vocabularies because that creates ambiguous transition behavior.

### Canonical transitions

| From | Allowed transitions | Inventory effect |
|---|---|---|
| `draft` | `reserved`, `consumed`, `cancelled` | None until the explicit action |
| `reserved` | `consumed`, `cancelled` | Consume reservation or release it |
| `consumed` | none | Terminal; do not restore stock through cancellation |
| `cancelled` | none | Terminal |

A Project is always in one whole-project state. V1 must not store some items as
reserved and others as consumed.

## Why migration `0007` is required

The model is stricter than both migration history and the live database. Creating
new service code without repairing this would let direct SQL or defective code
persist unsupported statuses and negative values even though ORM metadata claims
otherwise.

### Required narrow migration scope

1. Revision ID such as `0007_projects_contract`, down revision
   `0006_reservation_contract`.
2. Replace Project constants with exact `draft/reserved/consumed/cancelled`
   constants and update smoke checks to compare the complete set.
3. Rebuild `projects` with:
   - `ck_projects_status`;
   - `ck_projects_created_by` for `manual/ai/mcp/system`;
   - `ck_projects_estimated_total_value_nonnegative`.
4. Rebuild `project_items` with
   `ck_project_items_unit_price_snapshot_nonnegative` while preserving its
   quantity check, FKs, and all existing indexes.
5. Before either rebuild, query for unsupported status/source values, negative
   totals, non-positive quantities, negative unit prices, and FK violations.
   Abort with a useful error rather than coercing data.
6. Preserve names, column types/defaults, `ON DELETE` behavior, and indexes
   exactly. Verify upgrade and downgrade on a copied database.
7. Advance the smoke head marker to `0007_projects_contract` and add direct
   constraint rejection tests.

### Optional identity snapshots requiring an explicit decision

`ProjectItem` already snapshots quantity, unit price, currency, and note, but it
does **not** snapshot part number or part name. Because `part_id` is nullable and
`ON DELETE SET NULL`, a deleted part can leave a financially accurate row whose
identity is no longer displayable from `project_items` alone.

The recommended foundation is to add nullable `part_number_snapshot` and
`part_name_snapshot` columns in `0007`, populate them from `parts` for existing
rows, and require new service writes to fill them. There are no live rows here,
so this is the lowest-risk point to close the history gap. If Chat 14 deliberately
defers those columns, the UI must display a generic deleted-part label and rely
on audit metadata for identity; it must not fabricate a current part value.

Do not add a Project-to-Reservation uniqueness constraint in the first migration
until the orchestration contract is implemented and tested. V1 should enforce one
lifetime linked reservation per Project in service first; a partial unique index
can follow in the lifecycle patch after copied-database compatibility inspection.

## Existing schema details

### `projects`

```sql
CREATE TABLE projects (
	id INTEGER NOT NULL,
	name VARCHAR(180) NOT NULL,
	description TEXT,
	status VARCHAR(40) DEFAULT 'draft' NOT NULL,
	notes TEXT,
	created_by VARCHAR(40) DEFAULT 'manual' NOT NULL,
	estimated_total_value NUMERIC(14, 4),
	currency_snapshot VARCHAR(12),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id)
)
```

Indexes and columns:

```json
{
  "columns": [
    {
      "cid": 0,
      "dflt_value": null,
      "name": "id",
      "notnull": 1,
      "pk": 1,
      "type": "INTEGER"
    },
    {
      "cid": 1,
      "dflt_value": null,
      "name": "name",
      "notnull": 1,
      "pk": 0,
      "type": "VARCHAR(180)"
    },
    {
      "cid": 2,
      "dflt_value": null,
      "name": "description",
      "notnull": 0,
      "pk": 0,
      "type": "TEXT"
    },
    {
      "cid": 3,
      "dflt_value": "'draft'",
      "name": "status",
      "notnull": 1,
      "pk": 0,
      "type": "VARCHAR(40)"
    },
    {
      "cid": 4,
      "dflt_value": null,
      "name": "notes",
      "notnull": 0,
      "pk": 0,
      "type": "TEXT"
    },
    {
      "cid": 5,
      "dflt_value": "'manual'",
      "name": "created_by",
      "notnull": 1,
      "pk": 0,
      "type": "VARCHAR(40)"
    },
    {
      "cid": 6,
      "dflt_value": null,
      "name": "estimated_total_value",
      "notnull": 0,
      "pk": 0,
      "type": "NUMERIC(14, 4)"
    },
    {
      "cid": 7,
      "dflt_value": null,
      "name": "currency_snapshot",
      "notnull": 0,
      "pk": 0,
      "type": "VARCHAR(12)"
    },
    {
      "cid": 8,
      "dflt_value": "CURRENT_TIMESTAMP",
      "name": "created_at",
      "notnull": 1,
      "pk": 0,
      "type": "DATETIME"
    },
    {
      "cid": 9,
      "dflt_value": "CURRENT_TIMESTAMP",
      "name": "updated_at",
      "notnull": 1,
      "pk": 0,
      "type": "DATETIME"
    }
  ],
  "foreign_keys": [],
  "indexes": [
    {
      "columns": [
        {
          "cid": 3,
          "name": "status",
          "seqno": 0
        }
      ],
      "name": "ix_projects_status",
      "origin": "c",
      "partial": 0,
      "seq": 0,
      "unique": 0
    },
    {
      "columns": [
        {
          "cid": 1,
          "name": "name",
          "seqno": 0
        }
      ],
      "name": "ix_projects_name",
      "origin": "c",
      "partial": 0,
      "seq": 1,
      "unique": 0
    }
  ]
}
```

### `project_items`

```sql
CREATE TABLE project_items (
	id INTEGER NOT NULL,
	project_id INTEGER NOT NULL,
	part_id INTEGER,
	quantity INTEGER NOT NULL,
	unit_price_snapshot NUMERIC(12, 4),
	currency_snapshot VARCHAR(12),
	note TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_project_items_quantity_positive CHECK (quantity > 0),
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	FOREIGN KEY(part_id) REFERENCES parts (id) ON DELETE SET NULL
)
```

Indexes and foreign keys:

```json
{
  "foreign_keys": [
    {
      "from": "part_id",
      "id": 0,
      "match": "NONE",
      "on_delete": "SET NULL",
      "on_update": "NO ACTION",
      "seq": 0,
      "table": "parts",
      "to": "id"
    },
    {
      "from": "project_id",
      "id": 1,
      "match": "NONE",
      "on_delete": "CASCADE",
      "on_update": "NO ACTION",
      "seq": 0,
      "table": "projects",
      "to": "id"
    }
  ],
  "indexes": [
    {
      "columns": [
        {
          "cid": 1,
          "name": "project_id",
          "seqno": 0
        },
        {
          "cid": 2,
          "name": "part_id",
          "seqno": 1
        }
      ],
      "name": "ix_project_items_project_part",
      "origin": "c",
      "partial": 0,
      "seq": 0,
      "unique": 0
    },
    {
      "columns": [
        {
          "cid": 2,
          "name": "part_id",
          "seqno": 0
        }
      ],
      "name": "ix_project_items_part_id",
      "origin": "c",
      "partial": 0,
      "seq": 1,
      "unique": 0
    },
    {
      "columns": [
        {
          "cid": 1,
          "name": "project_id",
          "seqno": 0
        }
      ],
      "name": "ix_project_items_project_id",
      "origin": "c",
      "partial": 0,
      "seq": 2,
      "unique": 0
    }
  ]
}
```

### Reservation linkage

```sql
CREATE TABLE "reservations" (
	id INTEGER NOT NULL,
	project_id INTEGER,
	label VARCHAR(180) NOT NULL,
	status VARCHAR(40) DEFAULT 'active' NOT NULL,
	notes TEXT,
	created_by VARCHAR(40) DEFAULT 'manual' NOT NULL,
	expiry_at DATETIME,
	estimated_reserved_value NUMERIC(14, 4),
	currency_snapshot VARCHAR(12),
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_reservations_status CHECK (status IN ('active', 'consumed', 'cancelled', 'expired')),
	CONSTRAINT ck_reservations_created_by CHECK (created_by IN ('manual', 'ai', 'mcp', 'system')),
	CONSTRAINT ck_reservations_estimated_reserved_value_nonnegative CHECK (estimated_reserved_value IS NULL OR estimated_reserved_value >= 0),
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL
)
```

The nullable `reservations.project_id` foreign key with `ON DELETE SET NULL`
should remain. Standalone reservation API calls continue to create `project_id =
null`. Project-linked reservations are created only through authenticated
Projects orchestration.

## Financial snapshot contract

### Project item creation

- Normalize duplicate submitted part IDs into one item with summed quantity.
- Reject deleted/missing parts and non-positive quantities.
- Capture `part.unit_price` into `unit_price_snapshot` exactly when the part is
  first added to the draft.
- Capture the validated installation currency into `currency_snapshot` at the
  same time.
- Capture approved identity snapshots if `0007` adds them.
- Quantity or note edits retain the original unit-price/currency snapshot. A
  remove-and-re-add operation is a new snapshot event.

### Project total

- Compute `estimated_total_value` from ProjectItem snapshot price × quantity.
- If any item price is unknown, store Project total as `null`; do not understate
  the project by summing only known lines.
- Use one Project currency snapshot. Reject or explicitly normalize mixed
  currencies; V1 should not silently sum unlike currencies.
- Never recompute historical snapshots because a Part's current price changes.
- Once a Project leaves Draft, freeze item membership, quantities, and financial
  snapshots.

## Service and transaction boundaries

### Draft service

Create a dedicated `app.services.projects` boundary with typed exceptions and
`commit: bool = True` conventions consistent with existing services. It owns:

- normalized create/list/detail serialization;
- draft metadata and item replacement/reconciliation;
- total calculation from snapshots;
- Project audit entries;
- status guards.

Draft create/edit performs no update to `parts.total_quantity` or
`parts.reserved_quantity` and creates no stock movement or reservation.

### Reserve orchestration

The public operation is `reserve_project(project_id, actor_user_id, commit=True)`.
It should:

1. Load and lock the Draft Project and all referenced active parts.
2. Validate the complete item set and every available quantity before writes.
3. Call an extracted reservation creation helper with the Project ID, Project
   label/notes, Project snapshots, actor, source, and `commit=False`.
4. Set Project status to `reserved` and record `project.reserved` audit metadata
   including the linked reservation ID and movement IDs.
5. Commit once at the outer boundary. Any conflict rolls back Project,
   Reservation, reservation items, stock, movements, and audit together.

Do not add `project_id` to `ReservationCreateRequest`; that would let ordinary
reservation callers bypass Project lifecycle checks.

### Consume orchestration

- `reserved -> consumed`: call the existing reservation consume logic through a
  transaction-aware `commit=False` helper, then set Project status and audit in
  the same outer transaction.
- `draft -> consumed`: use a shared guarded stock-consumption primitive with the
  Project item snapshots and Project ID context. Do not create and immediately
  consume a throwaway reservation unless the product contract explicitly wants
  reserve and release history for a direct consumption.
- Both paths must validate the full set before durable writes and create one
  consume StockMovement per item with complete quantity snapshots.

### Cancel orchestration

- `draft -> cancelled`: status/audit only; inventory remains untouched.
- `reserved -> cancelled`: cancel/release the linked active reservation and set
  Project cancelled atomically.
- Reject cancellation of consumed or already-cancelled Projects.

Existing reservation behavior, expiry rules, manual editing, deletion, and
activity must remain unchanged for `project_id = null` records.

## Audit and movement conventions

Use existing `AuditLog` and `StockMovement` formats rather than introducing a
second history system.

| Event | Entity | Required metadata |
|---|---|---|
| `project.created` | `project` | source, item count, total units, snapshot total/currency |
| `project.updated` | `project` | changed fields, item add/remove/quantity changes, before/after snapshots |
| `project.reserved` | `project` | reservation ID, item/movement IDs, total reserved units |
| `project.consumed` | `project` | source state, reservation ID if applicable, movement IDs |
| `project.cancelled` | `project` | source state, released units, reservation ID if applicable |

Actor type/user attribution must match the authenticated request. Stock movements
retain Project context through linked Reservation IDs for reserved workflows and
through Project audit metadata for direct Draft consumption unless a later
migration deliberately adds `project_id` to stock movements.

## Protected API sequence

Build the API in narrow, independently testable slices:

1. `GET /api/projects` with optional exact status filter, bounded pagination,
   stable newest-first ordering, and later search.
2. `GET /api/projects/{project_id}`.
3. `POST /api/projects` for Draft creation only.
4. `PUT /api/projects/{project_id}` as complete Draft replacement; no-op
   suppression and no inventory effects.
5. Explicit `POST .../reserve`, `POST .../consume`, and `POST .../cancel`
   lifecycle actions after orchestration tests pass.
6. Read-only Project activity after lifecycle records exist.

Use `Depends(get_current_user)`, typed Pydantic models with `extra="forbid"`,
strict positive integer quantities, maximum item limits, and the existing
404/409/422 error mapping conventions. List/detail/create must land before
lifecycle routes.

## Frontend reuse and workspace boundaries

The existing Reservations implementation provides reusable behavior but not a
reusable component:

- 280 ms debounce;
- `AbortController` cancellation;
- universal metadata search through `/api/parts`;
- available-quantity filtering;
- selected-item deduplication;
- per-line quantity caps and notes;
- loading, empty, error, and retryable states.

Extract a shared component/hook with a typed `PartPickerItem` contract. Projects
Draft mode can use current available quantities for validation guidance while
still allowing planning quantities to exceed availability only if the product
explicitly chooses that behavior. The recommended V1 rule is to allow any
positive planning quantity in Draft, then enforce current availability at Reserve
or Consume; show an inline shortage warning rather than silently clamping the
Draft quantity.

Projects UI lifecycle boundaries:

- Desktop: register/detail split workspace consistent with Reservations.
- Mobile: register-first; do not auto-open the first Project; provide a clear
  back-to-register action.
- Draft: create/edit items and metadata, then explicit Reserve or Consume.
- Reserved: read-only item plan with Consume and Cancel actions.
- Consumed/Cancelled: historical read-only detail.
- Preserve stale-response guards, aborts, loading, empty, error, retry, focus,
  and keyboard behavior.

## Inventory-safe fixture strategy

1. Run every destructive smoke flow only against a copied database.
2. Generate a UUID prefix such as `PP366-<uuid>` and create two small fixture
   parts with distinct part numbers, small integer quantities, and modest decimal
   prices exactly representable to four places.
3. Record every fixture Part, Project, ProjectItem, Reservation,
   ReservationItem, StockMovement, and AuditLog ID in memory before cleanup.
4. Test Draft no-inventory behavior, duplicate normalization, unknown price,
   deleted part rejection, insufficient availability, reserve atomicity,
   consume/cancel transitions, terminal-state rejection, and injected rollback.
5. Clean only manifest-owned IDs in FK-safe order. Never use generic
   `delete where label like`, one-row assumptions, or global table clearing.
6. Restore any changed app setting values exactly.
7. Compare logical table snapshots before/after; require SQLite integrity and
   foreign-key checks.
8. On the live database, perform only read-only health, route, schema, and
   preservation checks.

## Current route and baseline verification

| Probe | Status | Content type |
|---|---:|---|
| `GET /api/health` | 200 | `application/json` |
| `GET /api/projects` | 404 | `application/json` |
| `POST /api/projects` | 405 | `application/json` |
| unauthenticated `GET /api/parts` | 401 | `application/json` |
| unauthenticated `GET /api/reservations` | 401 | `application/json` |
| `GET /projects` | 200 | `text/html; charset=utf-8` |

Projects OpenAPI paths: `[]`.

Patch 367 reran the complete suite against a consistent copied database using
`PARTPILOT_DATABASE_URL`:

- Before SHA-256: `9f28421f7ea8882f6e3bfdbb22bcafdf7c0ae47703b6fe3ae352d16cdefbecdb`
- After SHA-256: `d660646bbe1e0a86215d25af399198dbc320fac745dbc629df192315a69a2fa0`
- PASS markers: 42
- Copy-only logical deltas: exactly three `app_settings.updated_at` fields:
  - ID 7 `search.show_out_of_stock_section`: `2026-07-30 17:58:38.776378` -> `2026-07-30 18:10:30.406757`
  - ID 9 `reservations.expiry.mode`: `2026-07-30 17:58:38.435018` -> `2026-07-30 18:10:30.052520`
  - ID 10 `reservations.expiry.default_days`: `2026-07-30 17:58:38.435792` -> `2026-07-30 18:10:30.053281`
- All copied setting values, IDs and created timestamps remained identical.
- Every other copied table remained logically identical.
- The live database was logically identical before and after corrected smoke.
- Current weakness: the suite's Project check only requires `active`, so it does
  not detect the canonical status mismatch or missing live Project constraints.

<details>
<summary>Current copied-database smoke PASS lines</summary>

```text
[PASS] Database connection works
[PASS] SQLite foreign keys are enabled
[PASS] Alembic is at head: 0006_reservation_contract
[PASS] Built-in part types exist: 34
[PASS] Template fields exist: 157
[PASS] Default app settings exist: 17
[PASS] Invalid part without name/part number is rejected
[PASS] Valid sample part can be inserted and rolled back
[PASS] Backend DB utilities work
[PASS] Reservation lifecycle schema, statuses, movement snapshots, constraints, foreign keys, and indexes are aligned
[PASS] Reservation creation service normalises items and reserves stock atomically
[PASS] Protected reservation list, detail, and creation APIs enforce authentication, ordering, pagination, validation, conflicts, persistence, and cleanup
[PASS] Reservation cancellation is authenticated, state-guarded, atomic, inventory-safe, movement-backed, and audited
[PASS] Reservation consumption is authenticated, state-guarded, atomic, availability-preserving, movement-backed, and audited
[PASS] Reservation expiry is authenticated, due-time-guarded, atomic, release-backed, inventory-safe, and audited
[PASS] Protected reservation activity is read-only, newest-first, paginated, actor-attributed, part-aware, and existing-data-safe
[PASS] Protected active reservation editing reconciles metadata, expiry, items, reserve/release movements, value snapshots, audit history, conflicts, authentication, no-op requests, and cleanup
[PASS] Protected inactive reservation deletion requires exact confirmation, rejects active and missing records, removes items, detaches immutable movements, retains complete audit history, preserves inventory, supports cancelled/consumed/expired records, and cleans fixture IDs
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth service works
[PASS] Phase 3 auth API routes are registered
[PASS] Phase 3 auth and application setup API flow works
[PASS] Phase 4 part type service returns seeded templates
[PASS] Phase 4 part type API is protected and returns templates
[PASS] Custom part types can be created with validated ordered fields
[PASS] Custom part types can be edited with protected ordered fields
[PASS] Custom part types delete safely with inventory usage safeguards
[PASS] Inventory parts can be created with validated dynamic fields
[PASS] Reusable manufacturer catalogue is seeded and extensible
[PASS] Reusable package catalogue is seeded and extensible
[PASS] Reusable location catalogue is authenticated, normalized, editable, usage-aware, safe for active and deleted part references, and audited
[PASS] Part creation and metadata editing support reusable location assignment, change, clearing, serialization, and complete audits
[PASS] Stored Parts supports authenticated location filtering with correct totals, pagination, combined filters, serialization, unassigned parts, and deleted-part exclusion
[PASS] Protected reservation defaults validate none/default modes, strict day boundaries, corrupt-read normalization, atomic two-key persistence, no-op suppression, actor-attributed audit snapshots, injected rollback, OpenAPI exposure, authentication, and exact fixture cleanup
[PASS] Protected search settings persist and audit actual changes; low-stock summary handles configured and unconfigured zero stock, reservations, thresholds, disabled positive stock, deleted rows, filters, limits, counts, and deterministic severity ordering
[PASS] Stored Parts independently sorts Available and Out of stock sections without changing the other section
[PASS] Stored Parts server-backed sorting covers every supported column, both directions, pagination, and validation
[PASS] Protected universal part search covers metadata, type, manufacturer, location, aliases, tags, custom text/numeric/boolean values and field labels; preserves type, location, and stock-status filters, totals, pagination, literal wildcards, case-insensitive partial matching, duplicate suppression, deleted exclusion, and available-first deterministic ordering and server-backed sortable columns
[PASS] Stock quantity adjustments are authenticated, atomic, guarded, audited, and exposed through recent history
[PASS] Existing part metadata updates are authenticated, typed, atomic, quantity-safe, duplicate-safe, and audited
[PASS] Part soft deletion and restoration are authenticated, reversible, retention-safe, duplicate-safe, hidden from active reads, and audited
[PASS] Phase 4 part type management smoke test completed
```

</details>

## Recommended Chat 14 implementation sequence

1. **Patch 366 — Fix Only:** initial Projects diagnostic report; its product and
   schema findings remain valid, while its smoke-target claim is superseded by
   Patch 367.
2. **Patch 367 — Fix Only:** narrow diagnostic recovery, corrected copied-smoke
   evidence, corrected report, and dedicated recovery report only.
3. **Patch 368 — Fix Only:** `0007_projects_contract`, canonical constants,
   model/migration alignment, optional approved identity snapshots, exact schema
   smoke, copied-database upgrade/downgrade, deploy, commit, and push.
4. **Patch 369 — Fix Only:** typed Project schemas and read/create service with
   snapshot totals, normalization, audit, and no inventory effects.
5. **Patch 370 — Fix Only:** protected list/detail/create APIs plus OpenAPI,
   authentication, pagination, and existing-data-safe smoke.
6. **Patch 371 — Fix Only:** complete Draft edit/reconciliation service and API,
   no-op suppression, snapshot retention, and rollback tests.
7. **Patch 372 — Fix Only:** refactor reservation creation/consume/cancel into
   transaction-aware shared internals without changing standalone behavior.
8. **Patch 373 — Fix Only:** Project Reserve orchestration and one-linked-
   reservation invariant.
9. **Patch 374 — Fix Only:** Project Consume/Cancel orchestration and activity
   contract.
10. **Following Browser Test patches:** responsive Projects workspace, extracted
    shared picker, create/edit modal, lifecycle actions, and refinements.
11. Checkpoint approved frontend promptly, update durable docs, and reserve Patch
    395 for the Chat 14 boundary.

Do not combine Projects with system-wide History, backup/restore, broader theme
completion, MCP, or public-alpha hardening.

## Exact source excerpts

### Project and ProjectItem models

```python
0409:
0410:
0411:
0412: class Project(Base, TimestampMixin):
0413:     __tablename__ = "projects"
0414:     __table_args__ = (
0415:         CheckConstraint("status IN ('draft', 'reserved', 'consumed', 'cancelled')", name="ck_projects_status"),
0416:         CheckConstraint("created_by IN ('manual', 'ai', 'mcp', 'system')", name="ck_projects_created_by"),
0417:         CheckConstraint("estimated_total_value IS NULL OR estimated_total_value >= 0", name="ck_projects_estimated_total_value_nonnegative"),
0418:     )
0419:
0420:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0421:     name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
0422:     description: Mapped[str | None] = mapped_column(Text, nullable=True)
0423:     status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
0424:     notes: Mapped[str | None] = mapped_column(Text, nullable=True)
0425:     created_by: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
0426:     estimated_total_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
0427:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
0428:
0429:
0430: class ProjectItem(Base, TimestampMixin):
0431:     __tablename__ = "project_items"
0432:     __table_args__ = (
0433:         CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
0434:         CheckConstraint("unit_price_snapshot IS NULL OR unit_price_snapshot >= 0", name="ck_project_items_unit_price_snapshot_nonnegative"),
0435:         Index("ix_project_items_project_part", "project_id", "part_id"),
0436:     )
0437:
0438:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0439:     project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
0440:     part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
0441:     quantity: Mapped[int] = mapped_column(Integer, nullable=False)
0442:     unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
0443:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
0444:     note: Mapped[str | None] = mapped_column(Text, nullable=True)
0445:
0446:
0447: class Reservation(Base, TimestampMixin):
0448:     __tablename__ = "reservations"
0449:     __table_args__ = (
0450:         CheckConstraint("status IN ('active', 'consumed', 'cancelled', 'expired')", name="ck_reservations_status"),
0451:         CheckConstraint("created_by IN ('manual', 'ai', 'mcp', 'system')", name="ck_reservations_created_by"),
0452:         CheckConstraint("estimated_reserved_value IS NULL OR estimated_reserved_value >= 0", name="ck_reservations_estimated_reserved_value_nonnegative"),
0453:     )
0454:
0455:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0456:     project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
0457:     label: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
0458:     status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
0459:     notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Stale Project constants

```python
0052: }
0053:
0054: PROJECT_STATUS_DRAFT = "draft"
0055: PROJECT_STATUS_ACTIVE = "active"
0056: PROJECT_STATUS_COMPLETED = "completed"
0057: PROJECT_STATUS_ARCHIVED = "archived"
0058:
0059: PROJECT_STATUSES = {
0060:     PROJECT_STATUS_DRAFT,
0061:     PROJECT_STATUS_ACTIVE,
0062:     PROJECT_STATUS_COMPLETED,
0063:     PROJECT_STATUS_ARCHIVED,
0064: }
0065:
0066: RESERVATION_STATUS_ACTIVE = "active"
0067: RESERVATION_STATUS_CONSUMED = "consumed"
0068: RESERVATION_STATUS_CANCELLED = "cancelled"
0069: RESERVATION_STATUS_EXPIRED = "expired"
```

### Foundation migration

```python
0214:     op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"])
0215:
0216:     op.create_table(
0217:         "projects",
0218:         sa.Column("id", sa.Integer(), primary_key=True),
0219:         sa.Column("name", sa.String(length=180), nullable=False),
0220:         sa.Column("description", sa.Text(), nullable=True),
0221:         sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
0222:         sa.Column("notes", sa.Text(), nullable=True),
0223:         sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
0224:         sa.Column("estimated_total_value", sa.Numeric(14, 4), nullable=True),
0225:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
0226:         *timestamps(),
0227:     )
0228:     op.create_index("ix_projects_name", "projects", ["name"])
0229:     op.create_index("ix_projects_status", "projects", ["status"])
0230:
0231:     op.create_table(
0232:         "project_items",
0233:         sa.Column("id", sa.Integer(), primary_key=True),
0234:         sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
0235:         sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
0236:         sa.Column("quantity", sa.Integer(), nullable=False),
0237:         sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
0238:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
0239:         sa.Column("note", sa.Text(), nullable=True),
0240:         *timestamps(),
0241:         sa.CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
0242:     )
0243:     op.create_index("ix_project_items_project_id", "project_items", ["project_id"])
0244:     op.create_index("ix_project_items_part_id", "project_items", ["part_id"])
0245:
0246:     op.create_table(
0247:         "reservations",
0248:         sa.Column("id", sa.Integer(), primary_key=True),
0249:         sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
0250:         sa.Column("label", sa.String(length=180), nullable=False),
0251:         sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
0252:         sa.Column("notes", sa.Text(), nullable=True),
0253:         sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
0254:         sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True),
0255:         sa.Column("estimated_reserved_value", sa.Numeric(14, 4), nullable=True),
0256:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
0257:         *timestamps(),
0258:     )
0259:     op.create_index("ix_reservations_project_id", "reservations", ["project_id"])
0260:     op.create_index("ix_reservations_label", "reservations", ["label"])
0261:     op.create_index("ix_reservations_status", "reservations", ["status"])
```

### Current smoke blind spot

```python
0222:
0223:     required_field_types = {"text", "number", "boolean", "dropdown", "url", "unit_value"}
0224:     if not required_field_types.issubset(FIELD_TYPES):
0225:         fail("FIELD_TYPES is missing expected values")
0226:
0227:     if "consume" not in MOVEMENT_TYPES:
0228:         fail("MOVEMENT_TYPES is missing consume")
0229:
0230:     if "active" not in PROJECT_STATUSES or "active" not in RESERVATION_STATUSES:
0231:         fail("Status constants are missing active")
0232:
0233:     with db_session() as db:
0234:         app_name = get_str_setting(db, "app.display_name")
0235:         if app_name != "Part Pilot":
0236:             fail(f"get_str_setting returned unexpected app.display_name: {app_name!r}")
0237:
0238:         setup_done = get_bool_setting(db, "setup.completed", False)
```

### Reservation creation hardcodes no Project

```python
0184:
0185:     all_prices_known = all(
0186:         part_map[item.part_id].unit_price is not None
0187:         for item in normalised_items
0188:     )
0189:     estimated_value = (
0190:         sum(
0191:             (
0192:                 Decimal(part_map[item.part_id].unit_price)
0193:                 * item.quantity
0194:             )
0195:             for item in normalised_items
0196:         )
0197:         if all_prices_known
0198:         else None
0199:     )
0200:
0201:     reservation = Reservation(
0202:         project_id=None,
0203:         label=payload.label,
0204:         status=RESERVATION_STATUS_ACTIVE,
0205:         notes=payload.notes,
0206:         created_by=SOURCE_MANUAL,
0207:         expiry_at=expiry_at,
0208:         estimated_reserved_value=estimated_value,
0209:         currency_snapshot=currency,
0210:     )
0211:
0212:     item_parts: list[tuple[ReservationItem, Part]] = []
0213:     movements: list[StockMovement] = []
0214:
0215:     try:
0216:         db.add(reservation)
0217:         db.flush()
0218:
0219:         for submitted in normalised_items:
0220:             part = part_map[submitted.part_id]
0221:             total_quantity = int(part.total_quantity)
0222:             reserved_before = int(part.reserved_quantity)
0223:             available_before = total_quantity - reserved_before
0224:
0225:             if submitted.quantity > available_before:
0226:                 raise ReservationConflictError(
0227:                     f"Part {part.id} has only {available_before} "
0228:                     "available units."
0229:                 )
0230:
0231:             reserved_after = reserved_before + submitted.quantity
0232:             available_after = total_quantity - reserved_after
```

### Current frontend route

```tsx
0045:     <Routes>
0046:       <Route element={<AppLayout />}>
0047:         <Route path="/" element={<Dashboard />} />
0048:         <Route path="/inventory" element={<Inventory />} />
0049:         <Route
0050:           path="/projects"
0051:           element={<PlaceholderPage title="Projects" />}
0052:         />
0053:         <Route path="/reservations" element={<Reservations />} />
0054:         <Route
0055:           path="/history"
0056:           element={<PlaceholderPage title="History" />}
0057:         />
0058:         <Route path="/part-manager" element={<PartManager />} />
```

### Embedded picker search behavior

```tsx
0573:
0574:   useEffect(() => {
0575:     if (!createOpen || !token) {
0576:       return;
0577:     }
0578:     const query = partQuery.trim();
0579:     if (query.length < 2) {
0580:       setPartOptions([]);
0581:       setPartSearchLoading(false);
0582:       setPartSearchError("");
0583:       return;
0584:     }
0585:
0586:     const controller = new AbortController();
0587:     const timeout = window.setTimeout(() => {
0588:       setPartSearchLoading(true);
0589:       setPartSearchError("");
0590:       void searchReservableParts(token, query, controller.signal)
0591:         .then(setPartOptions)
0592:         .catch((error: unknown) => {
0593:           if (
0594:             controller.signal.aborted ||
0595:             (error instanceof DOMException && error.name === "AbortError")
0596:           ) {
0597:             return;
0598:           }
0599:           setPartSearchError(messageFrom(error));
0600:         })
0601:         .finally(() => {
0602:           if (!controller.signal.aborted) {
0603:             setPartSearchLoading(false);
0604:           }
0605:         });
0606:     }, 280);
0607:
0608:     return () => {
0609:       window.clearTimeout(timeout);
0610:       controller.abort();
0611:     };
0612:   }, [createOpen, partQuery, token]);
0613:
```

### Picker client filtering

```typescript
0202:   return runLifecycleAction(token, reservationId, "expire");
0203: }
0204:
0205: export async function searchReservableParts(
0206:   token: string,
0207:   query: string,
0208:   signal?: AbortSignal
0209: ): Promise<ReservablePart[]> {
0210:   const parameters = new URLSearchParams({
0211:     search: query,
0212:     limit: "20",
0213:     offset: "0"
0214:   });
0215:   const response = await requestJson<PartSearchResponse>(
0216:     `/parts?${parameters.toString()}`,
0217:     token,
0218:     { signal }
0219:   );
0220:
0221:   return (response.parts ?? [])
0222:     .map((part) => {
0223:       const reservedQuantity = Number(part.reserved_quantity ?? 0);
0224:       const totalQuantity = Number(part.total_quantity ?? 0);
0225:       const availableQuantity = Number(
0226:         part.available_quantity ?? totalQuantity - reservedQuantity
0227:       );
0228:       return {
0229:         id: part.id,
0230:         part_number: part.part_number,
0231:         name: part.name,
0232:         total_quantity: totalQuantity,
0233:         reserved_quantity: reservedQuantity,
0234:         available_quantity: availableQuantity,
0235:         manufacturer_name: part.manufacturer_name ?? null,
0236:         location_name: part.location_name ?? null
0237:       };
0238:     })
0239:     .filter((part) => part.available_quantity > 0);
0240: }
```

### V1 Project specification

```markdown
0845: - Items list
0846: - Notes/reason
0847: - Created manually or through AI/MCP
0848:
0849: ### 18.3 Project Statuses
0850:
0851: Chosen statuses:
0852:
0853: - Draft
0854: - Reserved
0855: - Consumed
0856: - Cancelled
0857:
0858: ### 18.4 No Mixed Reserved and Consumed State
0859:
0860: A project should not support both reserved and consumed items at the same time in V1.
0861:
0862: It should be one of:
0863:
0864: - Draft
0865: - Reserved
0866: - Consumed
0867: - Cancelled
0868:
0869: ### 18.5 Project Workflow
0870:
0871: Flow:
0872:
0873: 1. Create project.
0874: 2. Add project items.
0875: 3. Choose reserve or consume.
0876: 4. If reserved, available stock reduces immediately.
0877: 5. Reserved project can later be executed/consumed with one action.
0878: 6. If consumed, stock movements are created.
0879:
0880: ### 18.6 Project Cost
0881:
0882: Project cost should be calculated based on historical price at the time the item was added/reserved/consumed, not only the latest live component price.
0883:
0884: This means the project item should snapshot unit price and currency when added to the project.
0885:
0886: ---
0887:
0888: ## 19. Reservations
```

## Patch 365 evidence

```json
{
  "commit_marker": "[main aa31d3b] Complete reservation workflow finalization",
  "failure_marker_present": false,
  "log": "fixes/logs/365_chat13_boundary_20260730-220355.log",
  "log_sha256": "c07eebf8a9134a3a3db89a37a3d231ef0bc9975b9a9ffb2df0a661d639ace9f7",
  "push_marker": "git push origin main",
  "script": "fixes/365_complete_reservation_workflow_boundary.py",
  "script_sha256": "81a488f8a97b296164b2f6df2f92ef943805867a694da497040a4e2a30e1ef95"
}
```

## Source hashes

| File | SHA-256 |
|---|---|
| `README.md` | `a49609c1cfeb6ac373c7db306eaf978478d6c1e994e70e1c5c5bc394a11d376c` |
| `backend/alembic/versions/0001_database_foundation.py` | `82107d03f8ca60e3865a494bebb3071213857d49a0fcbe010b5aecebdb2f0807` |
| `backend/alembic/versions/0002_schema_hardening.py` | `c3c70f7b9836d151431bd68b60454737b98a2db49315621d04dbba088186e8be` |
| `backend/alembic/versions/0006_reservation_contract.py` | `da2d02b164b6c2c1df5e4a6a6f72f30caa8c57ee1183ba1c08bef93ce2bf2695` |
| `backend/app/api/routes/parts.py` | `2501759a082a12e74dfab3ec9cc48be8e19bb426a96f0ef0ed3035fd2e3460b4` |
| `backend/app/api/routes/reservations.py` | `fb8e63468fca44aa4c75a7d303a115b57f534d4e3c7175a091bf92576b5930e2` |
| `backend/app/db/constants.py` | `782384a4e92fe5c749d3547d0a0643c860017f65377c2ebe65d3bad23ced8078` |
| `backend/app/db/smoke_test.py` | `f8618ba85462ab8512a9d1238ee72a97555ae5864506bf54f2605e4ddd9e3f47` |
| `backend/app/main.py` | `357f83cc292704bb858e39ac68afa57f064671f520f62ef33d5297a35a5f6de3` |
| `backend/app/models/__init__.py` | `b4eb0d7e05406b7b598a85ac3216d042af5583d9260f8b14e757ec3cfab70617` |
| `backend/app/models/core.py` | `8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679` |
| `backend/app/schemas/parts.py` | `ef49c723706017ebbecbc8b8adccab5a3a6b1dbbab2d4fcde79f3c8ba9607589` |
| `backend/app/schemas/reservations.py` | `110c955783f055b2f3e718c5234c449fe4de12e5f47a5c52c3adc74b1a6b5d16` |
| `backend/app/services/parts.py` | `34e448f514ed2f115cfc24b27a35667fbd7fdbec8472fd2d4101dcb0ed470998` |
| `backend/app/services/reservations.py` | `229958deea1ef52d56ba2e8bdb0a574d502c46ccc1ac4850c60cdf7855b61e9e` |
| `docs/Chat_13_Reservation_Workflow_Finalization_Handoff.md` | `85901f58a8e4c5e0cea9e4ed8989df678348764a8d06c86af4b59f720d351f66` |
| `docs/Checkpoint.md` | `9c89a1c548f676b0f4fc5f865f27f846f7df6ab945126b5156a26eafbec1851d` |
| `docs/Implementation_Roadmap.md` | `6e34452441a247ea4fb0f1913f7ea5a80deffa4cd0e37b4fa66a64f7cda0c194` |
| `docs/PartPilot_V1_Product_Specification.md` | `1dfe7cd20d583b65e190569995a4988bba4ac9fec5260e6f4f8e97d767aa3c8c` |
| `docs/Part_Pilot_Project_Memory.txt` | `c96776965a5713fe6c9caf04cc26a29d7d1bf40f612c485aff623f903d7e02d0` |
| `frontend/src/app/App.tsx` | `9c5447280d0e4e715e50957cf5d9a39e9eaeb9fa819c3003d790a1c44b61db0a` |
| `frontend/src/app/AppLayout.tsx` | `a6dfac524d0f8d900f96e800fcf5deadb400aea231963f2ee5682fc264796bfe` |
| `frontend/src/pages/PlaceholderPage.tsx` | `79f45b149a8839b7d0fcb0c4c46e75202b270268da0185ef278925a64ec244a9` |
| `frontend/src/pages/Reservations.css` | `986d97d997988944ba69c12f10c8c1a82988403020cb4b6affa7b0e3aa078fab` |
| `frontend/src/pages/Reservations.tsx` | `249c88aa8875a267b3c52690afa49576d53d9777ba1d3bf6a690064de120c4e7` |
| `frontend/src/services/partsClient.ts` | `8dc0f4a07610807427e9bc56050ea84b76d504b5466ba377cdc4470f715fa43f` |
| `frontend/src/services/reservationsClient.ts` | `0b0305adbd567c4467909175b0e882b0932f16f444b69cbd57057cd363e5aa36` |
| `frontend/src/types/parts.ts` | `755bb9817dd6e4363ddab11ae34896b68a22b32543832f09b5fbd64c67bca930` |
| `frontend/src/types/reservations.ts` | `0b8d343698f907e43f94ea3cd56558eca32b941d06551157c442ed5e25dd16ff` |

## Anchor counts

### `backend/app/models/core.py`

| Anchor | Count |
|---|---:|
| `class Project(Base, TimestampMixin):` | 1 |
| `class ProjectItem(Base, TimestampMixin):` | 1 |
| `ck_projects_status` | 1 |
| `ck_projects_created_by` | 1 |
| `ck_projects_estimated_total_value_nonnegative` | 1 |
| `ck_project_items_unit_price_snapshot_nonnegative` | 1 |
| `ForeignKey("projects.id", ondelete="SET NULL")` | 1 |

### `backend/app/db/constants.py`

| Anchor | Count |
|---|---:|
| `PROJECT_STATUS_DRAFT = "draft"` | 1 |
| `PROJECT_STATUS_ACTIVE = "active"` | 1 |
| `PROJECT_STATUS_COMPLETED = "completed"` | 1 |
| `PROJECT_STATUS_ARCHIVED = "archived"` | 1 |
| `PROJECT_STATUSES = {` | 1 |

### `backend/app/db/smoke_test.py`

| Anchor | Count |
|---|---:|
| `EXPECTED_AUTH_SCHEMA_HEAD = "0006_reservation_contract"` | 1 |
| `if "active" not in PROJECT_STATUSES` | 1 |
| `def check_reservation_contract_schema()` | 1 |

### `backend/alembic/versions/0001_database_foundation.py`

| Anchor | Count |
|---|---:|
| `        "projects",` | 2 |
| `        "project_items",` | 2 |
| `        "reservations",` | 2 |
| `ck_project_items_quantity_positive` | 1 |
| `ck_projects_status` | 0 |
| `ck_project_items_unit_price_snapshot_nonnegative` | 0 |

### `backend/alembic/versions/0002_schema_hardening.py`

| Anchor | Count |
|---|---:|
| `op.create_index("ix_project_items_project_part"` | 1 |

### `backend/app/services/reservations.py`

| Anchor | Count |
|---|---:|
| `def create_reservation(` | 1 |
| `project_id=None,` | 1 |
| `"project_id": None` | 1 |
| `def consume_reservation(` | 1 |
| `def cancel_reservation(` | 1 |

### `backend/app/api/routes/reservations.py`

| Anchor | Count |
|---|---:|
| `prefix="/reservations"` | 1 |
| `Depends(get_current_user)` | 9 |

### `backend/app/main.py`

| Anchor | Count |
|---|---:|
| `from app.api.routes.reservations import router as reservations_router` | 1 |
| `app.include_router(reservations_router, prefix="/api")` | 1 |
| `projects_router` | 0 |

### `frontend/src/app/App.tsx`

| Anchor | Count |
|---|---:|
| `path="/projects"` | 1 |
| `element={<PlaceholderPage title="Projects" />}` | 1 |

### `frontend/src/pages/Reservations.tsx`

| Anchor | Count |
|---|---:|
| `void searchReservableParts(token, query, controller.signal)` | 1 |
| `const timeout = window.setTimeout` | 1 |
| `}, 280);` | 1 |
| `className="reservation-part-picker"` | 1 |
| `data-partpilot-mobile-landing="PARTPILOT:MOBILE_RESERVATION_LANDING:V343"` | 1 |

### `frontend/src/services/reservationsClient.ts`

| Anchor | Count |
|---|---:|
| `export async function searchReservableParts(` | 1 |
| `limit: "20"` | 1 |
| `.filter((part) => part.available_quantity > 0)` | 1 |

### `docs/PartPilot_V1_Product_Specification.md`

| Anchor | Count |
|---|---:|
| `### 18.3 Project Statuses` | 1 |
| `### 18.4 No Mixed Reserved and Consumed State` | 1 |
| `### 18.5 Project Workflow` | 1 |
| `### 18.6 Project Cost` | 1 |

### `docs/Implementation_Roadmap.md`

| Anchor | Count |
|---|---:|
| `### Project statuses` | 1 |
| `Project starts as Draft` | 1 |
| `Reserved project can later be converted to consumed` | 1 |

## Safety conclusion

Projects can begin safely only after the status/schema contract is aligned. The
next implementation must be a narrow migration/constants/smoke patch, not a
Projects service or UI patch. Project planning remains inventory-neutral; every
Reserve, Consume, and reserved-Cancel operation is one authenticated, atomic,
audited outer transaction built on shared stock/reservation internals. Existing
standalone Reservations and all live data remain protected throughout.
