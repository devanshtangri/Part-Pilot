# Diagnostic: reservation deletion and durable view preferences

**Patch:** 350
**Generated:** 2026-07-30T10:50:44.327188+00:00
**Repository:** `/projects/Part Pilot`
**Branch:** `main`
**HEAD/origin:** `918107968a856c5c57045c61e399484e60a02c0b`
**Alembic:** `0006_reservation_contract`
**Application source changed:** no
**Database changed:** no
**Deployment changed:** no

## Executive findings

1. The current API has no reservation `DELETE` route. The deployed protected path
   returns `405 Method Not Allowed` for `DELETE /api/reservations/1`.
2. The only live reservation is **Weather Station**, status **cancelled**. It has
   1 reservation item, 2 linked stock movements,
   and 3 reservation audit entries.
3. A safe hard-delete contract is possible without changing inventory:
   `reservation_items` cascades, while `stock_movements.reservation_id` uses
   `ON DELETE SET NULL`.
4. `audit_log.entity_id` is intentionally not foreign-keyed. Deletion must make
   an explicit product decision. The recommended policy is to retain prior audit
   records and add `reservation.deleted` with a complete final snapshot.
5. Reservations currently default to `all`, and their selected status tab is not
   persisted. The requested behavior is: missing or invalid preference defaults
   to `active`; valid tab choices survive refresh.
6. The only browser-stored view preference currently implemented is inventory
   page size. Inventory stock/type/location filters and both section sorts reset
   on every refresh.
7. The Available/Out-of-stock divider is a self-contained JSX block and CSS block.
   It can be removed without changing either colored section card.

## Exact live state

| Item | Finding |
|---|---|
| Reservation | #1 Weather Station — cancelled |
| Reservation items | 1 |
| Linked stock movements | 2 |
| Reservation audit entries | 3 |
| Active inventory parts | 7 |
| Total quantity | 144 |
| Reserved quantity | 0 |
| Available quantity | 144 |
| Projects | 0 |

The diagnostic must not delete or alter Weather Station. Future automated tests
must create unique fixture reservations and delete only their exact IDs.

## Reservation deletion contract

### Current database behavior

| Dependent data | Foreign-key behavior | Result when reservation row is deleted |
|---|---|---|
| `reservation_items.reservation_id` | `ON DELETE CASCADE` | Reservation item rows are removed. |
| `stock_movements.reservation_id` | `ON DELETE SET NULL` | Immutable stock history remains, detached from the deleted record. |
| `audit_log.entity_id` | No foreign key | Existing lifecycle history remains with the historical reservation ID. |
| `projects` | Reservation uses nullable `project_id` | Project remains unchanged. |

### Recommended backend rules

- Add authenticated `DELETE /api/reservations/{reservation_id}`.
- Accept an exact-label confirmation payload so direct API callers receive the
  same destructive-action safeguard as the UI.
- Permit deletion only for `cancelled`, `consumed`, or `expired` records.
- Reject active deletion with `409 Conflict`; users must cancel/consume/expire first.
- Lock and re-read the reservation before deletion.
- Assert no stock quantity is changed by the operation.
- Capture a complete final snapshot, including items, status, project link,
  value, expiry, creator, and timestamps.
- Add one `reservation.deleted` audit entry containing that snapshot and actor.
- Delete the reservation row; allow item cascade and movement detachment.
- Keep prior audit entries and stock movements for the future global History view.
- Return a small deletion response containing the deleted ID, label, previous
  status, removed-item count, detached-movement count, and deletion timestamp.
- Test only manifest-owned fixture IDs. Never use Weather Station as a deletion fixture.

### Required smoke coverage

- Authentication and OpenAPI exposure.
- `404` missing ID.
- `409` active reservation.
- `422` wrong confirmation label.
- Successful deletion for cancelled, consumed, and expired fixtures.
- Reservation row and item removal.
- Stock movements retained with `reservation_id = NULL`.
- Existing lifecycle audits retained plus one `reservation.deleted` audit.
- Inventory totals, reserved quantities, real reservations, and projects unchanged.
- Repeated delete returns `404` and creates no duplicate deletion audit.

## Durable view-preference policy

### Storage tiers

| Preference type | Storage | Reason |
|---|---|---|
| Installation-wide behavior | Authenticated `app_settings` API | Shared application behavior, already used by out-of-stock grouping. |
| Per-browser view choices | Validated namespaced `localStorage` | Fast, user-facing layout/filter memory without changing installation policy. |
| Transient workflow state | React state only | Avoid stale drawers, searches, pages, dialogs, and unsaved forms after refresh. |

### Persist now

- `partpilot.reservations.status-filter`: `active`, `all`, `consumed`,
  `cancelled`, or `expired`; default `active` when absent or invalid.
- `partpilot.inventory.page-size`: preserve the existing validated implementation.
- `partpilot.inventory.stock-filter`.
- `partpilot.inventory.part-type-filter` after validating the stored ID against
  loaded active part types.
- `partpilot.inventory.location-filter` after validating the stored ID against
  loaded locations.
- `partpilot.inventory.available-sort-by` and `...available-sort-direction`.
- `partpilot.inventory.out-of-stock-sort-by` and `...out-of-stock-sort-direction`.
- `partpilot.part-manager.type-filter` for All/Built-in/Custom.
- Future Projects tabs, filters, section choices, sorts, and page sizes should use
  the same helper and validation rules when Projects is implemented.

### Do not persist

- Search text.
- Pagination offsets or current page number.
- Selected reservation/part IDs and open detail drawers.
- Open dialogs, confirmation state, or modal state.
- Unsaved create/edit form content.
- Loading, error, success, or stale-request state.
- Temporary inventory adjustment operation and fields.

### Implementation shape

Create one typed helper such as `frontend/src/utils/viewPreferences.ts` with:

- safe read/write/remove wrappers that tolerate blocked storage;
- enum validation and numeric-ID validation;
- central namespaced keys;
- explicit defaults;
- no JSON parsing without schema checks;
- helpers that can be reused by Reservations, Inventory, Part Manager, and future Projects.

Every restored filter or sort must reset offset to page one. Invalid IDs must be
removed from storage after the corresponding catalogue loads.

## Current preference inventory

### Browser keys discovered in frontend source

- `partpilot.auth.token`
- `partpilot.inventory.page-size`

### Installation setting keys currently present

- `app.display_name`
- `appearance.light_theme_available`
- `appearance.theme`
- `backups.enabled`
- `backups.frequency`
- `backups.path`
- `backups.retention_count`
- `currency.default`
- `mcp.enabled`
- `mcp.read_tools_enabled`
- `mcp.write_tools_enabled`
- `price.warn_when_missing`
- `reservations.expiry.default_days`
- `reservations.expiry.mode`
- `search.show_out_of_stock_section`
- `setup.completed`
- `timezone.default`

The existing `search.show_out_of_stock_section` remains an installation setting;
it must not be duplicated into browser storage.

## Inventory divider removal

Remove only:

- the conditional `inventory-results-separator` JSX block in `PartManager.tsx`;
- the separator, line, badge, and separator-only mobile CSS selectors.

Preserve:

- Available section teal card/header treatment;
- Out-of-stock section red card/header treatment;
- independent section titles and counts;
- independent server-backed sorting;
- hidden-empty-section behavior;
- pagination and settings-driven out-of-stock grouping.

## Recommended patch sequence

1. **Patch 351 — Fix Only:** backend inactive-reservation deletion contract,
   schemas, route, service, fixture-safe smoke tests, commit/push.
2. **Patch 352 — Browser Test:** inactive-record Delete UI with exact-label
   confirmation plus persisted reservation status tab defaulting to Active.
3. **Patch 353 — Fix Only:** checkpoint/commit/push after browser approval.
4. **Patch 354 — Browser Test:** reusable view-preference helper; migrate
   inventory filters, Part Manager type filter, and both section sorts; remove
   the divider JSX/CSS while preserving colored cards.
5. **Patch 355 — Fix Only:** checkpoint/commit/push after browser approval.
6. Continue with reservation defaults/settings or Projects only after these
   slices are approved and durable docs are updated.

## Source hashes

| File | SHA-256 |
|---|---|
| `backend/app/api/routes/reservations.py` | `b896ef01b47d52502612c3cdef7bf7c6b628533f6588efbfa760aa9977755e1a` |
| `backend/app/db/smoke_test.py` | `9f9ec38ddb8481613eacd822fa681bbad26d6a5119ad45ca6cea9747efd4346b` |
| `backend/app/models/core.py` | `8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679` |
| `backend/app/schemas/app_settings.py` | `c2464d28cbbbaa5fe9939b3b7e9dd1759960e76c7988a59e3cc6675b3d796f1f` |
| `backend/app/services/app_settings.py` | `8ff3fe4c1cfd97e7ce3e9c6317f1621603193a4cc93602d6d00783995ec26238` |
| `backend/app/services/reservations.py` | `98d675583a584cd1d24d4c56d85bf955d79e70b47c20da5cdc97b1b097a691a5` |
| `frontend/src/pages/PartManager.css` | `b3c64207fa1c171e8770f46790cd693df41413f5fe5d242d52d4e5727bff10de` |
| `frontend/src/pages/PartManager.tsx` | `1122bb8b9525775cc794b404875a49b5dc28a2ff9f89fb5df85607176ec793b9` |
| `frontend/src/pages/Reservations.tsx` | `308c5f2b891d877c7e9f8235c9386df55df079d0e5f5283789388813f97e5622` |
| `frontend/src/pages/Settings.tsx` | `dcb30517bd591886f89466ba88fcc5f372d1aec1ca1e0f3834fd1f1ea3b1d75f` |
| `frontend/src/services/partsClient.ts` | `8dc0f4a07610807427e9bc56050ea84b76d504b5466ba377cdc4470f715fa43f` |
| `frontend/src/services/reservationsClient.ts` | `fb81de9bb2974e81e5e8492a0b4e648e0571ad0123d622a3bdf1df611459207c` |
| `frontend/src/types/reservations.ts` | `62845af36e9ef50198d56d2aea60bdc8cb7ce26fc3a15ff75739fd63c33d107c` |

## Anchor counts

### `backend/app/api/routes/reservations.py`

| Anchor | Count |
|---|---:|
| `@router.get(` | 3 |
| `@router.post(` | 4 |
| `@router.put(` | 1 |
| `@router.delete(` | 0 |

### `backend/app/services/reservations.py`

| Anchor | Count |
|---|---:|
| `def update_reservation(` | 1 |
| `def cancel_reservation(` | 1 |
| `def consume_reservation(` | 1 |
| `def expire_reservation(` | 1 |
| `def list_reservation_activity(` | 1 |
| `def delete_reservation(` | 0 |

### `frontend/src/pages/Reservations.tsx`

| Anchor | Count |
|---|---:|
| `useState<ReservationStatus | "all">("all")` | 1 |
| `reservations-status-tabs` | 1 |
| `PARTPILOT:RESERVATION_NOOP_FIX:V348` | 1 |
| `Delete reservation` | 0 |

### `frontend/src/pages/PartManager.tsx`

| Anchor | Count |
|---|---:|
| `INVENTORY_PAGE_SIZE_STORAGE_KEY` | 3 |
| `inventory-results-separator` | 4 |
| `availableInventorySortBy` | 5 |
| `outOfStockInventorySortBy` | 5 |
| `inventoryStockFilter` | 13 |
| `inventoryPartTypeFilter` | 9 |
| `inventoryLocationFilter` | 9 |

### `frontend/src/pages/PartManager.css`

| Anchor | Count |
|---|---:|
| `.part-manager-page .inventory-results-separator` | 6 |
| `--stored-parts-out-of-stock-card-v257` | 1 |
| `--stored-parts-available-card-v258` | 0 |

## Relevant source excerpts

### Reservation Models

```text
L352:             name="fk_stock_movements_reservation_id_reservations",
L447: class Reservation(Base, TimestampMixin):
L466: class ReservationItem(Base, TimestampMixin):
L475:     reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
L483: class AuditLog(Base):
```

### Reservation Routes

```text
L36: @router.get(
L61: @router.get(
L80: @router.post(
L112: @router.put(
L148: @router.post(
L177: @router.post(
L206: @router.post(
L241: @router.get(
```

### Reservation Filter

```text
L267:     useState<ReservationStatus | "all">("all");
L865:           className="reservations-status-tabs"
L879:                 setStatusFilter(option.value);
```

### Inventory Preferences

```text
L58: const INVENTORY_PAGE_SIZE_STORAGE_KEY = "partpilot.inventory.page-size";
L69:         INVENTORY_PAGE_SIZE_STORAGE_KEY
L95:       INVENTORY_PAGE_SIZE_STORAGE_KEY,
L415:   const [inventoryStockFilter, setInventoryStockFilter] =
L419:   const [availableInventorySortBy, setAvailableInventorySortBy] =
L425:   const [outOfStockInventorySortBy, setOutOfStockInventorySortBy] =
L434:   const [inventoryPartTypeFilter, setInventoryPartTypeFilter] =
L455:   const [inventoryLocationFilter, setInventoryLocationFilter] =
L629:       partTypeId: inventoryPartTypeFilter ?? undefined,
L630:       locationId: inventoryLocationFilter ?? undefined,
L632:       stockStatus: inventoryStockFilter,
L633:       availableSortBy: availableInventorySortBy,
L635:       outOfStockSortBy: outOfStockInventorySortBy,
L686:     inventoryLocationFilter,
L687:     inventoryPartTypeFilter,
L690:     inventoryStockFilter,
L691:     availableInventorySortBy,
L693:     outOfStockInventorySortBy,
L873:       inventoryLocationFilter === null
L876:             (location) => location.id === inventoryLocationFilter
L878:     [inventoryLocationFilter, inventoryLocations]
L882:       inventoryPartTypeFilter === null
L885:             (partType) => partType.id === inventoryPartTypeFilter
L887:     [collection, inventoryPartTypeFilter]
L896:       if (inventoryStockFilter === "in") {
L900:       if (inventoryStockFilter === "low") {
L904:       if (inventoryStockFilter === "out") {
L910:   }, [inventoryServerParts, inventoryStockFilter]);
L914:       inventoryStockFilter !== "all"
L925:     inventoryStockFilter,
L951:     || inventoryStockFilter !== "all"
L952:     || inventoryLocationFilter !== null
L953:     || inventoryPartTypeFilter !== null
L1499:         ? availableInventorySortBy
L1500:         : outOfStockInventorySortBy;
L1528:         ? availableInventorySortBy
L1529:         : outOfStockInventorySortBy;
L2514:               value={inventoryPartTypeFilter ?? ""}
L2545:               value={inventoryLocationFilter ?? ""}
L2597:                   inventoryStockFilter === mode ? "active" : ""
L2599:                 aria-pressed={inventoryStockFilter === mode}
L2631:           && inventoryStockFilter === "all"
L2632:           && inventoryLocationFilter === null
L2633:           && inventoryPartTypeFilter === null
L2705:             className="inventory-results-separator"
L2710:             <span className="inventory-results-separator-line" />
L2711:             <span className="inventory-results-separator-badge">
L2714:             <span className="inventory-results-separator-line" />
```

### Inventory Separator Css

```text
L2788: .part-manager-page .inventory-results-separator {
L2796: .part-manager-page .inventory-results-separator-line {
L2803: .part-manager-page .inventory-results-separator-badge {
L2824:   .part-manager-page .inventory-results-separator {
L2829:   .part-manager-page .inventory-results-separator-line {
L2833:   .part-manager-page .inventory-results-separator-badge {
L2843:   --stored-parts-out-of-stock-card-v257: 1;
```

## Safety conclusion

The requested work is feasible without a migration. The deletion slice is the
only part that mutates domain data and must be implemented first with isolated
fixtures and full history/inventory assertions. Preference persistence and the
inventory-divider removal are frontend-only but should follow the typed helper
policy above rather than adding unrelated ad-hoc storage calls.
