# Chat 15 → Chat 16 Handoff

## Next chat identity

**Required title:** `Chat 16: Backup and Restore Foundation`
**Patch range:** 427–456 inclusive
**Planned boundary:** Patch 456
**First patch:** 427

Do not create a `Chat_16_Starting_Prompt.md` file. The ready-to-paste prompt
is provided in the Chat 15 response only after Patch 426 succeeds with
`Everything PASS`.

## Authoritative boundary state

After successful Patch 426:

- branch: `main`;
- origin: `git@github.com:devanshtangri/Part-Pilot.git`;
- local `HEAD` equals `origin/main`;
- working tree is clean;
- Git index is empty;
- Compose service: `partpilot`;
- host port: `7890`;
- Alembic head: `0007_projects_contract`;
- Project lifecycle, system-wide History and the complete Settings/
  appearance workspace are committed and pushed;
- the deployed application matches the approved Patch 425 source;
- live users, catalogues, fixtures, inventory, Projects, Reservations,
  movements, audits and settings are preserved.

The boundary commit hash is printed by Patch 426. Inspect it rather than
assuming a hash from this handoff.

## Files Chat 16 must read first

1. `docs/Chat_15_Settings_and_Appearance_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `docs/Part_Pilot_Project_Memory.txt`
5. `README.md`
6. `docs/diagonostic_422_settings_desktop_composition_recovery.md`

Then inspect exact HomeLab Git, index, deployment, logs, SQLite state,
existing reset service and storage paths before issuing Patch 427.

## Completed in Chat 15

### Project lifecycle completion

- Reserved Projects consume or cancel atomically through exactly one linked
  active Reservation.
- Consumption decreases physical and reserved quantities together while
  preserving available quantity.
- Cancellation releases reserved quantity back to available stock without
  changing physical totals.
- Project and Reservation terminal statuses, movements and audits stay
  synchronized.
- Reserved commitments are editable from Projects or Reservations; quantity
  changes reserve or release only the delta.
- Direct Reservation consume/cancel/expiry synchronizes the linked Project.
- Accessible dialogs, duplicate-submit guards, stale refresh and responsive
  register-first mobile behavior are browser approved.
- Six realistic Patch 401 test parts remain intentionally preserved.

### System-wide History

- Protected `GET /api/history` and `/api/history/filter-options` expose a
  deterministic newest-first register over audits and stock movements.
- Filters cover kind, entity, event, actor, user, movement, dates and
  literal text; options include counted facets and event bounds.
- Entries hydrate actor/entity/Part/Reservation/Project context and expose
  stock snapshots or structured Before/After/metadata evidence.
- Desktop uses register/detail; mobile is register-first.
- General sorting is intentionally omitted to preserve chronological
  investigation. Oldest-first remains deferred unless a concrete workflow
  requires it.

### Global appearance and Settings

- Protected appearance settings persist `dark`, `light` or `system`, expose
  Light availability, validate corrupt/invalid values and write
  actor-attributed audits.
- A pre-paint bootstrap prevents opposite-theme flashing.
- System mode follows `prefers-color-scheme` changes without reload.
- Light mode covers Dashboard, Inventory, Part Manager, Projects,
  Reservations, History, Settings, tables, forms, drawers and dialogs.
- Cross-workspace primary, neutral, destructive, active, selected, status
  and real disabled states are visually distinct.
- Settings preserves the server-backed Out-of-stock and Reservation expiry
  preferences.
- Database reset uses one review action and an accessible phrase-confirmed
  dialog; the final erase action remains intentionally guarded.
- Final desktop layout:
  - Appearance: full width;
  - Inventory search: compact full width;
  - Reservation defaults and Database reset: equal-height lower pair.
- Mobile order remains Inventory → Reservations → Database reset.
- The redundant resolved-theme pill was removed; the page runtime status
  and selected theme card communicate the active state.

## Important recovery history

- Patch 400 and Patch 402 failed before writes on brittle lifecycle
  transformation/validation assumptions. Patches 401 and 403 recovered.
- Patch 404 failed before writes on checkpoint generation; Patch 405
  recovered and pushed the Project lifecycle.
- Patch 406 failed in copied smoke on an invalid fixture username; Patch
  407 recovered.
- Patch 408's frontend built but the verifier searched for a CSS comment
  stripped by Vite; Patch 409 added minifier-safe markers.
- Patch 412 built/deployed but Vite removed selector quotes; rollback was
  safe. Patch 413 failed before writes on brittle escaping. Patch 414
  recovered with semantic evidence.
- Patches 419 and 420 failed before writes on full-block equality and one
  remaining shared resolved-mode selector.
- Patch 421's in-memory implementation passed, but report generation
  stopped on trailing spaces from numbered blank lines.
- Patch 422 committed
  `docs/diagonostic_422_settings_desktop_composition_recovery.md` and
  recorded exact structural anchors and candidate hashes.
- Patch 423 applied that diagnostic-backed composition.
- Patch 424 built successfully, but Vite rewrote
  `@media (min-width: 901px)` to `@media (width>=901px)` and the verifier
  rejected the valid output. Rollback restored the exact Patch 423 state.
- Patch 425 accepted both authored and minified syntax and passed.

Future verifiers must prefer durable custom properties, data attributes,
semantic selector/token checks and accepted minifier forms over exact
source formatting.

## Approved live test state

- users: 1
- part types: 36
- manufacturers: 9
- packages: 23
- locations: 1
- parts: 15
- projects: 7
- project items: 10
- reservations: 9
- reservation items: 14
- stock movements: 32
- audits: 96
- app settings: 17
- appearance: `dark`
- separate Out-of-stock results: enabled
- Alembic: `0007_projects_contract`

Fixture manifest:

```text
/projects/Part Pilot/fixes/logs/patch_401_test_fixture_manifest.json
```

Preserve this data until an explicit cleanup or database reset.

## Immediate Chat 16 work

### 1. Inspect before designing

Read the exact current code for:

- database engine/session initialization and SQLite pragmas;
- `PARTPILOT_DATABASE_URL` handling;
- Docker `/data` volume behavior;
- database-reset route/service and authentication invalidation;
- app startup/shutdown and connection disposal;
- audit event creation;
- Settings Data section and reset dialog;
- current request/upload/download limits and middleware.

Do not assume a raw database-file replacement is safe.

### 2. Define the backup artifact

Use a versioned format with an explicit manifest. At minimum record:

- Part Pilot backup format version;
- creation timestamp in UTC;
- Alembic revision;
- database filename and SHA-256;
- SQLite integrity and foreign-key results;
- included scope;
- optional application/schema metadata needed for compatibility checks.

Create the SQLite snapshot through the online backup API. A live file copy
is not an acceptable consistency guarantee.

The first backup slice should be protected, stream/download safely, use a
deterministic human-readable filename, avoid cache retention, remove
temporary artifacts and write audit evidence without mutating inventory.

### 3. Define restore safety before implementation

Restore must be a separate guarded operation. Before touching live data:

- enforce upload and extracted-size limits;
- reject malformed archives and path traversal;
- validate manifest fields and hashes;
- validate format and Alembic/schema compatibility;
- run SQLite integrity and foreign-key checks;
- validate required tables and critical settings;
- reject invalid input with no live changes.

Before replacement, create a rollback snapshot of the current database.
Define how active SQLAlchemy connections are disposed, when replacement
occurs, whether a process restart is required and how authentication/session
behavior is communicated.

On failure, restore the rollback snapshot and verify the original logical
database before reporting failure.

### 4. Settings UI

Add backup and restore under the existing Data section without weakening
database-reset safeguards.

- Download backup should be a clear non-destructive action.
- Restore should require file selection, artifact summary and an accessible
  review/confirmation dialog.
- Show upload/validation/restoration progress and useful errors.
- Explain whether restore signs the user out or restarts the service.
- Keep mobile controls readable and avoid browser-native confirmation.

### 5. Testing and checkpointing

- Use copied databases and manifest-owned backup artifacts.
- Never restore into the real test database during automated tests.
- Verify exact round-trip preservation of users, catalogues, Parts,
  Projects, Reservations, movements, audits and settings.
- Test corrupt files, incompatible revisions, hash mismatch, oversized
  uploads, path traversal, interrupted restore and rollback.
- Browser-test download, invalid-file rejection, successful restore flow,
  responsive layout and post-restore authentication behavior.
- Keep browser-test source uncommitted until explicit approval, then use a
  separate checkpoint.

## Deferred after backup/restore

- MCP read tools and safeguarded write tools.
- Authenticated MCP server enable/disable Settings control.
- Accessibility, security and public-alpha release hardening.

Do not combine backup/restore and MCP in one implementation patch.

## Mandatory patch method

1. Use HomeLab for targeted read-only inspection of exact local state.
2. Treat local source and newest handoff/diagnostic as authoritative.
3. Generate every transformation in memory before backup/write.
4. Validate exact HEAD/origin, index, pending allowlist, hashes and logs.
5. Avoid brittle whitespace adjacency and source-format assumptions.
6. Back up source, SQLite and active image before application writes.
7. Build/deploy, verify Alembic, protected APIs, OpenAPI, SPA/bundle
   markers and the complete copied-database smoke suite.
8. Preserve live users, catalogues, inventory, Projects, Reservations,
   movements, audits and settings.
9. On failure, report phase, exception, actual command, rollback result,
   final Git state and log path.
10. After two consecutive pre-write failures or source uncertainty, stop
    and issue the next diagnostic-only patch.
11. Never put browser instructions inside patch scripts.
12. Never create or run a numbered patch on HomeLab unless the user
    explicitly grants permission.
