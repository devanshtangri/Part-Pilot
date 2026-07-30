# Chat 12: Reservations Foundation — Handoff

<!-- PARTPILOT:CHAT12_RESERVATIONS_FOUNDATION_HANDOFF:V335 -->

## Boundary result

Chat 12 began at Patch 294 with planned boundary Patch 323. Narrow boundary
recovery continued through Patch 335. Patch 335 commits and pushes the
browser-approved Reservations workspace and durable project documentation.

## Repository

- Root: `/projects/Part Pilot`
- Branch: `main`
- Compose service: `partpilot`
- Host port: `7890`
- Alembic head: `0006_reservation_contract`
- Parent before checkpoint: `ce4b9e6a641f14c612db695cd26e4b5c58bd957c`
- Commit subject: `Complete Reservations foundation workspace`

## Completed backend

- Reservation schema, items, statuses, constraints and indexes.
- Atomic creation and available-stock validation.
- Authenticated list, detail and create APIs.
- Cancel, consume and due-only expiry workflows.
- Release/consume stock movements and audit records.
- Existing-data-safe reservation smoke coverage.

## Completed frontend

- `frontend/src/app/App.tsx`
- `frontend/src/types/reservations.ts`
- `frontend/src/services/reservationsClient.ts`
- `frontend/src/pages/Reservations.tsx`
- `frontend/src/pages/Reservations.css`

Browser-approved behaviour includes list/detail, status filters, pagination,
server-backed part search, multi-item creation, cancel/consume/expire actions,
stale guards, responsive layouts and corrected part-picker alignment.

## Data safety

The browser-created **Weather Station** reservation remains in the live
database and is treated as user data. Automated cleanup must not delete it.

## Lessons

- Do not assume the reservations table is empty in smoke tests.
- Production bundles may strip comments and rewrite literal API paths.
- Verify deployed UI with route responses, durable CSS markers and stable
  user-facing strings.
- After repeated failures, separate diagnostic, smoke, CSS and checkpoint work.
- Browser tests requiring input must include mock values, expected results and
  cleanup.

## Next chat

- Title: `Chat 13: Reservation Workflow Finalization`
- First patch: 336
- Planned boundary: 365
- Ownership: Patch 336–365

The next chat must inspect this handoff, Checkpoint, Roadmap, project memory,
README and the latest `diagonostic_` report before issuing Patch 336.
