# Chat 14 → Chat 15 Handoff

## Next chat identity

**Required title:** `Chat 15: Project Lifecycle Completion`
**Patch range:** 397–426 inclusive
**Planned boundary:** Patch 426
**First patch:** 397

Do not create a `Chat_15_Starting_Prompt.md` file. The ready-to-paste prompt is
provided in the Chat 14 response only after Patch 396 succeeds with
`Everything PASS`.

## Boundary recovery note

Patch 395 failed before any write because its generated Checkpoint metadata used trailing Markdown spaces. Patch 396 is the narrow boundary recovery. Therefore Chat 15 starts at Patch 397 and ends at Patch 426.

## Authoritative boundary state

After successful Patch 396:

- branch: `main`;
- origin: `git@github.com:devanshtangri/Part-Pilot.git`;
- local HEAD equals `origin/main`;
- working tree is clean;
- Git index is empty;
- Compose service: `partpilot`;
- host port: `7890`;
- Alembic head: `0007_projects_contract`;
- Projects foundation and backend consumption are committed and pushed.

The boundary commit hash is printed by Patch 396. Inspect it rather than
assuming a hash from this handoff.

## Files Chat 15 must read first

1. `docs/Chat_14_Projects_Foundation_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `docs/Part_Pilot_Project_Memory.txt`
5. `README.md`
6. `docs/diagonostic_project_consumption_recovery_patch_393.md`

Then inspect exact HomeLab Git, source, deployment, logs and live SQLite state
before issuing Patch 396.

## Completed in Chat 14

### Project contract and persistence

- Canonical statuses:
  - `draft`
  - `reserved`
  - `consumed`
  - `cancelled`
- Alembic migration `0007_projects_contract` aligns schema and constants.
- Project and ProjectItem models preserve historical nullable part links,
  quantities, price/currency snapshots, notes and timestamps.
- Protected list/detail/create/update APIs support validation, pagination,
  Draft-only editing, item reconciliation, no-op suppression and auditing.

### Projects frontend

- Real responsive `/projects` workspace replaces the placeholder.
- Desktop register/detail split view and mobile register-first behavior.
- Draft create/edit forms with server-backed part search.
- Up to 50 visible search matches with persistent multi-selection.
- Current stock availability and value snapshots.
- Accessible loading, error and empty states.
- Browser approval is complete through Patch 386.

### Project-derived Reservations

- Reserving a Draft Project creates exactly one linked active Reservation.
- Reservation items mirror Project items and preserve notes/snapshots.
- Reserve movements increase reserved quantity without changing physical total.
- Project and Reservation reserve audits are paired.
- Projects is the normal planning entry point.
- Manual Reservation creation was removed from the frontend.
- Existing Reservation edit/cancel/consume/expire/delete/activity remains.
- Backend Reservation creation remains temporarily for API/MCP compatibility.

### Backend Project consumption

Patch 394 adds:

```text
POST /api/projects/{project_id}/consume
```

Behavior:

1. lock the Project and require `reserved`;
2. require exactly one linked active Reservation;
3. reuse `consume_reservation(..., commit=False)`;
4. reduce physical and reserved quantities by the same amount;
5. preserve available quantity;
6. create one consume movement per linked item;
7. transition Reservation `active → consumed`;
8. transition Project `reserved → consumed`;
9. add `reservation.consumed` and `project.consumed`;
10. roll back all changes on any conflict.

The complete copied-database smoke suite verifies OpenAPI, authentication,
inventory invariants, movement snapshots, paired audits, repeated-action guards,
orphan-link rejection and rollback.

## Important diagnostic history

Patch 391 failed before writes because it probed the undeployed consume route and
expected authentication instead of the valid pre-deployment `405`.

Patch 392 failed before writes because its wrapper expected `V392`, but its
base64 payloads still contained `V391`.

Patch 393 committed:

```text
docs/diagonostic_project_consumption_recovery_patch_393.md
```

Patch 394 was generated fresh, validated decoded `V394` payloads before backup
and passed. Do not derive future implementations by blind replacement over a
previous encoded wrapper.

## Immediate Chat 15 work

### 1. Backend Project cancellation

Implement:

```text
POST /api/projects/{project_id}/cancel
```

Required behavior:

- only a `reserved` Project may be cancelled;
- require exactly one linked active Reservation;
- reuse `cancel_reservation(..., commit=False)` in the same transaction;
- release reserved quantities without changing physical totals;
- increase available quantity by the released amount;
- transition Reservation `active → cancelled`;
- transition Project `reserved → cancelled`;
- create paired `reservation.cancelled` and `project.cancelled` audits;
- preserve release movement snapshots;
- reject missing, duplicate, inactive and repeated transitions;
- roll back status, quantity, movement and audit changes on conflict.

Inspect the exact current Reservation cancellation implementation before writing
the Project wrapper. Do not duplicate release logic.

### 2. Frontend terminal actions

After backend cancellation passes:

- add typed client methods for Project consume and cancel;
- show actions only for Reserved Projects;
- use accessible confirmation dialogs with explicit irreversible/release copy;
- prevent duplicate submissions;
- show pending, success and conflict feedback;
- refresh the Project list/detail after completion;
- refresh linked Reservation and inventory views when users navigate;
- display terminal statuses consistently on desktop and mobile.

### 3. Browser approval and checkpointing

Browser-test separately:

- Consume Project confirmation and resulting status;
- Cancel Project confirmation and stock release;
- button visibility for Draft/Reserved/Consumed/Cancelled;
- repeated-action guards;
- loading/error states;
- responsive layouts;
- inventory totals and linked Reservation status.

Keep browser-test source uncommitted until explicit approval. Use a separate
checkpoint script immediately after approval.

## Deferred work after lifecycle completion

- System-wide History and audit browser.
- Broader Settings and appearance.
- Backup and restore.
- MCP read tools and safeguarded write tools.
- Authenticated MCP server enable/disable Settings control.
- Accessibility, security and public-alpha hardening.

Do not combine these with the first cancellation or terminal-action patches.

## Deferred MCP Settings requirement

During the MCP phase, add an authenticated Settings control that enables or
disables the MCP server. Define:

- persisted setting and default;
- missing/invalid startup behavior;
- immediate versus restart-required application;
- transport and tool-registration gating;
- safeguarded write-tool behavior;
- audit events;
- clear disabled-state feedback;
- preservation of MCP configuration while disabled.

This is documentation-only at the Chat 14 boundary.

## Mandatory patch method

1. Use HomeLab for targeted read-only inspection of exact local state.
2. Treat local source and newest diagnostic/handoff as authoritative.
3. Generate transformations in memory before backup/write.
4. Validate exact HEAD/origin, index, pending allowlist, hashes and prior logs.
5. Avoid brittle whitespace adjacency; scope to verified functions/markers.
6. Back up source, SQLite and active image before application writes.
7. Build/deploy, verify Alembic, protected APIs, OpenAPI, SPA markers and the
   complete copied-database smoke suite.
8. Preserve live users, catalogues, inventory, Projects, Reservations,
   movements, audits and settings.
9. On failure, report phase, exception, actual failing command, useful output,
   rollback result, final Git state and log path.
10. After two consecutive pre-write failures or source uncertainty, stop and
    issue the next diagnostic-only patch.
11. Never place browser instructions inside scripts.
12. Never create or run a patch on HomeLab unless the user does so.
