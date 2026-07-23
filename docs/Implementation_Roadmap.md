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
