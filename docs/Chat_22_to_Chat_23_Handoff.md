# Chat 22 to Chat 23 Handoff

<!-- PARTPILOT:CHAT22_TO_CHAT23_HANDOFF:V660 -->

## Chat 23 identity

- Title: `Chat 23: MCP Permission Finalization and Settings Modernization`
- Patch range: `661-685`
- First patch: `661`
- Planned boundary: `685`
- Start by reading this handoff, `docs/Checkpoint.md`,
  `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`,
  `README.md`, and
  `docs/diagonostic_chat22_patch659_boundary_recovery.md`.
- Do not create a starting-prompt file.

## Exact boundary state

- Boundary recovery patch: `660`
- Pre-recovery HEAD/origin:
  `55a061670387ac22368cef65f1dcbf3a9489ad5e`
- Pre-recovery subject: `Diagnose Chat 22 boundary recovery`
- Branch: `main`
- Git index: clean
- Working tree: exactly 22 pending application files; they are authoritative
  browser-test source and must not be discarded, reset, overwritten, staged or
  committed before approval/checkpoint.
- Deployment image:
  `sha256:06018f157cdad0af9132a224fa0ad9e58579edbedc863f912bc5661aec4cd2c6`
- Deployment: healthy, restart count `0`
- Alembic: `0016_mcp_tool_permissions`
- SQLite SHA-256:
  `0d07bfbc3541a3611fd5660d47bc3df18ea9759a934a9eda772d02034badd424`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- `.dockerignore` SHA-256:
  `2bd494395e3997ded13aa0ab44b03ee242d8d3dc45af992d595f2e46c5da27e6`
- Live global MCP tool policy:
  - `search_parts=false`
  - `get_part_details=true`
  - `list_projects=true`
  - `get_project_details=true`
  - `list_reservations=true`
  - `get_reservation_details=true`
- OAuth and direct-client `denied_tools_json` lists are empty.
- MCP server/read are enabled. No safeguarded write tools are registered.

## Exact pending application files

Modified:

- `backend/app/api/routes/app_settings.py`
- `backend/app/db/backup_smoke_test.py`
- `backend/app/db/mcp_oauth_smoke_test.py`
- `backend/app/db/mcp_workspace_tools_smoke_test.py`
- `backend/app/db/seed.py`
- `backend/app/db/smoke_test.py`
- `backend/app/mcp/part_tools.py`
- `backend/app/mcp/workspace_tools.py`
- `backend/app/models/core.py`
- `backend/app/schemas/app_settings.py`
- `backend/app/services/backups.py`
- `backend/app/services/mcp_oauth.py`
- `frontend/src/components/McpDirectClientsSection.tsx`
- `frontend/src/pages/Settings.css`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/services/settingsClient.ts`
- `frontend/src/types/settings.ts`

Untracked:

- `backend/alembic/versions/0016_mcp_tool_permissions.py`
- `backend/app/db/mcp_permission_admin_smoke_test.py`
- `backend/app/db/mcp_tool_permissions_smoke_test.py`
- `backend/app/services/mcp_permissions.py`
- `frontend/src/components/McpClientPermissionsDialog.tsx`

## Current MCP permission architecture

- Canonical global setting: `mcp.tool_permissions`, exact tool name -> bool.
- Six current read tools default true for compatibility.
- Global policy is the hard ceiling.
- OAuth and named-direct clients persist `denied_tools_json`; policy is
  inherit-or-deny only and can never force-allow through the global ceiling.
- No-auth has no invented client identity and receives only global policy.
- Effective read permission requires MCP enabled, `mcp:read`, read-tools
  enabled, the global tool enabled and no named-client deny.
- Unknown or malformed policy fails closed.
- Existing credentials observe permission changes immediately.
- `tools/call` authorization runs before business lookup and denied calls use
  the normal secret-free `mcp.tool_called` failure audit.
- No write tools are registered.

Patch 654 added the browser-test Settings UI with global read-tool controls,
OAuth/direct client permission dialogs and inherited/global/effective status.

## Browser feedback for Patch 661

The user approved the rest of Patch 654 and requested:

1. A denied tool must disappear from the MCP catalogue returned to external
   clients, not merely fail when called.
2. A per-client control under a global block must be visibly greyed and
   non-editable.
3. Write-tool state must be honest: the six existing tools are read tools and
   there are currently no write tools. Future real write tools should populate
   from the canonical catalogue only when implemented.
4. Add-direct-client Client name and Authentication fields need consistent
   themed sizing, background, border and focus treatment.

## Patch 657 failure and passed rehearsal

Patch 657 failed before writes because one packaged candidate used different
formatting from the passed rehearsal while retaining the rehearsal SHA.

For `backend/app/db/mcp_workspace_tools_smoke_test.py`:

- passed rehearsal SHA:
  `29cd1e227674114e49b21eab2d6ba8f7b90bcaf60bf9479f179814184b46ec8b`
- packaged Patch 657 SHA:
  `53305a21b4691f83a14b48eae2bdb914b07f2785f3a029973d9e73baf93ddac2`

Read-only comparison proved formatting-only divergence around new `tools/list`
assertions.

The passed isolated candidate hashes were:

- `backend/app/services/mcp_permissions.py`
  `1178bd34197247dc0d88f634f588cd144f02150910862cd83181ef396002bda8`
- `backend/app/mcp/runtime.py`
  `f2d34b797255b5b26561005057e8cccbeb35b2e14dfae4dea9428d23ba4f5d32`
- `backend/app/db/mcp_tool_permissions_smoke_test.py`
  `502b15f416f7b2a406d97afcddc0313639365456012117bf959fb8cd6f98da5a`
- `backend/app/db/mcp_workspace_tools_smoke_test.py`
  `29cd1e227674114e49b21eab2d6ba8f7b90bcaf60bf9479f179814184b46ec8b`
- `backend/app/db/mcp_permission_admin_smoke_test.py`
  `03298584de85b7c3b57888e5edaf60b30b285cc1f1c5a64f223e6f32e7c05629`
- `frontend/src/components/McpClientPermissionsDialog.tsx`
  `67fd88d1b4b92f443dbae66d31fed698ce1e9187b9bb923ca56e7285ee60bf1a`
- `frontend/src/components/McpDirectClientsSection.tsx`
  `c146b411acf860e657deef0dd71422708c2e9ab4b87952b4c49163caf18daf80`
- `frontend/src/pages/Settings.tsx`
  `a4ff760df11ccce0853b31a869fc110ac160c62cbd1f80f6d264c6571dfe034e`
- `frontend/src/pages/Settings.css`
  `4211f267d12d54bb9bf79b8eb22bc524d955eae62548bcd787d5b5e8760f23eb`

That isolated candidate passed canonical Docker build, authenticated OAuth
`tools/list` filtering for per-client and global denies, catalogue restoration
after policy restoration, denied-call auditing, OAuth, named-direct, backup and
complete smoke tests.

Patch 661 must either reproduce those exact bytes or rerun the complete isolated
rehearsal for the exact packaged bytes it chooses. Never pin the hash of one
formatting variant while packaging another.

## Configuration-safe permission testing

The live browser test legitimately changed the global policy to 5/6. Permission
smokes must not assume a real installation always has 6/6 enabled.

Tests should snapshot configured policy, normalize only their disposable copied
database, run the matrix there and restore that copy. Production policy must be
preserved exactly.

## V1 follow-up already approved for the roadmap

- Reversible Settings preferences: toggles/selects autosave immediately;
  text/number preferences use a short debounce; ordinary Save/Reset-changes
  controls disappear; one guarded Reset-to-defaults action remains.
- Create/edit, credential, lifecycle, destructive and security workflows remain
  explicit submissions/confirmations.
- Routine manual Refresh is replaced by authenticated server-driven
  invalidation plus targeted refetch.
- Preferred transport is SSE with reconnect/resync; polling is fallback only.
- Future safeguarded MCP write tools join the canonical permission catalogue
  only after their runtime contracts exist.

## First actions in Chat 23

1. Verify the exact 22-file local source, index, live policy, deployment and
   Patch 659/660 docs before implementation.
2. Rehearse the exact Patch 661 packaged candidate in isolated `/tmp`.
3. Recover the principal-aware `tools/list` and UI refinement.
4. Browser-test it.
5. Checkpoint the full pending MCP permission backend/API/UI batch immediately
   after approval.
