# Part Pilot Implementation Roadmap

Generated: 2026-07-07
Project: Part Pilot
Purpose: Practical build order for taking Part Pilot from empty repository to working V1 prototype, then polished V1 release.

---

## 0. Roadmap Philosophy

Part Pilot should be built in small, testable loops.

The first successful prototype is:

> Add IRFZ44N, set quantity/location, search it, reserve 2, consume 1, and see history.

Do not start with MCP, advanced UI polish, backups, or complicated templates. Build the core inventory loop first, then layer polish and AI integration on top.

---

## 1. Confirmed V1 Stack

### Frontend

- React
- Vite
- TypeScript
- Responsive layout
- Dark theme first
- Light theme through settings later in V1

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic migrations
- Pydantic schemas

### Database

- SQLite for V1
- Persistent database stored under mounted `/data`

### Deployment

- Docker Compose first
- One app service for V1 unless splitting becomes necessary
- Persistent mounted data folder

### Recommended repository structure

```text
partpilot/
  README.md
  LICENSE
  docker-compose.yml
  .env.example
  backend/
    app/
      main.py
      core/
      api/
      models/
      schemas/
      services/
      db/
      mcp/
    tests/
    alembic/
    requirements.txt
    Dockerfile
  frontend/
    src/
      app/
      components/
      pages/
      features/
      services/
      styles/
      types/
    package.json
    vite.config.ts
  data/
    .gitkeep
  docs/
    Part Pilot_V1_Product_Specification.md
    Checkpoint.md
    Implementation_Roadmap.md
```

---

## 2. Phase 1 — Repository and Project Skeleton

Goal: Create a clean repository that can run a frontend and backend locally.

### Backend tasks

- [ ] Create `backend/` folder.
- [ ] Create Python virtual environment.
- [ ] Add FastAPI.
- [ ] Add Uvicorn.
- [ ] Add SQLAlchemy.
- [ ] Add Alembic.
- [ ] Add Pydantic settings support.
- [ ] Create `app/main.py`.
- [ ] Add `/health` route.
- [ ] Add basic settings loader.
- [ ] Add database connection setup.
- [ ] Add CORS configuration for local frontend.

### Frontend tasks

- [ ] Create React + Vite + TypeScript app.
- [ ] Add routing.
- [ ] Add basic API client.
- [ ] Add base layout shell.
- [ ] Add placeholder sidebar.
- [ ] Add placeholder dashboard.
- [ ] Add global CSS/theme variables.

### Docker tasks

- [ ] Add backend Dockerfile.
- [ ] Add frontend build process.
- [ ] Add Docker Compose file.
- [ ] Add persistent `/data` volume mapping.
- [ ] Verify service can start from Docker Compose.

### Completion criteria

- [ ] `docker compose up` starts the service.
- [ ] Frontend loads in browser.
- [ ] Backend `/health` returns OK.

---

## 3. Phase 2 — Database Foundation

Goal: Create the core database model before UI complexity.

### Initial tables

- [x] `app_settings`
- [x] `users`
- [x] `sessions`
- [x] `part_types`
- [x] `part_type_fields`
- [x] `parts`
- [x] `part_field_values`
- [x] `tags`
- [x] `part_tags`
- [x] `aliases`
- [x] `locations`
- [x] `stock_movements`
- [x] `projects`
- [x] `project_items`
- [x] `reservations`
- [x] `reservation_items`
- [x] `audit_log`
- [x] `backups`

### Migration tasks

- [x] Create first Alembic migration.
- [x] Ensure SQLite database is created under `/data/partpilot.db`.
- [x] Add timestamp fields consistently.
- [x] Add soft references or snapshots for audit events.

### Data rules

- [x] Part number is optional.
- [x] Name is optional.
- [x] At least one of name or part number is required.
- [x] Quantity is required.
- [x] Location is optional.
- [x] Price is optional.
- [x] Currency is configured during first-run setup.
- [x] Duplicate part numbers are blocked if part number is provided.

### Completion criteria

- [x] Database migrates cleanly.
- [x] Empty database can be initialized.
- [x] Built-in part types can be seeded.

---

## 3.1 Phase 2 Completion Notes

Phase 2 was completed as a database-only foundation before starting API/UI complexity.

Completed implementation additions:
- SQLAlchemy models for all V1 foundation tables.
- Alembic migration `0001_database_foundation`.
- Alembic migration `0002_schema_hardening`.
- SQLite foreign key enforcement.
- Built-in part type seed data.
- Built-in template field seed data.
- Default app setting seed data.
- Backend database utilities/constants/settings helpers.
- Database smoke test covering migration, seed data, constraints, rollback safety, and helper behavior.

Final Phase 2 smoke test command:

```bash
docker compose exec -T partpilot python -m app.db.smoke_test
```

Expected final line:

```text
[PASS] Phase 2 database smoke test completed
```

---

## 4. Phase 3 — First-run Setup and Authentication

Goal: Make Part Pilot a single-user protected app.

### First-run setup flow

- [x] Detect whether setup has been completed.
- [x] If not completed, show setup screen.
- [x] Collect username.
- [x] Collect password.
- [x] Collect default currency.
- [x] Collect timezone.
- [ ] Optionally collect theme preference — deferred to Settings polish later in V1.
- [x] Create first user.
- [x] Save app settings.
- [x] Mark setup complete.

### Authentication tasks

- [x] Password hashing.
- [x] Login endpoint.
- [x] Logout endpoint.
- [x] Session token creation.
- [x] Session token expiry.
- [x] Auth dependency for protected routes.
- [x] Frontend login page.
- [x] Frontend session persistence.
- [x] Auto-redirect unauthenticated users to login.

### Completion criteria

- [x] Fresh install opens setup page.
- [x] Setup creates account and settings.
- [x] User can log in and out.
- [x] Protected pages require login.


### Phase 3 completion notes

- First-run setup creates the single owner account.
- Currency and timezone are selected from detected dropdown values and persisted in `app_settings`.
- Timezones display their current GMT offset.
- Passwords are hashed and sessions are stored as hashed bearer tokens with expiry.
- Protected frontend routes restore valid sessions and redirect unauthenticated users to login.
- A temporary development-only database reset tool is available from Settings while `PARTPILOT_ENABLE_DEBUG_RESET` is enabled.
- Theme selection remains deferred to later Settings polish and does not block Phase 3 completion.

---

## 5. Phase 4 — Part Types and Custom Fields

Goal: Build the system that makes Part Pilot electronics-aware.

### Built-in part types

Seed these V1 types:

- [x] Resistor
- [x] Potentiometer
- [x] Capacitor
- [x] Inductor
- [x] Diode
- [x] Zener Diode
- [x] Schottky Diode
- [x] LED
- [x] RGB LED
- [x] Optocoupler
- [x] NPN Transistor
- [x] PNP Transistor
- [x] MOSFET
- [x] Voltage Regulator
- [x] IC
- [x] Microcontroller
- [x] Relay
- [x] Motor
- [x] Servo Motor
- [x] Stepper Motor
- [x] Solenoid
- [x] Buzzer
- [x] Speaker
- [x] Push Button
- [x] Switch
- [x] Rotary Encoder
- [x] Connector
- [x] Pin Header
- [x] Terminal Block
- [x] Fuse
- [x] Mechanical Hardware

### Custom field types

Support:

- [x] Text
- [x] Number
- [x] Boolean yes/no
- [x] Dropdown
- [x] URL
- [x] Unit-aware value

### Part Manager page

- [x] List built-in and custom part types.
- [ ] Create custom type.
- [ ] Edit custom type.
- [ ] Edit built-in type template.
- [ ] Restore built-in templates to defaults.
- [ ] Add/remove/reorder fields.


### Phase 4 progress notes

- Read-only authenticated API now exposes every seeded part type and ordered template field.
- Part Manager now lists, searches, filters, and inspects built-in/custom type templates.
- Creation, editing, restoration, and field reordering remain for the next Phase 4 batches.

### Completion criteria

- [ ] User can create/edit a part type.
- [ ] Add Part flow can render fields based on selected type.

---

## 6. Phase 5 — Add Part Flow

Goal: Create the first real inventory entry.

### UI flow

- [ ] Step 1: Choose part type.
- [ ] Step 2: Enter part number/name.
- [ ] Step 3: Button to copy part number to name or name to part number.
- [ ] Step 4: Fill type-specific fields.
- [ ] Step 5: Enter quantity.
- [ ] Step 6: Enter location or choose from autocomplete.
- [ ] Step 7: Enter price details.
- [ ] Step 8: Add tags.
- [ ] Step 9: Add aliases.
- [ ] Step 10: Add notes.
- [ ] Step 11: Save part.

### Price fields

- [ ] Unit price.
- [ ] Total purchase price.
- [ ] Quantity purchased.
- [ ] Purchase link.
- [ ] Purchase date.
- [ ] Price warning if missing, toggleable in settings.

### Location behavior

- [x] Location is optional.
- [ ] New typed location is saved as reusable location.
- [ ] Existing locations appear in dropdown/autocomplete.

### Backend behavior

- [ ] Create part record.
- [ ] Create initial stock movement.
- [ ] Create audit log event.
- [ ] Save price snapshot for initial stock addition.
- [ ] Block duplicate part number.
- [ ] If duplicate part number exists, redirect user to Add Stock flow for existing part.

### Completion criteria

- [ ] User can add IRFZ44N with quantity/location.
- [ ] Part appears in inventory.
- [ ] Initial stock addition appears in history.

---

## 7. Phase 6 — Inventory View and Component Detail Page

Goal: Let users browse and inspect stock.

### Inventory desktop view

- [ ] Table layout.
- [ ] Columns: part number/display title.
- [ ] Name.
- [ ] Type.
- [ ] Available.
- [ ] Reserved.
- [ ] Total/on hand.
- [ ] Location.
- [ ] Unit price.
- [ ] Total value.
- [ ] Tags.
- [ ] Actions.

### Mobile view

- [ ] Card layout.
- [ ] Show part number/name.
- [ ] Available quantity.
- [ ] Reserved quantity.
- [ ] Location.
- [ ] Low-stock/out-of-stock warning.
- [ ] Expandable area for type, price, tags, package, notes, custom fields.

### Component detail page

Always visible:

- [ ] Display title.
- [ ] Name/description.
- [ ] Type/subtype.
- [ ] Available quantity.
- [ ] Reserved quantity.
- [ ] Total quantity.
- [ ] Location.
- [ ] Unit price.
- [ ] Total value.
- [ ] Tags.
- [ ] Primary actions.

Expandable sections:

- [ ] Custom fields.
- [ ] Aliases.
- [ ] Notes.
- [ ] Purchase info.
- [ ] History.
- [ ] Reservations using this part.
- [ ] Stock movements.
- [ ] Danger zone.

### Completion criteria

- [ ] User can view inventory on desktop and mobile.
- [ ] User can open part details.
- [ ] User can see available/reserved/total quantities.

---

## 8. Phase 7 — Add Stock / Restocking Flow

Goal: Restock existing parts and optionally create missing parts during the same flow.

### Add Stock behavior

- [ ] User opens Add Stock.
- [ ] User searches/selects existing part.
- [ ] User enters quantity added.
- [ ] User enters unit price.
- [ ] User may enter total purchase price and quantity purchased.
- [ ] User may enter purchase link/date.
- [ ] User saves restock event.

### Create part inside restocking

- [ ] If part does not exist, user can click Create Part.
- [ ] Current restocking workflow pauses.
- [ ] User creates new part.
- [ ] Created part returns into restocking session.
- [ ] Audit logs record new part creation separately.
- [ ] Stock movement records initial/add stock correctly.

### Audit behavior

Existing part:

- [ ] `stock_added` movement.
- [ ] `part_restocked` audit event.

New part through restock flow:

- [ ] `part_created` audit event.
- [ ] `stock_added` movement.
- [ ] `initial_stock_added` or equivalent audit event.

### Completion criteria

- [ ] User can restock existing part.
- [ ] User can create missing part from Add Stock flow.
- [ ] Quantity and value update correctly.

---

## 9. Phase 8 — Search

Goal: Make search the main interaction of Part Pilot.

### Search targets

Search should cover:

- [ ] Part number.
- [ ] Name.
- [ ] Aliases.
- [ ] Description.
- [ ] Component type.
- [ ] Subtype.
- [ ] Tags.
- [ ] Location.
- [ ] Notes.
- [ ] Custom fields.

### Search UI

- [ ] Large dashboard search bar.
- [ ] Search opens modal/dialog.
- [ ] Show in-stock matches first.
- [ ] Show out-of-stock matches in separate section.
- [ ] If no active matches, show clear “No in-stock results found”.
- [ ] Then show “Out of Stock” section if matches exist.
- [ ] Search behavior configurable in settings.

### Search behavior settings

- [ ] Show out-of-stock section enabled/disabled.
- [ ] Possibly include out-of-stock in normal results later.

### Search engine

- [ ] Start with SQLite text search.
- [ ] Add SQLite FTS if needed.
- [ ] Add fuzzy typo-tolerant search later if necessary.

### Completion criteria

- [ ] Searching `IRFZ44N` finds the part.
- [ ] Searching partial text finds parts.
- [ ] Searching location/tags/custom fields works.
- [ ] Out-of-stock results are separated and clearly marked.

---

## 10. Phase 9 — Projects

Goal: Add lightweight project containers for planned inventory usage.

### Project fields

- [ ] Name.
- [ ] Optional description.
- [ ] Status.
- [ ] Created timestamp.
- [ ] Updated timestamp.
- [ ] Estimated total cost.

### Project statuses

- [ ] Draft.
- [ ] Reserved.
- [ ] Consumed.
- [ ] Cancelled.

### Project behavior

- [ ] Project starts as Draft.
- [ ] User adds parts and quantities.
- [ ] User chooses Reserve or Consume.
- [ ] Project cannot mix reserved and consumed items at the same time in V1.
- [ ] Reserved project can later be converted to consumed.
- [ ] Cancelled reserved project releases reservation.

### Project cost

- [ ] Cost uses historical price snapshot.
- [ ] Project cost should not change if component price is edited later.

### Completion criteria

- [ ] User can create Drone Project.
- [ ] User can add parts to project.
- [ ] User can reserve or consume the project.
- [ ] Project cost is calculated.

---

## 11. Phase 10 — Reservations

Goal: Make reserved stock visible and controllable.

### Reservation fields

- [ ] Project/name label.
- [ ] Notes.
- [ ] Expiry date.
- [ ] Created by manual/AI.
- [ ] Status.
- [ ] Estimated reserved value.

### Reservation statuses

- [ ] Active.
- [ ] Consumed.
- [ ] Cancelled.
- [ ] Expired.

### Reservation behavior

- [ ] Available quantity reduces immediately when reserved.
- [ ] Reserved quantity increases immediately.
- [ ] Reservation cannot exceed available quantity.
- [ ] Expiration configurable.
- [ ] No expiration option supported.
- [ ] Custom expiration supported.

### Reservations page

Show:

- [ ] Active reservations.
- [ ] Expired reservations.
- [ ] Cancelled reservations.
- [ ] Consumed reservations.
- [ ] Linked project.
- [ ] Parts and quantities.
- [ ] Created by manual/AI.
- [ ] Expiry date.
- [ ] Estimated value.

Actions:

- [ ] Consume reservation.
- [ ] Cancel reservation.
- [ ] Extend expiry.
- [ ] Open linked project.

### Completion criteria

- [ ] Reserving 2 IRFZ44N reduces available quantity.
- [ ] Reservation appears on Reservations page.
- [ ] Reservation can be consumed or cancelled.

---

## 12. Phase 11 — Consumption Flow

Goal: Remove available stock in a controlled, auditable way.

### Consumption behavior

- [ ] Allow multiple parts at once.
- [ ] Optional project name.
- [ ] Optional reason/note.
- [ ] Block consumption if available quantity is insufficient.
- [ ] Show warning with available/requested quantities.
- [ ] Record price snapshot for project cost/history.

### Consumption UI

- [ ] Create consumption button.
- [ ] Search/add multiple parts.
- [ ] Show available quantity per selected part.
- [ ] Show estimated cost.
- [ ] Confirm consumption.

### Completion criteria

- [ ] User can consume 1 IRFZ44N.
- [ ] Available quantity updates.
- [ ] History records consumption.

---

## 13. Phase 12 — Low Stock and Out-of-Stock Handling

Goal: Make stock status obvious without deleting part data.

### Low stock

- [ ] Per-component low stock threshold.
- [ ] Low stock enabled/disabled per component.
- [ ] Dashboard low stock cards.
- [ ] Inventory warning badges.

### Out of stock

- [ ] Quantity 0 does not delete part.
- [ ] Part remains restockable.
- [ ] Out-of-stock parts de-prioritized in search.
- [ ] Out-of-stock section in search dialog.
- [ ] Out-of-stock display toggle in settings.

### Completion criteria

- [ ] Component with available 0 is marked out of stock.
- [ ] It can be restocked later.
- [ ] It is not treated as deleted.

---

## 14. Phase 13 — History and Audit System

Goal: Preserve all meaningful actions forever.

### Events to log

- [ ] Setup completed.
- [ ] Login/logout if desired.
- [ ] Part created.
- [ ] Part edited.
- [ ] Part renamed.
- [ ] Part deleted.
- [ ] Location changed.
- [ ] Notes changed.
- [ ] Tags changed.
- [ ] Alias changed.
- [ ] Stock added.
- [ ] Stock consumed.
- [ ] Reservation created.
- [ ] Reservation cancelled.
- [ ] Reservation expired.
- [ ] Reservation consumed.
- [ ] Project created.
- [ ] Project edited.
- [ ] Project reserved.
- [ ] Project consumed.
- [ ] Project cancelled.
- [ ] Settings changed.
- [ ] Backup created.
- [ ] Backup restored.
- [ ] MCP token generated/rotated.
- [ ] MCP action performed.

### History UI

- [ ] All activity.
- [ ] Stock activity.
- [ ] Reservation activity.
- [ ] Project activity.
- [ ] Edit activity.
- [ ] Settings/security activity.

### Completion criteria

- [ ] User can inspect what happened to a part.
- [ ] User can inspect system-wide activity.
- [ ] Deleted parts still have audit snapshots.

---

## 15. Phase 14 — Settings

Goal: Make the app configurable without cluttering main workflows.

### Settings pages

- [ ] Account.
- [ ] Appearance.
- [ ] Currency/timezone.
- [ ] Backups.
- [ ] Search behavior.
- [ ] Price warnings.
- [ ] MCP access.
- [ ] Advanced/danger zone.

### Specific settings

- [ ] Theme: dark/light.
- [ ] Currency selected during setup.
- [ ] Timezone selected during setup.
- [ ] Out-of-stock search section toggle.
- [ ] Missing price warning toggle.
- [ ] Reservation expiration default.
- [ ] Backup frequency.
- [ ] Backup location.
- [ ] Backup retention.
- [ ] MCP enabled.
- [ ] MCP write tools enabled.
- [ ] MCP API token rotate/copy.

### Completion criteria

- [ ] User can configure core behavior.
- [ ] Dangerous actions are clearly separated.

---

## 16. Phase 15 — Backups and Restore

Goal: Make self-hosted migration safe and simple.

### Backup behavior

- [ ] Default backup location: `/data/backups`.
- [ ] Configurable backup path later.
- [ ] Daily backups on by default.
- [ ] User can turn backups off.
- [ ] User can change backup frequency.
- [ ] User can trigger manual backup.
- [ ] User can restore from backup.

### Backup contents

- [ ] SQLite database.
- [ ] Uploaded files folder, even though uploads are not V1-heavy.
- [ ] Config/settings.
- [ ] MCP configuration.
- [ ] Audit/history data.
- [ ] Metadata file.

### Backup format

- [ ] Zip archive.
- [ ] Filename format: `partpilot-backup-YYYY-MM-DD-HHMM.zip`.

### Completion criteria

- [ ] User can create backup.
- [ ] User can restore backup.
- [ ] Fresh instance can be cloned from backup.

---

## 17. Phase 16 — MCP Integration

Goal: Let AI assistants use inventory safely.

### MCP security

- [ ] MCP protected by API token.
- [ ] MCP can be disabled.
- [ ] MCP read tools enabled by default or after user setup.
- [ ] MCP write tools disabled by default.
- [ ] MCP token can be generated and rotated.

### MCP read tools

- [ ] Search parts.
- [ ] Get part details.
- [ ] List low-stock parts.
- [ ] List projects.
- [ ] Get project.
- [ ] List reservations.

### MCP write tools

Only when enabled:

- [ ] Create reservation.
- [ ] Consume parts.
- [ ] Convert reserved project to consumed.
- [ ] Cancel reservation.

### MCP disallowed actions in V1

- [ ] Add new parts.
- [ ] Edit parts.
- [ ] Delete parts.
- [ ] Edit settings.

### Confirmation model

- [ ] AI chat confirmation is enough.
- [ ] No separate web-app confirmation needed for MCP reserve/consume.
- [ ] MCP actions must still be logged.

### Completion criteria

- [ ] AI can search Part Pilot inventory.
- [ ] AI can reserve parts when enabled.
- [ ] AI can consume parts when enabled.
- [ ] All MCP actions appear in audit history.

---

## 18. Phase 17 — Dashboard Polish

Goal: Make Part Pilot feel premium and useful.

### Dashboard widgets

- [ ] Large universal search.
- [ ] Add Part card.
- [ ] Add Stock card.
- [ ] Create Project card.
- [ ] Reserve/Consume card.
- [ ] Inventory value card.
- [ ] Reserved value card.
- [ ] Low stock card.
- [ ] Recent activity card.

### Design polish

- [ ] Premium dark theme.
- [ ] Light theme.
- [ ] Smooth card hover states.
- [ ] Rounded cards.
- [ ] Clean table spacing.
- [ ] Subtle shadows/glow.
- [ ] Not too cyberpunk.
- [ ] Apple-like polish while still clearly an inventory tool.

### Completion criteria

- [ ] Dashboard feels like a product, not a plain admin panel.
- [ ] Most common actions are obvious.

---

## 19. Phase 18 — Testing and Reliability

Goal: Avoid corrupting inventory quantities.

### Backend tests

- [ ] Add part validation.
- [ ] Duplicate part number validation.
- [ ] Quantity calculations.
- [ ] Reservation available-stock checks.
- [ ] Consumption available-stock checks.
- [ ] Project reserve/consume conversion.
- [ ] Audit log creation.
- [ ] Backup creation.
- [ ] Restore behavior.
- [ ] Auth/session behavior.

### Frontend checks

- [ ] Add Part form validation.
- [ ] Add Stock flow.
- [ ] Search dialog behavior.
- [ ] Mobile inventory cards.
- [ ] Project flow.
- [ ] Reservations flow.
- [ ] Settings toggles.

### Completion criteria

- [ ] Core inventory loop is reliable.
- [ ] No negative available quantities.
- [ ] No silent stock mutation without history.

---

## 20. Phase 19 — First Public Alpha

Goal: Make it usable by the creator and maybe a few testers.

### Alpha requirements

- [ ] Docker Compose install works.
- [ ] README explains setup.
- [ ] First-run setup works.
- [ ] Add/search/reserve/consume/history works.
- [ ] Backups work.
- [ ] MCP read tools work.
- [ ] MCP write tools are clearly marked experimental.

### Documentation

- [ ] README.
- [ ] Docker install guide.
- [ ] MCP setup guide.
- [ ] Backup/restore guide.
- [ ] Development setup guide.

---

## 21. Later Features — Not V1

These should remain out of V1 unless explicitly pulled back in.

- [ ] Broken/partial parts with per-item notes.
- [ ] Photos.
- [ ] Datasheet upload.
- [ ] Datasheet auto-fetch.
- [ ] CSV import/export.
- [ ] Excel import/export.
- [ ] DigiKey import.
- [ ] Mouser import.
- [ ] LCSC import.
- [ ] JLCPCB BOM import.
- [ ] KiCad BOM import.
- [ ] Multi-user accounts.
- [ ] Role permissions.
- [ ] Home Assistant add-on.
- [ ] Windows `.exe` desktop app.
- [ ] Linux one-click installer.
- [ ] PWA offline mode.
- [ ] QR/barcode labels.
- [ ] Supplier integrations.
- [ ] Automatic exchange-rate conversion.
- [ ] PostgreSQL support.
- [ ] Full project management system.
- [ ] Tools/consumables tracking.
- [ ] 3D printed part tracking.

---

## 22. Recommended Build Order Summary

1. Repository skeleton.
2. Backend health route.
3. Frontend shell.
4. SQLite + migrations.
5. First-run setup/auth.
6. Built-in part types/custom fields.
7. Add Part flow.
8. Inventory view/detail page.
9. Add Stock flow.
10. Search.
11. Projects.
12. Reservations.
13. Consumption.
14. Low stock/out-of-stock behavior.
15. History/audit.
16. Settings.
17. Backups.
18. MCP.
19. Dashboard and UI polish.
20. Tests.
21. Alpha docs.

---

## 23. First Coding Sprint

The first coding sprint should target only:

- [ ] Backend FastAPI app.
- [ ] SQLite setup.
- [ ] Basic parts table.
- [ ] Basic part creation API.
- [ ] Basic stock movement API.
- [ ] Basic inventory list API.
- [ ] Simple React dashboard shell.
- [ ] Simple Add Part form.
- [ ] Simple Inventory list.

Do not implement:

- [ ] MCP.
- [ ] Backups.
- [ ] Complex UI polish.
- [ ] Projects.
- [ ] Reservations.
- [ ] Advanced templates.

Reason: prove the inventory foundation before adding complexity.

---

## 24. Files to Keep Updated

Always keep these project memory files updated:

- `Part Pilot_V1_Product_Specification.md`
- `Checkpoint.md`
- `Implementation_Roadmap.md`

When a decision changes, update all affected files.


### Phase 4 responsive shell checkpoint

- [x] Stabilize the shared desktop/mobile application shell before adding editor workflows.
- [x] Expand desktop page width.
- [x] Replace the squeezed mobile sidebar with a top bar and navigation drawer.
- [x] Reduce shared card, typography, and page spacing for information-dense mobile use.
- [ ] Continue with custom part type creation and template editing.


### Phase 4 custom part type creation checkpoint

- [x] Create custom part types.
- [x] Build custom template fields during creation.
- [x] Validate field keys and dropdown options.
- [x] Reorder fields before creation.
- [x] Show a live template preview.
- [ ] Edit existing custom part types.
- [ ] Delete custom part types with usage safeguards.


### Phase 4 custom part type editing checkpoint

- [x] Edit existing custom part types.
- [x] Preserve field IDs while editing and reordering.
- [x] Reuse the focused modal for create and edit workflows.
- [ ] Delete custom part types with usage safeguards.


### Phase 4 custom part type deletion checkpoint

- [x] Delete unused custom part types.
- [x] Protect built-in types from deletion.
- [x] Block deletion when inventory parts still use the type.
- [x] Require typed-name confirmation in the UI.
- [x] Record audit logs for successful deletion.


### Phase 4 inventory creation backend checkpoint

- [x] Create inventory parts from an active part type.
- [x] Persist typed template field values.
- [x] Validate required fields and template ownership.
- [x] Reject duplicate part numbers.
- [x] Read individual parts and filtered part collections.
- [ ] Add the dynamic Add Part modal to Part Manager.


### Phase 4 dynamic Add Part UI checkpoint

- [x] Add inventory parts from Part Manager.
- [x] Select a part type and render its dynamic fields.
- [x] Validate base and required template fields.
- [x] Preserve modal actions when the form overflows.
- [x] Submit to the authenticated inventory API.
- [ ] Add inventory browsing, searching, and part detail views.


### Phase 4 manufacturer catalogue checkpoint

- [x] Store manufacturers independently from part templates.
- [x] Reuse existing manufacturers across inventory records.
- [x] Create new manufacturers from the Add Part workflow.
- [x] Seed common electronics brands.
- [x] Backfill legacy manufacturer field values when possible.
- [x] Show manufacturer in the compact Part Added confirmation.
- [ ] Add manufacturer administration and merge tools.

<!-- PATCH 131 ROADMAP CHECKPOINT -->

---

## Current Roadmap Checkpoint — 2026-07-25

### Phase 4 inventory foundation completed

- [x] Inventory part creation.
- [x] Reusable manufacturer catalogue.
- [x] Inventory list and refresh.
- [x] Search by name, part number, type, and manufacturer.
- [x] In-stock, low-stock, and out-of-stock filtering.
- [x] Read-only part details.
- [x] Responsive details drawer/bottom sheet.
- [x] Clean numeric custom-field display.
- [x] Reusable package/form-factor catalogue.
- [x] Package migration and existing-value backfill.
- [x] Seeded and custom package selection in Add Part.
- [x] Consistent template-field row layout.

### Immediate next slice

- [ ] Diagnostic 132: inspect stock-movement and quantity-adjustment targets.
- [ ] Add stock.
- [ ] Remove stock.
- [ ] Consume stock.
- [ ] Correct stock with an explicit reason.
- [ ] Persist before/after quantities and audit context.
- [ ] Show recent movement history in part details.

### Following Phase 4 slices

- [ ] Metadata editing for existing parts.
- [ ] Soft deletion and restoration safeguards.
- [ ] Reusable location management.
- [ ] Low-stock dashboard and settings-driven out-of-stock grouping.
- [ ] Reservations.
- [ ] Projects.
- [ ] Reservation consumption and release.
- [ ] Full inventory/history pages.

### Later V1 phases

- [ ] Settings and appearance completion.
- [ ] Backup and restore workflows.
- [ ] MCP read tools.
- [ ] MCP write tools with confirmation safeguards.
- [ ] Final responsive, accessibility, and release polish.

The roadmap remains incremental: each implementation slice is browser-tested
before its checkpoint commit.

<!-- PATCH 140 STOCK MOVEMENT ROADMAP CHECKPOINT -->

---

## Current Roadmap Checkpoint — Stock Movement Complete

### Completed stock workflow

- [x] Diagnostic 132 mapped the stock-movement implementation targets.
- [x] Authenticated add-stock operation.
- [x] Authenticated remove-stock operation.
- [x] Authenticated consume-stock operation.
- [x] Signed quantity correction with explicit context.
- [x] Negative and reserved-stock safeguards.
- [x] Atomic part, stock movement, and audit writes.
- [x] Recent read-only movement history API.
- [x] Compact quantity action in part details.
- [x] Immediate selected-part and inventory-list refresh.
- [x] Responsive desktop drawer and mobile bottom-sheet support.
- [x] Manual browser verification completed.

### Immediate next slice

- [ ] Diagnostic 141: inspect existing-part metadata editing targets.
- [ ] Update base identification and descriptive fields.
- [ ] Update manufacturer and package selections safely.
- [ ] Update typed template-field values.
- [ ] Preserve duplicate part-number validation.
- [ ] Record before/after audit snapshots.
- [ ] Add a focused Edit details workflow.
- [ ] Browser-test before the next checkpoint commit.

### Following Phase 4 slices

- [ ] Soft deletion and restoration safeguards.
- [ ] Reusable location management.
- [ ] Low-stock dashboard and settings-driven out-of-stock grouping.
- [ ] Reservations.
- [ ] Projects.
- [ ] Reservation consumption and release.
- [ ] Full inventory/history pages.

The roadmap remains incremental: diagnostics are read-only, implementation
patches stay narrow, and each completed slice is browser-tested before its
checkpoint commit.

<!-- PATCH 149 PART METADATA EDIT ROADMAP CHECKPOINT -->

---

## Current Roadmap Checkpoint — Metadata Editing Complete

### Completed

- [x] Diagnostic 141 target inspection.
- [x] Authenticated base metadata update.
- [x] Manufacturer, package, and typed template-field update.
- [x] Fixed part type and excluded quantity fields.
- [x] Duplicate protection and atomic audit history.
- [x] Prefilled responsive Edit details workflow.
- [x] Correct drawer/editor transition.
- [x] Immediate detail and list refresh.
- [x] Decimal display normalisation.
- [x] Manual browser verification.

### Immediate next slice

- [ ] Diagnostic 150: inspect soft-delete and restoration targets.
- [ ] Authenticated soft deletion.
- [ ] Preserve part data, stock movements, and audit history.
- [ ] Safe restoration with duplicate/conflict handling.
- [ ] Focused delete confirmation.
- [ ] Recoverable deleted-parts restoration entry point.
- [ ] Browser-test before checkpoint commit.

### Following slices

- [ ] Reusable location management.
- [ ] Low-stock dashboard and out-of-stock grouping.
- [ ] Reservations and projects.
- [ ] Full inventory and history pages.

<!-- PATCH 154 PART SOFT DELETE RESTORE ROADMAP CHECKPOINT -->

---

## Current Roadmap Checkpoint — Part Lifecycle Recovery Complete

### Completed

- [x] Diagnostic 151 mapped deletion/restoration targets.
- [x] Authenticated soft deletion.
- [x] Authenticated restoration.
- [x] Dedicated deleted-parts collection.
- [x] Active reads continue hiding deleted records.
- [x] Quantity, field-value, and movement-history retention.
- [x] Part-number reservation while deleted.
- [x] Conflict handling for repeated transitions.
- [x] Complete lifecycle audit events.
- [x] Focused Delete confirmation UI.
- [x] Searchable Deleted items recovery UI.
- [x] Immediate active/deleted collection refresh.
- [x] Manual browser verification.

### Immediate next slice

- [ ] Diagnostic 155: inspect reusable location management targets.
- [ ] Add protected location catalogue API.
- [ ] Add safe create/edit/deactivate/delete semantics.
- [ ] Integrate location selection into part creation.
- [ ] Integrate location selection into part metadata editing.
- [ ] Add location filtering and details display.
- [ ] Browser-test before checkpoint commit.

### Following Phase 4 slices

- [ ] Low-stock dashboard and settings-driven out-of-stock grouping.
- [ ] Reservations.
- [ ] Projects.
- [ ] Reservation consumption and release.
- [ ] Full inventory and history pages.

<!-- PATCH 164 REUSABLE LOCATION ROADMAP CHECKPOINT -->

---

## Current Roadmap Checkpoint — Reusable Locations Integrated

### Overall V1 progress

**Estimated completion: 52%**

This estimate covers the complete V1 roadmap, including deferred projects,
reservations, settings, backups, MCP, dashboard, and release work.

### Completed in this checkpoint

- [x] Protected reusable location catalogue.
- [x] Normalised duplicate handling.
- [x] Safe in-use deletion conflicts.
- [x] Active/deleted part usage counts.
- [x] Location audit events.
- [x] Add Part location selection.
- [x] Inline location creation.
- [x] Edit details location prefill/change/clear.
- [x] Location response serialization.
- [x] Location audit retention through delete/restore.
- [x] Responsive location-control styling.
- [x] Correct mobile part-detail action footer.
- [x] Full automated and browser verification.

### Immediate next slice

- [ ] Read-only preflight for Stored Parts location targets.
- [ ] Add optional backend `location_id` list filtering.
- [ ] Add location to desktop inventory rows.
- [ ] Add location to responsive/mobile inventory cards.
- [ ] Add location to part details.
- [ ] Add reusable location filter UI.
- [ ] Browser-test and commit this slice independently.

### Following V1 work

- [ ] Low-stock dashboard and settings-driven out-of-stock grouping.
- [ ] Search completion.
- [ ] Reservations.
- [ ] Projects.
- [ ] Reservation consumption and release.
- [ ] History and audit browsing.
- [ ] Settings completion.
- [ ] Backups.
- [ ] MCP.
- [ ] Public-alpha readiness.

<!-- PATCH 173 STORED PARTS LOCATION FILTER ROADMAP CHECKPOINT -->

---
## Current Roadmap Checkpoint — Location-Aware Inventory Complete

### Overall V1 progress

**Estimated completion: 53%**

This estimate covers the entire V1 roadmap rather than only the current
inventory phase.

### Completed in this checkpoint

- [x] Read-only Stored Parts location target preflight.
- [x] Authenticated `location_id` collection filtering.
- [x] Correct filtered totals and pagination.
- [x] Combined part-type and location filtering.
- [x] Deleted-part exclusion and unassigned-part preservation.
- [x] Frontend location-filter client contract.
- [x] Reusable **All locations** selector.
- [x] Backend-driven location filtering in Stored Parts.
- [x] Location-name text search.
- [x] Location-aware result counts and empty states.
- [x] Location column in Stored Parts.
- [x] Location display in Part Details.
- [x] Desktop, tablet, and mobile toolbar support.
- [x] Complete smoke, deployment, bundle, route, and browser verification.

### Immediate next slice

- [ ] Diagnostic 174: inspect low-stock, dashboard, settings, and out-of-stock
      behaviour targets.
- [ ] Define one protected settings contract for the relevant behaviour.
- [ ] Add a trustworthy low-stock inventory summary.
- [ ] Implement the locked out-of-stock grouping/visibility behaviour.
- [ ] Preserve existing Stored Parts filters and location filtering.
- [ ] Add complete automated coverage.
- [ ] Browser-test before checkpointing.

### Following V1 work

- [ ] Universal search completion.
- [ ] Reservations.
- [ ] Projects.
- [ ] Reservation consumption and release.
- [ ] History and audit browsing.
- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools.
- [ ] MCP write tools with confirmation safeguards.
- [ ] Accessibility, responsive, security, and public-alpha polish.

The next slice should remain incremental. Diagnostic 174 is read-only, and
implementation should be divided into independently verifiable backend and
browser-tested frontend batches.

<!-- PARTPILOT:DASHBOARD_LOW_STOCK_ROADMAP:START -->
## Stock visibility milestone

| Item | Status |
| --- | --- |
| Protected low-stock summary API | Complete |
| Protected search-settings API | Complete |
| Dashboard low-stock summary UI | Complete |
| Zero-stock parts without configured thresholds | Complete |
| Settings control for out-of-stock grouping | Complete |
| Dedicated Stored Parts out-of-stock section | Complete |
| Explicit In stock, Low, and Out filters preserved | Complete |
| Search and location filtering across both result groups | Complete |
| Responsive width alignment and visual review | Complete |
| Complete smoke and deployed-asset verification | Complete |
| Browser approval | Complete |
| Commit and push | Complete through Patch 197 |

### Next planned step

Inspect the remaining Phase 4 roadmap and current repository state, then begin
the next smallest independently verifiable inventory workflow. Continue to
commit and push each approved batch promptly.
<!-- PARTPILOT:DASHBOARD_LOW_STOCK_ROADMAP:END -->

<!-- PARTPILOT:INVENTORY_PAGE_MODE_ROADMAP:START -->
## Focused Inventory page milestone

| Item | Status |
| --- | --- |
| Replace obsolete `/inventory` placeholder | Complete |
| Reuse the live Stored Parts workflow | Complete |
| Keep a single inventory implementation | Complete |
| Hide template management on `/inventory` | Complete |
| Preserve `/part-manager` template management | Complete |
| Inventory Add Part action | Complete |
| Search, locations, and stock filters | Complete |
| Settings-driven out-of-stock grouping | Complete |
| Details, quantity adjustment, editing, deletion, restoration | Complete |
| Automated verification | Complete |
| Desktop browser approval | Complete |
| Mobile functional approval | Complete |
| Mobile part-type status-pill polish | Complete through Patch 206 |
| Mobile visual browser approval | Complete |
| Commit and push | Complete through Patch 207 |

### Immediate next step

Inspect the current repository and the remaining Phase 4 roadmap, then select
the next smallest independently verifiable V1 workflow. Start with a
read-only diagnostic when exact implementation boundaries or source anchors
are not already established.

### Remaining major V1 areas

- Universal search completion.
- Reservations and reservation lifecycle.
- Projects and project-linked inventory.
- History and audit browsing.
- Settings and appearance completion.
- Backup and restore.
- MCP read tools.
- MCP write tools with confirmation safeguards.
- Accessibility, responsive, security, and public-alpha polish.
<!-- PARTPILOT:INVENTORY_PAGE_MODE_ROADMAP:END -->

<!-- PARTPILOT:UNIVERSAL_SEARCH_BACKEND_ROADMAP:START -->
## Universal search implementation status

| Work item | Status |
| --- | --- |
| Read-only architecture diagnostic | Complete through Diagnostic 209 |
| Protected backend query parameter | Complete through Patch 213 |
| Metadata search | Complete |
| Part type, manufacturer, and location search | Complete |
| Alias and tag search | Complete |
| Typed custom-field search | Complete |
| Stable numeric custom-field verification | Complete through Patch 215 |
| Literal wildcard handling | Complete |
| Filter and pagination composition | Complete |
| Deleted-part exclusion | Complete |
| Duplicate suppression | Complete |
| Available-before-out-of-stock ordering | Complete |
| Collision-safe smoke coverage | Complete |
| Backend checkpoint commit and push | Complete through Patch 216 |
| Typed frontend search client | Next |
| Dashboard search input and dialog | Pending |
| Available/out-of-stock result sections | Pending |
| Part-details integration | Pending |
| Mobile and keyboard browser approval | Pending |
| Stored Parts server-search migration | Pending separate batch |

### Immediate next step

Create the next sequential browser-test implementation for the frontend
universal-search client and Dashboard experience. Reuse the backend
`GET /api/parts?search=...` contract and existing part-details presentation.
Preserve settings-driven out-of-stock visibility, accessibility, responsive
behaviour, loading, error, empty, available, and out-of-stock states.

Avoid combining the Stored Parts migration into the same patch unless a fresh
read-only preflight proves that the resulting browser-test scope remains
small and independently reviewable.
<!-- PARTPILOT:UNIVERSAL_SEARCH_BACKEND_ROADMAP:END -->

<!-- PARTPILOT:DASHBOARD_UNIVERSAL_SEARCH_ROADMAP:START -->
## Universal search status after Dashboard delivery

| Work item | Status |
| --- | --- |
| Backend universal-search contract | Complete |
| Backend field coverage and ranking | Complete |
| Collision-safe smoke coverage | Complete |
| Typed frontend search client | Complete |
| Dashboard search launcher and modal | Complete |
| Debounced live search | Complete |
| Stale-response protection | Complete |
| Available / Out of stock result groups | Complete |
| Settings-driven hidden results | Complete |
| Empty-section suppression | Complete |
| Selected-result details | Complete |
| Keyboard interaction | Complete |
| Mobile Dashboard search | Complete |
| Mobile Dashboard summary cards | Complete |
| Mobile low-stock presentation | Complete |
| Browser approval | Complete |
| Frontend checkpoint commit and push | Complete through Patch 224 |
| Stored Parts server-search migration | Next |
| Search-result direct part-detail route | Future refinement |
| Search pagination / incremental loading | Future refinement |

### Immediate next step

Create Patch 225 as a read-only preflight or a small browser-test
implementation for migrating Stored Parts search from client-side filtering to
`GET /api/parts?search=...`.

Preserve:

- current type and location filters;
- accurate backend totals and pagination;
- available-before-out-of-stock ordering;
- the configured out-of-stock visibility behaviour;
- mobile Inventory layout;
- existing part selection and editing flows.
<!-- PARTPILOT:DASHBOARD_UNIVERSAL_SEARCH_ROADMAP:END -->

<!-- PARTPILOT:CHAT10_STORED_PARTS_SEARCH_ROADMAP:START -->
## Chat 10 — Stored Parts server-search migration

Required title: `Chat 10: Stored Parts Server Search Migration`

Starting operation: Patch 226

Immediate boundary: move Stored Parts search from filtering only the currently loaded frontend page to the backend universal-search contract.

Preserve:
- part-type and location filters;
- accurate backend totals and pagination;
- available-before-out-of-stock ordering;
- configured out-of-stock visibility;
- responsive Inventory layout;
- selection, details, quantity, movement, edit, delete, and restore flows;
- Part Manager management mode.

Patch 250 is the mandatory final Python file of Chat 10 and must create the Chat 11 handoff and starting prompt.
<!-- PARTPILOT:CHAT10_STORED_PARTS_SEARCH_ROADMAP:END -->

<!-- PARTPILOT:STORED_PARTS_SERVER_STOCK_FILTER:V231 -->
### Stored Parts server-search migration — backend prerequisite complete

**Completed in Patch 229 and checkpointed by Patch 230**

- Added protected server-side stock modes: `all`, `in`, `low`, and `out`.
- Preserved accurate backend totals and pagination after stock filtering.
- Composed stock mode with universal search, part-type and location filters.
- Preserved available-before-out-of-stock ordering.
- Added inventory-safe API smoke coverage and invalid-mode validation.

**Next**

Migrate the frontend Stored Parts request flow away from `limit: 250`,
`offset: 0` and client-side query/stock filtering. Add bounded pagination,
part-type filtering, 280 ms search debounce, stale-response protection and
settings-aware out-of-stock behaviour without disrupting selection, details,
quantity adjustments, movements, editing, delete/restore, mobile Inventory or
Part Manager management mode.

<!-- PARTPILOT:STORED_PARTS_SERVER_SEARCH_FRONTEND:V234 -->
### Stored Parts server-search migration — request migration approved

**Completed in Patch 233 and checkpointed by Patch 234**

- Added the typed `PartStockStatus` client contract.
- Sent debounced universal-search and stock-status values to `GET /api/parts`.
- Added explicit stale-response request sequencing.
- Removed client-side query matching over the currently loaded page.
- Preserved Available / Out of stock grouping and out-of-stock settings.
- Corrected server-search empty states.
- Browser-approved desktop, mobile Inventory, Part Manager and existing part
  workflows.

**Next**

Replace `limit: 250` and `offset: 0` with bounded page state and controls, add
the dedicated part-type selector, reset pagination when filters change, and use
backend totals for page information. Keep browser-test changes uncommitted
until explicit approval.

## Chat 11 - Stored Parts Search Finalization

<!-- PARTPILOT:CHAT10_BOUNDARY:V250 -->
<!-- PARTPILOT:CHAT10_BOUNDARY_RECOVERY:V253 -->

Start with Patch 254.

1. Apply the dashboard-search-like red theme to the complete Stored Parts
   out-of-stock card.
2. Correct the Patch 249 validator so `box-shadow: none !important;` is allowed.
3. Build, deploy, run the complete smoke suite, and obtain browser approval.
4. Remove only the manifest-owned Patch 241 fixtures after approval.
5. Verify all real inventory remains unchanged.
6. Update durable memory and commit/push the approved frontend batch.
7. Continue remaining finalization work as needed.
8. Finish Chat 11 with mandatory boundary Patch 275.

<!-- PARTPILOT:CHAT12_RESERVATIONS_FOUNDATION:V293 -->
## Chat 11 completion — Stored Parts Search Finalization

Chat 11 is complete after boundary recovery through Patch 293.

Completed:

- backend universal Stored Parts search;
- stock-status, part-type and location filter composition;
- accurate server totals and pagination;
- 25/50/100 page-size preference;
- stale-response guards;
- Available-first presentation;
- separate teal Available and red Out of stock cards;
- full-result independent section sorting for Part, Type, Manufacturer,
  Location, Available, Total and Status;
- responsive desktop and mobile presentation;
- browser approval;
- source commit and push;
- removal of exactly 70 PP241 fixture parts and exactly 70 matching creation
  audits with real inventory preserved.

## Chat 12 — Reservations Foundation

Required title: `Chat 12: Reservations Foundation`

Patch range: 294 through 323.

Start with **Patch 294 as a read-only diagnostic**. Inspect the exact local
repository and runtime before implementation:

1. existing `projects`, `project_items`, `reservations` and
   `reservation_items` models and migration constraints;
2. current available/reserved/total quantity semantics;
3. stock movement and audit service patterns;
4. protected API, schema, service and smoke-test conventions;
5. the `/reservations` placeholder route and responsive shell;
6. current inventory selection/search components that may be reused;
7. inventory-safe fixture strategy for reservation tests;
8. cancellation, consumption, expiry and project-linking boundaries.

Initial implementation goal:

- establish a protected reservation service and API contract;
- prevent reservations from exceeding available stock;
- expose list/detail creation and cancellation in narrow verified slices;
- update available quantity consistently;
- create structured audit and history records;
- add a responsive Reservations workspace only after the backend contract is
  independently verified.

Keep Projects as a separate implementation boundary until the reservation
lifecycle and quantity semantics are approved. Do not combine this chat with
backups, MCP, settings appearance or a full history-page implementation.

### HomeLab inspection policy

The HomeLab Terminal tool may be used only for read-only repository and runtime
inspection. It must never run commands that mutate files, Git, databases,
containers, deployment, fixtures or inventory. All changes must remain
downloadable numbered Python patch files run explicitly by the user.

### Boundary

Patch 323 is the planned final boundary patch for Chat 12. Failed scripts
consume their patch numbers. If boundary recovery is required, keep Chat 12
active until a recovery script ends with exactly `Everything PASS`.


<!-- PARTPILOT:RESERVATIONS_BACKEND_ROADMAP:V310 -->
## Reservations implementation status after cancellation delivery

| Work item | Status |
| --- | --- |
| Reservation architecture diagnostic | Complete through Patch 294 |
| Canonical schema and lifecycle contract | Complete through Patch 298 |
| Atomic reservation creation service | Complete through Patch 301 |
| Protected list, detail and create APIs | Complete through Patch 303 |
| Active-to-cancelled lifecycle | Complete through Patch 306 |
| Cancellation checkpoint commit and push | Complete through Patch 308 |
| Durable checkpoint and roadmap update | Complete through Patch 310 |
| Guarded reserved-stock release | Complete |
| Reserve and release movement snapshots | Complete |
| Creation and cancellation audit events | Complete |
| Authentication and HTTP error mapping | Complete |
| Inventory-safe backend smoke coverage | Complete |
| Active-reservation consumption | Next |
| Explicit expiry processing | Pending |
| Responsive Reservations workspace | Pending after backend lifecycle |
| Projects and project-linked reservations | Deferred separate boundary |

### Immediate next step

Implement reservation consumption as the next independently verifiable backend
slice.

Required behaviour:

- only an `active` reservation may be consumed;
- every reservation item is processed in one atomic transaction;
- physical `total_quantity` decreases by the consumed quantity;
- `reserved_quantity` decreases by the same quantity;
- available quantity remains mathematically consistent;
- one `consume` movement per item records physical, reserved and available
  before/after snapshots;
- the reservation status changes to `consumed` only after all guarded stock
  updates succeed;
- one structured `reservation.consumed` audit event records actor and item
  details;
- missing reservations return 404;
- cancelled, consumed and expired reservations return 409;
- any stale or inconsistent stock state rolls back every stock, movement,
  status and audit change;
- tests use unique fixture IDs and remove only fixture-owned rows;
- real inventory and existing history remain unchanged.

After consumption passes and is checkpointed, implement explicit expiry as a
separate release-style lifecycle operation. Build the Reservations frontend only
after creation, cancellation, consumption and expiry contracts are independently
verified. Projects remain out of scope until that lifecycle is stable.

### Current execution workflow

The HomeLab Terminal tool is read-only only. Every mutation, implementation,
fix, diagnostic, documentation update, checkpoint, commit and push must be
delivered as one complete downloadable sequential Python patch.

Only one new patch may be issued at a time. The user runs it and reports the
result before the next patch number is generated. Failed user-run scripts
consume their number unless the user explicitly resets the accepted sequence.

<!-- PARTPILOT:RESERVATIONS_FOUNDATION_ROADMAP:START -->
## Reservations phase status

### Completed in Chat 12

- Migration and backend reservation contract.
- Create, read, cancel, consume and due-expiry services/APIs.
- Inventory-safe movements and audit records.
- Existing-data-safe smoke coverage.
- Browser-approved responsive Reservations workspace.
- Part-picker vertical alignment.
- Boundary checkpoint and durable handoff.

### Next phase

`Chat 13: Reservation Workflow Finalization` owns Patch 336–365.

Recommended focus:

1. Review project/reservation linkage and history presentation.
2. Finalise action feedback, accessibility and edge-case UX.
3. Use isolated manifest-owned fixtures only.
4. Split unrelated work into separate patches after repeated failures.
<!-- PARTPILOT:RESERVATIONS_FOUNDATION_ROADMAP:END -->

<!-- PARTPILOT:RESERVATION_ACTIVITY_ROADMAP:V344:START -->
## Current roadmap checkpoint — Reservation activity finalized

### Overall V1 progress

**Estimated completion: 68%**

This estimate covers the complete polished V1/public-alpha target rather than
stale historical checkbox counts. The core inventory/search product is
approximately 82% complete.

### Completed through Patch 344

- [x] Inventory creation, browsing, editing, stock movement and recovery.
- [x] Reusable manufacturer, package and location catalogues.
- [x] Dashboard and Stored Parts universal search, filters and sorting.
- [x] Settings-driven low-stock and out-of-stock visibility.
- [x] Reservation create, list, detail, cancel, consume and expiry lifecycles.
- [x] Reservation activity API and responsive activity timeline.
- [x] Desktop register hierarchy and mobile reservation cards.
- [x] Mobile register landing without automatic detail opening.
- [x] Existing-data-safe smoke coverage and browser approval.

### Immediate next slice

- [ ] Define active-reservation update semantics.
- [ ] Support label, notes and expiry editing.
- [ ] Implement guarded item add/remove/quantity changes.
- [ ] Record movement and audit/activity entries for stock-affecting edits.
- [ ] Add accessible Edit reservation UI after backend verification.
- [ ] Browser-test and checkpoint independently.

### Remaining major V1 areas

- [ ] Reservation defaults, expiry settings and remaining action feedback.
- [ ] Lightweight Projects and project-linked reservations.
- [ ] System-wide History and audit browsing.
- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Accessibility, security and public-alpha release hardening.
<!-- PARTPILOT:RESERVATION_ACTIVITY_ROADMAP:V344:END -->

<!-- PARTPILOT:CHAT13_RESERVATION_FINALIZATION_ROADMAP:V365 -->
## Current roadmap checkpoint — Reservation workflow finalized

### Overall progress

**Working V1/public-alpha estimate: approximately 74%.**

The core inventory, search and reservation workflows are now mature. Remaining
work is concentrated in Projects, system-wide History, broader Settings and
appearance, backup/restore, MCP and release hardening.

### Completed through Patch 365

- [x] Reservation activity API and responsive timeline.
- [x] Desktop register hierarchy and mobile register-first workflow.
- [x] Atomic active-reservation editing with reserve/release reconciliation.
- [x] No-op edit suppression and date/time control refinement.
- [x] Exact-confirmation deletion for inactive reservations.
- [x] Inventory-safe deletion history and movement retention.
- [x] Authenticated atomic reservation-default settings API.
- [x] Reservation-default Settings card and new-form expiry prefill.
- [x] Existing/Edit reservation isolation from installation defaults.
- [x] Persistent inventory and Part Manager view preferences.
- [x] Explicit `fixes/logs/` ignore rule and tracked-log cleanup.
- [x] Complete smoke, protected API, SPA, browser and live-data preservation.

### Chat 14 — Projects Foundation

Required title: `Chat 14: Projects Foundation`
Patch range: 366–395
Planned boundary: Patch 395

#### Patch 366 — diagnostic-only

Inspect and document the exact local contract before implementation:

1. `Project` and `ProjectItem` model fields, constraints, indexes and migration
   history.
2. The mismatch between the model statuses
   `draft/reserved/consumed/cancelled` and constants
   `draft/active/completed/archived`.
3. Existing live project/project-item counts and foreign-key behavior.
4. Reservation `project_id` serialization versus absent create/update linkage.
5. Stock movement, reservation lifecycle and audit conventions that Projects
   must reuse rather than duplicate.
6. Protected route/schema/service/smoke-test conventions.
7. The `/projects` placeholder and reusable Reservations/Inventory UI patterns.
8. Price/currency snapshot semantics and deleted-part behavior.
9. An inventory-safe fixture and cleanup plan that never assumes empty tables.
10. Whether a migration is required before any Projects API is added.

The diagnostic report must use the exact `docs/diagonostic_*.md` naming rule and
be inspected before implementation begins.

#### Recommended implementation order

1. Resolve canonical statuses and migration requirements.
2. Add typed project read/create/update contracts and atomic service behavior.
3. Add authenticated list/detail/create APIs with pagination and validation.
4. Add project-item reconciliation and price/currency snapshots.
5. Define reserve, consume and cancel transitions by reusing reservation and
   stock-movement invariants; never create a competing stock model.
6. Link project reservations explicitly only after both contracts are stable.
7. Build a responsive Projects register/detail/create/edit UI after backend
   smoke coverage passes.
8. Browser-test, checkpoint approved source, update README/docs, then complete
   the Patch 395 boundary.

#### Scope limits

Keep system-wide History, backup/restore, appearance and MCP outside the initial
Projects foundation. Do not silently alter the existing Weather Station
reservation, reservation defaults, inventory quantities or unrelated audits.

### Mandatory execution method for Chat 14

Use the HomeLab-assisted method established in Chat 13: exact read-only local
inspection, `/tmp` target generation, deterministic hash comparison, isolated
clean builds and copied-database smoke tests before packaging, exact-byte patch
payloads, `[X/N]` runtime phases, full rollback, and separate browser approval /
checkpoint scripts. Do not return to speculative source anchors or scripts that
have not been executed against an isolated copy first.

<!-- PARTPILOT:PROJECTS_FOUNDATION_ROADMAP:V390 -->
## Current roadmap checkpoint — Projects foundation operational

### Overall progress

**Working V1/public-alpha estimate: approximately 80%.**

Inventory, universal search, Reservations and the first complete Projects
planning-to-reservation workflow are operational and browser approved.
Remaining work is concentrated in Project completion/cancellation, system-wide
History, broader Settings and appearance, backup/restore, MCP, accessibility,
security and public-alpha hardening.

### Completed through Patch 386

- [x] Canonical Project lifecycle schema and migration.
- [x] Protected Project list, detail, create and Draft-update APIs.
- [x] Project item reconciliation and price/currency snapshots.
- [x] Responsive Projects register/detail/create/edit workspace.
- [x] Atomic Draft Project reservation through a linked active Reservation.
- [x] Reserve stock movements, Project/Reservation audits and inventory guards.
- [x] Multi-result Project and Reservation part pickers with up to 50 matches.
- [x] Project-derived Reservations product model.
- [x] Manual Reservation creation removed from the frontend.
- [x] Existing Reservation edit/cancel/consume/expire/delete/activity retained.
- [x] Complete smoke, protected API, SPA, browser and live-data preservation.

### Immediate next slice

- [ ] Add atomic Reserved Project consumption using the linked Reservation.
- [ ] Add atomic Reserved Project cancellation/release.
- [ ] Synchronize Project and Reservation terminal statuses.
- [ ] Add accessible confirmation actions and error feedback.
- [ ] Checkpoint each approved lifecycle transition independently.

### Settings backlog

- [ ] Add an authenticated Settings control to enable or disable the MCP server.
- [ ] Define persisted default, startup behavior and invalid-value recovery.
- [ ] Define immediate-apply versus restart-required semantics.
- [ ] Gate MCP transport/tool availability safely when disabled.
- [ ] Audit real MCP setting changes.
- [ ] Keep this item deferred until the MCP implementation phase.

### Remaining major V1 areas

- [ ] Complete Project consume/cancel lifecycle.
- [ ] System-wide History and audit browsing.
- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Accessibility, security and public-alpha release hardening.

<!-- PARTPILOT:CHAT14_PROJECTS_FOUNDATION_ROADMAP:V396 -->
## Current roadmap checkpoint — Projects foundation complete

### Overall progress

**Working V1/public-alpha estimate: approximately 82%.**

Inventory, universal search, the complete Reservation workflow and the core
Projects planning/reservation foundation are operational. Reserved Projects now
also have a verified backend consumption transition. Remaining work is
concentrated in Project cancellation and terminal-action UI, system-wide
History, broader Settings and appearance, backup/restore, MCP, accessibility,
security and public-alpha hardening.

### Completed through Patch 394

- [x] Canonical Project lifecycle contract and migration.
- [x] Protected Project list/detail/create/update APIs.
- [x] Draft item reconciliation and price/currency snapshots.
- [x] Responsive Project register/detail/create/edit workspace.
- [x] Atomic Draft Project reservation through one linked active Reservation.
- [x] Paired Project/Reservation reserve audits and stock movements.
- [x] Project-derived Reservation product model.
- [x] Multi-result Project and Reservation part pickers.
- [x] Manual Reservation creation removed from the frontend.
- [x] Atomic Reserved Project consumption through the linked Reservation.
- [x] Project/Reservation `consumed` status synchronization.
- [x] Consume movements, audits, concurrency guards and rollback.
- [x] Complete copied-database smoke and live-data preservation.
- [x] Diagnostic recovery for the Patch 391/392 pre-write failures.

### Chat 15 — Project Lifecycle Completion

Required title: `Chat 15: Project Lifecycle Completion`
Patch range: 397–426
Planned boundary: Patch 426

#### Boundary recovery

Patch 395 failed before writes on generated Markdown trailing whitespace. Patch 396 completes the boundary recovery, so Chat 15 owns Patch 397–426 and Patch 426 is its boundary.

#### Immediate implementation order

1. Add atomic Reserved Project cancellation by reusing
   `cancel_reservation(..., commit=False)`.
2. Require exactly one linked active Reservation and synchronize
   `Project.cancelled` with `Reservation.cancelled`.
3. Add paired release movements and `project.cancelled` audit verification.
4. Add typed frontend client methods for Project consume and cancel.
5. Add accessible confirmation actions, pending states and conflict feedback.
6. Refresh Project, Reservation and inventory views after terminal actions.
7. Browser-test desktop/mobile layouts, repeated-action guards and linked status
   behavior.
8. Checkpoint each approved lifecycle slice before broadening scope.

### Remaining major V1 areas

- [ ] Complete Project cancellation/release backend.
- [ ] Add Project consume/cancel frontend actions and activity feedback.
- [ ] System-wide History and audit browsing.
- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Add the authenticated MCP server enable/disable Settings control during
  the MCP phase.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Do not combine Project cancellation, system-wide History, backup/restore or MCP
in one patch. Preserve existing inventory, Reservations, Projects, movements,
audits and settings. The backend manual Reservation-create API remains until an
explicit API/MCP compatibility decision is made.

<!-- PARTPILOT:CHAT15_PROJECT_LIFECYCLE_ROADMAP:V405 -->
## Current roadmap checkpoint — Project lifecycle complete

### Overall progress

**Working V1/public-alpha estimate: approximately 86%.**

Inventory, universal search, Reservations and the complete Project lifecycle are
operational and browser approved. Users can plan Draft Projects, reserve them,
edit the resulting commitment from either Projects or Reservations, and finish
through consumption or cancellation with synchronized inventory, movements,
statuses and audits.

### Completed through Patch 403

Patch 404 failed before writes on generated Markdown trailing whitespace. Patch 405 is the narrow checkpoint recovery.

- [x] Atomic Project reservation through one linked active Reservation.
- [x] Atomic Project consumption and cancellation/release.
- [x] Paired Project/Reservation terminal statuses, movements and audits.
- [x] Current-transaction movement verification that ignores historical edit
  movements.
- [x] Reserved Project editing with quantity-delta reserve/release behavior.
- [x] Two-way Project-linked Reservation editing from either workspace.
- [x] Direct Reservation consume/cancel/expiry synchronization to Projects.
- [x] Accessible in-app lifecycle confirmations and stale-state handling.
- [x] Mobile register-first behavior and compact summary metrics.
- [x] Physical, Reserved and Available movement snapshots in part history.
- [x] Complete copied-database regression coverage and browser approval.
- [x] Realistic manifest-owned test inventory for pre-reset validation.

### Next implementation order

1. Design the system-wide History information architecture and filters.
2. Add protected paginated audit/history APIs without duplicating existing
   Reservation activity or part movement logic.
3. Add entity, event, actor, date and text filtering with deterministic ordering.
4. Build responsive History list/detail views with readable before/after data.
5. Preserve inventory and use copied-database fixtures for all History tests.
6. Browser-test and checkpoint History independently.

### Remaining major V1 areas

- [ ] System-wide History and audit browsing.
- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Authenticated MCP server enable/disable Settings control.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Do not combine History, Settings, backup/restore or MCP in one implementation
slice. Preserve the realistic Patch 401 fixtures until an explicit cleanup or
database reset. The backend manual Reservation-create API remains temporarily
available pending the API/MCP compatibility decision.

<!-- PARTPILOT:SYSTEM_HISTORY_ROADMAP:V410 -->
## Current roadmap checkpoint — System-wide History complete

### Overall progress

**Working V1/public-alpha estimate: approximately 90%.**

Inventory, universal search, Reservations, the complete Project lifecycle
and system-wide History are operational, responsive and browser approved.

### Completed through Patch 409

- [x] Protected unified History API over audits and stock movements.
- [x] Deterministic newest-first pagination across both record kinds.
- [x] Literal text search and entity, event, actor, user, movement and date
  filters.
- [x] Counted filter facets and earliest/latest event bounds.
- [x] Actor, entity, Part, Reservation and Project context hydration.
- [x] Physical, Reserved and Available movement snapshots.
- [x] Structured audit Before, After and metadata inspection.
- [x] 280 ms frontend search, stale-response guards and page reset behavior.
- [x] Desktop register/detail workflow and mobile register-first workflow.
- [x] Complete copied-database regression coverage and desktop/mobile
  browser approval.
- [x] Chronological-order product decision: no general column sorting unless
  a future investigation workflow demonstrates a need for Oldest-first.

### Next implementation order

1. Inspect the current Settings routes, persisted app settings and appearance
   foundations before defining a UI slice.
2. Complete authenticated Settings information architecture and responsive
   layout.
3. Implement appearance/theme controls only where the runtime contract is
   explicit and testable.
4. Preserve existing settings and use copied-database tests for every write.
5. Keep the deferred MCP server enable/disable control separate unless the
   MCP runtime and restart semantics are fully defined.
6. Browser-test and checkpoint Settings independently.

### Remaining major V1 areas

- [ ] Settings and appearance completion.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Authenticated MCP server enable/disable control during the MCP phase.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Do not combine Settings, backup/restore and MCP in one implementation slice.
Preserve the six realistic Patch 401 fixtures and all existing operational
history until an explicit cleanup or database reset.

<!-- PARTPILOT:GLOBAL_APPEARANCE_ROADMAP:V417 -->
## Current roadmap checkpoint — Settings and appearance complete

### Overall progress

**Working V1/public-alpha estimate: approximately 93%.**

Inventory, universal search, Reservations, the complete Project lifecycle,
system-wide History and authenticated global appearance are operational,
responsive and browser approved.

### Completed through Patch 416

- [x] Protected Dark/Light/System appearance persistence and audit contract.
- [x] Light-theme availability guard and strict invalid-value handling.
- [x] Pre-paint bootstrap without opposite-theme flashing.
- [x] Authenticated server synchronization and live System-theme listener.
- [x] Responsive Settings information architecture.
- [x] Existing Inventory and Reservation preferences preserved.
- [x] Compact database-reset launcher with dialog-owned confirmation phrase.
- [x] Coherent Light surfaces across all current workspaces and overlays.
- [x] Consistent primary, neutral, destructive, active, selected, status and
  genuinely disabled Light-mode states.
- [x] Complete copied-database regression coverage and browser approval.

### Next implementation order

1. Reduce the Out-of-stock results preference to a compact control while
   preserving its server-backed boolean behavior and accessibility.
2. Browser-test and checkpoint that focused Settings refinement.
3. Implement backup and restore as a separate product slice.
4. Implement MCP read tools and safeguarded write tools.
5. Add the authenticated MCP enable/disable control only when MCP runtime
   and restart semantics are explicit.
6. Complete accessibility, security and public-alpha release hardening.

### Remaining major V1 areas

- [ ] Compact Out-of-stock preference refinement.
- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Authenticated MCP server enable/disable control during the MCP phase.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Keep the compact Settings refinement separate from backup/restore and MCP.
Preserve the realistic Patch 401 fixtures and all operational History until
an explicit cleanup or database reset.

<!-- PARTPILOT:CHAT16_BACKUP_RESTORE_ROADMAP:V426 -->
## Current roadmap checkpoint — Settings complete, backup/restore next

### Overall progress

**Working V1/public-alpha estimate: approximately 95%.**

Inventory, universal search, Reservations, the complete Project lifecycle,
system-wide History and authenticated global Settings/appearance are
operational, responsive and browser approved.

### Completed through Patch 425

- [x] Complete Project planning, reservation, editing, consumption and
  cancellation lifecycle.
- [x] Atomic linked Project/Reservation synchronization and inventory
  accounting.
- [x] Protected system-wide History and audit register.
- [x] Persisted Dark, Light and System appearance contract.
- [x] Pre-paint theme application and live System-theme following.
- [x] Complete Light-theme coverage and cross-workspace interaction
  hierarchy.
- [x] Responsive Settings information architecture.
- [x] Compact accessible Out-of-stock preference.
- [x] Reservation expiry defaults and guarded database-reset dialog.
- [x] Final desktop composition with equal-height Reservation and Data
  cards and natural mobile stacking.
- [x] Complete copied-database regression coverage and browser approval.

### Chat 16 — Backup and Restore Foundation

**Required title:** `Chat 16: Backup and Restore Foundation`
**Patch range:** 427–456 inclusive
**Planned boundary:** Patch 456
**First patch:** 427

### Immediate implementation order

1. Inspect the current SQLite path, reset service, authentication model,
   Docker volume layout and app startup/session behavior before designing
   the contract.
2. Define a versioned backup artifact and manifest containing format
   version, creation timestamp, Alembic revision, database metadata and
   integrity evidence.
3. Create backups using SQLite's online backup API rather than copying a
   live database file directly.
4. Add protected backup download behavior with explicit filename, media
   type, no-cache headers, audit evidence and cleanup of temporary files.
5. Design restore as a separate guarded transaction: upload limits, archive
   validation, path-traversal protection, manifest/schema compatibility,
   SQLite integrity and foreign-key checks, required-table validation and
   rejection before touching live data.
6. Before restore, create a rollback snapshot of the current database.
   Replace live data only after all validation succeeds, define connection
   and restart semantics explicitly, and restore the rollback snapshot on
   any failure.
7. Add responsive Settings Data controls for Download backup and Restore
   backup. Restore must use an accessible review dialog with explicit
   destructive copy and progress/error feedback.
8. Test exclusively with copied databases and manifest-owned artifacts.
   Verify exact preservation of users, catalogues, inventory, Projects,
   Reservations, movements, audits and settings across backup/restore.
9. Browser-test backup download, invalid-file rejection, successful restore,
   rollback behavior and responsive layouts before checkpointing.

### Remaining major V1 areas

- [ ] Backup and restore.
- [ ] MCP read tools and safeguarded write tools.
- [ ] Authenticated MCP server enable/disable control during the MCP phase.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Keep backup/restore separate from MCP. Do not silently clean the six
realistic Patch 401 fixtures or existing History. Do not design restore as
an unvalidated raw-file overwrite. The current database-reset action remains
a separate permanent operation and must not be conflated with restore.

<!-- PARTPILOT:CHAT17_BACKUP_STATUS_MCP_ROADMAP:V457 -->
## Current roadmap checkpoint — backup/restore core complete

### Overall progress

**Working V1/public-alpha estimate: approximately 97%.**

Inventory, Reservations, Projects, History, authenticated appearance, manual
backup download, strict restore validation/commit, responsive backup/restore
Settings controls and a truthful manual-backup status API are operational.

### Completed through Patch 453

- [x] Versioned `.ppbackup` artifact and manifest.
- [x] SQLite online snapshot generation.
- [x] Protected manual backup download with no-store headers and audit evidence.
- [x] Strict restore upload, archive, schema, hash and SQLite validation.
- [x] Persistent restore staging and maintenance lifecycle.
- [x] Pre-Uvicorn restore bootstrap and controlled restart.
- [x] Rollback snapshot, atomic replacement and post-replacement verification.
- [x] Restored-session invalidation and forced fresh login.
- [x] Responsive Settings backup/restore workspace.
- [x] Functional Settings section navigation and natural panel heights.
- [x] Desktop and mobile browser approval of the core workflow.
- [x] Evidence-preserving expired-staging cleanup.
- [x] Protected truthful manual-backup status API.
- [x] Complete copied-database regression coverage.

### Chat 17 — Backup Status Finalization and MCP Foundation

**Required title:** `Chat 17: Backup Status Finalization and MCP Foundation`
**Patch range:** 458–487 inclusive
**Planned boundary:** Patch 487
**First patch:** 458

### Immediate implementation order

1. Recover the Patch 455 manual-backup status UI candidate.
2. Verify minified CSS through the durable custom property rather than a
   stripped comment marker.
3. Browser-test desktop and mobile status layout, loading/error states and
   immediate refresh after a manual download.
4. Checkpoint and push the approved four-file frontend status slice.
5. Update public documentation to mark backup/restore fully complete.
6. Inspect and define the MCP runtime, transport, authentication, tool
   permissions, audit and restart contracts before implementation.
7. Implement MCP read tools first, then safeguarded writes with explicit
   confirmation and inventory invariants.
8. Add the authenticated MCP enable/disable control only after runtime and
   restart behavior are explicit.
9. Complete accessibility, security and public-alpha release hardening.

### Remaining major V1 areas

- [ ] Manual-backup status UI browser approval and checkpoint.
- [ ] MCP read tools.
- [ ] Safeguarded MCP write tools.
- [ ] Authenticated MCP server enable/disable control.
- [ ] Accessibility, security and public-alpha release hardening.

### Scope discipline

Do not claim scheduled backups exist. Current backup behavior is manual
download only and no server copy is retained. Preserve completed restore
evidence, the unused `backups` table, current inventory, History and the six
Patch 401 fixtures. Keep MCP work separate from the final status-UI checkpoint.


<!-- PARTPILOT:CHAT18_STATIC_BEARER_ROADMAP:V487 -->
## Current roadmap checkpoint — MCP foundation complete

### Overall status

The core inventory application, Reservation/Project lifecycle, History,
appearance, Settings and backup/restore workflow are operational. The
read-only OAuth MCP path and direct-key management backend are complete.

### Completed through Patch 486

- [x] Manual-backup status UI and browser-approved checkpoint.
- [x] OAuth client persistence, PKCE, consent and token lifecycle.
- [x] Protected OAuth discovery and authorization/token endpoints.
- [x] Stateless JSON Streamable HTTP `/mcp` runtime.
- [x] Host/origin validation and protected-resource challenges.
- [x] Six read-only inventory, Project and Reservation MCP tools.
- [x] MCP global enable/read/write Settings controls.
- [x] Encrypted direct-key persistence and rotation foundation.
- [x] Protected direct-key status/create/reveal/disable backend API.
- [x] Exact copied-database smoke isolation and live-data preservation.

### Chat 18 — Static Bearer MCP Integration

**Required title:** `Chat 18: Static Bearer MCP Integration`
**Patch range:** 488–517 inclusive
**Planned boundary:** Patch 517
**First patch:** 488

### Immediate implementation order

1. Inspect the exact `/mcp` OAuth gateway and tool principal/audit contract.
2. Recognize only `pp_mcp_key_...` Bearer credentials as direct keys.
3. Validate direct keys without weakening OAuth validation.
4. Preserve MCP enabled/read-tool gating for both authentication paths.
5. Add a direct-key principal shape compatible with tool audit attribution.
6. Verify invalid, rotated, disabled and missing-secret behavior.
7. Prove OAuth and static Bearer credentials coexist.
8. Add Settings UI for status, create, reveal, copy, rotate and disable.
9. Browser-test desktop and mobile, then checkpoint the approved UI.
10. Design custom-header and trusted-network modes separately.
11. Implement safeguarded write tools only after confirmation and audit
    contracts are explicit.

### Remaining major work

- [ ] Static Bearer validation in `/mcp`.
- [ ] Direct-key tool principal and audit attribution.
- [ ] Direct-key Settings UI and browser approval.
- [ ] Custom-header API-key mode.
- [ ] Trusted-network no-auth mode with strict proxy/client-IP validation.
- [ ] Independent OAuth/direct-auth controls.
- [ ] Safeguarded write tools and destructive-action confirmation.
- [ ] External MCP client testing and final public-alpha hardening.

### Scope discipline

Do not create a key automatically. Do not expose plaintext keys in status,
logs, audits or errors. Keep OAuth fully functional. Do not combine runtime
integration, frontend controls, custom-header mode, trusted-network mode and
write tools in one patch.

<!-- PARTPILOT:CHAT18_MCP_AUTHENTICATION_ROADMAP:V512 -->
## Current roadmap checkpoint — MCP authentication complete

### Completed through Patch 511

- [x] Static Bearer validation in `/mcp`.
- [x] Direct-key principal and audit attribution.
- [x] Direct-key Settings UI and browser checkpoint.
- [x] Custom-header management API, runtime, tests, and Settings UI.
- [x] Trusted-network persistence and protected management API.
- [x] Explicit trusted-proxy/client-IP resolver.
- [x] Trusted forwarded-origin integration for MCP and OAuth.
- [x] Trusted-network runtime with explicit-credential precedence.
- [x] Trusted-network Settings UI and browser checkpoint.
- [x] OAuth, Bearer, custom-header, and trusted-network coexistence tests.
- [x] Live inventory, credentials, restore staging, and database preservation.

### Current live posture

- Active direct mode: Bearer key.
- No trusted-network CIDRs are active.
- Trusted proxy CIDRs remain empty because the current reverse-proxy and direct
  published-port paths share the Docker gateway peer.
- Public MCP/OAuth origin is explicitly configured.
- Six read-only tools remain available.
- Write authorization settings exist, but safeguarded write tools are not yet
  implemented.

### Next implementation order

1. Inspect external MCP client compatibility and connection guidance.
2. Resolve any remaining independent OAuth/direct-auth administration gaps.
3. Define safeguarded write-tool confirmation, idempotency, quantity, audit,
   and rollback contracts.
4. Implement write tools in separate narrow slices only after the contract is
   explicit.
5. Complete accessibility, security, and public-alpha release hardening.
6. Complete the Chat 18 boundary at Patch 517.

### Remaining major work

- [ ] External MCP client testing and connection guidance.
- [ ] Independent OAuth/direct-auth controls, if the diagnostic finds a gap.
- [ ] Safeguarded MCP write tools and destructive-action confirmation.
- [ ] Accessibility, security, and public-alpha release hardening.

Do not activate trusted-network mode automatically. Do not trust the Docker
gateway while the published port remains directly reachable. Do not combine
external-client hardening and inventory-mutating write tools in one patch.

<!-- PARTPILOT:CHAT19_OAUTH_CONNECTOR_ROADMAP:V517 -->
## Current roadmap checkpoint — external OAuth connector completion

### Completed through Patch 516

- [x] OAuth discovery, dynamic registration, PKCE consent, token lifecycle, and
  revocation foundations.
- [x] Stateless public Streamable HTTP `/mcp`.
- [x] Six read-only inventory, Project, and Reservation tools.
- [x] Bearer, custom-header, and trusted-network authentication modes.
- [x] Strict proxy/client-IP and public-origin handling.
- [x] Official Python MCP SDK compatibility on copied data.
- [x] Live public-TLS SDK initialization, tool listing, and read call.
- [x] Live MCP/read enabled with write authorization disabled.
- [x] Claude, Google, and ChatGPT dynamic registration, consent, and code issuance proven.

### Blocking external-client issue

- [ ] Prevent duplicate consent-form submissions.
- [ ] Show progress and disable both actions immediately.
- [ ] Match standalone OAuth fields/buttons to the Part Pilot visual system.
- [ ] Override browser-autofill field colors.
- [ ] Replace raw expired, invalid, unavailable, and server-error pages.
- [ ] Complete a real Claude, Google, or ChatGPT token exchange.
- [ ] Complete external OAuth MCP initialization, tools/list, and a read call.
- [ ] Clean only exact abandoned tokenless test rows after successful retesting.

### Chat 19

**Required title:** `Chat 19: OAuth Connector Completion and MCP Write Foundation`
**Patch range:** `518-547`
**First patch:** `518`
**Planned boundary:** `547`

### Implementation order

1. Patch 518: implement the narrow OAuth standalone-page and duplicate-submit
   fix; build, deploy, and leave source uncommitted for browser testing.
2. Browser-test a fresh Claude, Google, or ChatGPT connector registration. Click Authorize
   once and verify callback, token exchange, connection, tools, and a read call.
3. Apply any browser feedback in the next sequential patch.
4. Checkpoint the approved OAuth source separately.
5. Clean only verified abandoned client/code/consent IDs from Chat 18 while
   preserving the successful external client and all unrelated rows.
6. Add connector administration/revocation visibility if required by the test.
7. Define safeguarded write-tool confirmation, idempotency, quantity, stock,
   audit, and rollback contracts in a diagnostic before implementation.
8. Implement write tools only in independent, inventory-safe slices.
9. Complete security, accessibility, and public-alpha hardening.
10. Complete the Chat 19 boundary at Patch 547.

### Scope discipline

Do not weaken or bypass the CSRF check. Do not alter the active direct Bearer
credential. Do not delete OAuth rows by name, timestamp, or broad query.
Do not start inventory-mutating MCP tools until one external OAuth read-only
client is fully connected and the write contract is independently approved.
