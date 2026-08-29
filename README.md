# Part Pilot

Part Pilot is a self-hosted electronics inventory and project management application
for makers, repair benches, engineering teams, classrooms, and small technical labs.
It keeps parts, stock, projects, reservations, history, users, backups, and AI-assisted
inventory workflows in one place while keeping the data under your control.

> **Release status:** the licensed `v1.0.0` release candidate is complete. The
> image-based Docker Compose package and tag-triggered GHCR workflow are prepared, but
> `v1.0.0` has not been tagged or published yet. Until the GHCR images are verified
> public, the source-build installation below remains the authoritative install path.

## Highlights

- **Electronics inventory** — parts, manufacturers, packages, storage locations,
  custom part types, typed fields, pricing, notes, aliases, tags, and purchase links.
- **Stock control** — physical, reserved, and available quantities with low-stock
  thresholds, stock corrections, consumption, movement history, and recoverable
  deletion.
- **Projects and reservations** — plan parts for a project, reserve available stock,
  edit active reservations, consume or cancel them, and retain complete history.
- **Fast search and filtering** — universal inventory search, stock/location/type
  filters, server-backed sorting, pagination, and responsive desktop/mobile views.
- **Multi-user access** — Primary Owner, Administrator, Operator, and Viewer roles
  with protected account and administration boundaries.
- **History and audit trail** — a unified activity register for inventory, projects,
  reservations, users, settings, API access, and supported AI actions.
- **Backups and restore** — portable `.ppbackup` backups with restore validation and
  database safety checks.
- **MCP / AI integration** — connect supported MCP clients such as Claude or ChatGPT
  to read inventory and, when explicitly permitted, perform safeguarded writes.
- **Self-hosted by default** — React/Vite frontend, FastAPI backend, SQLite storage,
  Alembic migrations, and Docker deployment with persistent local data.

## Quick start

### Requirements

- Docker Engine
- Docker Compose v2 (`docker compose`)
- Git

### 1. Clone Part Pilot

```bash
git clone https://github.com/devanshtangri/Part-Pilot.git
cd Part-Pilot
```

### 2. Create your environment file

Linux/macOS:

```bash
cp .env.example .env
```

Windows Command Prompt:

```bat
copy .env.example .env
```

The included Compose file maps host port `7890` to Part Pilot's fixed internal port `8000` (`7890:8000`). To use another host port, edit only the left side of the `ports:` mapping in `docker-compose.yml`, for example `9000:8000`. No Part Pilot port environment variable is required.

### 3. Build and start

```bash
docker compose up -d --build
```

Open:

```text
http://localhost:7890
```

On the first visit, Part Pilot starts the setup flow. The first account created during
initial setup becomes the permanent **Primary Owner**.

### 4. Check the service

```bash
docker compose ps
docker compose logs --tail=100 partpilot
```

A healthy deployment should show the `partpilot` container as healthy. On a fresh installation, container startup automatically migrates the database to the current schema and initializes the built-in catalogue and default settings before Part Pilot is served. Existing initialized databases are migrated without replaying the seed.

## Persistent data

The included Compose file mounts:

```text
./data  ->  /data
```

That directory contains the SQLite database and instance-specific secret material.
Treat the entire directory as private application data and include it in your normal
server backup strategy.

Do **not** delete `./data` unless you intentionally want to remove the Part Pilot
instance and its stored data.

## Configuration

Common settings in `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PARTPILOT_BIND_ADDRESS` | `0.0.0.0` | Host interface used for the published port. |
| `PARTPILOT_PUBLIC_BASE_URL` | empty | Canonical external HTTPS URL when using OAuth/MCP behind a reverse proxy. |
| `PARTPILOT_TRUSTED_PROXY_CIDRS` | empty | Immediate trusted reverse-proxy networks allowed to supply forwarded client/origin data. |
| `PARTPILOT_ENABLE_DEBUG_RESET` | `true` | Enables the server-side Primary-Owner database-reset endpoint. Set `false` to disable it. |
| `PARTPILOT_IMAGE` | `ghcr.io/devanshtangri/part-pilot:v1.0.0` | Image used by `docker-compose.release.yml`; override only when intentionally testing another image/tag. |
| `PARTPILOT_DATA_DIR` | `./data` | Host data directory mounted by `docker-compose.release.yml`. |

After changing `.env`, recreate the service:

```bash
docker compose up -d --force-recreate
```

## Reverse proxy and HTTPS

For an internet-facing deployment, place Part Pilot behind HTTPS using a reverse proxy
such as Nginx, Nginx Proxy Manager, Caddy, or Traefik.

Recommended deployment rules:

- Set `PARTPILOT_PUBLIC_BASE_URL` to the exact public HTTPS origin, for example
  `https://parts.example.com`, when OAuth/MCP discovery is exposed externally.
- Set `PARTPILOT_TRUSTED_PROXY_CIDRS` only to the network(s) of the immediate trusted
  reverse proxy.
- Prevent untrusted clients from bypassing the reverse proxy and reaching the raw
  Part Pilot port directly when forwarded-header trust is enabled.
- Keep the `./data` directory private and outside any publicly served path.

## Users and roles

Part Pilot uses four user levels:

| Role | Intended use |
| --- | --- |
| **Primary Owner** | The permanent first-init account. Full instance ownership and protected destructive/data-management actions. |
| **Administrator** | User administration and broad application management below the Primary Owner boundary. |
| **Operator** | Normal operational inventory/project work without administrative control. |
| **Viewer** | Read-focused access. |

Only the initial setup account can be the Primary Owner. Other accounts cannot be
promoted to Owner, and the Primary Owner cannot be demoted, disabled, or permanently
deleted through normal user management.

## MCP and AI assistants

Part Pilot includes Model Context Protocol (MCP) support so an authorized AI client can
work with the same inventory that you use in the web interface.

The current tool catalogue contains **14 tools**:

- **6 read tools** for inventory, projects, and reservations;
- **8 safeguarded write tools** for supported inventory and project/reservation actions.

Write access is not granted merely because a client can connect. MCP writes remain
bounded by server settings, client permissions, OAuth/direct-client scopes, and the
role of the authorizing Part Pilot user.

Safeguarded writes use a preview/confirmation flow with short-lived confirmation,
idempotency/replay protection, and state-drift checks. Part Pilot deliberately does
**not** expose permanent inventory purge/hard-delete as an MCP tool.

MCP connection and permission management is available from **Settings → MCP**. Depending
on the client and deployment, Part Pilot supports OAuth and controlled direct-client
authentication options. Keep unauthenticated MCP access disabled unless you explicitly
want reachable clients to receive the enabled read-only data.

## Backups and restore

Use Part Pilot's built-in backup tools before upgrades or major configuration changes.
Backups are exported as `.ppbackup` files and are validated during restore.

For additional infrastructure-level protection, back up the complete `./data` directory
while following normal SQLite/container backup practices.

Do not treat a copied database file as a replacement for testing the built-in restore
flow. Keep at least one recent `.ppbackup` file that you have verified can be read by
Part Pilot.

## Upgrading from the source-build installation

Until the published-image installation is released, update a source-based deployment
with:

```bash
git pull --ff-only
docker compose up -d --build
```

Before upgrading:

1. create a fresh Part Pilot backup;
2. keep a copy of the current `./data` directory or server backup;
3. review the release notes for the version you are installing.

Alembic migrations are part of the application startup/runtime workflow; do not manually
edit the SQLite schema.

## Published Docker image

The stable `v1.0.0` distribution is prepared for GitHub Container Registry at:

```text
ghcr.io/devanshtangri/part-pilot:v1.0.0
```

The repository also includes `docker-compose.release.yml`, which pulls that image instead
of building locally. **Until the `v1.0.0` tag has actually been published and the GHCR
package is confirmed public, continue using the source-build Quick start above.**

Once `v1.0.0` is published, a clean image-based installation is:

```bash
mkdir part-pilot
cd part-pilot
curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/devanshtangri/Part-Pilot/v1.0.0/docker-compose.release.yml
curl -fsSLo .env.example https://raw.githubusercontent.com/devanshtangri/Part-Pilot/v1.0.0/.env.example
cp .env.example .env
docker compose pull
docker compose up -d
```

The release Compose file keeps Part Pilot on fixed container port `8000`, defaults to host
port `7890`, and stores persistent application data in `./data`. Change only the left side
of the port mapping if another host port is required.

For an image-based upgrade after publication, create a fresh Part Pilot backup first, then
run:

```bash
docker compose pull
docker compose up -d
```

Do not switch an existing deployment to a different image/tag without first preserving the
current `./data` directory or a verified Part Pilot backup.

## Third-party software and corresponding source

Part Pilot's own license does not replace the licenses of third-party software included in
or used to build the application. Exact notices and collected license/copyright texts for
the locked `v1.0.0` dependency graph are provided in `THIRD_PARTY_NOTICES.md` and
`third_party/licenses/`. The application image also contains those materials under
`/app/third_party/`.

The release workflow is prepared to publish a version-matched companion source image for
Debian GPL/LGPL-covered base-image components:

```text
ghcr.io/devanshtangri/part-pilot-source:v1.0.0
```

After publication, the source archives can be copied out with Docker:

```bash
docker pull ghcr.io/devanshtangri/part-pilot-source:v1.0.0
cid=$(docker create ghcr.io/devanshtangri/part-pilot-source:v1.0.0)
docker cp "$cid:/sources" ./part-pilot-v1.0.0-third-party-sources
docker rm "$cid"
```

The source image is prepared from `third_party/debian-source-files.tsv`, which pins every
source archive by URL, byte size, and SHA-256. Both the application image and companion
source image must be made publicly accessible before `v1.0.0` is announced.

## Security notes

- Use HTTPS for internet-facing deployments.
- Use strong passwords and grant the lowest practical user role.
- Grant MCP/API permissions per client rather than enabling broad access by default.
- Protect `.env`, `./data`, backup files, API credentials, OAuth credentials, and MCP
  direct-client credentials.
- Keep unauthenticated MCP disabled unless its read-only exposure is intentional.
- Set `PARTPILOT_ENABLE_DEBUG_RESET=false` if you do not want the database-reset endpoint
  available on the server at all.
- Keep Docker, the host OS, and the reverse proxy updated.

## Development

Part Pilot's main application stack is:

- **Frontend:** React, TypeScript, Vite
- **Backend:** FastAPI, SQLAlchemy, Alembic
- **Database:** SQLite
- **Deployment:** Docker / Docker Compose

Backend development:

```bash
cd backend
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend development:

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server normally opens on:

```text
http://localhost:5173
```

## Repository layout

```text
backend/     FastAPI application, database models, services, API routes and migrations
frontend/    React/TypeScript web application
docs/        release notes, deployment/project documentation and durable project records
data/        local persistent runtime data; ignored by Git
fixes/       development patch/diagnostic scripts; ignored by Git
```

## Release notes

The current pre-publication release material is available in:

- [`docs/Public_Alpha_Release_Notes.md`](docs/Public_Alpha_Release_Notes.md)
- [`docs/Public_Alpha_Publishing_Checklist.md`](docs/Public_Alpha_Publishing_Checklist.md)

These documents are being reconciled to the final `v1.0.0` release before publication.

## License

Part Pilot's original code, documentation and owned assets are licensed under the
[`Part Pilot Source-Available License Version 1.0`](LICENSE). It permits free personal,
educational and internal organizational use, including self-hosting, operational backups,
migration, configuration and building the **unmodified** source. It does not permit
redistribution, public mirroring, source modification/derivative works, resale, product
incorporation, or offering Part Pilot itself as a hosted/managed/SaaS product to third
parties without separate written permission.

Part Pilot is therefore **source-available, not open source**. Third-party components are
not covered by the Part Pilot license; their own licenses and notices remain authoritative
and are documented in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
`third_party/licenses/`. The application container also carries the exact project license
at `/app/LICENSE` and third-party compliance material under `/app/third_party/`.
