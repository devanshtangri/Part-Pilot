# Chat 25 to Chat 26 Handoff

<!-- PARTPILOT:CHAT25_TO_CHAT26_HANDOFF:V742 -->

## Chat 26 identity

- Title: `Chat 26: MCP Inventory Writes and Public Alpha Finalization`
- Patch range: `743-767`
- First patch: `743`
- Planned boundary: `767`
- Start by reading this handoff, `docs/Checkpoint.md`,
  `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`,
  `README.md`, and `docs/diagonostic_patch_734_736_mcp_write_recovery.md` when
  recovery history is relevant.
- Do not create a separate starting-prompt file.

## Exact boundary state

Patch 742 checkpoints and pushes the browser-approved Patch 739 + 740 source plus the test-only mutable-policy smoke correction recovered from Patch 741.
After Patch 742 succeeds, the current local `HEAD` and `origin/main` are the
authoritative Chat 26 starting commit.

- Branch: `main`.
- Pre-boundary documentation checkpoint HEAD/origin:
  `d43f91d6265326e0c10fcb8144aa434d673aa119` (`Diagnose MCP write recovery failures`).
- Patch 742 commit subject: `Checkpoint safeguarded MCP writes and complete Chat 25`.
- Application working tree/index after Patch 742: clean; no browser-test source
  carries forward.
- Approved runtime image:
  `sha256:e5d90cbdc5dc376a4b8b6ab5ff61c39fd0ed381886c51f8d1707d43f1c2c8559`.
- Deployment: healthy, restart count `0`.
- Alembic: `0018_mcp_write_intents`.
- Instance-secret SHA-256 remains
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`.
- Live SQLite rows, Settings values, OAuth tokens/consents, per-client denied
  tools and global MCP booleans are legitimate mutable state. Validate shape,
  integrity and run-start values; do not freeze current values/hashes.

## What Chat 25 completed

1. **API-key/MCP integration live sync — Patch 714.** Authenticated targeted
   invalidation now covers REST API-key and MCP Settings/OAuth/direct-client
   administration without transporting plaintext credentials.
2. **MCP autosave + stable refresh — Patches 717/719.** Reversible MCP settings
   autosave with rollback/stale guards; already-loaded live-sync surfaces retain
   content during background refresh instead of flashing loading states.
3. **Public OpenAPI + restore hardening — Patch 723.** Swagger/ReDoc Bearer
   metadata and exact API-key scope documentation; restore schema/hash recovery.
4. **Stored Parts metrics — Patch 728.** Whole-inventory metrics with pricing
   coverage, Stock alerts and responsive 6/3/2/1 layout.
5. **Dashboard operational home — Patch 731.** Stock-alert dialog, six Quick
   actions and removal of redundant routine Refresh/status/low-stock panels.
6. **Roles/authorization — Patch 733.** Owner/Administrator/Operator/Viewer,
   role-capped REST/API-key access, session-only user administration and safe
   0017 migration. Dedicated Settings user-management presentation is deferred.
7. **Safeguarded MCP lifecycle writes — Patches 739/740, checkpointed by 741.**
   The production schema advances to 0018 and the canonical MCP catalogue is now
   six read + three safeguarded write tools.

## Safeguarded lifecycle-write contract

Implemented tools:
- `reserve_project`
- `consume_reservation`
- `cancel_reservation`

Authorization is defense in depth. A write is visible/callable only when all
applicable ceilings permit it:
- MCP server enabled;
- Write authorization enabled;
- individual global tool permission enabled;
- client-specific deny policy does not block it;
- authenticated principal carries `mcp:write`;
- backing Part Pilot user is active and Operator-or-higher.

No-auth remains permanently read-only even if other write settings are enabled.
Migration 0018 defaults all three write-tool permissions off, but live values are
mutable and may legitimately change after the boundary.

Consequential execution contract:
- first invocation produces an exact preview without mutating inventory;
- preview creates a short-lived one-time confirmation token (five minutes);
- confirmed invocation requires the matching client idempotency key and token;
- changed target state invalidates confirmation rather than applying stale deltas;
- completed writes can replay idempotently;
- Project/Reservation transactional stock invariants remain authoritative;
- successful writes use MCP audit/stock-movement attribution and publish live
  invalidation only after commit.

## OAuth scope nuance proven in browser testing

Settings global/client permission counts describe **policy allowance**, not the
final tool set of an already-authorized OAuth session. During Patch 739 browser
testing the active Claude OAuth token still carried only `mcp:read`, so Claude
correctly advertised six read tools even while Settings showed seven of nine
allowed by policy after `reserve_project` was globally/client allowed.

Existing OAuth tokens must never silently gain `mcp:write`. After Write
authorization is enabled, a client that needs write tools must go through a new
authorization/grant that includes `mcp:write`. Treat the exact current token and
consent rows as mutable live state, not a frozen Chat 26 prerequisite.

Patch 740 also fixes the client Permissions dialog so its nine-tool content is
scrollable within the viewport and the bottom actions remain reachable. Client
summaries now say `allowed by policy` and explicitly note that OAuth scopes can
further limit active tools.

## MCP inventory writes deliberately deferred

Do not interpret the three lifecycle tools as the full desired write catalogue.
The user explicitly expects later Part/stock management capabilities such as:
- add a new part;
- correct/edit part metadata;
- adjust/add/remove stock;
- delete a part and, where appropriate, restore it.

These were intentionally not squeezed into Chat 25. Chat 26 should implement
inventory mutation only in narrow slices on existing transactional services.
Start with add/edit/stock adjustment. Delete/restore should follow only after
verifying recycle-bin, dependency, reservation and exact-confirmation semantics.
Do not add a broad generic mutation tool that bypasses existing safeguards.

## Recovery lessons from the 734-739 sequence

The application candidate itself was sound; the failures were packaging/evidence
mistakes before application writes:
- Patch 734 collapsed Docker Go-template double braces, causing a false runtime
  mismatch while the real Patch 733 runtime remained unchanged.
- Patch 735 required console-only failure text inside Patch 734's durable log.
- Patch 736 hard-coded an HTTPS origin although this repo uses the canonical SSH
  origin `git@github.com:devanshtangri/Part-Pilot.git`.
- Patch 737 was the required diagnostic-only checkpoint and produced
  `docs/diagonostic_patch_734_736_mcp_write_recovery.md`.
- Patch 738 froze stale pre-completion fingerprints for the Patch 737 success log
  and diagnostic report.
- Patch 739 was delivered only after a complete read-only simulation of its
  actual preflight passed, then successfully deployed the exact rehearsed bytes.

Carry these rules forward: use actual completed evidence bytes, never infer
terminal output into durable logs, keep Docker Go templates double-braced, use
the established SSH origin, and run a read-only simulation of complex recovery
preflights before delivery.

## Patch 741 boundary failure and Patch 742 recovery

Patch 741 was consumed before documentation/source commit or database/deployment
mutation. Its copied-production `mcp_write_tools_smoke_test` incorrectly asserted
that the live nine-tool policy still equalled the original migration defaults.
During browser testing `reserve_project` had legitimately been enabled, so the
copy contained `reserve_project: true`. Patch 742 changes only the smoke contract:
it accepts any canonical nine-boolean starting policy, establishes the canonical
write-off baseline inside the copied fixture before visibility tests, and restores
the copied database bytes exactly afterward. Live administrator policy is never
reset by the recovery.

## Chat boundary overrun

Chat 25 was declared for patches `711-735`. The planned boundary was missed
because 734/735 entered a narrow recovery sequence. Per project policy, only
recovery/diagnostic work continued past that point. Patch 742 is the first safe
browser-approved checkpoint/boundary opportunity after the Patch 741 validation
failure and closes Chat 25. Chat 26 therefore starts at 743 and owns `743-767`.

## Chat 26 implementation order

1. Inventory MCP write slice: inspect existing part-create, metadata-edit and
   quantity-adjustment service contracts and add only explicit safeguarded tools
   that preserve those invariants.
2. Extend to delete/restore only if recycle-bin/dependency/reservation safety and
   confirmation semantics remain exact.
3. Add the role/user-management Settings UI when prioritized; backend role
   enforcement already exists from Patch 733.
4. Run final public-alpha accessibility, security, responsive, backup/restore,
   REST/OpenAPI and MCP regressions; checkpoint the release candidate.

Notifications & Messaging remain post-v1.

<!-- PARTPILOT:CHAT26_PROGRESS_PATCH754 -->
## Chat 26 progress through Patch 754

The first inventory MCP write slice is browser-approved. Alembic
`0019_mcp_inventory_stock_write` adds `adjust_part_quantity` to the canonical
ten-tool catalogue (six read + four safeguarded write) while preserving all prior
live tool-policy booleans and defaulting only the new write permission off. The
tool reuses canonical stock planning/floors/reason rules, MCP attribution and
post-commit inventory/history invalidation, with the lifecycle write
preview/confirmation/idempotency/replay/state-drift safeguards unchanged. No-auth
remains permanently read-only.

Browser feedback also exposed success-state flashing caused by expected live
reloads. The approved Settings/Appearance source now gives all autosave success
confirmations a consistent 3.5-second lifetime without background refetches
clearing them early.

Patch 753 was consumed by generated-doc EOF whitespace before staging/commit and
rolled all five docs back exactly. Patch 754 checkpoints the unchanged approved
bytes and corrected durable docs. Continue Chat 26
with only narrow inventory create/edit/delete/restore slices that preserve current
service/recycle-bin/dependency invariants, then final public-alpha hardening and
regression before the planned Patch 767 boundary.
