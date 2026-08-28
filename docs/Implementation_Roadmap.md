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

<!-- PARTPILOT:CHAT19_SETTINGS_ADMINISTRATION_ROADMAP:V528 -->
## Settings administration and integration-control roadmap

### Milestone baseline

- [x] Patch 527 committed and pushed the browser-approved OAuth workflow.
- [x] Claude and ChatGPT connected with `mcp:read`.
- [x] Hermes connected through direct Bearer authentication.
- [x] MCP/read enabled and MCP write authorization disabled.
- [x] Durable Settings-administration scope approved.
- [ ] Exact abandoned OAuth registration cleanup.
- [ ] Administration and permission features below.

### Phase A — terminology and OAuth hygiene

#### A1. Technical acronym formatter

- [ ] Preserve MCP, OAuth, API, HTTP, HTTPS, URL, URI, ID, IP, CIDR, PKCE, UI,
  CSV, and JSON.
- [ ] Apply to History rows, facets, actors, entities, details, and metadata.
- [ ] Preserve raw stored identifiers in technical fields.
- [ ] Browser-check desktop and mobile History.

#### A2. Exact abandoned-row cleanup

- [ ] Inspect current clients, codes, consents, token families, redirects, and
  successful ownership.
- [ ] Produce an exact ID allowlist before deletion.
- [ ] Preserve active Claude and ChatGPT registrations, tokens, grants, and
  refresh families.
- [ ] Delete no rows by broad name, origin, or timestamp.
- [ ] Verify integrity, foreign keys, connections, and before/after evidence.

### Phase B — OAuth administration

#### B1. Connected-client visibility

- [ ] Protected API for registered/connected/abandoned/revoked summaries.
- [ ] Derive status from registration, consent, code, token, and revocation
  state.
- [ ] Settings list with name, client ID, redirect origin, auth method, scopes,
  created/connected/last-used timestamps, token count, and status.
- [ ] Responsive loading, empty, error, and populated states.

#### B2. Revocation

- [ ] Review dialog with exact affected token-family/code counts.
- [ ] Transactionally revoke client or grant, active token families, and unused
  codes.
- [ ] Secret-free audit event and preserved history.
- [ ] Verify the revoked client fails while unrelated clients remain connected.

#### B3. Manual client registration

- [ ] Form for name, redirect URI(s), client type, grant/response types, and
  token-endpoint authentication.
- [ ] Generate collision-resistant client ID.
- [ ] Generate a secret for confidential clients, display once, hash at rest,
  and support rotation.
- [ ] Prefer PKCE/public-client defaults for desktop/local clients.
- [ ] Provide copyable configuration and connection guidance.

### Phase C — account and API administration

#### C1. Current-user profile and security

- [ ] Protected profile read/update API.
- [ ] Display-name and username changes with uniqueness/normalization.
- [ ] Password change requiring current password.
- [ ] Revoke other sessions by default after password change.
- [ ] Session list and targeted/all-other revocation.
- [ ] Built-in avatar catalogue and stored avatar ID.
- [ ] Uploaded avatars only after safe storage/crop/metadata/backup contracts.

#### C2. Multi-user foundation

- [ ] Roles: Owner, Administrator, Operator, Viewer.
- [ ] Permission checks on every protected REST/MCP operation.
- [ ] Add, disable, reactivate, role-change, force-reset, revoke, and delete.
- [ ] Last Owner cannot be disabled, deleted, or demoted.
- [ ] Backward compatibility for the current single owner.

#### C3. Scoped REST API keys

- [ ] Dedicated API-key table and `pp_api_...` credential prefix.
- [ ] One-time secret display and hash-only storage.
- [ ] Name, description, creator, prefix, expiration, last use, rotation,
  revocation, and audit.
- [ ] Scopes for inventory, Projects, Reservations, History, Settings, backups,
  and user administration.
- [ ] Dangerous scopes off by default.
- [ ] Distinguish session, API, OAuth, and MCP direct credentials.
- [ ] Copyable curl/OpenAPI examples.

### Phase D — MCP direct clients and permissions

#### D1. Direct-client master switch and no-auth mode

- [ ] Separate `Allow direct MCP clients` from the selected auth method.
- [ ] Modes: no authentication, Bearer, custom header, trusted network.
- [ ] No-auth is off by default, requires typed confirmation, warns when
  remotely reachable, and initially permits read tools only.
- [ ] Local-loopback and Docker-gateway guidance.
- [ ] Show last resolved direct-client address safely.

#### D2. Named direct clients

- [ ] Replace or migrate the singleton direct-auth record to named clients.
- [ ] Independent credential/network configuration, tool policy, metadata,
  rotation, disable, and revoke.
- [ ] Preserve existing Hermes access during migration.
- [ ] Support Local Claude Code, n8n, tunnel agents, and other direct clients
  without a shared identity.

#### D3. Tool catalogue and policy model

- [ ] Stable tool identifiers and read/write/risk metadata.
- [ ] Global policy per individual tool.
- [ ] Client override values: Inherit, Allow, Deny.
- [ ] OAuth and named-direct-client assignments.
- [ ] Deny wins; client Allow cannot exceed the global category/tool ceiling.
- [ ] Enforce in both `tools/list` and `tools/call`.
- [ ] Secret-free decision audits.
- [ ] Accessible desktop/mobile permission matrix.

### Phase E — expanded preferences

- [ ] Preferences workspace: theme, accent, density, font size, reduced motion,
  contrast, table density, sticky headings, sidebar, ISO currency, locale/time
  presentation, landing page and navigation behavior.
- [ ] Inventory-facing preferences: default filter/sort/page size/location/type,
  remembered filters, columns and other reversible display/default behavior. Keep
  stock policy, quantity rules and destructive/consequential controls outside the
  preference-autosave model.
- [ ] Reservation-facing preferences: expiry/default presentation, remembered
  section/sorting and other reversible defaults. Keep lifecycle mutations,
  over-reservation policy and consequential Project/Reservation actions explicit.
- [ ] Data & Maintenance: scheduled backups/retention, export/import preview,
  storage, integrity, diagnostics, audit retention, explicit cleanup.

### Phase F — restore defaults

- [x] Current Theme, Inventory display and Reservation-default cards document and
  expose their own `Reset to default` actions.
- [x] Targeted authenticated restore API resets exactly one current preference
  group and preserves users, credentials, clients, API keys, inventory, lifecycle
  records, backups, history and unrelated preference groups.
- [ ] Extend the same per-card/per-section default model as new Preferences are
  added; do not reintroduce one combined reset for unrelated preference groups.
- [ ] Add restore audit events/preview where a future preference group warrants it.
- [ ] Keep MCP/security restore separate from reversible Preferences and destructive
  access/data reset.

### Phase G — safeguarded MCP writes

Begin only after the client/tool permission model is complete.

- [ ] Explicit write-tool catalogue and scopes.
- [ ] Confirmation, idempotency, quantity, stock, transaction, audit, rollback,
  and error contracts.
- [ ] Separate inventory-safe implementation slices.
- [ ] Require OAuth `mcp:write`, global write, tool policy, and client permission.
- [ ] No-auth direct clients cannot receive write access initially.

### Immediate next patches

1. Patch 529: History technical acronym normalization.
2. Following patch: exact OAuth-row cleanup diagnostic/allowlist.
3. Cleanup implementation only after the diagnostic passes and is inspected.
4. OAuth connected-client administration.
5. Continue without combining unrelated security or data-mutation slices.

<!-- PARTPILOT:CHAT20_MANUAL_OAUTH_REGISTRATION_ROADMAP:V548 -->
## Current roadmap checkpoint — manual OAuth registration foundation

### Completed through Chat 19

- [x] Styled and hardened standalone OAuth consent/error workflow.
- [x] Claude and ChatGPT connected end to end with `mcp:read`.
- [x] Exact abandoned OAuth operational-row cleanup.
- [x] Canonical History acronym formatting.
- [x] Protected connected OAuth client list.
- [x] Exact connected-client revocation and audit.
- [x] Responsive Settings list and guarded revoke dialog.
- [x] Browser approval and frontend checkpoint.
- [x] Manual-registration readiness diagnostic.

### Blocking ownership requirement

`mcp_oauth_clients` does not identify the user who manually registered a
client. Registered-but-unconnected clients have no consent or token through
which current-user ownership can be derived.

- [ ] Add nullable `registered_by_user_id`.
- [ ] Keep historical dynamic registrations nullable.
- [ ] Set ownership only for authenticated manual registration.
- [ ] Never infer ownership from name, origin, timestamp, row order, or audit
  prose.

### Chat 20

**Required title:** `Chat 20: Manual OAuth Registration Foundation`
**Patch range:** `549-578`
**First patch:** `549`
**Planned boundary:** `578`

### Required implementation sequence

1. **Patch 549 — ownership and protected registration backend**
   - Add Alembic `0011_mcp_oauth_client_ownership`.
   - Add model relationship/index/foreign-key contracts.
   - Add protected `POST /api/settings/mcp/oauth-clients`.
   - Accept name, redirect URIs, public/confidential type, and compatible
     token-endpoint authentication method.
   - Fix grant types to authorization code plus refresh token.
   - Fix response type to code.
   - Return generated client ID and one-time secret only on creation.
   - Store only the secret digest.
   - Attribute the audit and owner to the authenticated user.
   - Add copied-database tests for ownership, secret leakage, validation,
     unauthenticated rejection, rollback, and preservation.

2. **Patch 550 — manageable-client administration list**
   - Return only clients registered by or connected to the current user.
   - Add safe `registered`, `connected`, and `revoked` status semantics.
   - Keep `Abandoned` deferred until an explicit age threshold is approved.
   - Preserve current connected-client metadata and revocation behavior.

3. **Patch 551 — browser-test Settings registration UI**
   - Accessible responsive form for name, redirect URIs, type, and auth method.
   - Public clients default to `none`.
   - Confidential clients use `client_secret_post` or
     `client_secret_basic`.
   - Dedicated one-time result dialog with Show/Hide and Copy controls.
   - Keep secrets only in component memory.
   - Never persist secrets in storage, URLs, logs, History, or errors.
   - Leave source uncommitted until browser approval.

4. **Patch 552 — feedback or approved checkpoint**
   - Apply browser feedback in the next sequential patch, or commit/push the
     exact approved backend/frontend batch.

5. Continue current-user profile, password, sessions, and built-in avatars only
   after manual OAuth registration is committed and pushed.

### Scope discipline

- Preserve live Claude, ChatGPT, and Hermes credentials.
- Keep MCP writes disabled.
- Do not modify existing dynamic registration behavior unnecessarily.
- Do not expose client-secret hashes or plaintext secrets in GET responses,
  logs, audit metadata, or History.
- Do not start REST API keys, named direct clients, tool policy, or
  inventory-mutating MCP writes in the same slice.
- Use unique copied-database fixtures and restore exact logical state after
  smoke tests.

<!-- PARTPILOT:CHAT20_BOUNDARY_ROADMAP:V580 -->
## Current roadmap checkpoint — Chat 20 complete

### Completed

- [x] Manual OAuth client creator ownership.
- [x] Protected manual OAuth registration.
- [x] One-time confidential secret display with digest-only storage.
- [x] Manageable registered/connected/revoked client semantics.
- [x] Current-user-owned registered-client revocation.
- [x] Browser-approved manual OAuth registration Settings UI.
- [x] Revoked clients hidden from the normal active Settings list.
- [x] Protected current-user profile read/update backend.
- [x] Username/display-name normalization and uniqueness handling.
- [x] Alembic `0012_user_avatar_id` and built-in avatar catalogue.
- [x] `/auth/me` avatar identity response and profile audit.
- [x] Password/session administration readiness diagnostic.

### Chat 21 — Account Security and Session Administration

**Required title:** `Chat 21: Account Security and Session Administration`
**Patch range:** `581-610`
**First patch:** `581`
**Planned boundary:** `610`

Implementation order:

1. Add password/session backend schemas, services, routes, audit, and
   copied-database smoke from Patch 577's locked contract.
2. Password change requires current-password verification, rejects reuse,
   updates the hash transactionally, revokes all other sessions by default,
   and preserves the current session.
3. Add safe session listing with current-session identification; never return
   bearer tokens or token hashes.
4. Add targeted session revocation and `revoke all other sessions`, scoped
   strictly to the current user.
5. Add frontend auth types/client/AuthContext refresh support.
6. Build the Account/Security Settings browser-test UI for profile, built-in
   avatars, password change, sessions and revocation.
7. Refine from browser feedback, then checkpoint the approved UI.
8. Resume scoped REST API keys only after account/security is complete.

### Deferred beyond the account/security slice

- Scoped REST API keys.
- Direct-client master switch, no-auth mode and named direct clients.
- Global individual-tool and per-client MCP policy.
- Expanded preference/default-restoration work.
- Multi-user roles and administration.
- Safeguarded inventory-mutating MCP write tools.

Keep MCP write authorization disabled until the permission model and
write-tool safeguards are complete.

<!-- PARTPILOT:POST_V1_NOTIFICATIONS_ROADMAP:V595 -->
## Post-v1 deferred roadmap — Notifications & Messaging

This feature family is explicitly deferred until after the first Part Pilot
release and must not block current-release completion.

### User contact and notification identity

- [ ] Optional per-user email address.
- [ ] Validation, normalization, uniqueness policy only if future product
  requirements require uniqueness.
- [ ] Keep notification contact data separate from login identity unless a later
  authentication design deliberately joins them.

### SMTP email channel

- [ ] SMTP host, port, TLS/STARTTLS mode, username and encrypted password/secret.
- [ ] Test-notification action before enabling the channel.
- [ ] Never expose SMTP secrets through GET responses, logs, History or audits.
- [ ] Delivery timeout, retry/backoff and clear failure state.

### Additional channels

- [ ] Pluggable channel contract so later transports can be added without
  redesigning event subscriptions.
- [ ] Evaluate webhook, push/mobile and other channels only when their security
  and delivery contracts are defined.

### Event subscriptions

- [ ] Per-user enable/disable controls.
- [ ] Category and individual-event selection.
- [ ] Candidate event families: low/out-of-stock, Project and Reservation
  lifecycle, account/security, backup/restore, and integration/API/MCP activity.
- [ ] Respect authorization boundaries; never disclose event data a recipient is
  not permitted to view.

### Delivery history and operations

- [ ] Persist safe delivery status, timestamps, channel and event identifier.
- [ ] Retry/backoff without duplicate notification storms.
- [ ] Secret-free audit of configuration and delivery outcomes.
- [ ] Restore/backup and multi-user behavior defined before implementation.

<!-- PARTPILOT:RECYCLE_BIN_ROADMAP:V607 -->
## Recycle-bin UX hardening — current Chat 21 browser-test slice

- [x] Preserve recoverable soft deletion as the normal Part delete behavior.
- [x] Define permanent purge for selected Deleted items with explicit `DELETE`
  confirmation and atomic all-or-nothing semantics.
- [x] Protect active/reserved workflows from permanent purge.
- [x] Preserve historical audit records and detach terminal historical links.
- [x] Split custom Part Type dependencies into active vs Deleted-items counts.
- [x] Make blocked Part Type deletion visually unambiguous: `Cannot delete`, no
  confirmation input/button, up to five named blockers per class, then `+N more`.
- [x] Add dominant direct Part Type delete-dialog navigation into Deleted items
  with the exact Part Type filter pre-applied.
- [x] Browser approved through Patch 609. ESP01 was permanently purged,
  Development Board was then deleted successfully, and 5V Relay remained
  recoverable.
- [x] Patch 614 checkpoints/pushes the approved V607-V609 batch and makes the
  legacy Part Type update/delete smoke audit-safe when SQLite reuses entity IDs.

This work does not replace the Recycle Bin with permanent-delete-only behavior.
Deleted items remain recoverable until the user explicitly chooses permanent
purge.

<!-- PARTPILOT:CHAT21_EXTENSION_ROADMAP:V614 -->
## Chat 21 extended implementation window

The user granted a one-chat exception extending this chat through Patch 629.

- Next implementation patch: **615**
- New Chat 21 boundary/handoff patch: **629**
- Chat 22 starts at **Patch 630**, only after Patch 629 succeeds.
- Do not create the Chat 21-to-22 handoff before Patch 629.

### Next implementation order

1. [x] Scoped REST API-key backend lifecycle: named one-time secrets, digest-only
   storage, explicit scopes, expiry, rotation/revocation and last-used metadata.
2. [x] Patch 617 wires API-key authentication and route-level scope enforcement
   across all eligible REST routes while keeping Auth/Settings/Backup/Restore
   session-only; Patch 616 failed before writes due to omitted untracked smoke bytes.
3. [x] Patch 620 browser-approved API Access and shared REST/MCP security dialogs.
   Patches 621/622/624 failed safely during checkpoint recovery; Patches 623/625
   diagnosed Docker context bytecode and file-mode drift; Patch 626 checkpoints
   the approved batch with a canonical Docker build context.
4. Named/direct MCP client administration and master/no-auth policy without
   weakening existing Bearer/custom-header/trusted-network authentication.
5. Global individual-tool and per-client MCP permissions.
6. During the broader Settings task, add restrained section dividers/groups
   throughout Settings wherever they improve hierarchy, not only MCP. Within MCP,
   `Enable MCP server` is first; subordinate controls are muted/disabled while off;
   read/write/tool authorization belongs under permissions/security.
7. Continue preference/default restoration, multi-user roles, safeguarded MCP
   writes, then final accessibility/security/docs/public-alpha hardening.

MCP write authorization remains disabled until permission policy and safeguarded
write tools are complete. Notifications & Messaging remain post-v1.


<!-- PARTPILOT:API_UI_CURRENCY_METRICS_ROADMAP:V618 -->
## API UI, currency and Stored Parts metrics — explicit V1 work

- [x] Patch 620 browser-approved and Patch 626 checkpoints API Access: scoped key
  lifecycle, one-time-secret handling, API-doc actions, hidden revoked records,
  aligned fields/readable scopes, and modal rotate/revoke security flows.
- [ ] Protect `/docs`, `/redoc` and the chosen OpenAPI-schema exposure policy
  deliberately before public alpha while keeping actual API administration
  session-only.
- [ ] Add the already-persisted app-wide ISO currency selector to the `Preferences` workspace. Use locale-aware formatting; changing the selector does not perform FX conversion or rewrite stored historical price numbers.
- [ ] Add server-backed Stored Parts summary metrics over the complete active
  inventory, not the current page: Total components, Inventory value with
  valuation coverage, Available, Reserved, Low stock, Out of stock and distinct
  Part count. Reserved quantity remains part of physical inventory value.
- [ ] During the later dashboard-metrics expansion, keep Stock alert as a metric card but remove the dashboard's inline Low stock inventory table. Clicking Stock alert should open a responsive dialog listing every part currently producing a stock alert; the dialog is the detail/drill-down surface.


<!-- PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_ROADMAP:V632 -->
## Chat 21 final checkpoint — named direct MCP clients complete

- [x] Alembic `0015_mcp_direct_clients` and deterministic backup/restore schema contract.
- [x] Named Bearer, custom-header and trusted-network direct clients with independent lifecycle and usage identity.
- [x] `Allow direct MCP clients` master policy and typed-confirmed, read-only instance-wide no-auth fallback.
- [x] OAuth remains independent; explicit credentials retain precedence; MCP writes remain disabled.
- [x] Browser-approved Settings administration, security dialogs, typography, aligned MCP section widths and readable single-level disabled state.
- [x] Patch 632 checkpoints and pushes the exact approved Patch 627-631 batch.

### Boundary

- Patch 633 is the mandatory Chat 21 boundary/handoff.
- Chat 22 starts at Patch 634 only after Patch 633 succeeds.
- Do not begin another implementation feature in Chat 21.

### Next implementation order after the boundary

1. Global individual-tool and per-client MCP permissions.
2. Broader Settings organization with restrained section dividers/grouping across relevant Settings areas.
3. API documentation exposure/access hardening for public alpha.
4. ISO currency selector using the persisted app-wide currency; formatting only, no FX conversion.
5. Server-backed Stored Parts metrics: Total components, Inventory value with price coverage, Available, Reserved, Low stock, Out of stock and distinct Part count.
6. Preference/default restoration, multi-user roles, safeguarded MCP write tools, then final accessibility/security/responsive/API-MCP regression.

Notifications & Messaging remain post-v1.

<!-- PARTPILOT:CHAT21_BOUNDARY_ROADMAP:V633 -->
## Chat 21 complete — Chat 22 next

Chat 21 completed current-user account/session administration, recycle-bin dependency/purge hardening, scoped REST API keys, canonical Docker-context hardening, API Access Settings administration, and named direct MCP client administration/master/no-auth policy.

### Chat 22

**Required title:** `Chat 22: MCP Permissions and Settings Organization`
**Patch range:** `634-658`
**First patch:** `634`
**Planned boundary:** `658`

Implementation order:

1. Patch 634 diagnostic-only: inspect exact MCP tool registry, runtime principals, OAuth/direct-client identity, current global read/write settings, Settings UI structure, backup/restore implications and smoke-test seams for individual-tool/per-client permissions.
2. Implement global individual-tool policy while preserving the six currently read-only tools and keeping all write tools disabled.
3. Add per-client permission overrides for OAuth and named direct clients without giving no-auth an invented named identity.
4. Add browser-test Settings permissions UI with accessible default/inherited/effective-state semantics; checkpoint promptly after approval.
5. Run the broader Settings organization pass with restrained section dividers/grouping across relevant Settings areas. Keep the flat/dense enterprise language and avoid decorative over-segmentation.
6. Then handle API docs/schema exposure hardening, persisted ISO currency selector, server-backed Stored Parts metrics, preference/default restoration, roles, safeguarded MCP writes and final alpha regression.

MCP write authorization remains disabled until permission policy and safeguarded write-tool contracts are complete. Notifications & Messaging remain post-v1.

<!-- PARTPILOT:CHAT22_RESPONSIVE_ROADMAP:V642 -->
## Chat 22 responsive regression complete — Patch 642

- [x] Diagnose the intermediate-width Projects title/action collapse.
- [x] Preserve wide desktop and existing `<=900px` Project-detail/mobile behavior.
- [x] Keep Draft/Reserved lifecycle controls readable without character-level
  Project-name wrapping or horizontal overflow.
- [x] Keep Consumed/Cancelled terminal headers compact.
- [x] Move the existing navigation drawer to `821-1080px` while retaining desktop
  content spacing; keep the persistent sidebar above 1080px and the existing
  compact/mobile shell at `<=820px`.
- [x] Browser approve and checkpoint the responsive regression batch.

### Next implementation order

1. Patch 643 diagnostic-only: global individual-tool and per-client MCP
   permissions.
2. Implement global individual-tool policy while preserving the six existing
   read-only tools and keeping MCP write authorization disabled.
3. Add per-client OAuth/named-direct overrides with explicit
   inherited/effective-state semantics.
4. Browser-test and checkpoint the permissions UI.
5. Continue broader Settings organization, API docs/schema hardening, ISO
   currency selector, Stored Parts metrics, preference restoration, roles,
   safeguarded MCP writes and final alpha regression.

Chat 22 planned boundary remains Patch 658.


<!-- PARTPILOT:AUTOSAVE_LIVE_SYNC_ROADMAP:V656 -->
## V1 interaction modernization — autosave and live synchronization

Add this as a cross-cutting V1 task after the current MCP-permissions browser
feedback/checkpoint. Do not squeeze implementation into the Chat 22 boundary.

### Reversible Settings autosave

- [x] Current reversible preferences no longer require ordinary Save/Reset-changes controls: Appearance and Stored Parts grouping already persist on selection; Patch 668 adds Reservation-default autosave and removes its Save/Reset row.
- [x] Discrete reversible preferences persist immediately. Reservation expiry mode now follows the same model.
- [x] Reservation default-days uses a 550 ms debounce so typing does not create one request per keystroke.
- [x] Current preference autosaves expose saving/saved/error state and restore the last confirmed value on request failure; Reservation defaults also guard late responses from overwriting newer edits.
- [x] Current Preferences use independent per-card `Reset to default` actions for Theme, Inventory display and Reservation defaults; each action confirms its own target.
- [x] Targeted preference reset preserves unrelated preferences plus users, passwords/sessions, OAuth/direct clients, API keys, credentials, inventory, Project/Reservation records, backups and audit/history data.
- [x] Autosave remains excluded from consequential/create/edit workflows such as Part edits, Project/Reservation mutations, password changes, MCP/security policy, credential/client creation, key rotation/revocation, backup/restore and delete.

### Live data synchronization

- [ ] Replace normal manual `Refresh` controls with near-immediate server-driven
  synchronization wherever data can change outside the current component.
- [ ] Preferred architecture: one authenticated server-sent event/invalidation
  stream from FastAPI. Events identify the changed resource/topic and cause the
  React client to refetch only affected data; do not push authoritative full
  records through the event stream.
- [ ] On stream reconnect, refetch active resources so missed events cannot
  leave stale UI. Use reconnect/backoff and connection-state handling.
- [ ] Polling is fallback/resilience only, not the primary refresh mechanism.
- [ ] Keep manual `Retry` only for error recovery; remove routine Refresh once
  the corresponding live-sync path is proven.
- [ ] Survey Dashboard, Stored Parts, Projects, Reservations, History, Settings
  status panels and API/MCP administration for current manual refresh/reload
  seams and migrate them deliberately.
- [ ] Preserve stale-request guards, pagination/filter/search state and
  inventory-safe mutation semantics while applying live invalidation/refetch.

SSE is preferred over a full WebSocket command bus because the current need is
primarily server-to-browser invalidation. If later requirements need persistent
bidirectional commands/subscriptions, the transport decision may be revisited
without changing the resource-event contract.

### MCP catalogue follow-up

- [ ] Do not permanently hardcode the permission UI to six read tools. The six
  entries are the only live tools today. When safeguarded write tools are
  actually implemented and registered in the canonical tool catalogue, expose
  them through the same global/per-client permission model with read/write/risk
  metadata. Write tools must not appear as fictitious controls before their
  runtime contracts exist.

Chat 22 remains bounded at Patch 658. Patch 657 should return to the pending MCP
permission browser-feedback fix; Patch 658 remains the mandatory boundary.


<!-- PARTPILOT:CHAT22_TO_CHAT23_BOUNDARY_RECOVERY:V660 -->
## Chat 22 complete — Chat 23 next

**Required title:** `Chat 23: MCP Permission Finalization and Settings Modernization`
**Patch range:** `661-685`
**First patch:** `661`
**Planned boundary:** `685`

Implementation order:

1. Patch 661 recovers the pending MCP permission browser refinement. Make
   authenticated MCP `tools/list` principal-aware so globally/per-client denied
   tools are omitted while call-time authorization remains defense in depth.
   Rehearse and freeze the exact packaged bytes before writing.
2. Browser-test and checkpoint the complete MCP permission foundation/API/UI
   immediately after approval.
3. Finish restrained Settings hierarchy and reversible preference autosave.
   Toggles/selects save immediately, text/number preferences debounce, ordinary
   Save/Reset-changes controls disappear, and reversible preference groups use
   independent scoped Reset-to-default actions.
4. Implement authenticated SSE invalidation plus targeted refetch for
   near-immediate cross-client updates. Polling is fallback only; routine
   Refresh controls disappear after each path is proven.
5. Continue public-alpha API docs/schema hardening, persisted ISO currency
   formatting, server-backed Stored Parts metrics, preference restoration,
   Owner/Admin/Operator/Viewer roles, safeguarded MCP writes and final alpha
   accessibility/security/responsive/API-MCP regression.

The six registered MCP tools are currently read-only. Do not add placeholder
write-tool controls. Future safeguarded write tools join the canonical catalogue
only when their runtime contracts exist.


<!-- PARTPILOT:MCP_PERMISSIONS_COMPLETE:V662 -->
## Chat 23 MCP permissions complete — Patch 662

- [x] Global exact-tool MCP permission policy with global hard-ceiling semantics.
- [x] OAuth and named-direct inherit-or-deny client overrides.
- [x] No-auth remains global-policy-only.
- [x] Call-time authorization before business lookup with secret-free failure audit.
- [x] Principal-aware authenticated `tools/list` omits ineffective tools.
- [x] Globally blocked per-client controls are visibly disabled and non-editable.
- [x] Six current tools are labelled as read tools; Write tools honestly show
  `0 available` with no placeholder runtime contracts.
- [x] Add-direct-client form controls use consistent Settings theming/alignment.
- [x] Configuration-safe permission smokes preserve legitimate production policy.
- [x] Browser approve and checkpoint/push the complete 23-file MCP permission batch.

### Next implementation order

1. Patch 665/666: first Settings hierarchy refinement is browser approved and checkpointed.
   Direct MCP access now groups its parent switches with Named direct clients and
   dependency-disabled controls no longer impersonate an active save.
2. Continue Settings modernization with reversible preference autosave. Toggles/selects
   persist immediately; text/number preferences debounce; ordinary Save/Reset-changes
   controls disappear; reversible preference groups reset independently.
3. Add authenticated SSE invalidation plus targeted refetch with reconnect/resync.
   Polling is fallback only; remove routine Refresh after each live-sync path is
   proven.
4. Harden API docs/OpenAPI exposure for public alpha.
5. Add persisted app-wide ISO currency formatting and server-backed Stored Parts
   whole-inventory metrics with explicit price coverage.
6. Preference/default restoration, Owner/Admin/Operator/Viewer roles, safeguarded
   MCP write tools and final alpha accessibility/security/responsive/API-MCP
   regression.

Chat 23 planned boundary remains Patch 685.


<!-- PARTPILOT:MCP_DIRECT_ACCESS_COMPLETE:V666 -->
## Chat 23 Direct MCP access hierarchy complete — Patch 666

- [x] Group Allow direct MCP clients + No authentication with Named direct clients.
- [x] Keep Server / Read tools / Write authorization in global MCP access.
- [x] Use `not-allowed` for dependency-disabled controls and `wait` only while saving.
- [x] Repair `mcp_settings_smoke_test.py` for the five-field contract and configuration-safe audit counts.
- [x] Browser approve and checkpoint/push the exact three-file batch.

Next: reversible preference autosave, then authenticated SSE invalidation/targeted refetch.


<!-- PARTPILOT:REVERSIBLE_PREFERENCE_AUTOSAVE_COMPLETE:V669 -->
## Chat 23 reversible preference autosave — Patch 669

- [x] Appearance selection autosaves with rollback.
- [x] Stored Parts out-of-stock grouping autosaves with rollback.
- [x] Reservation expiry mode autosaves immediately.
- [x] Reservation default-days autosaves after 550 ms debounce.
- [x] Invalid days are not sent; failures restore confirmed server state; stale responses cannot overwrite newer edits.
- [x] Ordinary Reservation Save/Reset-changes controls removed.
- [x] Security, credentials, lifecycle and destructive actions remain explicit.
- [x] Consolidate Theme, Inventory display and Reservation defaults under Preferences with independent targeted Reset-to-default actions.
- [x] Persisted ISO currency selector completed with Regional display/timezone in Patch 684; formatting only, no FX conversion.
- [ ] Later dashboard metrics: Stock alert card opens an all-alert-parts dialog; remove the inline Low stock inventory table.


<!-- PARTPILOT:PREFERENCES_TARGETED_RESET_COMPLETE:V674 -->
## Chat 23 Preferences consolidation and targeted resets — Patch 674

- [x] Replace separate Appearance/Inventory/Reservations settings tabs with one Preferences workspace for the current reversible defaults.
- [x] Keep legacy settings hashes routed to Preferences.
- [x] Keep autosave behavior independent for Theme, Inventory display and Reservation defaults.
- [x] Give each current preference card its own target-specific Reset-to-default action and confirmation.
- [x] Backend reset accepts exactly one preference target and preserves unrelated preference/security/business state; reservation reset is atomic.
- [x] Persisted ISO currency selector and themed Regional display/timezone completed and checkpointed in Patch 684.
- [ ] Later dashboard metrics: Stock alert card opens an all-alert-parts dialog; remove the inline Low stock inventory table.

<!-- PARTPILOT:REGIONAL_DISPLAY_COMPLETE:V684 -->
## Chat 23 regional display and currency — Patch 684

- [x] Persist app-wide uppercase three-letter ISO currency as display/formatting semantics only.
- [x] Apply currency to current inventory/Add/Edit price presentation without FX conversion.
- [x] Preserve historical Project/Reservation currency snapshots.
- [x] Add persisted IANA display timezone with protected GET/PATCH APIs and copied-DB smoke coverage.
- [x] Apply workspace timezone to passive timestamps without rewriting stored timestamps or datetime-local input semantics.
- [x] Theme Currency and Display timezone controls consistently with Part Pilot and stack them responsively below 760 px.
- [x] Browser approve the combined Patch 675 + Regional display/timezone source and checkpoint it in Patch 684.

### Next implementation order

1. Patch 685: complete the Chat 23 durable boundary/handoff.
2. Authenticated SSE invalidation + targeted refetch across Dashboard, Stored Parts, Projects, Reservations, History, Settings and API/MCP administration; one authenticated stream, reconnect/resync and polling fallback.
3. Harden API docs/OpenAPI exposure for public alpha.
4. Add server-backed whole-inventory Stored Parts metrics and the Dashboard Stock alert dialog; remove the inline Low stock table.
5. Add Owner/Admin/Operator/Viewer roles, safeguarded MCP write tools and final alpha accessibility/security/responsive/API-MCP regression.

Notifications & Messaging remain post-v1.

<!-- PARTPILOT:CHAT24_PLAN:V685 -->
## Chat 24 plan — authenticated live sync and public-alpha hardening

**Required title:** `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
**Patch range:** `686-710`
**First patch:** `686`
**Planned boundary:** `710`

Implementation order:

1. Add authenticated server-driven invalidation using one SSE-compatible stream and targeted refetch across Dashboard, Stored Parts, Projects, Reservations, History, Settings and API/MCP administration. Preserve stale-request guards, filters, pagination and current selection. Reconnect/resync on interruption; polling is fallback only; keep Retry on explicit errors.
2. Remove routine Refresh controls only after the corresponding live-sync path is proven reliable in browser testing.
3. Harden `/docs`, `/redoc` and `/openapi.json` exposure/schema behavior for public alpha without weakening authenticated application APIs.
4. Add server-backed whole-inventory Stored Parts metrics: Total components, Inventory value with price coverage, Available, Reserved, Low stock, Out of stock and distinct Part count. Keep the Dashboard Stock alert metric card, make it open a dialog listing all alert-producing parts, and remove the inline Low stock table.
5. Add Owner/Admin/Operator/Viewer roles, then safeguarded MCP write tools through the canonical catalogue/permission model only when their runtime contracts exist.
6. Finish alpha accessibility, security, responsive and API/MCP regression.

Notifications & Messaging remain post-v1.


<!-- PARTPILOT:INVENTORY_HISTORY_LIVE_SYNC_ROADMAP:V699 -->
### Patch 699 — first authenticated live-sync slice browser-approved

Completed:
- [x] Process-local live-sync broker with generation/sequence, bounded replay,
  resync and topic revision state.
- [x] Protected authenticated SSE stream/state endpoints that cooperate with
  lifecycle drain/maintenance.
- [x] Frontend fetch/ReadableStream SSE client with Last-Event-ID reconnect,
  bounded backoff and degraded polling fallback.
- [x] Same-origin BroadcastChannel invalidation relay with event-ID
  deduplication for reliable multi-tab browser behavior.
- [x] Post-commit `inventory` + `history` publication for part mutations.
- [x] Stored Parts/Part Manager targeted refetch, including selected drawer and
  movement history, while preserving local filters/search/sort/page/selection.
- [x] History targeted refetch and intermediate-width filter/date layout fixes.
- [x] Browser approval for the Inventory/Part Manager + History slice.

Still required before the live-sync task is complete:
- [ ] Dashboard invalidation/refetch paths.
- [ ] Projects invalidation/refetch paths.
- [ ] Reservations invalidation/refetch paths.
- [ ] Settings/preferences/account status invalidation where server-side
  changes can make another open client stale.
- [ ] API/MCP administration/integration status invalidation.
- [ ] Deliberately remove routine Refresh controls only after each
  corresponding path has its own browser proof; keep Retry for errors.

After the live-sync expansion, continue Chat 24 with public-alpha OpenAPI/docs
hardening, whole-inventory Stored Parts metrics + Dashboard Stock alert dialog,
roles, safeguarded MCP write tools and final alpha regression.


<!-- PARTPILOT:PROJECTS_RESERVATIONS_LIVE_SYNC_ROADMAP:V702 -->
### Patch 702 — Projects/Reservations live sync browser-approved

Completed in the second live-sync slice:
- [x] Projects post-commit topic publication.
- [x] Reservations post-commit topic publication.
- [x] Linked Project/Reservation cross-workspace invalidation.
- [x] Projects list + selected-detail targeted refetch.
- [x] Reservations list + selected-detail + Activity targeted refetch.
- [x] Browser proof that observing tabs update without copying another tab's
  local filter/search/page/selection controls.

Remaining live-sync surfaces:
- [ ] Dashboard status/stock alert refresh paths.
- [ ] Settings/preferences/account state that can become stale cross-client.
- [ ] API/MCP administration/integration status.
- [ ] Remove routine Refresh only after each remaining path has browser proof.

Then continue Chat 24 with public-alpha OpenAPI/docs hardening, whole-inventory
Stored Parts metrics + Dashboard Stock alert dialog, roles, safeguarded MCP
write tools and final alpha regression.


<!-- PARTPILOT:DASHBOARD_LIVE_SYNC_ROADMAP:V704 -->
### Patch 704 — Dashboard inventory live sync browser-approved

Completed:
- [x] Dashboard low-stock summary reacts to `inventory`.
- [x] Open Dashboard universal search reacts to `inventory`.
- [x] Search query remains local during live refetch.
- [x] Selected search result is preserved by ID when still present.
- [x] Existing stale-request guard remains in force.
- [x] Browser proof for cross-tab quantity/metadata refresh.

Remaining live-sync work:
- [ ] Settings/account state that can become stale cross-client.
- [ ] API/MCP administration/integration status.
- [ ] Remove routine Refresh controls only after remaining surfaces are proven.

After live-sync completion, continue Chat 24 with public-alpha OpenAPI/docs
hardening, whole-inventory Stored Parts metrics + Dashboard Stock alert dialog,
roles, safeguarded MCP write tools and final alpha regression.


<!-- PARTPILOT:SETTINGS_ACCOUNT_LIVE_SYNC_ROADMAP:V706 -->
### Patch 706 - Settings/account/preferences live sync browser-approved

Completed:
- [x] Preferences publish post-commit `preferences` + `history`.
- [x] Profile/avatar/password/session mutations publish `account` + `history`.
- [x] Manual backup generation publishes `backups` + `history`.
- [x] Theme, currency, timezone and account identity update across open tabs.
- [x] Part Manager and Dashboard follow the shared inventory display preference.
- [x] Settings follows preference/account/session/backup status invalidations.
- [x] Unsaved Account and Reservation drafts survive cross-tab refresh.
- [x] Active save/autosave/reset/security/backup operations defer live reload.
- [x] Browser proof completed for the non-credential Settings slice.

Remaining live-sync work:
- [ ] REST API key administration via `integrations.api_keys`.
- [ ] MCP administration/status via `integrations.mcp`.
- [ ] Remove routine Refresh controls only where each surface is fully proven.

After the integration slice, continue Chat 24 with public-alpha OpenAPI/docs
hardening, whole-inventory Stored Parts metrics + Dashboard Stock alert dialog,
roles, safeguarded MCP write tools and final alpha regression.


<!-- PARTPILOT:CHAT24_TO_CHAT25_DIAGNOSTIC_ROADMAP:V710 -->
### Patch 710 - Chat 24 diagnostic boundary

- [x] Preserve the clean Patch 706 application checkpoint after 707/708/709
  recovery failures.
- [x] Diagnose the manageable-OAuth smoke's stale permission-field contract.
- [x] Diagnose the durable-log evidence-contract mistake in Patch 708.
- [x] Diagnose hard-coded connected client IDs 9 and 13 as mutable-live-data
  coupling.
- [x] Define fixture-owned connected OAuth recovery for Patch 711.
- [x] Move remaining integration live-sync/browser proof into Chat 25.

Chat 25 starts at Patch 711. The final integration live-sync slice remains
unapproved/uncommitted; public-alpha hardening follows only after that slice is
recovered and browser-approved.


<!-- PARTPILOT:INTEGRATION_LIVE_SYNC_ROADMAP:V714 -->
### Patch 714 - API-key/MCP integration live sync browser-approved

Completed:
- [x] REST API-key administration live invalidation without secret transport.
- [x] MCP settings and global/client permission live invalidation.
- [x] Manual OAuth and named direct-client lifecycle live invalidation.
- [x] External OAuth lifecycle invalidation with refresh-token History noise
  suppression.
- [x] Cross-tab targeted refetch with unfinished MCP draft preservation.
- [x] Credential reveal/rotation dialog isolation across tabs.
- [x] Fixture-owned manageable OAuth smoke independent of historical IDs.
- [x] OAuth HTTP smoke safe against copied production OAuth persistence.
- [x] Browser approval of the final current-scope live-sync integration slice.

Current-scope authenticated live-sync migration is complete.

Next public-alpha work:
- [ ] Harden OpenAPI/public API documentation.
- [ ] Add whole-inventory Stored Parts metrics.
- [ ] Add the Dashboard Stock alert dialog.
- [ ] Add roles/authorization foundations.
- [ ] Add safeguarded MCP write tools.
- [ ] Run final public-alpha regression/hardening.

MCP configuration currently retains its explicit `Save changes` interaction;
changing that behavior is a separate UX/semantics task rather than part of this
approved live-sync checkpoint.


<!-- PARTPILOT:MCP_AUTOSAVE_STABLE_REFRESH_ROADMAP:V717 -->
### Patch 717 - MCP autosave and stable background refresh browser-approved

Completed:
- [x] Remove manual save/reset controls from reversible MCP access settings.
- [x] Autosave global read-tool permissions with rollback/stale guards.
- [x] Preserve explicit confirmation for enabling no-auth.
- [x] Keep loaded MCP settings/tool/OAuth/direct-client content mounted during
  background/live refetches.
- [x] Scope cached MCP refresh state to the active auth token.
- [x] Browser proof that MCP autosave no longer flashes the section.

Immediate hardening work:
- [ ] Apply initial-load vs background-refresh separation to Projects.
- [ ] Apply it to Reservations list/detail/activity.
- [ ] Apply it to History and Dashboard live-refresh surfaces.
- [ ] Apply it to Settings preferences/account/backups and REST API keys.
- [ ] Apply it to selected Stored Parts detail/movement refreshes.
- [ ] Preserve last-known-good content on transient background-refresh failures.
- [ ] Browser-test cross-tab refresh stability across the full sweep.

After refresh-stability hardening, continue with OpenAPI/public API docs,
whole-inventory Stored Parts metrics, Dashboard Stock alert dialog, roles,
safeguarded MCP write tools and final public-alpha regression.


<!-- PARTPILOT:STABLE_BACKGROUND_REFRESH_ROADMAP:V719 -->
### Patch 719 - Stable live background refresh browser-approved

Completed:
- [x] Projects list/detail stable same-identity live refresh.
- [x] Reservations list/detail/activity stable same-identity live refresh.
- [x] History register/filter-option background refresh without register flash.
- [x] Dashboard low-stock and open-search background refresh stability.
- [x] Preferences/account/manual-backup refresh stability.
- [x] REST API-key list refresh stability.
- [x] Selected Stored Parts detail/movement refresh stability.
- [x] Token/query/selection-scoped cache guards and last-known-good error policy.
- [x] Browser proof across the full refresh-stability sweep.

Next public-alpha work:
- [ ] Harden OpenAPI/public API documentation.
- [ ] Add whole-inventory Stored Parts metrics.
- [ ] Add the Dashboard Stock alert dialog.
- [ ] Add roles/authorization foundations.
- [ ] Add safeguarded MCP write tools.
- [ ] Run final public-alpha regression/hardening.


<!-- PARTPILOT:OPENAPI_RESTORE_ROADMAP:V723 -->
### Patch 723 - Public OpenAPI and restore recovery browser-approved

Completed:
- [x] Swagger/ReDoc API metadata and Bearer authorization contract.
- [x] Exact 43-operation REST API-key scope/access documentation.
- [x] Session-only/public/OAuth protocol access classification.
- [x] Restore schemas aligned to Alembic 0016.
- [x] BLOB-safe deterministic restore logical hashing and regression proof.
- [x] Browser approval and copied-production restore/API regression proof.

Next public-alpha work:
- [ ] Add whole-inventory Stored Parts metrics.
- [ ] Add the Dashboard Stock alert dialog.
- [ ] Add roles/authorization foundations.
- [ ] Add safeguarded MCP write tools.
- [ ] Run final public-alpha regression/hardening.


<!-- PARTPILOT:INVENTORY_METRICS_ROADMAP:V728 -->
### Patch 728 - Stored Parts whole-inventory metrics browser-approved

Completed:
- [x] Whole-inventory active-part, physical, reserved and available totals.
- [x] Inventory value with explicit priced-record coverage and display-only
  workspace currency semantics.
- [x] Stock-alert aggregate using the existing low/out-of-stock definition.
- [x] Protected `/api/parts/metrics` with `inventory:read` API-key scope.
- [x] OpenAPI/API-key scope map expanded from 43 to 44 operations.
- [x] Live inventory refresh without card flashing.
- [x] Symmetric container-aware 6 / 3 / 2 / 1 responsive card layout.
- [x] Browser approval and copied-production regression proof.

Next public-alpha work:
- [ ] Add the Dashboard Stock alert dialog.
- [ ] Add roles/authorization foundations.
- [ ] Add safeguarded MCP write tools.
- [ ] Run final public-alpha regression/hardening.


<!-- PARTPILOT:DASHBOARD_OPERATIONAL_HOME_ROADMAP:V731 -->
### Patch 731 - Dashboard operational home browser-approved

Completed:
- [x] Dashboard Stock alerts launcher/dialog with live background refresh.
- [x] Remove permanent Backend/Online status card.
- [x] Remove duplicated inline Low-stock inventory table.
- [x] Add responsive Quick actions for Add part, New project, Stored parts,
  Reservations, Part Manager and History.
- [x] Add one-shot Add part / New project modal intents.
- [x] Remove routine Refresh buttons from the remaining live-synced workspaces
  while preserving Retry/Try again error recovery.
- [x] Browser approval and copied-production live-sync/application regression.

Next public-alpha work:
- [ ] Add roles/authorization foundations.
- [ ] Add safeguarded MCP write tools.
- [ ] Run final public-alpha regression/hardening.


<!-- PARTPILOT:USER_ROLES_AUTHORIZATION_ROADMAP:V733 -->
### Patch 733 - User roles and authorization foundation

Completed:
- [x] Add `0017_user_roles` with safe in-place SQLite migration and exact
  pre-existing-account Owner backfill.
- [x] Define canonical Owner / Administrator / Operator / Viewer role levels.
- [x] Enforce Viewer read-only and Operator operational-write ceilings centrally
  across scoped REST session/API-key access.
- [x] Prevent REST API-key scopes from elevating above the current owning role.
- [x] Restrict workspace preference writes, MCP administration and backups to
  Administrator-or-higher; restrict restore/debug-reset to Owner.
- [x] Add session-only user administration for create/list, role/active changes,
  force-reset, session revocation and confirmed deletion.
- [x] Protect the last active Owner and prevent self-disable/self-delete.
- [x] Align backup/restore schema contracts and copied-production regressions to
  Alembic 0017.
- [x] Prove migration downgrade/re-upgrade preserves sessions, API keys, OAuth,
  audits and every other production row/sequence exactly.

Deferred presentation:
- [ ] Add a dedicated Settings role/user-management UI when that workflow is
  prioritized; the backend authorization boundary is already enforceable.

Next public-alpha work:
- [ ] Add safeguarded MCP write tools on the Operator-or-higher role foundation.
- [ ] Run final public-alpha regression/hardening.

<!-- PARTPILOT:CHAT26_PLAN:V742 -->
### Patch 742 — safeguarded lifecycle MCP writes complete; Chat 26 next

Patch 741 was consumed by a copied-production smoke that froze mutable MCP
policy to migration defaults. Patch 742 recovers the boundary with a fixture-owned
policy baseline and exact copied-DB restoration.

Completed in the Chat 25 closeout:
- [x] `0018_mcp_write_intents` migration and backup/restore schema alignment.
- [x] Six-read + three-write canonical MCP catalogue.
- [x] Operator-or-higher write-role ceiling and `mcp:write` OAuth scope ceiling.
- [x] Global Write authorization, individual write-tool policy and client deny
  overrides with no-auth permanently read-only.
- [x] Preview -> five-minute one-time confirmation, idempotency and state-drift
  safeguards for `reserve_project`, `consume_reservation`, and
  `cancel_reservation`.
- [x] MCP movement/audit attribution plus post-commit live invalidation.
- [x] Browser-approved client permission dialog scrolling and policy-vs-OAuth
  scope wording.
- [x] Browser approval and checkpoint of the complete lifecycle-write slice.

**Chat 26 title:** `Chat 26: MCP Inventory Writes and Public Alpha Finalization`
**Patch range:** `743-767`
**First patch:** `743`
**Planned boundary:** `767`

Chat 26 implementation order:
1. Add inventory-mutating MCP writes only in narrow, separately safeguarded
   slices. Start by inspecting existing inventory create/edit/quantity/delete
   transactional services and define the minimum honest tool catalogue. Do not
   bypass current REST/service invariants.
2. Cover add-part, metadata correction/editing and stock adjustment before any
   delete/restore semantics; keep confirmation/idempotency/state-drift and role/
   global/client/scope ceilings identical to the lifecycle-write foundation.
3. Add delete/restore MCP operations only if their recycle-bin/dependency and
   exact-confirmation contracts can be preserved without weakening the UI/API
   safety model.
4. Add the dedicated Settings user/role-management UI on the already-enforced
   Patch 733 backend boundary when prioritized.
5. Run the final public-alpha accessibility, security, responsive, backup/
   restore, REST/OpenAPI and MCP regression sweep and checkpoint the release
   candidate.

Notifications & Messaging remain post-v1. Live database/settings/OAuth/tool
policy are mutable state and must not be frozen as future patch prerequisites.

<!-- PARTPILOT:PATCH754_MCP_INVENTORY_STOCK_ROADMAP -->
### Patch 754 — guarded inventory stock adjustment complete

Completed in Chat 26:
- [x] Recover the consumed Patch 753 documentation EOF validation failure without
  changing the 20 browser-approved application files or live data/deployment.
- [x] Add data-only `0019_mcp_inventory_stock_write` while preserving mutable
  existing tool-policy values and defaulting the new write permission off.
- [x] Add guarded `adjust_part_quantity` using canonical inventory stock rules,
  MCP attribution, post-commit live invalidation, and the existing two-step
  confirmation/idempotency/state-drift contract.
- [x] Expand the canonical MCP catalogue to six read + four safeguarded write tools.
- [x] Standardize all Settings autosave success confirmations to 3.5 seconds and
  prevent expected live-sync/refetches from flashing them away.
- [x] Complete browser approval and checkpoint the combined source.

Next Chat 26 work:
1. Continue inventory create/edit and later delete/restore MCP slices only when
   their existing transactional/recycle-bin/dependency invariants can be preserved.
2. Add the dedicated Settings user/role-management UI when prioritized.
3. Run final public-alpha accessibility, security, responsive, backup/restore,
   REST/OpenAPI and MCP regression/hardening and checkpoint the release candidate.

<!-- PARTPILOT:PATCH759_MCP_PART_CREATE_ROADMAP -->
### Patch 759 — guarded inventory part creation and MCP client attribution complete

Completed in Chat 26:
- [x] Add data-only `0020_mcp_inventory_part_create`, preserving the prior ten
  mutable tool-policy values and defaulting only `create_part` off.
- [x] Expand the MCP catalogue to six read + five safeguarded write tools.
- [x] Add guarded `create_part` on canonical inventory validation with normalized
  preview, catalogue/template dependency drift checks, confirmation, idempotency,
  replay protection, MCP attribution and post-commit inventory/history refresh.
- [x] Fix the OAuth MCP challenge so enabled read/write categories are requested;
  existing tokens still require explicit reauthorization for `mcp:write`.
- [x] Browser-prove Claude sees and executes enabled writes after reauthorization.
- [x] Show OAuth/direct MCP client names in History while retaining the backing
  user ID for authority/filtering; classify MCP stock movements as MCP and hydrate
  older matching MCP business audits without rewriting stored history.
- [x] Make copied-production write-intent regressions fixture-owned rather than
  assuming production has no legitimate MCP write evidence.
- [x] Browser approve and checkpoint the combined Patch 756-758 source.

Next Chat 26 work:
1. Add a separately safeguarded inventory metadata edit/correction tool only by
   reusing the existing canonical edit service and exact state-drift semantics.
2. Add delete/restore MCP operations only if recycle-bin, dependency, reservation
   and typed/exact-confirmation safeguards can remain at least as strict as the UI.
3. Add the dedicated Settings user/role-management UI when prioritized.
4. Run final public-alpha accessibility, security, responsive, backup/restore,
   REST/OpenAPI and MCP regression/hardening and checkpoint the release candidate.

Notifications & Messaging remain post-v1. Planned Chat 26 boundary remains Patch
767.

<!-- PARTPILOT:PATCH761_MCP_METADATA_UPDATE_ROADMAP -->
### Patch 761 — guarded inventory metadata editing complete

Completed in Chat 26:
- [x] Add data-only `0021_mcp_inventory_part_metadata_update`, preserving all
  existing mutable tool-policy values and defaulting only the new edit permission
  off.
- [x] Expand the MCP catalogue to six read + six safeguarded write tools.
- [x] Add `update_part_metadata` on the canonical typed metadata service with a
  complete explicit replacement contract and no stock quantity parameters.
- [x] Preview exact before/after metadata plus catalogue/template dependencies;
  reject metadata/dependency drift without coupling confirmation to unrelated
  stock-only changes.
- [x] Preserve confirmation/idempotency/replay, Operator+ role, `mcp:write`,
  global/client ceilings, MCP client attribution and post-commit live invalidation.
- [x] Browser-prove the Claude flow, zero stock movements, unchanged 12/0 stock,
  exact metadata replacement and History attribution.
- [x] Correct the complete-smoke package assertion so the one-time 0005 migration
  backfill is not frozen against legitimate later free-text package values.
- [x] Checkpoint the approved source without rewriting legitimate live MCP test
  inventory, OAuth, audit or write-intent evidence.

Next Chat 26 work:
1. Inspect existing part soft-delete/restore/purge dependency and reservation
   contracts before deciding the minimum honest MCP delete/restore catalogue.
2. Add delete/restore only if the MCP preview/confirmation is at least as strict as
   the existing UI/API safety model; keep permanent purge separately reviewed.
3. Add the dedicated Settings user/role-management UI when prioritized.
4. Run final public-alpha accessibility, security, responsive, backup/restore,
   REST/OpenAPI and MCP regression/hardening before the planned Patch 767 boundary.

<!-- PARTPILOT:CHAT26_BOUNDARY_ROADMAP:V768 -->
### Patch 768 — recovered Chat 26 lifecycle/History checkpoint and boundary

Recovery note:
- [x] Patch 767 was consumed pre-write because its origin check expected GitHub HTTPS
  syntax while the verified repository uses the equivalent SSH origin. No source,
  index, documentation, database or deployment write occurred. Patch 768 corrects
  only that boundary prerequisite and records the immutable failure evidence.

Completed in Chat 26:
- [x] Guard stock adjustment with canonical stock invariants, confirmation,
  idempotency/replay, drift rejection and MCP attribution.
- [x] Guard canonical part creation with normalized catalogue/template dependency
  snapshots and post-commit live refresh.
- [x] Guard complete typed metadata replacement without permitting stock changes.
- [x] Add reversible `soft_delete_part` + `restore_part` on the existing recycle-
  bin services while preserving stock, reservations, fields, movements and History.
- [x] Keep permanent purge/hard delete outside the MCP catalogue.
- [x] Advance the data-safe MCP permission migrations through
  `0022_mcp_inventory_part_lifecycle`; current catalogue is six read + eight
  safeguarded write tools (14 total).
- [x] Preserve connected MCP client identity in History while retaining the backing
  user as authorization authority.
- [x] Browser-prove Claude lifecycle preview/confirm/replay and no-purge exposure.
- [x] Fix History intermediate-width column clipping with an aligned horizontal
  register scroller while preserving the <=680px card layout.
- [x] Browser-approve the combined lifecycle + responsive History source and
  checkpoint it at the Chat 26 boundary.

Next chat:
- **Title:** `Chat 27: User Management UI and Public Alpha Release Candidate`
- **Patch range:** `769-793`
- **First patch:** `769`
- **Planned boundary:** `793`

Chat 27 implementation order:
1. Build the dedicated Settings user/role-management presentation on the already
   enforced Patch 733 Owner/Administrator/Operator/Viewer backend boundary. Keep
   create/access-change/disable/reactivate/force-reset/session-revoke/delete
   actions explicit and preserve last-active-Owner/self-protection semantics.
2. Browser-test user management across desktop/intermediate/mobile widths and
   relevant role ceilings without broad cleanup of real users/sessions.
3. Run the final public-alpha accessibility, security, responsive, backup/restore,
   REST/OpenAPI, MCP OAuth/direct-auth/tool-permission/write and live-sync
   regression sweep against copied production data.
4. Resolve only release-blocking findings, then produce the public-alpha release
   candidate checkpoint and durable handoff.

Permanent inventory purge remains intentionally separate from MCP. Notifications
& Messaging remain post-v1. Live database/settings/OAuth/client/tool-policy values
remain mutable state and must not be frozen as patch prerequisites.

<!-- PARTPILOT:USER_MANAGEMENT_PRIMARY_OWNER_ROADMAP:V776 -->
### Patch 776 — user management + Primary Owner checkpoint

Completed in Chat 27:
- [x] Add a dedicated responsive Settings Users & Roles workspace on the existing
  backend authorization boundary.
- [x] Hydrate the authenticated Owner/Administrator/Operator/Viewer role through
  the frontend auth model and display the actual account role.
- [x] Reserve `owner` permanently for the first-init account at request-schema,
  service, frontend and restore-validation boundaries; no later account can be
  created/promoted to Owner and the Primary Owner cannot be demoted/disabled/
  permanently deleted.
- [x] Hide Settings workspaces a role cannot use and suppress their restricted
  background administrative fetches. Operator/Viewer retain Account + API access;
  Administrator additionally sees Users/Preferences/MCP/Data, with restore/reset
  remaining Primary-Owner-only.
- [x] Redesign Users into a readable roster + focused Add/Manage dialogs while
  keeping create, role change, disable/reactivate, password reset, session revoke
  and permanent delete explicit.
- [x] Browser-test desktop/intermediate/mobile layout and role ceilings, then
  remove the redundant `Initial account` visual badge while preserving the
  `Primary Owner` role/protected state.
- [x] Keep the approved application source uncommitted until browser approval and
  checkpoint it separately in Patch 776.

Final V1/public-alpha work:
1. Run the complete accessibility/security/responsive/backup-restore/REST-OpenAPI/
   MCP OAuth/direct-auth/tool-permission/write/live-sync regression against copied
   production data and the approved deployment.
2. Investigate the pre-existing restore-commit readiness/drain smoke failure that
   reproduces on the Patch 773 baseline; fix it only if it represents a real
   release blocker rather than stale harness behavior.
3. Resolve only release-blocking findings, then create the public-alpha release
   candidate checkpoint and durable Chat 27 handoff.

Permanent inventory purge remains outside MCP. Notifications & Messaging remain
post-v1. Live DB/settings/OAuth/client/tool-policy values remain mutable state and
must not be frozen as checkpoint prerequisites.


<!-- PARTPILOT:PUBLIC_ALPHA_AUTOMATED_REGRESSION_ROADMAP:V777 -->
### Patch 777 — automated public-alpha regression gate

Completed in Chat 27:
- [x] Rebuild the clean Patch 776 source canonically and reproduce the exact
  browser-approved runtime image `sha256:a6b6cfa6933c4d98a7b936e5f8cf9257cec7309956cea0828a941fdcf8530e38`.
- [x] Run all 44 current release smoke invocations on separate copied-production
  databases, preserving live data and mutable MCP permission values; use a copied
  avatar fixture for the full custom-avatar flow and OAuth-admin `--check-only`
  where the historical full-flow fixture freezes old external-client rows.
- [x] Exclude only the superseded `mcp_direct_auth_smoke_test` migration fixture,
  which freezes Alembic 0015; current direct-auth API/named/transport smokes pass.
- [x] Re-run backup/validation/commit/bootstrap restore coverage with the canonical
  `PARTPILOT_RESTORE_SUPERVISOR_CONTRACT=compose-restart-v1` environment.
- [x] Confirm the earlier restore-commit readiness/drain failure was an invocation
  error in the rehearsal harness rather than a product regression; no source fix is
  required.
- [x] Verify health, protected routes, SPA routes, OpenAPI role boundaries, Primary
  Owner integrity, runtime markers, Alembic and SQLite integrity without redeploying.

Remaining public-alpha gate:
1. Browser-level accessibility/responsive sweep across the major workspaces and
   role-hidden Settings surfaces.
2. Real external-client OAuth/direct-MCP verification, including tool discovery,
   permission ceilings and at least one safeguarded write preview/confirmation.
3. Fix only genuine release blockers, then checkpoint the public-alpha release
   candidate and complete the Chat 27 durable handoff.

<!-- PARTPILOT:PUBLIC_ALPHA_RELEASE_POLISH_ROADMAP:V786 -->
### Patch 786 — browser-approved public-alpha release polish checkpoint

Completed in Chat 27:
- [x] Remove the redundant Dashboard Stock alerts launcher/dialog while preserving
  the live-synced operational layout.
- [x] Keep Projects and Reservations Updated timestamps reachable at intermediate
  widths with aligned horizontal register scrolling and unchanged mobile cards.
- [x] Deep-link History Part-related records directly into the matching Inventory
  Part details drawer.
- [x] Move generated API/MCP/OAuth Copy controls inside their fields and retain
  integrated Show/Hide for secrets.
- [x] Redesign MCP Settings into Server, Capabilities, Connections and Advanced
  access without changing authorization, autosave, live-sync or credential
  lifecycle semantics.
- [x] Extend the same grouped hierarchy across Account, Users, Preferences, API and
  Data while keeping specialized controls intact.
- [x] Normalize built-in avatar selectors to fixed 46 x 46 px square choices.
- [x] Remove misleading sequential Settings number badges and replace them with 16
  restrained semantic SVG landmarks; optically center the Connections glyph only.
- [x] Browser-approve the complete Patch 779-785 release-polish source.
- [x] Verify real Claude OAuth tool discovery and guarded metadata write behavior;
  classify the Hermes event-loop failure as client-side after the public Part Pilot
  MCP endpoint succeeds from inside the Hermes container.

Remaining Chat 27/public-alpha work:
1. Create the final public-alpha release-candidate durable handoff/documentation and
   close the planned Chat 27 boundary no later than Patch 793.
2. Fix only genuinely new release blockers found before that boundary.
3. Keep permanent inventory purge outside MCP and Notifications & Messaging
   post-v1.

<!-- PARTPILOT:PUBLIC_ALPHA_RELEASE_HYGIENE_ROADMAP:V790 -->
### Patch 790 — recover public-alpha release-facing hygiene

Completed in this recovery:
- [x] Preserve the Patch 789 diagnostic as immutable evidence for the P787/P788
  pre-write failures.
- [x] Rebuild the five release-hygiene candidates from the exact post-P789 baseline.
- [x] Correct stale MCP/public-alpha README claims and add deployment-security
  guidance without changing runtime behavior.
- [x] Update only `.env.example`'s informational environment label/comments; leave
  the live `.env`, database, credentials and mutable MCP settings untouched.
- [x] Validate exact allowlist, diff cleanliness, canonical image equivalence,
  Alembic/SQLite, protected routes and the canonical fourteen-tool policy shape.

Remaining before the Chat 27 boundary:
1. Repository owner chooses an explicit software license, or intentionally keeps the
   repository source-available without one; do not auto-select licensing terms.
2. Complete final release-candidate handoff/boundary documentation by Patch 793.
3. Fix only genuinely new release blockers discovered before that boundary.


<!-- PARTPILOT:CHAT27_PUBLIC_ALPHA_BOUNDARY_ROADMAP:V796 -->
### Patch 796 — recover and complete Chat 27 public-alpha boundary

Completed:
- [x] Use the committed Patch 795 diagnostic as the authoritative recovery contract.
- [x] Rehearse all five mutable-fixture adapters before the complete release matrix.
- [x] Re-run all 44 release smoke invocations on independent copied-production databases.
- [x] Preserve all live direct clients and mutable MCP settings while normalizing only historical test copies.
- [x] Revalidate approved V785 image, Alembic `0022_mcp_inventory_part_lifecycle`, SQLite, Primary Owner/OpenAPI/SPA contracts and the fourteen-tool MCP policy shape.
- [x] Close Chat 27 with durable checkpoint, README/memory updates and `Chat_27_to_Chat_28_Handoff.md`.

Because recovery consumed patches beyond the planned 793 boundary, Chat 28 now starts
at Patch 797 and owns patches 797-821, with planned boundary 821. Its first priority is
public-alpha publishing/release packaging and release notes. Repository licensing remains
an explicit owner decision; do not add a license automatically. Notifications & Messaging
remain post-v1 unless explicitly reprioritized.
