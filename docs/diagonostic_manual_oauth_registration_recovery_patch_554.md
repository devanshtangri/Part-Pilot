# Patch 554 Diagnostic — Manual OAuth Registration Recovery

<!-- PARTPILOT:DIAGONOSTIC_MANUAL_OAUTH_REGISTRATION_RECOVERY:V554 -->

Generated: `2026-08-07 05:57:30Z`

## Verdict

**PASS — Chat 20 remains on the exact clean application source and Alembic
0010 baseline. Patch 553 failed before writes only because its expected
SHA-256 for `mcp_oauth_admin_smoke_test.py` was mistyped; HomeLab verified the
actual source is unchanged and every other expected hash matched. Patch 555
may resume the manual OAuth registration implementation.**

## Exact repository and deployment

- Branch: `main`
- HEAD/origin: `670e54caf1b295ee2a0715adc5d42ac2042d9948`
- Git/index at diagnostic start: clean
- Alembic: `0010_mcp_trusted_networks`
- Deployment image: `sha256:2642e15b2b4e412a19d37b62982723f5e85eef1f8e0eacbbd1b29301643963e9`
- Deployment: running, healthy, restart count `0`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Instance-secret mode/size: `0600` / `65`
- Restore staging captured and preservation-checked

## Current core state

- Parts: `15`
- Projects: `8`
- Reservations: `10`
- Users: `1`

## Volatile activity state at diagnostic capture

These are intentionally **reported but not compared to handoff totals**:

- `stock_movements`: `35`
- `audit_log`: `177`
- `sessions`: `4`
- `mcp_oauth_tokens`: `4`
- `mcp_oauth_authorization_codes`: `2`

OAuth token rows, authorization codes, sessions, audit rows, and stock
movements may change through normal application/client activity. Future
preflight must validate semantic invariants and capture-at-start preservation,
not stale absolute totals.

## Why Patch 552 failed

Patch 552 hard-coded:

- `stock_movements = 33`
- `audit_log = 175`

The live database had already legitimately advanced beyond those handoff
snapshots. The two newest stock movements were a manual `+50` restock and
`-50` correction on part `13`, with matching user-attributed audit rows. Their
net stock effect is zero; part `13` is back at `total_quantity=200`.

Patch 552 therefore failed before writes even though Git, source, database
integrity, OAuth connections, Hermes Bearer, deployment, and Alembic were all
healthy.

## Why Patch 553 failed

Patch 553 failed before writes because one hard-coded expected SHA-256 was
typed incorrectly. It expected:

- `b8684e37a5e951827e0e1e8ee2e9eafd5362fd4bec6e00a64df86f40f2d2aa71`

HomeLab verified the actual unchanged `mcp_oauth_admin_smoke_test.py` SHA-256 is:

- `b8684e37a5a951827e0e1e8ee2e9eafd5362fd4bec6e00a64df86f40f2d2aa71`

A comparison of every expected hash in Patch 553 found this was the **only**
mismatch. The repository, source, database, Alembic and deployment remained
clean and unchanged.

## Prior failure chain

- Patch 549 reached copied-database smoke and exposed the no-store-header issue
  for cross-field Pydantic validation.
- Patch 550 failed before writes because it searched an internal log for a
  terminal-only rollback sentence.
- Patch 551 failed before writes because it searched the same internal log for
  terminal-only `Phase:` text.
- Patch 552 failed before writes because it treated volatile history totals as
  immutable.
- Patch 553 failed before writes because one expected source SHA-256 was
  mistyped.

No application-source commit from Patches 549-553 exists.

## OAuth and Hermes semantics

- DB client `9` — `Claude`, auth `client_secret_post`, active consent `1`, active token `1`, token families `1`.
- DB client `13` — `ChatGPT`, auth `none`, active consent `1`, active token `1`, token families `1`.

- Existing OAuth clients remain unrevoked.
- Each has exactly one active consent, one active token, and one token family.
- `registered_by_user_id` remains absent before migration.
- Hermes remains configured through `bearer_key`.
- No existing credential, ciphertext, token value, token-family ID, or secret
  digest is emitted by this report.

## Verified implementation anchors

- `backend/app/models/core.py`: `[1, 1]`
- `backend/app/services/mcp_oauth.py`: `[1, 1]`
- `backend/app/schemas/app_settings.py`: `[1]`
- `backend/app/api/routes/app_settings.py`: `[1, 1, 1]`

Every anchor count is exactly one against the current local source.

## Source hashes

- `backend/app/models/core.py`: `56c4f76497eacf8d5bdc7924c3a1d562ad5277c3bbd8cdf4b299541fdf9a4f28`
- `backend/app/services/mcp_oauth.py`: `d0f46c56923b38fcd7c80c9610c073963561538fc967bbf4e8d36fa57b792824`
- `backend/app/schemas/app_settings.py`: `03079a92a315b4f175d623b7d18ab79a5ab32bac26bbfe2573359ca4194cc032`
- `backend/app/api/routes/app_settings.py`: `1561bc9d90ff29f828f1e63f0d6364a9d72a0a85e52852104478d1798972f38a`
- `backend/app/db/mcp_oauth_admin_smoke_test.py`: `b8684e37a5a951827e0e1e8ee2e9eafd5362fd4bec6e00a64df86f40f2d2aa71`
- `backend/app/db/mcp_oauth_http_smoke_test.py`: `b0525f05880d7e0428daeea2e3f12656ddcc7f8019316e5d5d2a96fd7a870aa2`
- `backend/app/db/mcp_oauth_service_smoke_test.py`: `bddf05a59b3ea31be6af28164ac083da28efb15ed864adb7757f259089ebfe1d`
- `backend/app/db/smoke_test.py`: `96dabad556c32ce133b5680a91a198911578281db59c70e2d1a1891e2fb13268`
- `backend/Dockerfile`: `37841e343fcf891b0e3c6ba30d047388ed0f15861a2e33a17ed9bc426805d506`

## Failure-evidence hashes

- `fixes/549_add_manual_oauth_registration_foundation.py`: `c6134098a0d314433d0475645890aedf820e3bd194e5cef379ea666394efb0f7`
- `fixes/550_recover_manual_oauth_registration_foundation.py`: `dac7bcfc082f51bee2ab1ff3c75732793bf55a9852691d14d3d1d7ccadf247df`
- `fixes/551_recover_manual_oauth_registration_evidence.py`: `2ad9eadc55d812fd803b59aabfb4974b5b7913b2059c66ccb16398fe4f27bbca`
- `fixes/552_diagnose_manual_oauth_registration_recovery.py`: `75c49e506f382ac9d83e4a8554050f682b2f95e6f871ac9c1375b0ab9e037803`
- `fixes/553_recover_manual_oauth_registration_diagnostic.py`: `6d00b3d4a203a272c593cafb520e3f67b38f715585daea6a42d815fbfb65c435`
- `fixes/logs/549_manual_oauth_registration_20260806-174300.log`: `bd844fc4005ebcf83f533d2cc830d94415131e2ab7a2847367d6dbaf7e0155c4`
- `fixes/logs/550_manual_oauth_registration_recovery_20260806-174658.log`: `270b9f47ef0e87e210f484baf42fd7cacd37b598e0c77ab26d6c4fa498312500`
- `fixes/logs/551_manual_oauth_registration_evidence_recovery_20260806-185417.log`: `58bee96871bfe4396e71249b3d4187b6e171c8847ff9abafc273c7bc4a40a015`
- `fixes/logs/552_manual_oauth_registration_recovery_20260807-052530.log`: `9bc78c332049ea7a6264b10180dc781c9a136499230ef7f474b49abb870fec39`
- `fixes/logs/553_manual_oauth_registration_diagnostic_recovery_20260807-053852.log`: `493ac3eff25e7d8082c2dbbfd59459da7ddb4e19a9d0ed96a29eac79a0d94c03`

## Patch 555 implementation plan

1. Validate this diagnostic report/commit, current source hashes, clean
   Git/index, healthy deployment, Alembic `0010`, SQLite integrity, exact table
   set, OAuth client semantics, Hermes mode, secret metadata and restore
   staging.
2. Capture live stable-table state at patch start and compare it after
   candidate/copied-database tests. Do not compare volatile history/session/
   token totals to handoff snapshots.
3. Add Alembic `0011_mcp_oauth_client_ownership`.
4. Add nullable indexed `registered_by_user_id` with named FK to `users.id`,
   `ON DELETE SET NULL`, and no ownership backfill.
5. Extend `register_client()` with explicit `registered_by_user_id`.
6. Add strict protected Settings registration request/response schemas.
7. Keep primitive request validation in Pydantic, but enforce public versus
   confidential authentication-method compatibility inside the protected route
   so all such `422` responses receive no-store headers.
8. Fix grants to `authorization_code` + `refresh_token` and response type to
   `code`.
9. Set both `registered_by_user_id` and audit `actor_user_id` to
   `current_user.id`.
10. Return a confidential plaintext secret exactly once in the creation
    response and persist only its digest.
11. Prove on a copied database: public/confidential creation, ownership,
    user-attributed audit, one-time secret, digest-only storage, plaintext
    absence across text/JSON columns, public/confidential mismatch rejection,
    invalid redirect rejection, unauthenticated `401`, no partial rows, and
    exact copied-database restoration.
12. Preserve Claude, ChatGPT, Hermes, inventory, Projects, Reservations,
    settings, users, instance secret and restore staging.
13. Build/deploy, migrate to `0011`, verify protected endpoint/OpenAPI, run
    migration/OAuth admin/OAuth HTTP/OAuth service/complete smoke, then commit
    and push only the exact backend/migration/smoke files.

## Patch 554 mutation statement

- Application source: unchanged.
- Database: no writes performed by this diagnostic.
- Deployment: unchanged.
- Credentials: unchanged.
- OAuth connections: unchanged.
- Hermes Bearer: unchanged.
- Browser testing: not applicable.
- Commit/push scope: this diagnostic report only.
