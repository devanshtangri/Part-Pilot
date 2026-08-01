# Diagnostic 422 — Settings desktop composition recovery

<!-- PARTPILOT:DIAGONOSTIC_SETTINGS_COMPOSITION:V422 -->

## Purpose

Patch 422 is diagnostic-only. It recovers the Patch 421 report
whitespace failure after two earlier pre-write failures and does
not modify, stage or commit either pending application file.

## Exact repository state

- Repository: `/projects/Part Pilot`
- Branch: `main`
- Baseline HEAD/origin: `e90354ec74abb1f26d066c4c815dd39a8c6f2400`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Git index: empty
- Pending files: `Settings.tsx`, `Settings.css`
- Pending binary diff SHA-256: `fe9f198f7356fc7cd5b6bc5479db9df69f9c685f76bba61b6859074a7e5c99fa`
- Settings.tsx SHA-256: `333ba4b9dd805d26699d086b0e1546b620d302629d764d4d0ecb0f4e6e41f6d6`
- Settings.css SHA-256: `2bac9f381fae973865d48bca2359177852c915421fcd724de0129794fcbcb5cd`

Pending diff summary:

```text
frontend/src/pages/Settings.css | 182 ++++++++++++++++++++++++++++++++++++++++
 frontend/src/pages/Settings.tsx | 116 ++++++++++++-------------
 2 files changed, 241 insertions(+), 57 deletions(-)
```

## Deployment and live data

- Image ID: `sha256:e323cfcfafd3f1d096df16dc1a7b15ad97928ab86aa03b411444a8dd25f5f031`
- Image reference: `partpilot-partpilot`
- Alembic: `0007_projects_contract`
- SQLite file SHA-256: `5f9bf25f4c1fa41f229d1b69208e7f22b49716ce85d536a3b1420b9540d9e52d`
- SQLite logical SHA-256: `371e79bce6d793abce86c5c7f2ed390b2414773c67309fd81724084fb45794a4`
- Integrity: `ok`; foreign-key violations: `0`
- Parts: `15`
- Projects: `7`
- Reservations: `9`
- Stock movements: `32`
- Audits: `96`
- App settings: `17`
- Appearance: `dark`
- Separate out-of-stock results: `true`

The deployed application remains the successful Patch 418 build.
Protected Search, Reservation and Appearance settings contracts
remain unchanged.

## Failure history

### Patch 419

Patch 419 failed before writes because it compared the complete
Database reset JSX block against an embedded copy with different
indentation. The live block was correct; the equality check was
brittle.

### Patch 420

Patch 420 structurally discovered the Database reset block and
removed two resolved-mode CSS shapes, but one shared base selector
still contained `settings-current-mode`. Its final zero-reference
assertion correctly stopped the patch before writes.

### Patch 421

Patch 421 completed the full in-memory implementation simulation but
its diagnostic report embedded numbered blank source lines as strings
ending in a space. The report validator identified lines 84, 92 and
99 and stopped before the report was written.

Patch 422 formats numbered blank lines without a trailing separator
and normalizes every generated report line before validation.

## Exact resolved-mode occurrences

### Settings.tsx

```text
0420:             </p>
0421:           </div>
0422:           <span className="settings-current-mode">
0423:             Resolved: <strong>{resolvedTheme}</strong>
0424:           </span>
0425:         </div>
```

### Settings.css — all three occurrences

```text
0019:
0020: .settings-runtime-status,
0021: .settings-current-mode,
0022: .settings-danger-badge {
0023:   display: inline-flex;
0024:   flex: 0 0 auto;

0111: }
0112:
0113: .settings-current-mode strong {
0114:   color: var(--text);
0115:   text-transform: capitalize;
0116: }

0754:   }
0755:
0756:   .settings-current-mode,
0757:   .settings-danger-badge {
0758:     align-self: flex-start;
0759:   }
```

The missing Patch 420 transform is:

```css
.settings-runtime-status,
.settings-current-mode,
.settings-danger-badge {
```

It must become:

```css
.settings-runtime-status,
.settings-danger-badge {
```

## Verified source structure

- JSX `settings-current-mode`: `1`
- JSX `Resolved:`: `1`
- CSS `settings-current-mode`: `3`
- Content-grid openings: `1`
- Inventory sections: `1`
- Reservation sections: `1`
- Database reset sections: `1`
- Reset-dialog boundaries: `1`
- Database reset discovered lines: `784`–`819`

## In-memory Patch 423 simulation

No application file was written. The complete proposed
transformation passed in memory.

- Candidate Settings.tsx SHA-256: `5efe64e39cd29c508daf566c857ecf2fe914bbad36032af294ebd04844839ffe`
- Candidate Settings.css SHA-256: `8ed42f2bd00bbc170e39c227ae227bee762e26cb43dcf8e2875d7b56c8480d15`
- Candidate Settings.tsx lines: `907`
- Candidate Settings.css lines: `1163`
- Remaining JSX resolved-mode references: `0`
- Remaining CSS resolved-mode references: `0`
- Database reset section count: `1`
- DOM order: `Inventory → Reservations → Data`
- Trailing whitespace: none

Desktop composition:

```text
Appearance — full width
Compact Inventory preference — full width
Reservation defaults | Database reset
```

Mobile order:

```text
Inventory
Reservations
Database reset
```

## Safe Patch 423 plan

1. Validate this report, both failure logs, source hashes, pending
   diff hash, deployment and live database.
2. Remove the single `Resolved:` JSX element.
3. Remove `settings-current-mode` from all three verified CSS
   shapes: shared base selector, dedicated strong block and mobile
   group.
4. Discover the Database reset section using the verified unique
   section start and reset-dialog boundary.
5. Move the exact discovered block inside the Settings content grid.
6. Assign explicit Inventory, Reservations and Data grid areas.
7. Add the verified desktop and mobile grid-area CSS.
8. Require zero remaining resolved-mode references and one Data
   section in the correct DOM order.
9. Preflight the complete transform in memory before backup/write.
10. Build, deploy, verify production markers, run the complete
    copied-database smoke suite and leave only the two Settings
    files pending for browser test.

## Safety conclusion

All three failures occurred before writes. The exact Patch 418
source, deployment, database and pending diff remain intact.
Patch 423 can safely resume using the fully validated
transformation above.
