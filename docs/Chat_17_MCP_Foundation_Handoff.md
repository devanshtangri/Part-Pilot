# Chat 17 → Chat 18 Handoff

## Next chat identity

**Required title:** `Chat 18: Static Bearer MCP Integration`
**Patch range:** 488–517 inclusive
**Planned boundary:** Patch 517
**First patch:** 488

Do not create a separate Chat 18 starting-prompt document. The ready-to-paste
prompt is provided in Chat 17 only after Patch 487 ends with `Everything PASS`.

## Authoritative boundary state

Before Patch 487 documentation commit:

- branch: `main`
- local `HEAD` and `origin/main`: `219c0b9cd39efc2b62b5296a841432c7a0d7d5f4`
- latest subject: `Add MCP direct key management API`
- Git working tree and index: clean
- Compose service: healthy, restart count `0`
- deployment image: `sha256:ffd7330722d3150551894ebe24cc95e3275ea3ba9d9860894966388cb54bbcad`
- Alembic: `0009_mcp_direct_auth`
- database SHA-256: `1c242eeb874136578ee7d9af8b508c7c7a5a9e396c4b7965d31577cb9136c7b4`
- database logical rows hash: `6f4632f2c05ced870f9a8c520312a2a2541d6c4285826931b070d1455bb071bc`
- SQLite integrity: `ok`; foreign-key violations: `0`
- direct-auth rows: `0`
- OAuth clients/tokens: `0/`
  `0`
- instance-secret file: absent
- restore staging operations: `3`
- pending restore jobs: `0`

Patch 487 prints the new boundary commit hash. Inspect it rather than assuming
it from this handoff.

## Read first in Chat 18

1. `docs/Chat_17_MCP_Foundation_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `docs/Part_Pilot_Project_Memory.txt`
5. `README.md`
6. `docs/diagonostic_mcp_direct_auth_patch_481.md`
7. Patch 486 script and success log
8. Exact current runtime, tool principal and audit source

Then inspect HomeLab Git/index, deployment, database, restore staging and source
hashes before issuing Patch 488.

## Completed Chat 17 work

### Backup status finalization

- The manual-backup status UI is implemented, browser approved and committed.
- Settings reports manual mode, no scheduling, no retained server copy,
  recorded download count and latest artifact metadata.

### OAuth and runtime foundation

- Alembic `0008_mcp_oauth` persists clients, authorization codes, tokens and
  consent.
- OAuth supports PKCE S256, public/confidential clients, refresh rotation,
  replay handling, revocation and scope validation.
- Protected-resource, authorization and token endpoints are committed.
- `/mcp` uses stateless JSON Streamable HTTP.
- The gateway validates externally visible host/origin and issues OAuth
  protected-resource challenges.
- Global MCP enabled and read-tool settings gate access.
- OAuth is currently the only active runtime authentication path.

### Read-only tools

The committed registry contains exactly:

- `search_parts`
- `get_part_details`
- `list_projects`
- `get_project_details`
- `list_reservations`
- `get_reservation_details`

Tool calls use canonical application services and create secret-free
`mcp.tool_called` audits.

### Direct-key backend

- Alembic `0009_mcp_direct_auth` adds a singleton direct-auth table.
- Direct keys use `pp_mcp_key_` plus secure random material.
- Validation uses a keyed digest and constant-time comparison.
- Recoverable plaintext is encrypted at rest with a stable instance secret.
- Rotation invalidates the old key immediately.
- Reveal, disable and throttled last-use tracking are implemented.
- Audits never contain plaintext, ciphertext or complete digests.
- Protected management endpoints:
  - `GET /api/settings/mcp/direct-auth`
  - `POST /api/settings/mcp/direct-auth/bearer-key`
  - `POST /api/settings/mcp/direct-auth/reveal`
  - `DELETE /api/settings/mcp/direct-auth`
- Secret responses use no-store/no-cache.
- The persistent instance-secret file is created with mode `0600` only on the
  first real rotation.
- No direct-auth row, key or secret file exists at this boundary.

## Recovery evidence

- Patch 482 failed because unrelated smoke fixtures changed only
  `app_settings.updated_at` on a disposable copy.
- Patch 483 isolated mutating smoke and committed direct-auth persistence and
  service primitives.
- Patch 484 failed because its new smoke assumed `sqlite_sequence` existed.
- Patch 485 fixed sequence handling but applied `create=True` to
  `digest_bearer_key()` instead of `rotate_bearer_key()`.
- Patch 486 fixed the scoped transform, improved response diagnostics, passed
  all candidate/deployed-image smoke, committed and pushed the management API.

## Patch 488 task

Patch 488 should be diagnostic/implementation-preflight focused and must inspect:

- `backend/app/mcp/runtime.py`
- `backend/app/mcp/part_tools.py`
- `backend/app/mcp/workspace_tools.py`
- `backend/app/services/mcp_direct_auth.py`
- `backend/app/services/mcp_oauth.py`
- `backend/app/db/mcp_transport_smoke_test.py`
- direct-auth service/API smoke
- current database, deployment and restore staging

The implementation should:

1. Detect only `pp_mcp_key_...` Bearer values as direct credentials.
2. Leave every other Bearer value on the existing OAuth validation path.
3. Validate direct credentials through `validate_bearer_key`.
4. Preserve host/origin validation and MCP enabled/read-tool gating.
5. Define a principal shape accepted by all six tools.
6. Allow direct-key tool audits without fabricating an OAuth client or user.
7. Never log or audit the supplied key.
8. Verify correct, wrong, rotated, disabled and missing-secret behavior.
9. Prove OAuth remains fully functional.
10. Use copied-database smoke for mutations and preserve live data exactly.

Do not add frontend controls, custom-header auth, trusted-network auth or write
tools in the same patch.

## Live data to preserve

- users: `1`
- sessions: `3`
- part types: `36`
- manufacturers: `9`
- packages: `23`
- locations: `1`
- parts: `15`
- projects: `7`
- project items: `10`
- reservations: `9`
- reservation items: `14`
- stock movements: `32`
- audits: `105`
- app settings: `17`
- OAuth clients: `0`
- OAuth tokens: `0`
- direct-auth rows: `0`

The six realistic Patch 401 parts and all current History remain intentionally
preserved.
