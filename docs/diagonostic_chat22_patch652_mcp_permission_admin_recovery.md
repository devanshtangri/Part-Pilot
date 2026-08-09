# Chat 22 Patch 652 diagnostic — MCP permission-admin recovery

## Status

Patches 650 and 651 were both consumed by pre-write failures. Neither changed
application source, SQLite, deployment, the Git index, HEAD or origin/main.

The authoritative application state remains the Patch 649 pending backend
foundation:

- HEAD/origin: `918bb71cf66ace9e8a677c453546e27022b3e20a`
- subject: `Diagnose MCP permission transform recovery`
- deployment:
  `sha256:fc7fdef56a28b775430da5fc0a12658cfff9f948a2163473f92d3dcef15aaf2a`
  healthy, restart count 0
- Alembic: `0016_mcp_tool_permissions (head)`
- Git index: clean
- application working tree: exact 12-file Patch 649 pending set

Patch 652 is diagnostic-only. It commits and pushes only this report.

## Patch 650 failure

Patch 650 script SHA-256:

`ee93d907bedf61d388a61a16270ef6e1717ec5082fa4372ebe930a24ecbdecc6`

Patch 650 log SHA-256:

`24df7c9e2d5e1b061e8371e10e27c09a5ccb49a7a00fdf1057e3adc28ca4a94c`

Patch 650 stopped in phase 1 before writes.

Its shared `runtime()` verifier checked these future candidate routes:

- `GET /api/settings/mcp/tool-permissions`
- `PATCH /api/settings/mcp/oauth-clients/1/permissions`
- `PATCH /api/settings/mcp/direct-clients/1/permissions`

and `preflight()` called that verifier against the Patch 649 baseline image.

The baseline correctly returned:

- future global permission route: HTTP 404
- future OAuth permission route: HTTP 405
- future direct-client permission route: HTTP 405
- existing `GET /api/settings/mcp`: HTTP 401

Therefore Patch 650 required routes that it had not written or deployed yet.
This is a verifier phase-contract error in the patch harness. It does not
invalidate the migration, permission model, API design or rehearsed candidate.

## Patch 651 failure

Patch 651 script SHA-256:

`e8b99ce83c0e30874492a7cb567d6aa7bda1f7d53d5d17e82f81931689951965`

Patch 651 log SHA-256:

`150816e25e93ff0f7299baa4f925d87e5a626cf0146f94a240cd37d0fc00b76c`

Patch 651 also stopped before writes.

Its generated report contained:

`This is a patch-harness phase-contract`

followed on the next source line by:

`bug, not an application-source...`

The diagnostic validator then searched for the contiguous literal:

`patch-harness phase-contract bug`

Because the report intentionally wrapped that sentence across a newline, the
validator rejected its own correct report with `Root cause missing from report`.

This was another unnecessary exact-text self-check. Patch 652 removes semantic
phrase matching entirely.

## Exact pending Patch 649 application fingerprints

- `backend/app/db/backup_smoke_test.py`
  `30a07d9f194855ba98f9325c97928377e1035fa635858937bf5250113eb356b3`
- `backend/app/db/mcp_oauth_smoke_test.py`
  `9d3acd3852c727f9b3c0b02f3da3134de35bf1b572ff12a156b1f736ac8355a4`
- `backend/app/db/mcp_workspace_tools_smoke_test.py`
  `d25b4f4f797ff75bde597bbb926910d1edbd0b1ba05f7f515e5ca494b50cbf60`
- `backend/app/db/seed.py`
  `ae1bc273c74bdcf1aa09fb63294761a3271440dc438d8302ae253f551a856a9f`
- `backend/app/db/smoke_test.py`
  `c2523acb2a696a36d94187871e2169c9a7bffe8b593cabb2e83fa35e921364c1`
- `backend/app/mcp/part_tools.py`
  `e42ccb83c314d6553ed424090ea38fea64033341166e617102452522546aff38`
- `backend/app/mcp/workspace_tools.py`
  `6e418c7e923f548068e32e482acb2082647db2fb873d3d13615e73115db17e37`
- `backend/app/models/core.py`
  `728d0e1ddc50968ccc249b78d1d12cb8128f8f5e763881496bde739519ad7de6`
- `backend/app/services/backups.py`
  `4a6272e02fd34254344a690129c4114ea6d8d8fc359171403d54cad86d2a12c3`
- `backend/alembic/versions/0016_mcp_tool_permissions.py`
  `857e60d71d258670348961f9e9830e502794fb71a7acec68b18cdf5cbeb812f9`
- `backend/app/db/mcp_tool_permissions_smoke_test.py`
  `b3cab6e1906a28ffb77263f90ad6b5233cdb47d3a2c3c558bbfad251fea17b58`
- `backend/app/services/mcp_permissions.py`
  `e5163d53a6020610e26f8147916f3698ac2ffeef631914e910323e7ef85dd00d`

The API files Patch 650 intended to change remain clean at:

- `backend/app/api/routes/app_settings.py`
  `5dc087809244d5d053657c08719c17046ce3c3fe0982910c3041ad597cc4c93e`
- `backend/app/schemas/app_settings.py`
  `402fc2b3aa8c2c589038ed7860276bec1260453df6595b08649d3040db98564d`
- `backend/app/services/mcp_oauth.py`
  `55f322bb2b604deeb9196f8f6acc74ba1b97202fe02692255a7f086c59f68969`

## Database and runtime state

SQLite integrity and foreign-key checks pass.

The global `mcp.tool_permissions` row remains the compatibility default with all
six current tools enabled.

Existing OAuth and named direct clients still have empty `denied_tools_json`
arrays, so all continue to inherit the global policy.

At diagnostic inspection there was one named direct client and ten OAuth
clients. These counts are evidence only, not a Patch 653 preflight invariant.

The three future permission-admin routes remain absent from Patch 649 OpenAPI.
The existing MCP Settings endpoint remains present and protected.

## Rehearsed Patch 650 candidate remains valid

Patch 650 failed before decoding or writing its five-file candidate archive, so
its earlier isolated build and copied-database smoke results remain relevant.

The exact candidate hashes remain:

- `backend/app/api/routes/app_settings.py`
  `4cd3119cc698d6aab8139544746ad9277a2fcc53f12fdc1d0811aa0f160807c9`
- `backend/app/schemas/app_settings.py`
  `85e3aa11e689944f36506d6cc5a562ab95896af7330a17950abcc2ba35c43a62`
- `backend/app/services/mcp_permissions.py`
  `28251c36511c71acae86b298a92b87043ff71bb5b72d16f4f4a5f425d5e01c56`
- `backend/app/services/mcp_oauth.py`
  `6de52724654e9cfb4e7441fc489fe325137c94abff1d699f764bfa4e7e4da61b`
- `backend/app/db/mcp_permission_admin_smoke_test.py`
  `5dbe08b2d355957a9274a0c3fbf5d91ee28ac11992cd475a63f31f3c74f835cb`

## Patch 653 recovery plan

Patch 653 may resume the five-file backend/API implementation after this report
is committed, pushed and re-read.

It must:

1. preflight the exact Patch 652 report commit while allowing only the exact
   12 pending Patch 649 application files;
2. pin Patch 649 success and Patch 650/651 failure evidence;
3. validate the 12 pending hashes and clean index before any write;
4. use separate baseline and candidate runtime verifiers;
5. baseline verification must check only state that already exists:
   deployment identity/health/restart count, Alembic 0016, existing protected
   `/api/settings/mcp`, SPA routes and existing runtime markers;
6. candidate-only route and OpenAPI checks must run only after candidate
   deployment;
7. decode the exact five rehearsed payloads and validate every candidate SHA
   before backup/write;
8. compile Python and run `git diff --check`;
9. canonical Docker build;
10. run the copied-live-database permission-admin, tool-enforcement, workspace,
    OAuth, named-direct, backup and complete Part Pilot smoke suite;
11. do not add the stale legacy `mcp_settings_smoke_test.py` full-flow smoke to
    this slice because it predates V627 required direct-client fields;
12. deploy only after all isolated checks pass;
13. after deployment require all three new permission endpoints to return
    unauthenticated HTTP 401 and require the expected OpenAPI methods;
14. prove live SQLite bytes, all-enabled global compatibility defaults,
    inherit-all per-client defaults, instance secret and restore staging remain
    unchanged;
15. leave the backend/API source uncommitted for the Settings UI browser-test
    slice.

## Conclusion

No redesign is required. Patches 650 and 651 were both blocked by brittle patch
harness validation, while the application source and live Patch 649 foundation
remained intact.

Patch 653 should be a narrow verifier-phase recovery using the already-rehearsed
five-file candidate.
