# Chat 26 to Chat 27 Handoff

<!-- PARTPILOT:CHAT26_TO_CHAT27_HANDOFF:V768 -->

## Boundary

- Closing chat: `Chat 26: MCP Inventory Writes and Public Alpha Finalization`
- Boundary patch: `768_recover_chat26_boundary_mcp_lifecycle_history_scroll.py`
- Consumed boundary attempt: `767_checkpoint_chat26_boundary_mcp_lifecycle_history_scroll.py`
- Next chat: `Chat 27: User Management UI and Public Alpha Release Candidate`
- Next patch range: `769-793`
- First patch: `769`
- Planned boundary: `793`

Patch 767 was consumed before any writes because its preflight expected the GitHub
HTTPS origin spelling while the verified repository uses the equivalent SSH origin
`git@github.com:devanshtangri/Part-Pilot.git`. Its durable log records only the
branch/origin reads; the approved 24-file source, clean index, database and runtime
were unchanged. Patch 768 corrects that prerequisite and is the authoritative Chat
26 boundary. After Patch 768 succeeds, **inspect local Git/index, runtime, Alembic,
production SQLite and this handoff before trusting any volatile hash copied into a
new chat**. The successful commit hash is intentionally not pre-guessed here.

## Expected post-Patch-768 repository/runtime state

- Branch `main`; local HEAD must equal `origin/main`; working tree and index clean.
- Commit subject: `Checkpoint MCP lifecycle and History responsive register`.
- Production Alembic: `0022_mcp_inventory_part_lifecycle (head)`.
- Browser-approved source/runtime image:
  `sha256:44a9a7a36907587aecf8d6dae34ff4e0837c24a3b6bce6bcb86c853dda8c17fb`.
- Canonical MCP catalogue: 14 tools = six reads + eight safeguarded writes.
- Live `mcp.tool_permissions` values are mutable administrator state. Patch 768
  validates the exact 14-key boolean shape and preserves the values observed at
  preflight rather than restoring migration defaults.
- Production DB, users/sessions/inventory/Projects/Reservations/movements/audits/
  API keys/OAuth/direct clients/settings/backups and instance secret are preserved.

## Chat 26 completed work

### Stock adjustment
- Added `0019_mcp_inventory_stock_write` and guarded `adjust_part_quantity`.
- Reuses canonical stock rules including reserved floors and correction reasons.
- Preview/confirm, five-minute token, idempotency/replay, drift rejection, MCP
  attribution and post-commit inventory/history invalidation are enforced.

### Part creation
- Added `0020_mcp_inventory_part_create` and guarded `create_part`.
- Preview freezes normalized payload plus catalogue/template dependencies.
- OAuth protected-resource challenge was corrected to advertise the read/write
  scope categories currently enabled; existing tokens still require explicit
  reauthorization before gaining `mcp:write`.
- History uses MCP client name (Claude/direct client) while retaining backing
  user authority.

### Metadata replacement
- Added `0021_mcp_inventory_part_metadata_update` and `update_part_metadata`.
- Full explicit editable metadata replacement only; stock is excluded.
- Relevant metadata/catalogue/template drift rejects confirmation while unrelated
  stock-only changes do not falsely stale the preview.
- Patch 761 checkpoint also fixed a test-only assumption that had frozen the
  migration-time 0005 package-catalogue backfill as a permanent runtime invariant.

### Reversible part lifecycle
- Added data-only `0022_mcp_inventory_part_lifecycle`.
- Added default-off `soft_delete_part` and `restore_part`; catalogue is now 14.
- Both reuse canonical lifecycle services and retain MCP server/write/global/client/
  scope/Operator+ ceilings, preview/confirm, idempotency/completed replay and drift
  rejection.
- Soft delete preserves physical/reserved stock, typed fields, movements and
  History. Restore acts on the same record, checks deleted-state snapshot and
  part-number availability, and returns the same part ID.
- Neither creates a stock movement merely for lifecycle transition.
- MCP has **no permanent purge, hard-delete or recycle-bin-emptying tool**. Keep
  permanent purge separately reviewed.

### Claude lifecycle browser evidence
- Existing test fixture: part ID 16, part number `MCP-P756-CREATE-TEST`, name
  `Patch 760 MCP Metadata Test`, Resistor, physical 12, reserved 0, three fields.
- `soft_delete_part` preview showed reversible delete and preserved state; confirmed
  delete preserved 12/0 + fields with zero stock movements. History actor = Claude.
- Exact confirmed soft-delete replay returned `replayed:true` with no duplicate
  mutation/audit/movement.
- `restore_part` preview found no part-number conflict; confirmed restore returned
  same ID 16, same part number, 12/0 and fields with no movement. Exact replay
  returned completed result without duplicate audit/mutation.
- Claude's lifecycle-affecting tool list contained only reversible soft delete and
  restore; no permanent purge tool was exposed.
- This Part 16 state/evidence is legitimate live data. Do not automatically delete,
  normalize or recreate it.

### History responsive correction
- Patch 766 fixed the intermediate-width chronological register clipping found
  during the lifecycle browser test.
- Header + rows share `.history-list-scroll`; default/intermediate minimum widths
  are 740 / 580 / 430px. Columns remain aligned and reachable horizontally.
- `Chronological register` heading and pagination do not scroll sideways.
- At <=680px the pre-existing card layout remains and does not receive an
  unnecessary horizontal scrollbar. Browser approved.
- Runtime marker: `PARTPILOT:HISTORY_REGISTER_HORIZONTAL_SCROLL:V766`.

## Current MCP tools

Reads:
1. `search_parts`
2. `get_part_details`
3. `list_projects`
4. `get_project_details`
5. `list_reservations`
6. `get_reservation_details`

Safeguarded writes:
1. `reserve_project`
2. `consume_reservation`
3. `cancel_reservation`
4. `adjust_part_quantity`
5. `create_part`
6. `update_part_metadata`
7. `soft_delete_part`
8. `restore_part`

## Chat 27 priorities

1. Inspect the newest handoff first, then `docs/Checkpoint.md`,
   `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`,
   `README.md`, newer handoffs/diagnostics and exact local repo state.
2. Build the dedicated Settings user/role-management UI on the existing Patch 733
   backend APIs/authorization. Do not redesign backend role semantics unless a
   verified defect requires it.
3. Preserve explicit/consequential UX for user creation, role/access changes,
   disable/reactivate, force-reset, session revocation and confirmed deletion.
   Preserve last-active-Owner and self-disable/self-delete protections.
4. Browser-test the UI at desktop/intermediate/mobile widths and across relevant
   role ceilings. Use test-owned users/sessions; never broadly delete real users.
5. Run final public-alpha accessibility/security/responsive/backup-restore/REST-
   OpenAPI/MCP OAuth/direct-auth/tool-permission/write/live-sync regression on
   copied production data. Fix release blockers only, then checkpoint the public-
   alpha release candidate.
6. Notifications & Messaging remain post-v1.

## Operating rules that matter most

- Every patch is one sequential Python file under `fixes/`; failed executed scripts
  consume numbers; success final line exactly `Everything PASS`.
- Do not execute numbered patches unless the user explicitly asks to run that exact
  patch. On such a request run only the requested command once and return raw output.
- Browser-test source stays uncommitted until explicit approval. After approval use
  a separate exact-allowlist checkpoint/commit/push patch.
- After two consecutive pre-write failures/anchor mismatches/source uncertainty,
  diagnostic-only next with `docs/diagonostic_*.md`.
- Never freeze mutable live DB/settings/OAuth/client/tool-policy values. Preserve
  real data and secrets. Rehearsals stay isolated from live source/deployment.
- For AI/MCP browser tests always give the user exact copy-paste prompts to send.
- Preferred patch response order: file/path, SHA-256, concise scope/status, exact
  run commands, expected `Everything PASS`.
