# Diagnostic 810 - Failed diagnostic gate recovery

Generated: 2026-08-28T12:17:02.637543+00:00

## Status

Patch 810 is diagnostic-only. Patches 806 through 809 all stopped before tracked application/configuration writes. The clean Patch 805 application baseline remains authoritative. This report is the required recovery gate before any further bootstrap/port/README/favicon implementation attempt.

## Authoritative state

- Branch: `main`
- Baseline HEAD/origin: `3f175d88b327cd4ac0e24b658a83f1fddb221104`
- Subject: `Diagnose stale bootstrap recovery fingerprints`
- Runtime: `running|healthy|0|sha256:7fca90c47ce7305089a7055083628776c9b2d16abf4567ee79c2c9b3dd3fce68`
- Alembic: `0022_mcp_inventory_part_lifecycle`
- SQLite quick check: `ok`
- Foreign-key violations: `0`
- MCP permission shape: `14` Boolean tool keys; live values remain mutable and were not normalized.
- Private `.env` was read only for a before/after hash comparison; its contents are not included here.

## Actual Primary Owner invariant

Observed `users` columns: `id`, `username`, `password_hash`, `is_active`, `last_login_at`, `created_at`, `updated_at`, `display_name`, `avatar_id`, `avatar_image_data`, `avatar_image_mime`, `avatar_image_sha256`, `avatar_image_size_bytes`, `role`

There is no `users.is_primary_owner` column. Existing source in `backend/app/services/user_admin.py` defines the bootstrap Owner as the lowest user ID, while `backend/app/db/user_roles_smoke_test.py` verifies the first user is active Owner and no later user is Owner. Diagnostic 810 uses only the real columns `id`, `role`, and `is_active`: first user ID `1` is the active Owner and exactly `1` Owner exists. No username or credential material is recorded.

## Exact failure chain

### Patch 806

P806 stopped during isolated Compose rendering because the candidate Compose declares service-level `env_file: .env`, while the isolated snapshot contained only `.env.example`. `--env-file .env.example` controls Compose interpolation but does not satisfy the service-level `.env` file. No tracked candidate write or deployment occurred.

### Patch 807

P807 froze the correct SHA-256 for the P806 log but attached it to a nonexistent filename beginning with `807_` instead of the actual P806 log filename beginning with `806_`. It therefore stopped in preflight. Its immutable log proves it reached only these commands:

- `git branch --show-current`
- `git remote get-url origin`
- `git fetch origin main`
- `git rev-parse HEAD`
- `git rev-parse origin/main`
- `git log -1 --pretty=%s`
- `git status --porcelain=v1 --untracked-files=all`

It did **not** reach `docker inspect`; later runtime evidence cannot legitimately be required from that log.

### Patch 808

P808 remained diagnostic-only but guessed a nonexistent `users.is_primary_owner` column and failed read-only SQLite validation before writing its report.

### Patch 809

P809 corrected the Owner schema inspection, but then incorrectly required P807's log to contain a runtime-inspection result even though P807 had already stopped before that command. P809 therefore also failed before report write.

## Exact clean source shape

- `.env.example` SHA-256: `86f0e298c584bb9c6e71447d6038c44f2c9a9efed15e66953449508eac56bbd2`
- `README.md` SHA-256: `ce387b3cb434753a8b517aa76d80f8e09fae9e030c501451881ee473f4166e9f`
- `backend/Dockerfile` SHA-256: `37841e343fcf891b0e3c6ba30d047388ed0f15861a2e33a17ed9bc426805d506`
- `backend/app/core/config.py` SHA-256: `ca0a39a16b8d145e19e2de151f4f1d106e282cd52add94c09a24ebd7b630f040`
- `backend/app/db/user_roles_smoke_test.py` SHA-256: `d9cbc9b0016a769a5fca7064edc5439eb0df0fbecc45388d24001757ecde6df8`
- `backend/app/services/user_admin.py` SHA-256: `cfbec59962097663e02268b97c69086e1d4f787bb7ad0325dfea535eec94ad92`
- `docker-compose.yml` SHA-256: `90024234bae81fa67ff3997bd9ad9388532b6ef934ec5796c98e06df0fa1b8ce`
- `docs/Checkpoint.md` SHA-256: `e32868cee2b46b8beff060b8d10e83ffc9fb16848a4e81438ab29c82fa264460`
- `docs/Implementation_Roadmap.md` SHA-256: `a3270cbff3950f8ac6bc28c5d7d407d7ffd62d8c25a989ae9b4e200a83a36369`
- `docs/Part_Pilot_Project_Memory.txt` SHA-256: `65076b4034a2a66bf014f49c7e2c9d32f24042f5b7b2c330ea4a9f632bcf425a`
- `docs/diagonostic_805_bootstrap_port_mapping_recovery.md` SHA-256: `288e3c1f9b32c118cc7220c5aab0065840ee8c4c01f7bd7b106d64bef117fd1c`
- `frontend/index.html` SHA-256: `9967e7892b283e7cbd0a3afa06677a15b53ab24b6d3c92a8d865a30374b9d039`

Current browser/release candidate markers remain absent: no startup-bootstrap modules, no favicon, no release Compose/workflow, no LICENSE/COPYING file, and no `v1.0.0` tag. Current README still contains exactly one Day-to-day Docker commands section and one Troubleshooting section; the old host/container port settings remain in the unchanged baseline.

## Recovery gate for Patch 811

Patch 811 may be a Browser Test only after Patch 810 succeeds and this report is inspected. It must preserve the already-approved scope without adding new product behavior:

1. restore bootstrap -> guarded database bootstrap -> Uvicorn on fixed container port `8000`;
2. fresh SQLite migrates to the single Alembic head and receives idempotent built-in/default seed data;
3. interrupted initialization resumes while `setup.completed` is absent;
4. initialized Alembic-managed databases migrate without seed replay;
5. non-empty unversioned SQLite fails closed;
6. remove `PARTPILOT_HOST_PORT` and `PARTPILOT_CONTAINER_PORT`;
7. Compose defaults to direct `7890:8000`, and users change only the host side directly in Compose;
8. remove README Day-to-day Docker commands and Troubleshooting sections;
9. add/link the compact Part Pilot SVG favicon;
10. deploy the exact tested candidate but leave every browser-test source file unstaged, uncommitted and unpushed pending explicit favicon approval.

### Required isolated Compose rehearsal

After constructing the clean candidate snapshot, copy the **candidate** `.env.example` to **snapshot-only** `.env` before invoking Compose. Keep the alternate-port Compose file beside that same isolated `.env`. Never edit, copy out, print, normalize or commit the real repository `.env`.

### Evidence discipline for Patch 811

- Prior failed logs are immutable evidence identified by their exact filenames and hashes; do not infer that a failed patch reached commands absent from its log.
- Validate database schema with `PRAGMA table_info` and existing source before issuing invariant SQL.
- Do not freeze mutable production database hashes, user activity, settings values, credentials or MCP permission values.
- Before writes, validate every transform and candidate hash in an isolated snapshot.
- Keep the Git index clean throughout the Browser Test.

## Conclusion

The repeated P806-P809 failures are patch/diagnostic tooling failures. Git, the approved runtime, production Alembic state and the current application source remain on the clean baseline. Patch 811 can resume the bounded implementation only after this diagnostic is successfully committed and inspected.
