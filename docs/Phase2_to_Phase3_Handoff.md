# Part Pilot — Phase 2 to Phase 3 Handoff

Generated: 2026-07-07  
Status: Phase 2 complete, ready for Phase 3 after final verification.

---

## 1. Project

- Product name: **Part Pilot**
- Repository: `https://github.com/devanshtangri/Part-Pilot.git`
- Deployment target: Docker Compose
- Backend: Python, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: React, Vite, TypeScript
- V1 database path in Docker: `/data/partpilot.db`
- Public Docker host port currently used by user: `7890`
- Internal backend/container port: `8000`

Important note for future chats: GitHub only reflects committed code. If debugging local state, first ask for:

```bash
git status --short
```

---

## 2. Locked naming decision

User-facing name is:

```text
Part Pilot
```

Technical/internal names may remain compact where appropriate:

```text
PARTPILOT_* env vars
partpilot.db
partpilot container name
partpilot Python/Docker identifiers
```

Reason: spaces are unsuitable for env prefixes, DB filenames, Docker identifiers, module names, and URLs.

---

## 3. Current completed implementation phases

### Phase 1 — Repository and project skeleton

Completed:
- Backend FastAPI app.
- `/health` and `/api/health` routes.
- Settings loader.
- Database session base wiring.
- Alembic skeleton.
- React/Vite/TypeScript frontend shell.
- Sidebar/dashboard placeholder UI.
- Docker Compose deployment.
- Configurable Docker host/container ports through `.env`.
- User-facing app name updated to `Part Pilot`.

### Phase 2 — Database foundation

Completed:
- Core SQLAlchemy models.
- Alembic migration `0001_database_foundation`.
- Alembic migration `0002_schema_hardening`.
- SQLite foreign key enforcement at runtime.
- Built-in part type seeding.
- Built-in template field seeding.
- Default app settings seeding.
- Backend database utility helpers.
- Database smoke test.

---

## 4. Current database migrations

Expected Alembic head:

```text
0002_schema_hardening
```

Verify with:

```bash
docker compose exec -T partpilot alembic current
```

Expected output includes:

```text
0002_schema_hardening (head)
```

---

## 5. Current core tables

Phase 2 database includes:

```text
app_settings
users
sessions
part_types
part_type_fields
parts
part_field_values
tags
part_tags
aliases
locations
stock_movements
projects
project_items
reservations
reservation_items
audit_log
backups
alembic_version
```

---

## 6. Seed data expectations

After running:

```bash
docker compose exec -T partpilot python -m app.db.seed
```

Expected state:

```text
part_types: 34
part_type_fields: 153
app_settings: 17
```

Important defaults:
- `setup.completed = false`
- `app.display_name = "Part Pilot"`
- `appearance.theme = "dark"`
- `appearance.light_theme_available = true`
- `search.show_out_of_stock_section = true`
- `price.warn_when_missing = true`
- `backups.enabled = true`
- `backups.frequency = "daily"`
- `backups.path = "/data/backups"`
- `mcp.enabled = false`
- `mcp.write_tools_enabled = false`

---

## 7. Current backend DB utility modules

Created in Phase 2.6:

```text
backend/app/db/constants.py
backend/app/db/settings.py
backend/app/db/utils.py
```

Helpers include:
- app setting get/set helpers
- safe JSON-ish app setting value handling
- slug/normalization helpers
- location normalization helper
- part display-title helper: `part_number` first, fallback to `name`
- quantity helper: available = total - reserved
- constants for field types, movement types, project statuses, reservation statuses, actor/source/status values

Smoke test checks these helpers.

---

## 8. Current smoke test

Run:

```bash
docker compose exec -T partpilot python -m app.db.smoke_test
```

Expected checks:
- database connection works
- SQLite foreign keys are enabled
- Alembic is at head
- 34 built-in part types exist
- 153 template fields exist
- 17 default app settings exist
- invalid part without name/part number is rejected
- valid sample part can be inserted and rolled back
- backend DB utilities work

Expected final line:

```text
[PASS] Phase 2 database smoke test completed
```

---

## 9. Important product/database decisions implemented

- Part type is required.
- Quantity is integer-only in V1.
- Either `name` or `part_number` is required.
- `part_number` is optional, but unique when provided.
- Display title should prefer `part_number`; fallback to `name`.
- Total quantity and reserved quantity are stored.
- Available quantity is derived: `total_quantity - reserved_quantity`.
- Reserved quantity cannot exceed total quantity.
- Price fields are optional.
- Location is optional.
- Locations are simple normalized text entries in V1.
- Deleted parts are soft-deleted from active views, with audit/snapshot preservation strategy.
- Built-in templates are seeded, but later editable/restorable through Part Manager.
- MCP defaults are disabled until user enables them later.

---

## 10. Phase 3 target

Start Phase 3 next: **First-run Setup and Authentication**.

Phase 3 should implement:
- setup status detection using `setup.completed`
- first-run setup backend endpoints
- password hashing
- first user creation
- app settings update for currency/timezone/theme/setup completion
- login endpoint
- logout endpoint
- session token creation
- session token expiry
- auth dependency for protected API routes
- frontend setup page
- frontend login page
- frontend session persistence
- redirect unauthenticated users to login

Phase 3 should not start MCP, inventory CRUD UI, advanced search, backups UI, or project/reservation behavior yet.

---

## 11. First command to run in the next chat

Before making Phase 3 changes, run:

```bash
git status --short
git log --oneline -8
docker compose exec -T partpilot python -m app.db.smoke_test
```

Use the output to verify local state matches the committed Phase 2 baseline.
