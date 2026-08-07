# Patch 558 Diagnostic — Manageable OAuth Backend Recovery

<!-- PARTPILOT:DIAGONOSTIC_MANAGEABLE_OAUTH_RECOVERY:V558 -->

Generated: `2026-08-07 07:27:40Z`

## Verdict

**PASS — application source is clean at Patch 555. Patches 556 and 557 failed in smoke-test mechanics before any commit/push. Patch 559 may recover the same manageable OAuth backend implementation after correcting the smoke harness only.**

## Exact baseline

- Branch: `main`
- HEAD/origin: `8a6b8b995532b18576a5e7ee1ac6d024ced673ba`
- Alembic: `0011_mcp_oauth_client_ownership`
- Deployment image: `sha256:523e88a42a7d214eed8b95a252c482d036c3d01709fe47d4f1f8b5ad2bbdb428`
- Deployment: running, healthy, restart count `0`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Claude DB client `9`: connected; ownership remains NULL
- ChatGPT DB client `13`: connected; ownership remains NULL
- Hermes direct auth: bearer key configured
- Application source: exact Patch 555 hashes restored
- Git/index: clean

## Patch 556 failure

1. Secret-safety smoke searched serialized JSON for raw substring `client_secret`, so valid enum value `client_secret_post` caused a false positive.
2. Cleanup attempted `os.replace()` over a Docker bind-mounted SQLite file and Linux returned `EBUSY`.

## Patch 557 failure

Patch 557 corrected those two issues and the first manageable GET returned HTTP 200. Its `full()` smoke then opened `TestClient(app)` a second time in the same process. Part Pilot's MCP `StreamableHTTPSessionManager` is one-shot per process, so the second FastAPI lifespan startup raised:

`StreamableHTTPSessionManager .run() can only be called once per instance.`

Patch 557 contains exactly three `with TestClient(app) as client:` contexts total: one check-only and two in full flow.

## Patch 559 narrow recovery plan

1. Reuse the same manageable OAuth backend schema/service/route design.
2. Keep existing connected-client GET unchanged.
3. Keep separate protected `GET /api/settings/mcp/oauth-clients/manageable`.
4. Keep statuses only `registered`, `connected`, `revoked`; no `Abandoned`.
5. Keep current-user ownership OR OAuth relationship history eligibility.
6. Keep secret-safe response fields only.
7. Use one `TestClient(app)` lifespan for the entire full smoke.
8. Revoke the owned fixture between first and second GET while that same TestClient stays open.
9. Restore copied-DB fixture rows transactionally, never replace the bind-mounted database file.
10. Check exact JSON keys and forbidden credential material, not ambiguous substrings such as `client_secret`.
11. Run manageable, registration, admin and complete copied-database smoke.
12. Deploy only after copied smoke passes.
13. Preserve Claude, ChatGPT, Hermes, inventory/workflow data, instance secret and restore staging.
14. Commit/push only exact backend/schema/route/service/smoke files after all checks pass.

## Mutation statement

Patch 558 is diagnostic-only. It changes no application source, database, deployment, credentials, OAuth connections, Hermes configuration, fixtures, or inventory. Its only intended committed file is this diagnostic report.
