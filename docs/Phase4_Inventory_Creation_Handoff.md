# Part Pilot — Phase 4 Inventory Creation Handoff

Generated automatically by Patch 102 after all automated verification passed.

## Repository checkpoint

- Branch: `main`
- Last committed HEAD: `bfda422ee3558f18ef60482d1741f372a3cf97fe` (`bfda422`)
- The working tree intentionally contains the uncommitted inventory-creation batch.
- Do not discard or reset these changes.

Current status:

```text
M backend/app/db/smoke_test.py
 M backend/app/main.py
 M backend/app/models/__init__.py
 M backend/app/models/core.py
 M docs/Checkpoint.md
 M docs/Implementation_Roadmap.md
 M frontend/src/pages/PartManager.css
 M frontend/src/pages/PartManager.tsx
?? backend/alembic/versions/0004_manufacturers.py
?? backend/app/api/routes/manufacturers.py
?? backend/app/api/routes/parts.py
?? backend/app/schemas/manufacturers.py
?? backend/app/schemas/parts.py
?? backend/app/services/manufacturers.py
?? backend/app/services/parts.py
?? frontend/src/components/AddPartModal.css
?? frontend/src/components/AddPartModal.tsx
?? frontend/src/services/manufacturersClient.ts
?? frontend/src/services/partsClient.ts
?? frontend/src/types/manufacturers.ts
?? frontend/src/types/parts.ts
```

## Completed in this batch

### Safe custom part-type management

- Custom part types can be created, edited, and safely deleted.
- Built-in templates cannot be deleted.
- Deletion is blocked while any inventory part references the type.
- Deletion creates an audit event.
- The delete dialog uses typed-name confirmation and Part Pilot styling.

### Inventory backend — Patch 093

Authenticated routes now exist:

- `POST /api/parts`
- `GET /api/parts`
- `GET /api/parts/{id}`

Implemented behavior:

- Creates parts from active part-type templates.
- Stores base identifiers, package, description, notes, quantity, unit price, purchase link, and low-stock settings.
- Persists dynamic typed field values.
- Validates required, text, number, boolean, dropdown, URL, and unit-value fields.
- Rejects duplicate part numbers.
- Creates `part.created` audit events.
- Includes protected API smoke coverage and cleanup.

### Add Part modal — Patch 094

- Part Manager has an `Add part` action.
- The selected part type is preselected.
- Template fields render dynamically.
- The modal supports all existing template field types.
- Header and footer remain visible while form content scrolls.
- Client and backend errors stay inside the modal.
- Successful creation shows a confirmation state.

### Manufacturer catalogue — Patch 102

Database:

- Alembic head is `0004_manufacturers`.
- Manufacturers are reusable first-class records.
- Parts link to manufacturers through `manufacturer_id`.
- Existing legacy template values named `manufacturer` or `manufacturer_name` are backfilled where possible.
- Manufacturer deletion behavior is not implemented yet.

Seeded manufacturers:

- Espressif Systems
- Arduino
- NXP Semiconductors
- STMicroelectronics
- Texas Instruments
- Microchip Technology
- Nordic Semiconductor
- Raspberry Pi

Authenticated routes:

- `GET /api/manufacturers`
- `POST /api/manufacturers`

Frontend:

- Add Part includes a reusable manufacturer dropdown.
- Users can create a manufacturer inline and immediately select it.
- Templates with a legacy manufacturer field do not display a duplicate control.
- The Part Added state is a compact receipt-style card showing type, manufacturer, quantity, and part number.
- The manufacturer-field key normalizer uses ES-compatible regex replacement instead of `String.replaceAll`.
- `Part.manufacturer_id` is inserted and verified inside the SQLAlchemy `Part` class using AST structure rather than a whitespace regex.

## Automated verification completed

- Python source compilation
- `git diff --check`
- Docker image build
- Alembic upgrade to `0004_manufacturers`
- Complete Part Pilot smoke suite
- Manufacturer API smoke coverage
- Deployed bundle marker verification
- `/part-manager` React SPA route verification
- Database backup created before migration

## Manual browser verification completed

1. Hard-refresh `/part-manager`.
2. Select `Development Board`.
3. Open `Add part`.
4. Confirm the Manufacturer dropdown contains seeded options.
5. Use `Add new` to create a temporary custom manufacturer.
6. Confirm the new manufacturer becomes selected and remains reusable.
7. Confirm no second manufacturer template field appears.
8. Create a test inventory part.
9. Confirm the compact Part Added card shows:
   - part type
   - manufacturer
   - quantity
   - part number
10. Close and reopen Add Part to confirm the custom manufacturer remains available.

## Commit status

The browser workflow above was confirmed after Patch 106. The inventory and manufacturer batch is approved for checkpointing.

After browser verification, create one Python checkpoint script that:

- verifies Alembic is at `0004_manufacturers`
- runs the complete smoke suite
- builds the frontend
- stages only intended Phase 4 inventory/manufacturer files and this handoff
- commits and pushes the batch
- prints `Everything PASS` only after push and clean tracked status

Suggested commit message:

```text
Add inventory part creation and manufacturer catalogue
```

## Next implementation area

After checkpointing this batch, continue with inventory browsing:

- inventory list/table
- search by name and part number
- filtering by type and manufacturer
- stock and low-stock status
- out-of-stock grouping according to settings
- part detail view
- edit workflow
- quantity adjustment history
- soft deletion and restoration safeguards

<!-- PATCH 107 CHECKPOINT APPROVAL -->

## Manufacturer field preset — Patch 106

- The custom part-type editor now offers `Manufacturer` as a semantic field preset.
- The preset remains compatible with the existing API and database contract by storing `field_type = "text"` and `field_key = "manufacturer"`.
- The reserved manufacturer key is locked while the preset is selected.
- Existing `manufacturer` and `manufacturer_name` template fields are recognized.
- A custom template cannot contain more than one Manufacturer preset.
- Add Part continues to use the persistent manufacturer catalogue and does not show a duplicate template input.

## Final browser approval

The following workflow was manually verified and passed:

- seeded manufacturers appear
- custom manufacturers can be created
- a newly created manufacturer becomes selected
- custom manufacturers remain reusable after reopening Add Part
- no duplicate Manufacturer template control appears
- a test inventory part can be created
- the compact Part Added receipt displays type, manufacturer, quantity, and part number
- a custom template can select and retain the Manufacturer preset
- duplicate Manufacturer presets are rejected

This batch is approved for commit with:

```text
Add inventory part creation and manufacturer catalogue
```
