# Chat 11 to Chat 12 Handoff

<!-- PARTPILOT:CHAT11_TO_CHAT12_HANDOFF:V293 -->
<!-- PARTPILOT:HOMELAB_READ_ONLY_POLICY:V293 -->

## Next chat

**Chat 12: Reservations Foundation**

- First patch: **294**
- Owned patch range: **294 through 323**
- Planned boundary patch: **323**
- Starting action: read-only reservation architecture diagnostic
- Next-chat prompt file: **not created**

The ready-to-paste prompt is supplied in chat only after Patch 293 has actually
run and its terminal output ends with exactly `Everything PASS`.

## Repository and deployment

- Repository: `https://github.com/devanshtangri/Part-Pilot.git`
- Root: `/projects/Part Pilot`
- Branch: `main`
- Compose service: `partpilot`
- Usual host port: `7890`
- Alembic head: `0005_packages`
- Diagnostic checkpoint before boundary:
  `b96e72658a497cbd18c6336b5f409e3d8fdfd501` — `Diagnose duplicate inventory audit event`
- Boundary commit subject: `Close Chat 11 Stored Parts finalization`

## Chat 11 completed scope

Stored Parts is finalized and browser-approved:

- backend universal search;
- part-type, location and stock-status filters;
- accurate totals and pagination across the full filtered result set;
- 25/50/100 page-size preference;
- stale-response protection;
- Available-first grouping;
- separate teal Available and red Out of stock cards;
- empty-section hiding;
- compact responsive section headers;
- independent full-result sorting for Part, Type, Manufacturer, Location,
  Available, Total and Status;
- page reset on sort change;
- preservation of selection, details, quantity, movement history, metadata
  editing, deletion and restoration.

Approved source commit:

```text
ba721e5 Finalize Stored Parts search and sorting
```

## Fixture cleanup

Patch 292 completed the cleanup:

- manifest-owned PP241 parts removed: 70;
- matching PP241 `part.created` audits removed: 70;
- PP241 parts remaining: 0;
- PP241 audit rows remaining: 0;
- real inventory preserved;
- app-setting identities and values preserved;
- SQLite integrity `ok`;
- zero foreign-key violations;
- complete isolated smoke suite passed before live cleanup;
- complete live smoke suite passed after cleanup.

Root cause of the earlier smoke failure:

- the initial cleanup deleted fixture parts but retained historical creation
  audits;
- SQLite reused a deleted part ID because `parts` has no AUTOINCREMENT
  sequence;
- the smoke audit query matched the old PP241 audit plus the new smoke audit;
- corrected cleanup removes the exact manifest-owned audit IDs before the exact
  manifest-owned part IDs.

## Durable workflow

- Every diagnostic, fix, implementation, cleanup, checkpoint and boundary is
  one complete downloadable numbered Python file.
- Successful scripts print exactly `Everything PASS` last.
- Failed scripts consume their patch numbers.
- Do not create or commit next-chat prompt files.
- Do not recreate `docs/Part_Pilot_Project_Memory.txt`.
- Durable continuity uses the newest handoff, Checkpoint, Roadmap, README and
  newest relevant `diagonostic_` report.
- Browser-test source remains uncommitted until explicit approval.
- Preserve real inventory and use manifest-owned IDs for test cleanup.

## HomeLab Terminal restriction

The assistant may use the HomeLab Terminal tool to inspect the actual filebase,
Git state, source, logs, deployment and databases, but **read-only commands
only**.

Never use that tool to:

- create, edit, remove, rename or move files;
- stage, commit, reset, checkout, merge, rebase or push Git;
- write to SQLite or any other database;
- build, restart, stop or recreate containers;
- modify deployment, inventory, fixtures or system configuration.

All mutations must be delivered as a numbered Python patch that the user runs.

## Chat 12 first diagnostic

Patch 294 must inspect:

1. `Project`, `ProjectItem`, `Reservation` and `ReservationItem` models;
2. current database constraints and empty table state;
3. quantity semantics for total, reserved and available;
4. stock movement and audit conventions;
5. auth/schema/service/route patterns;
6. smoke-test fixture and cleanup patterns;
7. `/reservations` and `/projects` placeholder routes;
8. reusable inventory search/selection UI;
9. cancellation, consumption, expiry and project-link boundaries.

Current architecture scan:

- the four reservation/project tables already exist;
- the tables are empty;
- model relationships and foreign keys exist;
- no reservation/project schemas, services or API routes exist;
- `/projects` and `/reservations` are frontend placeholders.

Start with reservations. Keep Projects as a separate implementation boundary
until reservation quantity semantics and lifecycle are verified.
