# Part Pilot

Self-hosted electronics inventory manager for makers, hobbyists, small labs, and repair shops.

This repository is currently at **Phase 1: Repository and Project Skeleton**.

## Phase 1 scope

Implemented in this skeleton:

- FastAPI backend app
- `/health` and `/api/health` routes
- Pydantic settings loader
- SQLAlchemy database engine/session setup
- CORS for local frontend development
- React + Vite + TypeScript frontend shell
- React Router setup
- Basic API client
- Sidebar + placeholder dashboard
- Global dark-theme CSS variables
- Single-service Docker Compose setup
- Persistent `./data:/data` volume mapping

Not implemented yet:

- Authentication / first-run setup
- Parts database models
- Inventory APIs
- Add Part flow
- Search
- Projects
- Reservations
- Backups
- MCP

## Local backend development

From the repository root:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example ..\.env
uvicorn app.main:app --reload
```

Backend health checks:

```text
http://localhost:8000/health
http://localhost:8000/api/health
```

## Local frontend development

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

The local `.env.example` uses `../data/partpilot.db` so the database lives in the repository `data/` folder during development.

## Docker Compose

From the repository root:

```bash
copy .env.example .env
docker compose up --build
```

App:

```text
http://localhost:8000
```

Health:

```text
http://localhost:8000/health
```

## Database smoke test

Run the Phase 2 database smoke test inside the container after migrations and seed data are applied:

```bash
docker compose exec -T partpilot python -m app.db.smoke_test
```

The test checks database connectivity, Alembic head state, seed data, SQLite foreign key enforcement, invalid part rejection, and valid sample part rollback.


### Backend DB utilities

Phase 2 includes reusable database helper modules used by later API/service layers:

- `app.db.utils` for normalization, slugs, part display titles, and quantity helpers.
- `app.db.settings` for database-backed app setting reads/writes.
- `app.db.constants` for shared database vocabulary such as movement and reservation statuses.
