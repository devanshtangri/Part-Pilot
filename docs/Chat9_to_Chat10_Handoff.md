<!-- PARTPILOT:CHAT9_TO_CHAT10_HANDOFF:V225 -->
# Part Pilot — Chat 9 to Chat 10 Handoff

## Required next chat title

`Chat 10: Stored Parts Server Search Migration`

## Repository

- GitHub: `https://github.com/devanshtangri/Part-Pilot.git`
- Local root: `/projects/Part Pilot`
- Branch: `main`
- Docker service: `partpilot`
- Typical port: `7890`
- Alembic head: `0005_packages`

## Read first in Chat 10

1. `docs/Chat9_to_Chat10_Handoff.md`
2. `docs/Part_Pilot_Project_Memory.txt`
3. `docs/Universal_Search_Frontend_Handoff.md`
4. `docs/Universal_Search_Backend_Handoff.md`
5. `docs/Checkpoint.md`
6. `docs/Implementation_Roadmap.md`
7. `README.md`

## Completed in Chat 9

Backend universal search is committed and pushed. It supports protected search across part metadata, part type, manufacturer, location, aliases, tags, and typed custom fields. It preserves filters, pagination, deleted-part exclusion, duplicate suppression, and available-before-out-of-stock ordering.

Dashboard universal search is committed and pushed. It includes typed frontend search support, 280 ms live search, stale-response invalidation, loading/error/no-match states, Available and Out of stock result groups, settings-driven hidden out-of-stock behaviour, selected-result details, keyboard shortcuts, responsive mobile layouts, a centred SVG close icon, populated-section-only rendering, and clearly separated teal/red stock cards.

The user explicitly browser-approved the final Dashboard design.

## Mandatory boundary rule

Patch 225 is the final Python file of Chat 9.

If Patch 225 succeeds, Chat 10 starts with Patch 226.

If Patch 225 fails, do not issue Patch 226 in Chat 9. Update the Chat 10 prompt with the failure, rollback state, and required fix. Chat 10 then starts with Patch 226.

Patch 250 is the final Python file of Chat 10.

## Immediate next task

Migrate Stored Parts search from client-side filtering over the loaded page to the backend universal-search contract.

Preserve part-type and location filters, backend totals and pagination, available-before-out-of-stock ordering, out-of-stock visibility settings, mobile Inventory layout, selection/details, quantity and movement flows, metadata editing, delete/restore, and Part Manager management mode.

Use a read-only preflight first if exact current anchors are uncertain.

## Starting prompt

The ready-to-paste prompt is stored in:

`docs/Chat10_Starting_Prompt.txt`
