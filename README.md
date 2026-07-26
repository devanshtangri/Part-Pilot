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
- Browse and search active inventory.
- Filter by stock status and reusable location.
- View responsive part details.
- Edit existing part metadata and typed values.
- Add, remove, consume, and correct quantities with safeguards.
- Review recent stock movement history.
- Soft-delete parts and restore them without losing metadata or history.

### Reusable catalogues

- Manufacturer catalogue with seeded electronics brands and inline creation.
- Package/form-factor catalogue with seeded options and inline creation.
- Location catalogue with create, rename, notes, usage counts, and safe
  in-use deletion protection.
- Custom part types with ordered dynamic fields.
- Safe custom-type editing and deletion safeguards.

### Platform

- First-run setup and authenticated sessions.
- FastAPI, SQLAlchemy, SQLite, and Alembic backend.
- React, TypeScript, and Vite frontend.
- Responsive desktop and mobile application shell.
- Docker Compose deployment with persistent `/data` storage.
- Automated database, API, migration, frontend-build, and route smoke checks.
- Structured audit records for implemented inventory operations.

## Planned V1 work

Major remaining areas include:

- Low-stock dashboard and settings-driven out-of-stock behaviour.
- Universal search completion.
- Reservations and lightweight projects.
- Full history and audit browsing.
- Settings and appearance completion.
- Backup and restore.
- MCP read tools and safeguarded write tools.
- Accessibility, security, responsive, and public-alpha polish.

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
| Stored Parts search and location filtering | Available |
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
