# Diagnostic: reservation defaults and expiry settings

**Patch:** 360
**Generated:** 2026-07-30T13:43:31.510521+00:00
**Repository:** `/projects/Part Pilot`
**Branch:** `main`
**HEAD/origin:** `c3f93e079ee394db0fb1a9be352206f1ab8ea46a`
**Alembic:** `0006_reservation_contract`
**Application source changed:** no
**Database changed:** no
**Deployment changed:** no

## Executive findings

1. The database already seeds `reservations.expiry.mode` and
   `reservations.expiry.default_days`; no migration is required.
2. The live values are mode `none` and default days `null`.
3. No schema, service, route, frontend client, Settings card, or reservation-form
   logic currently reads or updates those keys.
4. The existing protected settings API exposes only `/api/settings/search`.
   Unauthenticated GET returns `404` and PATCH returns `405` for
   `/api/settings/reservations`, proving the reservation-settings contract does
   not yet exist.
5. New reservation currently resets expiry to blank. Edit reservation correctly
   loads the selected reservation's committed expiry and must remain isolated
   from installation defaults.
6. The safest V1 behavior is a non-enforcing default: optionally prefill new
   manual reservation forms after a configured number of days, while preserving
   the user's ability to clear or change it.
7. Direct reservation API calls must remain explicit. The backend reservation
   service must not silently inject a default when `expiry_at` is omitted or
   explicitly null.

## Exact live state

| Item | Current value |
|---|---|
| Reservation expiry mode | `none` |
| Reservation default days | `null` |
| Installation timezone | `Asia/Kolkata` |
| Existing reservation | #1 Weather Station — cancelled |
| Existing reservation expiry | `2026-07-31 12:22:00.000000` |
| Active inventory parts | 7 |
| Total quantity | 144 |
| Reserved quantity | 0 |
| Available quantity | 144 |

Weather Station, its audit history, and all real inventory must remain unchanged
through every settings test. Settings smoke coverage must snapshot and restore
only the two reservation setting rows and fixture-owned audit IDs.

## Recommended product contract

### Supported modes

| Mode | User-facing label | New reservation behavior | Existing/Edit behavior |
|---|---|---|---|
| `none` | No automatic expiry | Expiry starts blank. | Never changed. |
| `default` | Default expiry after N days | Expiry is prefilled with now plus N 24-hour days. The user may clear or change it. | Never changed or re-defaulted. |

Do not add a `required` mode in this slice. Required-expiry enforcement creates
migration and compatibility questions for existing no-expiry reservations,
API/MCP callers, edits, imports, and future project workflows. It can be added
later only with an explicit enforcement design.

### Validation

- `expiry_mode` must be exactly `none` or `default`.
- In `none` mode, persist `default_days = null` even if a stale client submits a
  prior number.
- In `default` mode, `default_days` is required and must be an integer from 1 to
  3650 inclusive.
- Reject booleans, floats, strings, zero, negative values, and values above 3650.
- GET must defensively normalize corrupt legacy combinations to `none/null`
  without silently writing during a read.
- PATCH updates both settings in one transaction.
- A no-op PATCH returns the current response and creates no audit row.

### API

Add authenticated:

- `GET /api/settings/reservations`
- `PATCH /api/settings/reservations`

Response and update payload:

```json
{
  "expiry_mode": "none",
  "default_days": null
}
```

Use typed Pydantic models with `extra="forbid"`. Return `422` for invalid mode/day
combinations. Keep settings separate from reservation creation so API callers
continue to make an explicit `expiry_at` decision.

### Audit behavior

- Event: `settings.reservations_updated`.
- Entity type: `app_setting`.
- Entity ID: the `reservations.expiry.mode` setting row ID.
- One audit entry covers both keys atomically.
- `before_json` and `after_json` contain `expiry_mode` and `default_days`.
- Metadata lists both setting keys and only the fields that actually changed.
- Attribute the authenticated user.
- No audit on a no-op update.

## Settings UI

Add a restrained **Reservation defaults** card above Developer tools:

- A two-choice segmented control or select for **No automatic expiry** and
  **Default expiry after**.
- Show a numeric days field only when default mode is selected.
- Explain that the value prefills new reservations and can still be cleared.
- Use an explicit **Save reservation defaults** action because mode and days are
  one atomic setting pair.
- Preserve unsaved changes on API error and restore the last saved values only
  after an explicit reset/cancel action.
- Provide loading, saving, saved, validation, and retry states.
- Match the existing flat Settings card, controls, focus states, and mobile layout.

## New reservation integration

- Load reservation settings through the authenticated Settings client.
- Do not block the Reservations register or New reservation button while settings
  load; fallback is no automatic expiry.
- `openCreate` resets the form and, only in `default` mode with a valid day count,
  sets expiry to `Date.now() + default_days * 24 hours` at minute precision.
- The resulting local `datetime-local` value converts to an explicit UTC ISO
  timestamp through the existing submit path.
- Users may clear or change the prefilled value before creation.
- `openEdit` must continue loading only `selectedReservation.expiry_at`; it must
  never call or apply the default.
- Reopening New reservation recomputes from the current time instead of reusing a
  stale draft.
- Unsaved form values, open modal state, and search text remain transient.

## Required backend smoke coverage

- Seeded defaults read as `none/null`.
- Authentication and OpenAPI exposure.
- Valid transitions `none -> default -> none`.
- Boundary values 1 and 3650.
- Invalid mode, missing days, zero, negative, float, boolean, string, and 3651.
- Atomic two-key persistence and exact text/json values.
- One audit for a real change; no audit for no-op.
- Actor attribution and changed-field metadata.
- Rollback on injected failure between the two setting writes.
- Exact restoration of original setting values and fixture audit rows.
- Weather Station, inventory, reservations, movements, projects, and unrelated
  settings unchanged.

## Required browser coverage

- Current live default `none` renders correctly.
- Save `default` with a temporary fixture value only if the browser test plans an
  exact restoration before approval; otherwise test validation and cancel paths
  without changing live settings.
- New reservation starts blank in `none` mode.
- In a reversible test setting, New reservation receives the calculated default,
  can clear it, and Cancel leaves no reservation.
- Edit reservation never changes an existing expiry from defaults.
- Settings errors do not block Reservations.
- Desktop/mobile layout and keyboard focus are correct.

## Recommended remaining Chat 13 sequence

1. **Patch 361 — Fix Only:** backend reservation-settings schemas, service, routes,
   atomic audit behavior, and existing-data-safe smoke coverage; commit/push.
2. **Patch 362 — Browser Test:** Settings card, typed client/contracts, and New
   reservation default integration in one coherent frontend slice.
3. **Patch 363 — Fix or Browser Test:** apply only approval feedback, or checkpoint
   immediately if Patch 362 is approved unchanged.
4. **Patch 364 — Fix Only:** checkpoint approved frontend and update durable
   reservation/settings documentation; reserve narrow recovery if needed.
5. **Patch 365 — Fix Only:** Chat 13 boundary, durable handoff, final docs, commit,
   push, and next-chat prompt supplied only after `Everything PASS`.

Projects remain a separate implementation boundary for the next chat. Do not
start Projects, History, backup/restore, appearance, or MCP work before the Chat
13 boundary is complete.

## Current HTTP contract

| Probe | Status | Content type |
|---|---:|---|
| `GET /api/settings/search` | 401 | `application/json` |
| `GET /api/settings/reservations` | 404 | `application/json` |
| `PATCH /api/settings/reservations` | 405 | `application/json` |

## Source hashes

| File | SHA-256 |
|---|---|
| `backend/app/api/routes/app_settings.py` | `6da540c40dd540d2e4c29a6cff3ca056798e6a24948d81c020d214f082a8a0ae` |
| `backend/app/db/seed.py` | `6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de` |
| `backend/app/db/settings.py` | `f0c3037f153f856a97a4424ce87ddf30470b0b4fdd2ac150b728ea1f9cdca12b` |
| `backend/app/db/smoke_test.py` | `8acb7390f673d31a53926f6cef648f37ed4305157b8ed36403450bd986549b4f` |
| `backend/app/models/core.py` | `8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679` |
| `backend/app/schemas/app_settings.py` | `c2464d28cbbbaa5fe9939b3b7e9dd1759960e76c7988a59e3cc6675b3d796f1f` |
| `backend/app/schemas/reservations.py` | `110c955783f055b2f3e718c5234c449fe4de12e5f47a5c52c3adc74b1a6b5d16` |
| `backend/app/services/app_settings.py` | `8ff3fe4c1cfd97e7ce3e9c6317f1621603193a4cc93602d6d00783995ec26238` |
| `backend/app/services/reservations.py` | `229958deea1ef52d56ba2e8bdb0a574d502c46ccc1ac4850c60cdf7855b61e9e` |
| `docs/Checkpoint.md` | `44b76e79597320ce0a202cf19599d4504bcd7a5c71f357a134bd15049f84567e` |
| `docs/Implementation_Roadmap.md` | `1e83d492d6870a263aa9571723497aa446286f53776411eca7c4a87acc2cba94` |
| `frontend/src/pages/Reservations.tsx` | `814a69b8e0dfb7f33b9598b6caca1ea38c96ca6a3a74582c063e2576ca47231b` |
| `frontend/src/pages/Settings.css` | `05c49f436d3c578c05882cf41f53994c70b6482bc30164dff1bb2ff8805f10bd` |
| `frontend/src/pages/Settings.tsx` | `dcb30517bd591886f89466ba88fcc5f372d1aec1ca1e0f3834fd1f1ea3b1d75f` |
| `frontend/src/services/settingsClient.ts` | `a3c4d5f482bc3c8948458afe3fa74835201677c8f4a17871ffa3c1f74f8186e6` |
| `frontend/src/types/settings.ts` | `d8edf78b012dba509f43746077d5b4b5f22f5f7a12ed74ac741e362b1f8ae456` |
| `frontend/src/utils/viewPreferences.ts` | `4678368f7d279976b0827e8145fccb1fbcdeede9066755912a612e290d3a06e3` |

## Anchor counts

### `backend/app/db/seed.py`

| Anchor | Count |
|---|---:|
| `"reservations.expiry.mode"` | 1 |
| `"reservations.expiry.default_days"` | 1 |

### `backend/app/schemas/app_settings.py`

| Anchor | Count |
|---|---:|
| `SearchSettingsResponse` | 1 |
| `ReservationSettingsResponse` | 0 |

### `backend/app/services/app_settings.py`

| Anchor | Count |
|---|---:|
| `get_search_settings` | 1 |
| `get_reservation_settings` | 0 |
| `update_reservation_settings` | 0 |

### `backend/app/api/routes/app_settings.py`

| Anchor | Count |
|---|---:|
| `@router.get("/search"` | 1 |
| `@router.get("/reservations"` | 0 |
| `@router.patch("/reservations"` | 0 |

### `frontend/src/pages/Settings.tsx`

| Anchor | Count |
|---|---:|
| `getSearchSettings` | 2 |
| `Reservation defaults` | 0 |
| `reservations.expiry` | 0 |

### `frontend/src/pages/Reservations.tsx`

| Anchor | Count |
|---|---:|
| `setDraftExpiry("")` | 1 |
| `const openCreate = () =>` | 1 |
| `const openEdit = () =>` | 1 |
| `setDraftExpiry(toLocalDateTimeInput(selectedReservation.expiry_at))` | 1 |

## Safety conclusion

Reservation defaults can be implemented without a migration and without changing
reservation lifecycle semantics. Keep the settings contract non-enforcing,
installation-wide, explicit, atomic, and audited. Apply defaults only when opening
a new manual reservation form; never rewrite existing reservations and never
silently alter direct API payloads.
