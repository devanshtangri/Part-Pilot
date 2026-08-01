# Diagnostic — Project consumption recovery (Patch 393)

## Purpose

Patch 393 is diagnostic-only. It records the exact state after two consecutive
pre-write Project-consumption failures and defines the safe implementation plan
for Patch 394.

No application source, deployment, database row, fixture, or inventory value is
changed by this diagnostic.

## Authoritative repository state

- Repository root: `/projects/Part Pilot`
- Branch: `main`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Local HEAD: `94abac66d32cb04f237362110f9e42b59a17692e`
- `origin/main`: `94abac66d32cb04f237362110f9e42b59a17692e`
- Git working tree before Patch 393: clean
- Git index before Patch 393: empty
- Alembic head: `0007_projects_contract`

## Exact source baseline

| Path | SHA-256 |
|---|---|
| `backend/app/services/projects.py` | `751962ed89f9a6893443bebf1831b72ecd48f72e389791d656384baa232cf79f` |
| `backend/app/api/routes/projects.py` | `8e47badef948986be94a3b3ac0fd20015f6ba1319e7302c6f0e142eaac592d1d` |
| `backend/app/db/smoke_test.py` | `3f163b9e74a1237050f4780d4c5f8b081536187b04f2c5b80cc98860b482ac51` |
| `backend/app/services/reservations.py` | `229958deea1ef52d56ba2e8bdb0a574d502c46ccc1ac4850c60cdf7855b61e9e` |
| `backend/app/api/routes/reservations.py` | `fb8e63468fca44aa4c75a7d303a115b57f534d4e3c7175a091bf92576b5930e2` |

The Projects service currently ends immediately after `reserve_project()`. The
Projects routes currently end immediately after
`POST /api/projects/{project_id}/reserve`. The smoke registration currently
places `check_project_reservation_api` directly before the Reservation checks.

These are stable, explicit insertion boundaries for Patch 394.

## Failed script evidence

| Patch | Script SHA-256 | Result |
|---|---|---|
| 391 | `212abaab5c2b7103fb39934aec107704b00a35c204271bf015e8ab3394814043` | Failed during preflight before writes |
| 392 | `e2934fa6643e3bcecc19c45a52d319d2ef7df1c569caf7e5343840bbaff4b25f` | Failed during in-memory transformation validation before writes |

Both failures left:

- working tree clean;
- index empty;
- local HEAD unchanged;
- `origin/main` unchanged;
- application source unchanged;
- deployment unchanged;
- live database unchanged.

## Root cause 1 — Patch 391 pre-deployment route check

Patch 391 called:

```text
POST /api/projects/999999999/consume
```

against the still-deployed Patch 390 application before the new route existed.

The deployed application correctly returned:

```text
405 Method Not Allowed
```

Patch 391 incorrectly required `401/403` during the pre-deployment phase. The
route could only become protected after the new source was built and deployed.

### Required correction

Patch 394 must separate endpoint verification:

- **Pre-deployment:** verify only endpoints that already exist in Patch 390.
- **Post-deployment:** require
  `POST /api/projects/{project_id}/consume` to appear in OpenAPI and return
  `401/403` without authentication.

HTTP checks must set their own failure-command description so a failed request
is not reported as the previous shell command.

## Root cause 2 — Patch 392 payload/version mismatch

Patch 392 updated visible wrapper strings from `V391` to `V392`, but its three
base64-encoded implementation payloads were copied unchanged from Patch 391.

Decoded payload inspection proved:

| Payload | `V391` count | `V392` count |
|---|---:|---:|
| `service_function` | 1 | 0 |
| `route_function` | 1 | 0 |
| `smoke_function` | 1 | 0 |

Therefore, the in-memory transformed Projects service contained:

```text
PARTPILOT:PROJECT_CONSUMPTION_SERVICE:V391
```

while the Patch 392 validator required:

```text
PARTPILOT:PROJECT_CONSUMPTION_SERVICE:V392
```

The validator correctly stopped before any backup or write.

### Required correction

Patch 394 must be generated fresh from decoded source blocks. It must not be
created by blind string replacement over Patch 392.

Before packaging, the generated script must decode its own payloads and verify:

- service payload contains only `PROJECT_CONSUMPTION_SERVICE:V394`;
- route payload contains only `PROJECT_CONSUMPTION_ROUTE:V394`;
- smoke payload contains only `PROJECT_CONSUMPTION_SMOKE:V394`;
- no payload contains `V391`, `V392`, or `V393`;
- the runtime-required markers exactly match the payload markers.

The runtime must repeat equivalent validation before any backup or write.

## Existing Reservation consumption primitive

`backend/app/services/reservations.py` already provides
`consume_reservation(..., commit=False)` with the required inventory invariants:

- locks the active Reservation;
- locks all linked parts;
- verifies physical and reserved quantities;
- reduces `total_quantity` and `reserved_quantity` by the same amount;
- preserves available quantity;
- creates one `consume` stock movement per Reservation item;
- transitions the Reservation from `active` to `consumed`;
- creates `reservation.consumed`;
- rolls back the transaction on any conflict.

The Reservation service does not import the Projects service. Importing
`consume_reservation` into `app.services.projects` does not introduce a circular
service import.

## Safe Patch 394 contract

Patch 394 should modify only:

```text
backend/app/services/projects.py
backend/app/api/routes/projects.py
backend/app/db/smoke_test.py
```

It should add:

```text
POST /api/projects/{project_id}/consume
```

### Service behavior

1. Lock the Project and require status `reserved`.
2. Lock Reservations linked by `project_id`.
3. Require exactly one linked Reservation.
4. Require the linked Reservation to be `active`.
5. Call `consume_reservation(..., commit=False)` in the same transaction.
6. Require the linked Reservation to become `consumed`.
7. Atomically transition the Project from `reserved` to `consumed`.
8. Add one `project.consumed` audit containing:
   - linked Reservation ID;
   - previous and new Project status;
   - previous and new Reservation status;
   - consumed unit count;
   - consume stock-movement IDs.
9. Commit only after both lifecycle transitions and both audit trails succeed.
10. Roll back all inventory, status, movement and audit changes on failure.

### Required guards

Reject:

- missing Project;
- Project not in `reserved`;
- missing linked Reservation;
- multiple linked Reservations;
- linked Reservation not `active`;
- linked Reservation without items;
- deleted or missing linked parts;
- insufficient physical quantity;
- insufficient reserved quantity;
- concurrent inventory change;
- concurrent Project or Reservation status change;
- repeated consumption.

### Smoke coverage

The isolated smoke test must prove:

- unauthenticated consume returns `401/403` after deployment;
- OpenAPI exposes exactly `POST`;
- reserve setup creates the linked active Reservation;
- consumption changes Project `reserved → consumed`;
- consumption changes Reservation `active → consumed`;
- total and reserved quantities decrease together;
- available quantity remains unchanged;
- consume movement snapshots are correct;
- exactly one `reservation.consumed` and one `project.consumed` audit exist;
- repeated consumption is rejected;
- a Reserved Project without a linked Reservation is rejected without mutation;
- fixture cleanup removes only manifest-owned IDs.

## Patch 394 packaging requirements

Patch 394 must:

1. validate the exact post-Patch-393 HEAD and clean Git/index state;
2. validate the exact three target hashes and Reservation primitive hash;
3. validate successful Patch 390 and Patch 393 logs;
4. validate both Patch 391 and 392 failure evidence;
5. generate all target bytes in memory;
6. decode and validate its own embedded payload markers before backup;
7. run pre-deployment checks without probing the absent consume route;
8. back up source, SQLite and active image;
9. write only the three target files;
10. run `git diff --check` and Python compilation;
11. build and deploy;
12. verify the new protected route and OpenAPI only after deployment;
13. run the complete smoke suite against a copied `/data` database;
14. verify live inventory, Projects, Reservations, movements, audits and settings
    are unchanged;
15. restore source, database and deployment on failure;
16. leave source uncommitted for the Chat 15 frontend lifecycle continuation.

## Chat-boundary constraint

Chat 14 owns Patch 366–395.

- Patch 393: this diagnostic-only checkpoint.
- Patch 394: one corrected backend Project-consumption implementation.
- Patch 395: mandatory Chat 14 boundary and handoff.

The boundary must carry the Project-consumption frontend, Project cancellation,
linked Reservation release and remaining lifecycle UI into the next chat. Patch
395 must not claim those items are complete unless Patch 394 and any required
browser work have actually passed.
