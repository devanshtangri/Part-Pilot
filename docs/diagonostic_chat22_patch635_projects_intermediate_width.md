# Chat 22 Patch 635 diagnostic — Projects intermediate-width detail collapse recovery

## Recovery status

Patch 634 was consumed but failed before any repository write.

The failure was in the diagnostic harness rather than the Projects application:
it queried `app_settings.value`, while the live schema uses `value_json` and
`value_text`. The rollback path then attempted to unstage a report that had
never been created, adding a misleading pathspec error to the failure output.

Failure evidence is preserved as:

- Patch 634 script SHA-256:
  `bf1d642722b994a42cda9cb498541a305772472bd4e55d10f0cce94c2d6d2bf2`
- Patch 634 failure log SHA-256:
  `9b8b8af3fed70b61f5ee7b3e04a2c533521897446fab7f4bbc8b47b7c5db7df1`
- Patch 634 final HEAD/origin:
  `a5fb15febaf86a3ece61d30636f3342c710bba27`
- Git/index after failure: clean.

Patch 635 is therefore diagnostic-only recovery. The Projects browser-test
implementation moves to Patch 636.

## Exact source inspected

The diagnosis is locked to the clean Patch 633 application source:

- `frontend/src/pages/Projects.tsx`
  `f32ad2dd643e647b1f97421b152d6adcd95ab250caecd10c1d1db64de4302df8`
- `frontend/src/pages/Projects.css`
  `e49e74f80f29ee40a8a4d187939985853ab69f3abf6163b3e4919c3686805ec6`
- `frontend/src/styles/global.css`
  `eba2bb72ac1a71ba43f0a047445adf154e7bd280b0f1eecf396eee7af8474c5a`
- `frontend/src/app/AppLayout.tsx`
  `f821cace858f9f1c404df5f3529c90caad46e6c9443ff5bec4197c5aa8688f75`

The full Projects cascade was inspected, including later lifecycle selectors and
media-query overrides.

## Exact responsive cascade

The effective Projects desktop layout is:

1. Base workspace:
   `grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr)`.
2. At `max-width: 1180px`:
   `grid-template-columns: minmax(0, 1fr) minmax(310px, 0.72fr)`.
3. At `max-width: 900px`, `.projects-workspace` switches to `display: block`
   and the Project detail becomes the existing fixed/mobile presentation.
4. The application shell independently retains its persistent `232px` sidebar
   until `max-width: 820px`.
5. Desktop `.main-panel` horizontal padding is
   `clamp(20px, 2.2vw, 38px)`.
6. `.project-detail-actions` is `display: flex` and `flex: 0 0 auto`.
7. The lifecycle V398 rule allows the buttons inside that action group to wrap,
   but does not allow the action flex item itself to surrender width.
8. The lifecycle header itself is not stacked until `max-width: 680px`.
9. `.project-detail-header h2` uses `overflow-wrap: anywhere`.

The `680px` header-stacking rule is therefore too late for a defect that occurs
while the desktop two-column Projects workspace is still active above `900px`.

## Usable workspace and detail widths

Above the shell's 820px drawer breakpoint, the Projects workspace width is
approximately:

`min(1440px, viewport - 232px sidebar - 2 × main horizontal padding)`.

The exact committed grid then yields the following useful widths:

| Viewport | Workspace | List track | Detail track | Detail header inner width |
| ---: | ---: | ---: | ---: | ---: |
| 1800 | 1440.0 | 856.8 | 571.2 | 533.2 |
| 1600 | 1297.6 | 771.4 | 514.2 | 476.2 |
| 1440 | 1144.6 | 679.6 | 453.1 | 415.1 |
| 1280 | 991.7 | 587.8 | 391.9 | 353.9 |
| 1200 | 915.2 | 541.9 | 361.3 | 323.3 |
| 1181 | 897.0 | 531.0 | 354.0 | 316.0 |
| 1180 | 896.1 | 514.0 | 370.1 | 332.1 |
| 1100 | 819.6 | 469.5 | 338.1 | 300.1 |
| 1024 | 746.9 | 424.9 | 310.0 | 272.0 |
| 1000 | 724.0 | 402.0 | 310.0 | 272.0 |
| 960 | 685.8 | 363.8 | 310.0 | 272.0 |
| 901 | 629.0 | 307.0 | 310.0 | 272.0 |

At exactly 900px, the existing fixed-detail presentation takes over and this
two-column starvation ends.

## Lifecycle action sets

The exact detail-header actions are:

- Draft: `Reserve Project` and `Edit Draft`.
- Reserved: `Edit Reserved`, `Consume Project`, and `Cancel Project`.
- Consumed: no desktop lifecycle action buttons.
- Cancelled: no desktop lifecycle action buttons.
- `Close` exists in the action container but is hidden until the existing
  fixed/mobile detail presentation.

An isolated Chromium layout rehearsal using the exact committed CSS, without
mutating live Part Pilot source or deployment, measured approximately:

- Draft action group: `253px`.
- Reserved action group: `436px`.

The Reserved action group alone is therefore wider than the complete `272px`
usable header content at the 310px detail-track floor.

With Project name `Power Meter`, the same isolated measurement showed the
Reserved title-copy width collapsing from about `83px` at a 1800px viewport to
about `27px` at 1600px, then effectively zero through much of the narrower
desktop range. Because the title is allowed to wrap `anywhere`, this becomes the
one/few-character-per-line defect observed in the browser.

Draft is less severe because it has two actions instead of three. Consumed and
Cancelled do not suffer the action-width competition.

## Root cause

This is a CSS flex-sizing/responsive-contract defect, not a Project lifecycle or
data defect.

The failure requires three conditions:

1. the two-column workspace permits a narrow detail track;
2. `.project-detail-actions` is a non-shrinking flex item with substantial
   max-content width;
3. the title is the shrinkable sibling and explicitly permits arbitrary
   character breaks.

The later action `flex-wrap` rule only wraps buttons inside the action container.
It does not fix competition between the title block and the action container.

## Safe Patch 636 implementation contract

Patch 636 should be a narrow frontend browser-test fix and should preferably
touch only `frontend/src/pages/Projects.css`.

The safe contract is:

1. Preserve the existing wide desktop two-column workspace.
2. Preserve the existing `<=900px` fixed/mobile Project detail behavior.
3. At intermediate desktop widths where Draft or Reserved lifecycle buttons are
   visible, stop making the title compete horizontally with the non-shrinking
   action group. Stack the lifecycle actions below the title, or provide an
   equivalent layout that guarantees readable title width.
4. Scope the intermediate stacked behavior to headers that actually have visible
   lifecycle actions so Consumed and Cancelled do not gain an empty action row
   from the hidden mobile Close button.
5. Keep the action group inside the detail width and allow its buttons to wrap
   without causing page/detail horizontal overflow.
6. Replace ordinary Project-title wrapping with word-boundary wrapping while
   retaining an emergency break for genuinely unbreakable long tokens.
   `Power Meter` must never collapse character-by-character.
7. Preserve all reserve/edit/consume/cancel controls, focus behavior, notices,
   register selection, filters, pagination, modals and lifecycle semantics.
8. Do not change the application-shell sidebar or the existing 900px detail-mode
   breakpoint as part of this regression fix.
9. Keep Patch 636 source uncommitted until explicit browser approval.

The implementation breakpoint should be chosen from the measured detail/action
space, not simply copied from the old 1180px Projects breakpoint. The problem is
already visible on substantially wider viewports because the Reserved action
group is large.

## Patch 636 browser-test matrix

Use Project name `Power Meter`:

- Draft:
  `Reserve Project` + `Edit Draft`.
- Reserved:
  `Edit Reserved` + `Consume Project` + `Cancel Project`.
- Consumed terminal state.
- Cancelled terminal state.
- Wide desktop visually unchanged.
- Intermediate/narrow desktop has no character-level title collapse.
- Existing `<=900px` fixed/mobile detail behavior remains unchanged.
- No horizontal page/detail overflow.
- A deliberately long Project name wraps at sensible word boundaries and only
  breaks a truly unbreakable token when required.

After Patch 636 is browser-approved, checkpoint the responsive regression fix
promptly. Then resume Chat 22's deferred global individual-tool/per-client MCP
permission diagnostic and implementation work.
