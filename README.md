# Part Pilot

Part Pilot is a self-hosted electronics inventory manager for makers,
hobbyists, repair benches, and small technical labs.

It combines configurable component templates with practical stock workflows,
reusable catalogues, recoverable deletion, audit history, and a responsive
dark interface. The long-term differentiator is MCP integration so approved AI
assistants can understand and act on inventory safely.

> **Project status:** active V1 development. The core inventory workflow is
> usable, but the project is not yet a public-alpha release.

## Current capabilities

### Inventory

- Create parts from built-in or custom part-type templates.
- Store typed template values, part numbers, descriptions, pricing, purchase
  links, notes, packages, manufacturers, and locations.
- Search active inventory across part metadata, catalogues, locations,
  aliases, tags and typed custom fields.
- Use server-backed part-type, location and stock-status filters with
  accurate totals and pagination.
- Sort Available and Out of stock sections independently across the
  complete filtered result set.
- Filter by stock status and reusable location.
- View responsive part details.
- Edit existing part metadata and typed values.
- Add, remove, consume, and correct quantities with safeguards.
- Review recent stock movement history.
- Move parts to Deleted items and restore them without losing metadata or history.
- Permanently purge selected Deleted items with explicit confirmation; active
  Reservations, Draft/Reserved Projects, and reserved quantities block purge.

### Reusable catalogues

- Manufacturer catalogue with seeded electronics brands and inline creation.
- Package/form-factor catalogue with seeded options and inline creation.
- Location catalogue with create, rename, notes, usage counts, and safe
  in-use deletion protection.
- Custom part types with ordered dynamic fields.
- Safe custom-type editing and deletion safeguards, including separate active
  and Deleted-items dependency counts with direct filtered recycle-bin navigation.

### Platform

- First-run setup and authenticated sessions.
- FastAPI, SQLAlchemy, SQLite, and Alembic backend.
- React, TypeScript, and Vite frontend.
- Responsive desktop and mobile application shell.
- Docker Compose deployment with persistent `/data` storage.
- Automated database, API, migration, frontend-build, and route smoke checks.
- Structured audit records for implemented inventory operations.
- Protected system-wide History with unified audit and stock-movement search, filters, pagination and responsive detail inspection.

## Planned V1 work

Major remaining areas include:

- Static Bearer authentication in the MCP runtime.
- Direct-key Settings controls and browser approval.
- Custom-header and trusted-network MCP authentication modes.
- Safeguarded MCP write tools.
- Accessibility, security and public-alpha hardening.

See [`docs/Implementation_Roadmap.md`](docs/Implementation_Roadmap.md) for the
detailed build plan and [`docs/Checkpoint.md`](docs/Checkpoint.md) for durable
project decisions and completed checkpoints.

## Quick start with Docker Compose

### 1. Clone the repository

```bash
git clone https://github.com/devanshtangri/Part-Pilot.git
cd Part-Pilot
```

### 2. Create the environment file

Linux/macOS:

```bash
cp .env.example .env
```

Windows Command Prompt:

```bat
copy .env.example .env
```

The default host port is `7890`. Change `PARTPILOT_HOST_PORT` in `.env` when
needed.

### 3. Build and start Part Pilot

```bash
docker compose up -d --build
```

Open:

```text
http://localhost:7890
```

Persistent application data is stored under:

```text
./data
```

### 4. Check container status

```bash
docker compose ps
docker compose logs --tail=100 partpilot
```

### 5. Run the complete smoke suite

```bash
docker compose exec -T partpilot python -m app.db.smoke_test
```

### 6. Stop the application

```bash
docker compose down
```

Do not delete `./data` unless the database and application state are no longer
needed.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment, install dependencies, then run:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite development server defaults to:

```text
http://localhost:5173
```

## Repository structure

```text
backend/     FastAPI application, models, services, routes, migrations
frontend/    React and TypeScript application
docs/        product specification, roadmap, checkpoints, and handoffs
data/        persistent local runtime data; created during deployment
fixes/       repository patch and diagnostic scripts used during development
```

## Development discipline

Part Pilot is being developed in narrow, verifiable slices:

1. Inspect exact targets.
2. Preflight transformations before writes.
3. Back up changed files.
4. Build and deploy.
5. Run the complete smoke suite.
6. Browser-test UI work.
7. Commit implementation and documentation checkpoints separately.

This keeps the repository recoverable while larger V1 workflows are built.

<!-- PARTPILOT:DASHBOARD_LOW_STOCK_STATUS:START -->
## Current development status

The current checkpoint includes authenticated dashboard stock alerts and a
settings-driven Stored Parts workflow for separating zero-stock matches from
available inventory.

| Capability | Status |
| --- | --- |
| Inventory creation and metadata editing | Available |
| Manufacturer, package, and location catalogues | Available |
| Stock quantity adjustments and movement history | Available |
| Soft deletion and restoration | Available |
| Stored Parts universal search, filters, pagination, and sorting | Available |
| Dashboard low-stock alerts | Available |
| Unconfigured zero-stock detection | Available |
| Settings-driven out-of-stock grouping | Available |
| Explicit In stock, Low, and Out filters | Available |

When grouping is enabled, matching zero-stock parts appear in a dedicated
section below normal Stored Parts results while the All filter is active.
Disabling that preference hides the separate section without removing access
to those parts through the explicit Out filter.
<!-- PARTPILOT:DASHBOARD_LOW_STOCK_STATUS:END -->

<!-- PARTPILOT:INVENTORY_PAGE_MODE_STATUS:START -->
## Focused Inventory workspace

The `/inventory` route now provides the live Stored Parts experience rather
than a placeholder. It reuses the same implementation that remains available
inside Part Manager, avoiding duplicate inventory logic.

The focused Inventory page supports:

- adding and browsing parts;
- search and location filters;
- All, In stock, Low, and Out stock filters;
- settings-driven separation of zero-stock matches;
- part details and stock movement history;
- quantity adjustments;
- metadata editing;
- recoverable deletion and restoration.

Part-type templates and custom-field management remain under
`/part-manager`.
<!-- PARTPILOT:INVENTORY_PAGE_MODE_STATUS:END -->

<!-- PARTPILOT:DASHBOARD_UNIVERSAL_SEARCH_README:START -->
## Universal inventory search

Part Pilot now includes a responsive Dashboard search experience backed by the
inventory API.

**Search coverage**

- part numbers and names;
- descriptions, notes, and packages;
- part types and manufacturers;
- storage locations;
- aliases and tags;
- custom-field names and typed values.

**Result experience**

- live results after a short pause while typing;
- available parts shown before out-of-stock parts;
- separate **Available** and **Out of stock** result cards;
- result sections appear only when they contain matches;
- selected-part quantities, location, notes, package, and custom fields;
- keyboard launch with `/`;
- responsive desktop and mobile layouts;
- out-of-stock visibility controlled by Search settings.

Dashboard and Stored Parts search are complete and browser approved. Stored
Parts now uses the backend universal-search contract with part-type, location
and stock-status filters, accurate pagination, stale-response guards, and
independent full-result sorting for Available and Out of stock sections.
<!-- PARTPILOT:DASHBOARD_UNIVERSAL_SEARCH_README:END -->

<!-- PARTPILOT:PROJECTS_AND_RESERVATIONS:START -->
## Projects and reservations

Part Pilot separates **planning** from **operational inventory commitments**.

Users create a Draft Project for a build, repair, prototype or other planned
work. A Project stores parts, quantities, notes and price snapshots without
changing stock. Reserving the Project creates one linked active Reservation and
atomically commits its planned quantities.

```text
Draft Project
    ↓ Reserve
Reserved Project + Active Reservation
    ├─ Edit    → synchronized Project + Reservation commitment
    ├─ Consume → Consumed Project + Consumed Reservation
    └─ Cancel  → Cancelled Project + Cancelled Reservation
```

| Capability | Status |
|---|---|
| Project register, detail, creation and Draft/Reserved editing | Available |
| Server-backed multi-result part search (up to 50 matches) | Available |
| Price, currency and current-availability snapshots | Available |
| Atomic Project reservation with linked Reservation | Available |
| Atomic Project consumption API and UI | Available |
| Atomic Project cancellation/release API and UI | Available |
| Two-way linked editing from Projects or Reservations | Available |
| Available/reserved/physical quantity accounting | Available |
| Reserve/release/consume movements and paired audits | Available |
| Physical, Reserved and Available history snapshots | Available |
| Reservation activity and lifecycle actions | Available |
| Accessible in-app confirmations and stale-state handling | Available |
| Responsive desktop and mobile workflows | Available |

Project consumption reuses the linked Reservation transaction: physical and
reserved quantities decrease together, available quantity remains unchanged,
both records become `consumed`, and paired movements and audits are written.

Project cancellation also reuses the linked Reservation transaction: reserved
quantity returns to available stock without changing physical totals, both
records become `cancelled`, and paired release movements and audits are written.

A Reserved commitment can be edited from either workspace. Projects preserves
Project-specific description data, while shared names, notes, items, quantities,
price/value snapshots and inventory deltas remain synchronized atomically.
Quantity increases reserve only the additional units; decreases release only the
removed units.

The Reservations page is the operational queue for committed inventory. Manual
Reservation creation is intentionally absent from the frontend so users have one
clear entry path: plan work in Projects, then reserve it. The backend
Reservation-create API remains temporarily available for compatibility while
future API and MCP behavior is defined.

### Planned administration control

A future Settings update will add an authenticated control to enable or disable
the MCP server. Default, restart behavior, transport/tool gating and auditing
will be defined during the MCP implementation phase; the control is not
implemented yet.
<!-- PARTPILOT:PROJECTS_AND_RESERVATIONS:END -->

<!-- PARTPILOT:SYSTEM_HISTORY_README:V410:START -->
## System-wide History

Part Pilot provides a protected chronological register across operational
inventory and audit events.

| Capability | Status |
|---|---|
| Unified audit and stock-movement register | Available |
| Deterministic newest-first pagination | Available |
| Literal text search | Available |
| Kind, entity, event, actor, user and movement filters | Available |
| From/to date filtering | Available |
| Counted filter facets | Available |
| Part, Reservation and Project context | Available |
| Physical, Reserved and Available snapshots | Available |
| Structured Before, After and metadata evidence | Available |
| Desktop register/detail workspace | Available |
| Register-first mobile detail workflow | Available |
| Stale-response protection | Available |

History remains newest-first by design. General sortable columns are omitted
because the available filters support investigation without breaking the
operational timeline. An Oldest-first option can be added later if a concrete
investigation workflow requires it.
<!-- PARTPILOT:SYSTEM_HISTORY_README:V410:END -->

<!-- PARTPILOT:GLOBAL_APPEARANCE_README:V417:START -->
## Global appearance and Settings

Part Pilot provides authenticated installation-wide appearance preferences
with Dark, Light and System modes.

| Capability | Status |
|---|---|
| Persisted Dark, Light and System preferences | Available |
| Pre-paint theme application | Available |
| Live operating-system theme following | Available |
| Server synchronization and audit evidence | Available |
| Responsive Appearance settings | Available |
| Inventory search preference | Available |
| Reservation expiry defaults | Available |
| Accessible database-reset review dialog | Available |
| Light-theme coverage across all current workspaces | Available |
| Explicit active, destructive and disabled states | Available |

The stored preference is applied before the React application renders, so
direct route loads do not flash the opposite theme. System mode follows
`prefers-color-scheme` changes without a reload.

Database reset remains intentionally guarded: Settings presents one review
action, then requires the exact destructive phrase inside an accessible
in-app dialog before the final erase action becomes available.
<!-- PARTPILOT:GLOBAL_APPEARANCE_README:V417:END -->

<!-- PARTPILOT:SETTINGS_COMPLETION_README:V426:START -->
## Completed Settings workspace

The Settings workspace now uses a compact, responsive composition:

| Section | Desktop | Mobile |
|---|---|---|
| Appearance | Full width | Full width |
| Inventory search | Full-width compact row | Full width |
| Reservation defaults | Lower two-column row | Full width |
| Database reset | Equal-height lower card | Full width |

The Inventory preference preserves its server-backed boolean behavior and
explicit Out filter while displaying a concise On/Off/Saving switch. The
Reservation and Database reset cards align on desktop without enlarging
their controls, and return to natural independent heights below the desktop
breakpoint.

Dark, Light and System modes remain installation-wide. The page-level
runtime status and selected theme card identify the active appearance;
duplicate resolved-theme text has been removed.

Backup and restore is the next independent product area. The existing
database-reset action remains a separate guarded permanent operation.
<!-- PARTPILOT:SETTINGS_COMPLETION_README:V426:END -->

<!-- PARTPILOT:BACKUP_RESTORE_README:V457:START -->
## Backup and restore

Part Pilot supports portable manual backups and guarded database restoration.

| Capability | Status |
|---|---|
| Versioned `.ppbackup` artifact | Available |
| SQLite online snapshot | Available |
| Manifest, schema, hash and integrity evidence | Available |
| Protected manual download | Available |
| No-store response headers | Available |
| Strict archive and database validation | Available |
| Review-before-restore workflow | Available |
| Rollback snapshot and atomic replacement | Available |
| Session invalidation after restore | Available |
| Responsive Settings controls | Available |
| Manual-backup status API | Available |
| Scheduled backups | Not implemented |
| Retained server-side backup copies | Not implemented |

A `.ppbackup` contains exactly `manifest.json` and `partpilot.db`. Restore
validation completes before live data is touched. A successful restore uses a
same-filesystem staged replacement, verifies the result, records an audit and
requires every user to sign in again.

Current backup behavior is manual download only. Part Pilot does not schedule
backups and does not retain a server-side copy after the download operation.
The compact manual-backup status display is implemented and available in Settings.
<!-- PARTPILOT:BACKUP_RESTORE_README:V457:END -->


<!-- PARTPILOT:MCP_AUTHENTICATION_README:V580:START -->
## Model Context Protocol authentication and OAuth administration

Part Pilot exposes an authenticated, stateless JSON Streamable HTTP endpoint at
`/mcp`.

| Capability | Status |
|---|---|
| OAuth protected-resource discovery | Available |
| OAuth authorization code with PKCE | Available |
| Access/refresh token rotation and revocation | Available |
| Standalone OAuth consent and error experience | Available |
| Claude and ChatGPT OAuth read-only flows | Verified end to end |
| Connected/manageable OAuth client administration | Available |
| Manual OAuth client registration in Settings | Available |
| Public clients with PKCE and no client secret | Available |
| Confidential clients with secret POST or Basic | Available |
| One-time confidential secret display with digest-only storage | Available |
| Explicit public-origin and Host/Origin validation | Available |
| Global MCP and read/write authorization settings | Available |
| Six read-only inventory, Project and Reservation tools | Available |
| Official Python MCP SDK compatibility | Verified |
| Public Nginx TLS Streamable HTTP path | Verified |
| Static Bearer key authentication | Available |
| Dedicated custom-header key authentication | Available |
| Trusted-network authentication with IPv4/IPv6 CIDRs | Available |
| Direct-auth Settings management and browser UI | Available |
| Safeguarded MCP write tools | Not yet implemented |

The live installation keeps MCP and read tools enabled while write
authorization remains disabled. OAuth client registration supports explicit
current-user ownership for manually created clients, safe manageable-client
status, exact revocation, and one-time confidential secret display. Revoked
clients remain available to backend audit/history semantics but are hidden from
the normal active Settings list.

Claude and ChatGPT OAuth connection flows have been verified end to end.
During Chat 20, a manually registered Claude client also connected successfully
using Claude's fixed callback and `client_secret_post`. Gemini/Google reached
Part Pilot consent and authorization-code issuance during testing, but the
Google callback did not complete a token exchange; Part Pilot's issued code was
not redeemed.

### Current-user account and session administration

| Capability | Status |
|---|---|
| Protected profile read/update API | Available |
| Username normalization and uniqueness | Available |
| Display-name update | Available |
| Built-in avatar persistence/catalogue | Available |
| Database-backed custom avatar upload/crop/removal | Available |
| Current-user avatar state in `/auth/me` | Available |
| Password change requiring current password | Available |
| Current-session-safe password rotation | Available |
| Active-session list and targeted/revoke-all-other controls | Available |
| New-session User-Agent/client-IP capture | Available |
| Account/Security Settings UI | Available |

Built-in avatar IDs are `initials`, `chip`, `circuit`, `terminal`, `storage`,
and `rocket`. Uploaded avatars are normalized server-side and stored in SQLite
so backup/restore preserves them. Sessions created before client-metadata capture
remain honestly reported as Unknown rather than being backfilled or guessed.
<!-- PARTPILOT:MCP_AUTHENTICATION_README:V580:END -->
