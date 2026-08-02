# Chat 16 → Chat 17 Handoff

## Next chat identity

**Required title:** `Chat 17: Backup Status Finalization and MCP Foundation`
**Patch range:** 458–487 inclusive
**Planned boundary:** Patch 487
**First patch:** 458

Do not create a separate Chat 17 starting-prompt document. The ready-to-paste prompt is
provided in Chat 16 only after Patch 457 ends with `Everything PASS`.

## Authoritative boundary state

After successful Patch 457:

- branch: `main`;
- origin: `git@github.com:devanshtangri/Part-Pilot.git`;
- local `HEAD` equals `origin/main`;
- working tree and Git index are clean;
- Compose service `partpilot` is healthy on host port `7890`;
- Alembic head is `0007_projects_contract`;
- the committed application baseline is Patch 453;
- the deployed application is the clean Patch 453 image;
- all users, catalogues, Parts, Projects, Reservations, movements, audits,
  settings and restore staging artifacts are preserved;
- no pending restore commit job exists.

Patch 457 prints the boundary commit hash. Inspect it rather than assuming it
from this handoff.

## Read first in Chat 17

1. `docs/Chat_16_Backup_and_Restore_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `docs/Part_Pilot_Project_Memory.txt`
5. `README.md`
6. `docs/diagonostic_447_settings_tabs_restore_staging.md`
7. Patch 455 script and failure log

Then inspect exact HomeLab Git, source, deployment, database and staging before
issuing Patch 458.

## Completed backup contract

### Artifact and download

- Media type: `application/vnd.partpilot.backup+zip`
- Extension: `.ppbackup`
- Archive members: exactly `manifest.json` and `partpilot.db`
- Snapshot method: SQLite online backup API
- Manifest records format/version, UTC creation time, Alembic revision,
  database size/hash, schema fingerprint, integrity results, included scope and
  restore policy.
- Protected `POST /api/backups/download` returns a deterministic filename,
  no-store headers and records `backup.generated`.
- Temporary backup files are operation-owned and removed after delivery.

### Restore validation and commit

- Protected `POST /api/restores/validate` validates upload size, archive shape,
  path safety, manifest fields, exact revision compatibility, hashes, SQLite
  integrity, foreign keys, required schema, settings and active-user state.
- Validated artifacts are staged under `/data/.partpilot-restore` with 0700
  operation directories and 0600 operation-owned files.
- Protected `POST /api/restores/{validation_token}/commit` requires exact
  confirmation and creates a persistent commit job.
- Pre-Uvicorn bootstrap applies the commit before the web server starts.
- Restore creates a current-database rollback snapshot, drains requests,
  replaces the database atomically on the same filesystem, fsyncs, verifies,
  invalidates restored sessions, records `backup.restored` and rolls back on
  any failure.
- A successful restore consumes `candidate.db`; completed evidence contains
  commit/result, previous and rollback snapshots.
- Expiry cleanup removes only exact validation-only operations and preserves
  pending, completed, malformed and unknown-extra evidence.

### Settings and browser approval

- Settings contains real Appearance, Inventory, Reservations and Data buttons.
- The active section is URL-hash backed, accessible and the only visible panel.
- All sections remain mounted to preserve in-progress state.
- Backup download, file validation, review dialog, restore progress and forced
  fresh login are implemented.
- Desktop and mobile browser testing approved the core workflow.
- Patch 450 committed the approved four frontend files.

### Manual-backup status

- Protected `GET /api/backups/status` is committed and deployed.
- It reports manual-download mode, scheduling inactive, no retained server
  copy, valid recorded download count and latest filename/time/sizes/schema.
- It is read-only and leaves the unused `backups` table untouched.

## Exact pending frontend task

Patch 454 and Patch 455 did not leave pending source.

Patch 454 generated the intended four-file status UI but failed before writes
because `Settings.tsx` intentionally contained three V454 UI-marker sites
while the validator expected two.

Patch 455 corrected that count, wrote, built and deployed the candidate, but
the verifier incorrectly required the authored CSS comment
`PARTPILOT:SETTINGS_MANUAL_BACKUP_STATUS_STYLES:V454` in the minified bundle.
Vite strips comments. The durable custom property
`--partpilot-settings-manual-backup-status-v454` is the correct CSS evidence.
Patch 455 rolled back source, deployment, database and staging exactly.

Patch 456 then failed before documentation writes because the boundary
verifier issued GET requests to POST-only protected routes. Patch 457
corrected the HTTP methods and completed the documentation-only boundary.

### Patch 458 requirements

- Start from the clean Patch 453 baseline and exact hashes recorded by Patch
  456.
- Hash-validate Patch 454 and Patch 455 scripts/logs.
- Reuse the Patch 455 implementation without changing product behavior.
- Validate exactly three generated V454 UI-marker sites.
- In authored CSS, require the V454 comment and custom property.
- In built CSS, require only the minifier-safe custom property and semantic
  selectors/tokens; never require the stripped comment.
- Build/deploy, verify Alembic, protected APIs, SPA markers and complete copied
  database smoke tests.
- Preserve the live database and all restore staging fingerprints.
- Leave exactly four frontend files uncommitted for browser approval:
  `Settings.tsx`, `Settings.css`, `backupsClient.ts`, `backups.ts`.

### Browser test after Patch 458 terminal success

- Desktop Data panel shows latest manual backup, recorded count, timestamp,
  filename, archive/database sizes and schema.
- Copy clearly states manual only, scheduling inactive and no server copy.
- Downloading a new backup updates the displayed count and latest entry.
- Download and Restore cards retain natural independent heights.
- Loading/error/retry states are readable.
- Mobile layout stacks correctly with no overflow and compact one-column
  status details.
- Restore and database-reset workflows remain unchanged.

After approval, use a separate checkpoint patch to commit/push the four files.

## Live data to preserve

- users: 1
- sessions: 2
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
- audits: 100
- app settings: 17
- backups rows: 0
- restore operations: 3
- pending restore jobs: 0
- database SHA-256: `91b0a498cd75b34f4db2be624cd0652d7cbdf9683ae0e0ff859303f8a099fa7c`

The six realistic Patch 401 parts remain intentionally preserved:
`/projects/Part Pilot/fixes/logs/patch_401_test_fixture_manifest.json`

## After status UI finalization

Proceed diagnostic-first for MCP:

1. inspect current process/network/auth/config/runtime boundaries;
2. define transport and authentication;
3. define read-tool schemas and pagination;
4. implement read tools before writes;
5. define explicit write confirmations, idempotency, inventory invariants and
   audit events;
6. add the Settings MCP enable/disable control only after startup/restart and
   tool-gating semantics are explicit.

Do not combine the status UI checkpoint with MCP implementation.
