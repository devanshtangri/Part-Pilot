# Chat 22 Patch 643 diagnostic — MCP individual-tool and per-client permissions

## Status

Patch 642 checkpointed and pushed the browser-approved Projects/header and
821-1080 navigation-drawer regression fixes. The repository is clean at
`d7ae6dd08c2e5beb1d8c915931ced0816a0f6749`, deployment remains healthy on
Alembic `0015_mcp_direct_clients`, and MCP permission work can now resume from a
committed baseline.

Patch 643 is diagnostic-only. It does not change application source, schema,
deployment, credentials, inventory, Projects, Reservations or live MCP client
configuration.

## Exact MCP tool registry

Part Pilot currently registers exactly six MCP tools:

1. `search_parts`
2. `get_part_details`
3. `list_projects`
4. `get_project_details`
5. `list_reservations`
6. `get_reservation_details`

`part_tools.py` owns the two inventory tools and `workspace_tools.py` owns the
four Project/Reservation tools. Every current tool is annotated read-only,
non-destructive and idempotent.

The registry is static: `runtime.py` creates one `FastMCP` instance and calls
`register_part_tools()` plus `register_workspace_tools()` at import time.

## Current authorization stack

The existing authorization layers are:

1. `mcp.enabled` — MCP server master.
2. OAuth/direct authentication — establish a principal.
3. `mcp:read` — required for all six current tools.
4. `mcp.read_tools_enabled` — global read-tool master.
5. The tool function performs its business query.
6. The existing `mcp.tool_called` audit records success/failure.

`mcp.write_tools_enabled` can make `mcp:write` available as an OAuth scope, but
there are still no write tools in the registered tool set. Write authorization
must remain off during this permission slice.

The six tool functions currently call `_ensure_read_tools_enabled(db)`. There
is no individual-tool policy yet.

## Principal identity seams

The runtime already carries enough stable identity for per-client policy:

### OAuth

OAuth principals contain:

- `auth_method = "oauth"`
- `actor_user_id`
- `oauth.token_id`
- `oauth.client_database_id`
- `oauth.client_id`

`oauth.client_database_id` is the correct stable key for a client-specific
permission lookup.

### Named direct clients

Bearer, custom-header and trusted-network principals contain:

- `direct_auth_id`
- `direct_client_name`
- optional `client_ip`

`direct_auth_id` is the correct stable key for direct-client policy.

### No authentication

No-auth deliberately contains:

- `direct_auth_id = None`
- `direct_client_name = "No authentication"`
- resolved `client_ip`

No-auth is not a named client and must not be given an invented database
identity merely to support overrides. It should inherit global tool policy only.

## Recommended permission semantics

Use a layered, least-privilege contract.

### Global policy

Add one canonical global setting:

`mcp.tool_permissions`

Its JSON value is an object containing the exact registered read-tool names and
booleans. For the existing installation and fresh upgrades, all six values begin
`true` so behavior is preserved.

The existing `mcp.read_tools_enabled` remains the read-tool master. A tool is
never allowed when the read master is off, regardless of its individual global
value.

Unknown tool names must never be silently enabled. The permission service must
validate the stored map against the canonical tool catalogue. Missing policy on
an upgrade path may use the explicit compatibility default of all six current
read tools enabled; malformed persisted policy should fail closed rather than
silently grant access.

### Per-client policy

Per-client policy should refine, never bypass, the global policy.

Use a `denied_tools_json` list on each named OAuth/direct client:

- omitted from the list = inherit the global policy;
- present in the list = deny this tool for this client.

There is intentionally no per-client "force allow" that can override a global
disable. Effective permission is:

`server enabled`
AND `mcp:read present`
AND `read-tools master enabled`
AND `global tool enabled`
AND `tool not denied for this named client`.

No-auth has no per-client denied list and therefore stops at the global policy.

This model is clearer and safer than a tri-state allow/deny map: global policy
is a hard ceiling, client policy only removes privilege.

## Persistence recommendation

Do not overload `McpOAuthClient.metadata_json`. That field is OAuth registration
metadata and mixing Part Pilot authorization policy into client-supplied
metadata would blur trust boundaries.

The named direct model has no safe existing policy field.

Patch 644 should therefore introduce Alembic `0016_mcp_tool_permissions` with:

- `mcp_oauth_clients.denied_tools_json`
- `mcp_direct_auth.denied_tools_json`

Both should be JSON arrays with an empty-list default for existing rows and new
clients.

The same migration should insert `mcp.tool_permissions` when missing, with all
six current read tools enabled. Fresh-install seed defaults in
`backend/app/db/seed.py` must contain the same canonical map.

The migration must preserve every existing OAuth/direct client, token, consent,
credential, revocation state and direct-client secret byte-for-byte except for
the new policy columns/defaults.

## Canonical permission catalogue

Create one backend catalogue that owns permission metadata for all registered
tools. At minimum each entry needs:

- exact MCP tool name;
- human-readable label;
- capability (`read` for all six current tools);
- stable ordering for Settings UI.

A smoke test must prove the catalogue's names equal the actual FastMCP registered
tool names. This prevents a future tool from being registered without an
explicit permission classification.

Future write tools must not inherit an implicit allow. Adding a write tool must
require an explicit catalogue entry and remain gated by `mcp.write_tools_enabled`
plus its own safeguarded contract.

## Runtime enforcement seam

Replace the coarse `_ensure_read_tools_enabled(db)` call with a shared
tool-specific authorization function, for example:

`authorize_mcp_tool(db, principal, tool_name)`

The guard should execute before any business-data lookup and should:

1. validate the tool exists in the canonical catalogue;
2. require the appropriate MCP scope/master capability;
3. load the global individual-tool policy;
4. when OAuth, load the current OAuth client by `client_database_id`;
5. when named direct, load the current direct client by `direct_auth_id`;
6. deny if the tool is in that client's `denied_tools_json`;
7. treat no-auth as global-only;
8. raise a dedicated permission-denied error before business data access.

The existing tool exception/audit paths should record denied calls as
`mcp.tool_called` failures with the tool name and client attribution, without
secret material.

Changing global or per-client permissions should affect subsequent calls
immediately; OAuth tokens do not need rotation because `mcp:read` remains a
coarser prerequisite rather than the individual-tool policy carrier.

## Tool discovery limitation

The installed FastMCP SDK exposes:

- `FastMCP.list_tools(self)` with no request/context parameter and a direct
  static tool-manager listing;
- `FastMCP.call_tool(self, name, arguments)` which obtains the active request
  context before invoking the tool.

Therefore the low-risk implementation should enforce permissions at
`tools/call`. Denied tools may remain discoverable in `tools/list`.

Do not fork or monkey-patch MCP protocol internals merely to hide per-client
tools in this slice. Context-aware discovery filtering can be evaluated later if
the SDK provides a supported hook. The security boundary is call authorization,
not UI concealment.

## Session-only administration API

Permission administration must remain under the existing authenticated Settings
API; REST API keys and MCP credentials must not administer MCP permissions.

Recommended API shape:

- global GET/PATCH permission policy under `/api/settings/mcp/...`;
- OAuth-client policy update keyed by OAuth database ID;
- named-direct-client policy update keyed by direct client ID.

The API should accept only canonical tool names. Per-client payloads should
represent the denied-tool set, not arbitrary allow overrides.

OAuth policy editing should use the same "manageable client" ownership/consent
semantics already used by current Settings administration and must reject
revoked clients. Direct-client policy editing should reject revoked records.

Permission changes need secret-free audit events with before/after denied-tool
sets or global booleans.

## Settings UI contract

The browser-test UI should preserve the current flat/dense MCP layout.

### Global tools

Under MCP permissions/security, show the six canonical read tools as dense rows
with individual switches. They are subordinate to:

- Enable MCP server;
- Read tools.

If either master is off, individual rows remain visible but muted/disabled so
the hierarchy is understandable.

`Write authorization` remains off and continues to say that no write tools are
available.

### Per-client tools

OAuth and named-direct client cards should expose a `Permissions` action. A
single accessible dialog can show the six tools with:

- inherited global state;
- client-specific block control;
- effective allowed/blocked result.

Do not add a permission editor for no-auth. Its warning should state that it can
use only globally enabled read tools.

Revoked OAuth/direct clients stay non-editable.

## Backup/restore implications

Backup compatibility is exact-revision and exact-critical-schema.

Current backup constants are:

- revision `0015_mcp_direct_clients`;
- critical schema SHA-256
  `4c4017e84da3725adc5c20060e0452ad37aded19493b1c9b2a46e7c714f7f339`.

Adding columns to both MCP client tables changes the critical schema hash.
Therefore the implementation must:

1. advance backup revision support to `0016_mcp_tool_permissions`;
2. freeze the new critical schema SHA;
3. add the `0015` contract to legacy/unsupported backup contracts;
4. update backup/restore smokes;
5. update OAuth schema smoke expected columns;
6. update direct-client migration/schema smokes;
7. prove copied-backup restore preserves global policy and both clients'
   denied-tool sets exactly.

Existing backup data itself already includes `app_settings`, `mcp_direct_auth`
and all OAuth tables, so no new backup scope category is needed.

## Existing smoke-test seams

The following tests are direct extension points:

- `mcp_workspace_tools_smoke_test.py`
  - already calls all four workspace tools with an OAuth client;
  - add global deny, OAuth-client deny and audit-denial assertions.
- inventory MCP tests / Part-tool path
  - cover the two inventory tools with the same policy guard.
- `mcp_settings_smoke_test.py`
  - extend global policy API persistence/validation/audit coverage.
- `mcp_oauth_smoke_test.py`
  - advance head and expected OAuth client columns.
- `mcp_named_direct_clients_smoke_test.py`
  - verify new clients inherit and one client's denied tools do not affect
    another client.
- direct Bearer/custom-header/trusted-network transport smokes
  - prove per-client policy is enforced regardless of direct authentication
    mode.
- `backup_smoke_test.py`
  - advance exact schema/restore policy.
- complete `smoke_test.py`
  - remains mandatory.

Tests must use manifest-owned/temporary client IDs only and restore the live
database exactly.

## Exact source fingerprints inspected

- `backend/app/mcp/part_tools.py`
  `3630f50532f0a2a77fe5f06571d20283afd8879c4cabd661ffbb9a4a8fa581fa`
- `backend/app/mcp/runtime.py`
  `07835598a918ad6e7527fcb53dd523b9be9ec485bca14dc05ecaf4ce3b97b6e0`
- `backend/app/mcp/workspace_tools.py`
  `e0e9916ca8345a1e822fe63650ce84648d6fbc30a0b71156eeff1538c1c942a6`
- `backend/app/models/core.py`
  `ff93a4ac6466562cd41db734d4c0e9977b9a6566b5cf41da4714f354c9ebd7d6`
- `backend/app/services/app_settings.py`
  `6fa9ce3a14ddb5ab034596bde2d7005c9ac3a2b6ef92474aa3c778d315481230`
- `backend/app/services/mcp_oauth.py`
  `55f322bb2b604deeb9196f8f6acc74ba1b97202fe02692255a7f086c59f68969`
- `backend/app/services/mcp_direct_auth.py`
  `971dcadfde3240a9b8c342f018146902e7b905b9acaf9cc23ffe98495e131c48`
- `backend/app/services/backups.py`
  `9e8d68da13b2e1e79c8d595318962ad1c2e5c3f281ce9f9dae2dcfb602b2c6a9`
- `backend/app/schemas/app_settings.py`
  `402fc2b3aa8c2c589038ed7860276bec1260453df6595b08649d3040db98564d`
- `backend/app/api/routes/app_settings.py`
  `5dc087809244d5d053657c08719c17046ce3c3fe0982910c3041ad597cc4c93e`
- `backend/app/db/seed.py`
  `6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de`
- `frontend/src/pages/Settings.tsx`
  `e53c208dc3ef90486d978376cbc9b125f2af9ee79fc62c06c2411bf5017a3bd3`
- `frontend/src/components/McpDirectClientsSection.tsx`
  `c67b1d2677e4903516f60c579099cf2ea527b884d62cee2d3b968608b49a2251`
- `frontend/src/pages/Settings.css`
  `6977439610e6f307c7840c5f24e59ba5143105d4fbc4d356746e0484953e5804`
- `frontend/src/services/settingsClient.ts`
  `7c7eb10f6634348d083b965248f153a1dc95f1c6197b4c9f75c97306e01841cb`
- `frontend/src/types/settings.ts`
  `4657413f08cd178c646258b26d0f0a1bdd533ba519c0e25b49a6a37f118756ca`

The duplicated settings-client line above is intentionally called out as a
diagnostic generation hazard: Patch 644 must use the repository's exact current
SHA rather than copying a stale or mistyped report value.

## Safe implementation sequence

### Patch 644 — backend/schema foundation

- Re-read this report and exact clean source.
- Create Alembic `0016_mcp_tool_permissions`.
- Add canonical tool catalogue and global policy service.
- Add `denied_tools_json` to OAuth/direct clients.
- Seed/upgrade compatible defaults.
- Add tool-call authorization guard and denial audit behavior.
- Advance backup/restore exact schema contracts.
- Extend backend smokes.
- Keep all six existing tools functionally enabled by default and write tools
  unavailable.

This is backend/security behavior and should not yet redesign Settings visually.

### Patch 645 — administration API / client semantics

- Expose validated session-only global and per-client policy administration.
- Extend OAuth/direct client response types with inherited/effective policy
  information as needed.
- Prove revoked/no-auth boundaries and immediate effect on existing OAuth tokens
  and all direct authentication modes.

### Patch 646 — Browser Test

- Add dense global tool rows.
- Add per-OAuth and per-direct-client Permissions controls/dialog.
- Show inherited/global/effective semantics accessibly.
- Preserve current MCP layout, disabled-state hierarchy and mobile behavior.

### Patch 647 — checkpoint after explicit browser approval

Commit/push the permission batch promptly, then continue broader Settings
organization.

## Non-goals for this slice

- no MCP write tools;
- no permission bypass of the global master/read scope;
- no invented no-auth client identity;
- no REST API-key administration of MCP policy;
- no token rotation solely because a tool permission changes;
- no unsupported FastMCP monkey-patching for per-client `tools/list` filtering;
- no broader Settings redesign until the permission slice is checkpointed.
