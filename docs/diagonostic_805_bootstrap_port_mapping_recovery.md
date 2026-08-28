# Diagnostic 805 - Bootstrap and Docker port-mapping recovery

Generated: 2026-08-28T11:17:53.318105+00:00

## Status

Patch 805 is diagnostic-only. Patches 802, 803 and 804 all stopped before tracked application/configuration writes. The clean Patch 801 checkpoint remains authoritative. This diagnostic writes and commits only this Markdown report.

## Authoritative baseline

- Branch: `main`
- HEAD/origin before this diagnostic: `e302bff621b8cf2edb748bb33e1eb064b66572e5`
- Subject: `Checkpoint approved Users polish and customer README`
- Runtime: `running|healthy|0|sha256:7fca90c47ce7305089a7055083628776c9b2d16abf4567ee79c2c9b3dd3fce68`
- Alembic: `0022_mcp_inventory_part_lifecycle`
- SQLite quick check: `ok`
- Foreign-key violations: `0`
- Primary Owner ID: `1`
- MCP permission shape: `14` boolean tool keys; live values remain mutable and are not normalized.

### Exact application/configuration hashes

- `.env.example`: `86f0e298c584bb9c6e71447d6038c44f2c9a9efed15e66953449508eac56bbd2`
- `docker-compose.yml`: `90024234bae81fa67ff3997bd9ad9388532b6ef934ec5796c98e06df0fa1b8ce`
- `backend/app/core/config.py`: `ca0a39a16b8d145e19e2de151f4f1d106e282cd52add94c09a24ebd7b630f040`
- `backend/Dockerfile`: `37841e343fcf891b0e3c6ba30d047388ed0f15861a2e33a17ed9bc426805d506`
- `README.md`: `ce387b3cb434753a8b517aa76d80f8e09fae9e030c501451881ee473f4166e9f`
- `docs/Checkpoint.md`: `e32868cee2b46b8beff060b8d10e83ffc9fb16848a4e81438ab29c82fa264460`
- `docs/Implementation_Roadmap.md`: `a3270cbff3950f8ac6bc28c5d7d407d7ffd62d8c25a989ae9b4e200a83a36369`
- `docs/Part_Pilot_Project_Memory.txt`: `65076b4034a2a66bf014f49c7e2c9d32f24042f5b7b2c330ea4a9f632bcf425a`

## Failure sequence

### Patch 802

The isolated image-based Compose rehearsal reached Docker health but a genuinely fresh database did not reach an Alembic revision. This identified a real release blocker: startup must migrate/initialize SQLite before Uvicorn serves a new installation. Patch 802 did not reach tracked release-distribution writes, Git staging, commit, tag or publication.

### Patch 803

Patch 803 attempted the guarded startup-bootstrap recovery but stopped during isolated snapshot construction. The host is Python `3.11.2` and `TarFile.extractall` is `(self, path='.', members=None, *, numeric_owner=False)`; this runtime does not accept the `filter=` keyword used by the patch. The durable P803 log stops before candidate validation or tracked source writes.

### Patch 804

Patch 804 was correctly diagnostic-only, but its diagnostic preflight itself froze three candidate-era fingerprints instead of the actual clean Patch 801 bytes:

- `.env.example`: Patch 804 expected `05293d773153149536dbde404936eef445235868afa179afe243401347b3e4d79`, actual clean P801 baseline `86f0e298c584bb9c6e71447d6038c44f2c9a9efed15e66953449508eac56bbd2`
- `docker-compose.yml`: Patch 804 expected `d0ff4d03bb4bd840435134050bed8240a4c01a73ccc61c4b00f2173b54ae0071`, actual clean P801 baseline `90024234bae81fa67ff3997bd9ad9388532b6ef934ec5796c98e06df0fa1b8ce`
- `backend/app/core/config.py`: Patch 804 expected `d6887c9e95c6d8684977f699f442653eeddf7aac753de95498858362ab5565ad`, actual clean P801 baseline `ca0a39a16b8d145e19e2de151f4f1d106e282cd52add94c09a24ebd7b630f040`

Its first baseline equality check therefore rejected the unchanged repository and stopped before report construction. Patch 804 created no `diagonostic_804_...` report, no 804 durable log, no staging and no commit. The repository did not drift.

## Exact current source shape

- Existing old host-port reference count across `.env.example`, Compose and backend Settings: `3`.
- Existing old container-port reference count across `.env.example`, Compose, backend Settings and Dockerfile: `5`.
- `README.md` contains exactly `1` `Day-to-day Docker commands` section.
- `README.md` contains exactly `1` `Troubleshooting` section.
- Neither startup-bootstrap module is tracked yet.
- The current tracked snapshot contains no symlinks, so Python-3.11-compatible archive extraction can validate every member as a safe relative regular file/directory before calling `extractall()` without `filter=`.

## Owner-approved recovery contract for Patch 806

### Docker ports

1. Part Pilot listens on fixed container HTTP port `8000`.
2. Docker Compose publishes host `7890` to container `8000` by default.
3. Users change the host port by editing only the left side of the Compose mapping, for example `9000:8000`.
4. No `PARTPILOT_HOST_PORT` environment variable is required.
5. No `PARTPILOT_CONTAINER_PORT` environment variable is required.
6. Remove those two keys from `.env.example`, Compose interpolation, backend Settings, Dockerfile runtime command and current README guidance.
7. Existing private `.env` files are not edited. Legacy port keys become ignored once all application/Compose references are removed.
8. `PARTPILOT_BIND_ADDRESS` remains solely a bind-interface control.

Target mapping:

```yaml
ports:
  - "${PARTPILOT_BIND_ADDRESS:-0.0.0.0}:7890:8000"
```

Target startup order:

```text
restore bootstrap -> guarded database bootstrap -> Uvicorn on 0.0.0.0:8000
```

### README

Patch 806 must:

- remove the complete `Day-to-day Docker commands` section;
- remove the complete `Troubleshooting` section;
- explain the default `7890:8000` mapping concisely in Quick start;
- explain that users may change only the host-side `7890` directly in Compose;
- remove `PARTPILOT_HOST_PORT` and `PARTPILOT_CONTAINER_PORT` from the configuration table;
- retain concise first-start database-bootstrap guidance;
- avoid recreating the removed command/reference clutter elsewhere.

### Startup bootstrap

Patch 806 must preserve the already-bounded P803 design:

- pending restore processing remains first;
- fresh/empty SQLite is upgraded to the single Alembic head and receives built-in/default seed data;
- interrupted initialization with missing `setup.completed` resumes idempotent seed;
- initialized Alembic-managed databases migrate but do not reseed;
- an older managed database upgrades automatically to current head;
- a non-empty unversioned SQLite database fails closed rather than being guessed or stamped;
- legitimate template/preference customization remains preserved on restart/upgrade.

## Patch 806 implementation allowlist

1. `.env.example`
2. `docker-compose.yml`
3. `backend/app/core/config.py`
4. `backend/Dockerfile`
5. `backend/app/db/startup_bootstrap.py` (new)
6. `backend/app/db/startup_bootstrap_smoke_test.py` (new)
7. `README.md`
8. `docs/Checkpoint.md`
9. `docs/Implementation_Roadmap.md`
10. `docs/Part_Pilot_Project_Memory.txt`

## Required Patch 806 validation

Before live writes, construct and validate exact candidate bytes in an isolated clean snapshot using Python-3.11-compatible safe tar extraction. Then prove:

- relevant Python compilation and `git diff --check`;
- Compose default host `7890` -> target `8000` with no port environment keys;
- a separately rendered alternate direct mapping such as `19040:8000` works without a Part Pilot port environment variable;
- fresh container startup reaches Alembic `0022_mcp_inventory_part_lifecycle`, receives required defaults and exposes first-run setup;
- interrupted-seed recovery, initialized customization preservation, `0021 -> 0022` upgrade and non-empty-unversioned refusal all pass;
- copied-production startup reaches `0022_mcp_inventory_part_lifecycle`, explicitly skips seed and preserves logical production data;
- canonical Docker build, complete applicable copied-production smoke, protected APIs, SPA/runtime markers, Primary Owner and fourteen-tool MCP policy shape pass;
- only after isolated proof, deploy the exact candidate while keeping the live mapping `7890:8000`;
- live `.env` bytes remain untouched, even if legacy port keys still exist;
- production data, credentials, sessions, integrations, restore evidence and mutable MCP permission values remain unchanged by the patch;
- stage only the ten-file allowlist, commit/push `main`, fetch and verify `HEAD == origin/main`.

## Release sequence after Patch 806

Patch 806 fixes the startup/port/README release blocker only. A later sequential patch may then recover the image-based/GHCR distribution package originally attempted by Patch 802. Do not create a `LICENSE`, `v1.0.0` tag, GHCR publication or GitHub Release as part of Patch 806.
