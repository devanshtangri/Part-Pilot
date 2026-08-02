# Diagnostic 447: Settings Tabs and Restore Staging

## Purpose

Recovered after two consecutive implementation pre-write failures and the consumed Patch 446 report-format failure. This patch is documentation-only.

## Git and Pending Source

- Branch: `main`
- HEAD before diagnostic commit: `f4e52f2b04cea5944fcac8ff6d9765b31a902a94`
- origin/main before diagnostic commit: `f4e52f2b04cea5944fcac8ff6d9765b31a902a94`
- Index before diagnostic commit: empty
- Pending source:
  - ` M frontend/src/pages/Settings.css`
  - ` M frontend/src/pages/Settings.tsx`
  - `?? frontend/src/services/backupsClient.ts`
  - `?? frontend/src/types/backups.ts`

### Pending SHA-256

| File | SHA-256 |
|---|---|
| `frontend/src/pages/Settings.css` | `1bddbd71286c6348ea1ae570e77c301fe73da25a377de9e6e2875808d3b739e5` |
| `frontend/src/pages/Settings.tsx` | `3a0e8194fab18f16dc7ab5c4b953eecd2a1a48c58c068e51aa6b91bc8d252e30` |
| `frontend/src/services/backupsClient.ts` | `8e18a15ebcf144cf2cf83bd8eded5ddee55e661ba464a10ff9347700d276d3ce` |
| `frontend/src/types/backups.ts` | `e3afb29b1c2888b7c0574fcd5df43d7db574f6b9df50e92ef9ed097150111e97` |

## Failure Evidence

- Patch 444 failed because a fixed `sessions=1` expectation became false after a normal second owner login.
- Patch 445 failed because it required `candidate.db` in every operation, including a completed successful restore.
- Patch 446 correctly classified the operations but failed while building the Markdown report because four blank excerpt lines were rendered with a trailing space after their line number.

## Runtime Database

- SHA-256: `279fdc57f1ee4646d2de57464178d32c54725518ee5dfaaaf269ff9a52078e9e`
- Size: `565248` bytes
- Mode: `0o644`
- Alembic: `0007_projects_contract`
- Sessions: `2`
- Audit rows: `98`
- Successful restore audits: `1`

Session and audit counts are mutable runtime state. Future patches must snapshot them at preflight and verify preservation.

## Restore Staging

- Root mode: `0o700`
- Operation count: `3`
- Pending jobs by source contract: `0`

| Operation | Classification | Files |
|---|---|---|
| `validated--Ahgtn8KJzRvUAv1icTG7GNCVn3QWVyvvj5kcUliFdM` | `completed-success` | `.partpilot-restore-operation`, `commit.json`, `previous.db`, `result.json`, `rollback.db`, `state.json`, `upload.ppbackup` |
| `validated-gmI5MOnLIXwxpJFhrsf4hlqAdP03yuG3Ehkr4vcrbh0` | `validation-only` | `.partpilot-restore-operation`, `candidate.db`, `state.json`, `upload.ppbackup` |
| `validated-z8HNr2RSzA_dNP8kz6hKSOisOrIRfFmBvUpmXdfR8Ls` | `validation-only` | `.partpilot-restore-operation`, `candidate.db`, `state.json`, `upload.ppbackup` |

### Shape Conclusions

1. Validation-only operations require `candidate.db`.
2. Completed operations require `commit.json` and `result.json`.
3. Successful completion intentionally consumes `candidate.db` through `os.replace(candidate_path, live_database_path)`.
4. Pending means `commit.json` exists while `result.json` does not.
5. No pending jobs exist.
6. Existing validation and completed artifacts must remain untouched during the Settings UI fix.

## Source Excerpts

### Pending-job discovery

```text
247:     pending: list[
248:         tuple[Path, RestoreCommitJob]
249:     ] = []
250:     for operation in sorted(root.iterdir()):
251:         if not _operation_is_owned(
252:             operation,
253:             staging_root=root,
254:         ):
255:             continue
256:         job_path = (
257:             operation
258:             / RESTORE_COMMIT_FILENAME
259:         )
260:         result_path = (
261:             operation
262:             / RESTORE_RESULT_FILENAME
263:         )
264:         if (
265:             job_path.is_file()
266:             and not result_path.exists()
267:         ):
268:             pending.append(
269:                 (
270:                     operation,
271:                     _load_job(job_path),
272:                 )
273:             )
274:     if not pending:
275:         return None
276:     if len(pending) != 1:
277:         raise RestoreBootstrapFatalError(
278:             "Multiple pending restore jobs require manual recovery."
279:         )
280:     return pending[0]
```

### Candidate consumption

```text
803:         inject("before_replace")
804:
805:         os.replace(
806:             live_database_path,
807:             previous_path,
808:         )
809:         replacement_started = True
810:         _fsync_directory(
811:             live_database_path.parent
812:         )
813:         os.replace(
814:             candidate_path,
815:             live_database_path,
816:         )
817:         _fsync_file(
818:             live_database_path
819:         )
820:         _fsync_directory(
821:             live_database_path.parent
822:         )
823:         inject("after_replace")
```

### Current Settings navigation

```text
588:       <nav
589:         className="settings-section-nav"
590:         aria-label="Settings sections"
591:       >
592:         <a href="#settings-appearance">Appearance</a>
593:         <a href="#settings-inventory">Inventory</a>
594:         <a href="#settings-reservations">Reservations</a>
595:         <a href="#settings-data">Data</a>
596:       </nav>
597:
598:       <section
599:         id="settings-appearance"
600:         className="card settings-section settings-appearance-section"
601:         aria-labelledby="settings-appearance-title"
602:       >
```

### Current equal-height rule

```text
1156: /* PARTPILOT:SETTINGS_LOWER_CARD_HEIGHT_SYNC:V425 */
1157: .settings-page {
1158:   --partpilot-settings-lower-card-height-v425: 1;
1159: }
1160:
1161: @media (min-width: 901px) {
1162:   .settings-content-grid > .settings-grid-reservations,
1163:   .settings-content-grid > .settings-grid-data {
1164:     align-self: stretch;
1165:   }
1166:
1167:   .settings-content-grid > .settings-grid-data {
1168:     align-content: space-between;
1169:   }
1170: }
```

## Anchor Counts

### `frontend/src/pages/Settings.tsx`

| Marker | Count |
|---|---:|
| `<nav
        className="settings-section-nav"` | 1 |
| `<a href="#settings-appearance">Appearance</a>` | 1 |
| `id="settings-appearance"` | 1 |
| `id="settings-inventory"` | 1 |
| `id="settings-reservations"` | 1 |
| `id="settings-data"` | 1 |
| `PARTPILOT:SETTINGS_BACKUP_RESTORE_UI:V442` | 1 |

### `frontend/src/pages/Settings.css`

| Marker | Count |
|---|---:|
| `.settings-section-nav a {` | 2 |
| `/* PARTPILOT:SETTINGS_LOWER_CARD_HEIGHT_SYNC:V425 */` | 1 |
| `align-self: stretch;` | 1 |
| `align-content: space-between;` | 1 |
| `/* PARTPILOT:SETTINGS_BACKUP_RESTORE_STYLES:V442 */` | 1 |

### `backend/app/services/restore_bootstrap.py`

| Marker | Count |
|---|---:|
| `def discover_pending_restore_job(` | 1 |
| `and not result_path.exists()` | 1 |
| `os.replace(
            candidate_path,` | 1 |
| `def process_pending_restore(` | 1 |

## Deployment

- Container: `115295cb57e442f907bd7e096cf346fd293209eb74fe19ce62f322e5246c17d6`
- Image: `sha256:a080dc1bd4c93feb6a668400bc56b1c0e4797d7abccb2bdeff403df0e0d1fc8e`
- Health: `healthy`
- Restart count: `1`
- Started: `2026-08-02T04:38:56.901453965Z`
- Command: `["sh","-c","python -m app.restore_bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PARTPILOT_CONTAINER_PORT:-8000}"]`

## Safe Patch 448 Plan

1. Preserve the exact four pending frontend files.
2. Snapshot the runtime database and staging fingerprint at preflight; do not hard-code session count, audit count, DB hash, operation count, or token names.
3. Classify validation-only, completed, and pending operations using the source semantics above. Completed success may lack `candidate.db`.
4. Do not clean restore artifacts in the Settings tabs patch.
5. Transform only `Settings.tsx` and `Settings.css`: accessible section buttons, one visible panel, URL hash, state preservation, and removal of the V425 equal-height rule.
6. Build/deploy, wait for Docker healthy, run restore and complete smoke only against copied databases, and prove live DB/staging snapshots unchanged.
7. Leave all four frontend files uncommitted for desktop and mobile approval.

## Diagnostic Result

- Pending source: exact and authoritative.
- Database: healthy.
- Restore staging: safe; zero pending jobs.
- Deployment: healthy.
- Patch 448 may proceed only after this report is inspected.
