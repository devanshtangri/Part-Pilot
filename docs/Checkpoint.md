# Part Pilot Checkpoint

Generated: 2026-07-07
Purpose: Master checklist and project memory for Part Pilot. This file tracks every locked decision, V1 task, later feature, design polish item, and implementation concern discussed so far.

---

## 0. Project Snapshot

- Project name: Part Pilot
- Product type: Self-hosted electronics inventory manager
- Core differentiator: MCP integration for AI-aware inventory use
- Primary users: Hobbyists, makers, small labs, repair shops
- Main deployment: Docker Compose
- V1 user model: Single-user with login
- V1 app style: Premium, modern, dark-theme-first, mobile-friendly web app
- First milestone: Add IRFZ44N, set quantity/location, search it, reserve 2, consume 1, and see history

---

## 1. Locked Product Decisions

### 1.1 Name

- [x] Use **Part Pilot** as the project name.

### 1.2 Product Purpose

- [x] Prevent duplicate purchases by making inventory searchable and trustworthy.
- [x] Help users know whether they already own a part.
- [x] Help users know available, reserved, and out-of-stock quantities.
- [x] Help AI assistants understand available parts through MCP.

### 1.3 Target Users

- [x] Hobbyists
- [x] Makers
- [x] Small labs
- [x] Repair shops
- [x] Small technical teams
- [ ] Enterprise inventory support — not V1

### 1.4 Main USP

- [x] MCP plugin/server so AI chatbots can query inventory.
- [x] AI can suggest available parts during project planning.
- [x] AI can reserve/consume parts if enabled and confirmed in chat.

---

## 2. Tech Stack Decisions

### 2.1 Frontend

- [x] Use React.
- [x] Use Vite.
- [x] Use TypeScript.
- [x] Build fully responsive UI.
- [x] Design with PWA future compatibility in mind.
- [ ] Full PWA/offline support — later.

### 2.2 Backend

- [x] Use Python.
- [x] Use FastAPI.
- [x] Backend should expose REST API.
- [x] Backend should also expose MCP tools.

### 2.3 Database

- [x] Use SQLite for V1.
- [x] Use SQLAlchemy.
- [x] Use Alembic for migrations.
- [ ] PostgreSQL support — possible future.

### 2.4 Deployment

- [x] Docker Compose first.
- [x] Persistent `/data` volume.
- [x] Backups inside mounted volume by default.
- [ ] Windows `.exe` — later.
- [ ] Linux one-click installer — later.
- [ ] Home Assistant add-on — later.

---

## 3. UI/UX Decisions

### 3.1 Overall Feel

- [x] Modern webpage.
- [x] Premium feel.
- [x] Polished like an Apple-style product.
- [x] Must still feel like a useful inventory tool.
- [x] Dark theme first.
- [x] Light theme available in settings.
- [x] Mobile fully supported.
- [x] Smooth interactions and clean cards.
- [x] Avoid lifeless database/admin-panel feeling.

### 3.2 Visual Reference

- [x] Use POS/product dashboard style as structural inspiration only.
- [x] Do not copy the reference theme directly.
- [x] Use premium dark color scheme selected during design.

### 3.3 Sidebar

Sidebar items:

- [x] Dashboard
- [x] Inventory
- [x] Projects
- [x] Reservations
- [x] History
- [x] Part Manager
- [x] Settings

### 3.4 Dashboard

Dashboard should include:

- [x] Large universal search bar.
- [x] Quick action cards.
- [x] Low-stock cards.
- [x] Recent activity.
- [x] Inventory value summary.
- [x] Reservation/project summary.

Quick actions to consider:

- [x] Add Part
- [x] Add Stock
- [x] Create Project
- [x] Reserve Parts
- [x] Consume Parts
- [x] View Inventory
- [x] View History

### 3.5 Inventory View

- [x] Desktop: table view.
- [x] Mobile: card view.
- [ ] Optional view toggle — later or polish.

Desktop table fields:

- [x] Part number/display title
- [x] Name
- [x] Type
- [x] Available
- [x] Reserved
- [x] Total
- [x] Location
- [x] Unit price
- [x] Total value
- [x] Tags
- [x] Actions

Mobile card fields:

- [x] Part number/name
- [x] Available quantity
- [x] Reserved quantity
- [x] Location
- [x] Low-stock/out-of-stock warning
- [ ] Type if space allows
- [ ] Expandable view for price, tags, package, notes, custom fields

---

## 4. Authentication and First Setup

### 4.1 Login

- [x] V1 requires login.
- [x] V1 is single-user.
- [x] Use session tokens so user does not repeatedly log in.
- [x] Session should expire eventually.
- [ ] Multi-user permissions — later.

### 4.2 First-run Setup

Collect during setup:

- [x] Username
- [x] Password
- [x] Currency
- [x] Timezone
- [ ] Optional theme preference
- [ ] Optional backup frequency

---

## 5. Inventory Scope

### 5.1 Included in V1

- [x] Components
- [x] Modules
- [x] Connectors
- [x] Electromechanical parts
- [x] Motors
- [x] Actuators
- [x] Pumps/solenoids where relevant
- [x] Mechanical hardware such as nuts and bolts
- [x] Development boards

### 5.2 Excluded from V1

- [x] Tools
- [x] Consumables
- [x] 3D printed parts
- [x] Photos
- [x] Datasheets
- [x] Manuals
- [x] STEP files
- [x] 3D models
- [x] Symbols
- [x] Footprints
- [x] Import/export
- [x] QR/barcodes

---

## 6. Built-in Part Types

Initial V1 type list:

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
- [x] Module
- [x] Sensor
- [x] Custom

---

## 7. Part Manager

Part Manager should handle:

- [x] Built-in templates.
- [x] Custom part types.
- [x] Editing built-in templates.
- [x] Restoring built-in templates to defaults.
- [x] Custom field definitions.
- [ ] Possibly tag management later.
- [ ] Possibly reusable location management later.

---

## 8. Custom Fields

### 8.1 Supported Field Types

- [x] Text
- [x] Number
- [x] Boolean yes/no
- [x] Dropdown
- [x] URL
- [x] Unit-aware value

### 8.2 Units to Support Eventually

Electrical:

- [x] V
- [x] A
- [x] W
- [x] Ω
- [x] kΩ
- [x] MΩ
- [x] F
- [x] uF
- [x] nF
- [x] pF
- [x] H
- [x] mH
- [x] uH
- [x] Hz
- [x] kHz
- [x] MHz

Mechanical:

- [x] mm
- [x] cm
- [x] m
- [x] g

### 8.3 Example MOSFET Template

- [x] Channel type dropdown: N-channel/P-channel
- [x] Max voltage unit value
- [x] Max current unit value
- [x] RDS(on) unit value
- [x] Gate threshold voltage unit value
- [x] Logic-level boolean
- [x] Package field

### 8.4 Example Mechanical Hardware Template

- [x] Size
- [x] Length
- [x] Thread type
- [x] Material
- [x] Head type
- [ ] Quantity
- [ ] Location

---

## 9. Add Component Flow

### 9.1 Flow Order

- [x] Choose type first.
- [x] Enter part number/name second.
- [x] Fill custom/type-specific fields.
- [x] Enter quantity.
- [x] Enter optional location.
- [x] Enter optional pricing.
- [x] Enter notes/tags/aliases/purchase info.
- [x] Save.

### 9.2 Required Fields

- [x] Type required.
- [x] Quantity required.
- [x] Either name or part number required.
- [x] Location optional.
- [x] Price optional.

### 9.3 Name/Part Number Behavior

- [x] Part number optional.
- [x] Name optional only if part number exists.
- [x] Either name or part number required.
- [x] If part number exists, use it as primary display title.
- [x] If part number does not exist, use name as display title.
- [x] Add button/checkbox to keep name and part number the same.

### 9.4 No Quick Add

- [x] No quick-add mode in V1.

---

## 10. Create Part vs Add Stock

### 10.1 Conceptual Separation

- [x] Creating a part means creating a stock entry/component record.
- [x] Adding stock means restocking an existing component.
- [x] Creating a new part with initial quantity should create initial stock movement.

### 10.2 Add Stock Workflow

- [x] Add Stock should allow selecting existing parts.
- [x] Add Stock should allow multiple parts at once.
- [x] If searched part does not exist, user can create it without losing restock workflow.
- [x] New part creation during restock should return user to restocking flow.
- [x] Audit must distinguish new part creation from existing stock addition.

---

## 11. Locations

- [x] V1 uses simple location text.
- [x] Location field has autocomplete/dropdown with typing.
- [x] Previously used locations become suggestions.
- [x] Location is optional.
- [ ] Hierarchical room/cabinet/drawer model — later.

---

## 12. Search

### 12.1 Search Fields

Search should cover:

- [x] Part number
- [x] Name
- [x] Partial name
- [x] Value
- [x] Attributes
- [x] Aliases
- [x] Tags
- [x] Location
- [x] Notes
- [x] Custom fields
- [x] Package

### 12.2 Search Quality

- [x] Fuzzy/typo-tolerant search desired.
- [x] Search dialog opens from large search bar.
- [x] No results state should be polished.

### 12.3 Out-of-stock Search

- [x] In-stock results shown first.
- [x] Out-of-stock results shown in separate section.
- [x] If no in-stock result, show no available results and then Out of Stock section.
- [x] Out-of-stock search visibility toggleable from settings.

---

## 13. Quantity and Stock

### 13.1 V1 Quantity

- [x] Integer quantities only.
- [ ] Decimal quantities — later.
- [x] Length/weight/volume quantities — later.

### 13.2 Quantity Fields

- [x] Total/on-hand quantity.
- [x] Reserved quantity.
- [x] Available quantity.

Formula:

```text
Available = Total - Reserved
```

### 13.3 Consumption Rules

- [x] Consumption can include multiple parts.
- [x] Consumption project/name/reason is optional.
- [x] Consumption should not be allowed if available quantity is insufficient.
- [x] Show warning if requested quantity exceeds available quantity.

---

## 14. Out of Stock vs Deletion

### 14.1 Out of Stock

- [x] Part remains in database.
- [x] Part details remain.
- [x] Quantity is zero.
- [x] Can be restocked later.
- [x] Search can show it separately as out of stock.
- [x] Must not be confused with deletion.

### 14.2 Deletion

- [x] Actual deletion removes active component record.
- [x] Actual deletion removes active settings/details/search visibility.
- [x] Logs/audit history remain.
- [x] Deleted component snapshot remains in audit history.
- [x] Deletion is rare.
- [x] Deletion should be in danger/admin area.

---

## 15. Projects

### 15.1 Inclusion

- [x] V1 includes lightweight Projects.
- [x] Projects are not full project-management boards.

### 15.2 Project Fields

- [x] Name
- [x] Optional description
- [x] List of parts
- [x] Quantities
- [x] Status
- [x] Notes/reason
- [x] Created by manual/AI
- [x] Created/updated timestamps

### 15.3 Project Statuses

- [x] Draft
- [x] Reserved
- [x] Consumed
- [x] Cancelled

### 15.4 Project Behavior

- [x] Project cannot mix reserved and consumed items in V1.
- [x] Draft project can become Reserved.
- [x] Draft project can become Consumed.
- [x] Reserved project can be executed/converted to Consumed.
- [x] Cancelled project releases reservations if applicable.

---

## 16. Reservations

### 16.1 Behavior

- [x] Reservations reduce available quantity immediately.
- [x] Reservations can be created by UI.
- [x] Reservations can be created by MCP/AI if enabled.
- [x] Reservations can expire based on setting.
- [x] Expiry can be disabled.

### 16.2 Reservation Fields

- [x] Project/name label
- [x] Notes
- [x] Expiry date
- [x] Created by AI/manual
- [x] Status
- [x] Created date
- [x] Estimated value

### 16.3 Reservations Page

Reservations page should show:

- [x] Active reservations
- [x] Expired reservations
- [x] Consumed reservations
- [x] Cancelled reservations
- [x] Linked project
- [x] Reserved parts
- [x] Quantities
- [x] Created by manual/AI
- [x] Expiry
- [x] Actions: consume, cancel, extend, open project

---

## 17. Pricing and Currency

### 17.1 Price Fields

- [x] Unit price.
- [x] Total purchase price.
- [x] Quantity purchased.
- [x] Currency.
- [x] Purchase date.
- [x] Purchase link.
- [x] Optional price note/source.

### 17.2 Price Optionality

- [x] Price optional.
- [x] Missing-price alert when saving.
- [x] Missing-price alert toggleable in settings.

### 17.3 Currency

- [x] No hardcoded global default.
- [x] User selects currency during setup.
- [x] User selects timezone during setup.
- [x] One app-wide currency in V1.
- [ ] Per-part currency — V2.
- [ ] Live currency conversion — V2.

### 17.4 Inventory Value

Show:

- [x] Unit price.
- [x] Component total value.
- [x] Total inventory value.
- [x] Available inventory value.
- [x] Reserved inventory value.
- [x] Project estimated cost.

### 17.5 Historical Pricing

- [x] Project cost should use price snapshot at time part is added/reserved/consumed.
- [x] Current unit price should not rewrite historical project cost.

---

## 18. Low Stock

- [x] Low-stock warnings supported.
- [x] Threshold is per component only in V1.
- [x] Component has low-stock enabled setting.
- [x] Component has threshold value.
- [x] Dashboard should show low-stock warnings.

---

## 19. History and Audit

### 19.1 Logging Philosophy

- [x] Everything important logged forever.
- [x] Structured database logs, not plain log files as primary source.
- [x] Logs should be searchable/filterable.

### 19.2 Events to Log

- [x] Component created
- [x] Component edited
- [x] Component renamed
- [x] Component deleted
- [x] Stock added
- [x] Stock consumed
- [x] Stock adjusted
- [x] Reservation created
- [x] Reservation cancelled
- [x] Reservation consumed
- [x] Reservation expired
- [x] Project created
- [x] Project reserved
- [x] Project consumed
- [x] Project cancelled
- [x] Settings changed
- [x] Backup created
- [x] Backup restored
- [x] MCP action performed
- [x] Login/security events

### 19.3 History Views

- [x] All activity
- [x] Stock activity
- [x] Reservation activity
- [x] Project activity
- [x] Edit activity
- [x] MCP activity
- [x] Backup/settings activity

### 19.4 Undo

- [x] No undo from history in V1.
- [x] Restore from backups instead.

---

## 20. Backups

- [x] Automatic daily backups by default.
- [x] User can turn backups on/off.
- [x] User can configure frequency.
- [x] User can configure backup location later.
- [x] Default backup path: `/data/backups`.
- [x] Backup should be complete app snapshot.

Backup should include:

- [x] Database
- [x] Settings
- [x] MCP settings
- [x] Audit logs
- [x] Component templates
- [x] Custom fields
- [x] Config files
- [x] Uploaded files if added later

---

## 21. MCP

### 21.1 MCP Core

- [x] MCP is star feature.
- [x] MCP protected by API token.
- [x] MCP read tools enabled by default.
- [x] MCP write tools disabled by default until enabled.

### 21.2 Allowed MCP Actions

AI/MCP can:

- [x] Search inventory.
- [x] Read part details.
- [x] Read notes.
- [x] See reservations.
- [x] Reserve parts if enabled.
- [x] Consume parts if enabled.
- [x] Convert reservation/project to consumption if enabled.

AI/MCP cannot:

- [x] Add parts.
- [x] Edit parts.
- [x] Delete parts.

### 21.3 Confirmation

- [x] Reserve requires confirmation in AI chat.
- [x] Consume requires confirmation in AI chat.
- [x] No extra web-app confirmation required for V1.

### 21.4 Initial MCP Tool Ideas

- [ ] `search_parts`
- [ ] `get_part_details`
- [ ] `list_low_stock`
- [ ] `list_projects`
- [ ] `get_project`
- [ ] `create_project`
- [ ] `create_reservation`
- [ ] `consume_parts`
- [ ] `convert_reservation_to_consumption`
- [ ] `cancel_reservation`

---

## 22. V1 Exclusions / Later Features

### 22.1 Not V1

- [ ] Broken/partial parts
- [ ] Photos
- [ ] Datasheets
- [ ] Manuals
- [ ] STEP files
- [ ] 3D models
- [ ] Symbols/footprints
- [ ] Import/export
- [ ] CSV import/export
- [ ] Excel import/export
- [ ] DigiKey integration
- [ ] Mouser integration
- [ ] LCSC integration
- [ ] JLCPCB BOM import
- [ ] KiCad BOM import
- [ ] Supplier integrations
- [ ] Automatic currency exchange
- [ ] Multi-user accounts
- [ ] User roles/permissions
- [ ] Home Assistant add-on
- [ ] Desktop app
- [ ] QR/barcode labels
- [ ] Offline PWA mode
- [ ] Decimal quantities
- [ ] Wire length tracking
- [ ] Consumables tracking
- [ ] Full project-management tools

### 22.2 Future Broken/Partial Parts Design

- [ ] Broken parts should be item-level notes, not just quantity.
- [ ] Example: ESP32 with GPIO 15 broken but rest usable.
- [ ] AI may be allowed to see broken parts clearly marked.
- [ ] AI may suggest using partially broken part if broken feature does not affect project.

### 22.3 Future Import/Export

- [ ] CSV
- [ ] Excel
- [ ] KiCad BOM
- [ ] JLCPCB BOM
- [ ] DigiKey
- [ ] Mouser
- [ ] LCSC

### 22.4 Future Files

- [ ] Photos
- [ ] Datasheets
- [ ] Manuals
- [ ] STEP files
- [ ] Symbols/footprints

---

## 23. Database Areas to Design Next

Tables likely needed:

- [ ] users/settings
- [ ] sessions
- [ ] app_settings
- [ ] currencies/settings
- [ ] part_types
- [ ] custom_fields
- [ ] custom_field_values
- [ ] parts
- [ ] part_aliases
- [ ] tags
- [ ] part_tags
- [ ] locations
- [ ] stock_movements
- [ ] projects
- [ ] project_items
- [ ] reservations
- [ ] reservation_items
- [ ] audit_log
- [ ] backups
- [ ] mcp_tokens/settings

Need decide:

- [ ] Exact schema for price snapshots.
- [ ] Exact schema for out-of-stock behavior.
- [ ] Exact schema for deleted component snapshots.
- [ ] Exact schema for custom typed fields.
- [ ] Search indexing strategy.

---

## 24. API Areas to Design Next

API groups likely needed:

- [ ] Auth API
- [ ] Setup API
- [ ] Parts API
- [ ] Part Types API
- [ ] Custom Fields API
- [ ] Locations API
- [ ] Tags API
- [ ] Stock API
- [ ] Projects API
- [ ] Reservations API
- [ ] Search API
- [ ] History/Audit API
- [x] Settings API
- [ ] Backup/Restore API
- [ ] MCP API/tool layer

---

## 25. UI Screens to Design Next

Screens likely needed:

- [x] First-run setup
- [x] Login
- [ ] Dashboard
- [ ] Search dialog
- [ ] Inventory list/table
- [ ] Mobile inventory cards
- [ ] Component detail page/drawer
- [ ] Add Part flow
- [ ] Add Stock/restock flow
- [ ] Project list
- [ ] Project detail
- [ ] Create project
- [ ] Reservations page
- [ ] Consume parts flow
- [ ] History page
- [x] Part Manager
- [ ] Settings
- [ ] Backup/restore settings
- [ ] MCP settings
- [ ] Danger zone/delete flow

---

## 26. Design Polish Ideas

- [ ] Premium dark dashboard.
- [ ] Large command-palette-like search dialog.
- [ ] Smooth card expansion animations.
- [ ] Clear out-of-stock section in search.
- [ ] Polished empty states.
- [ ] Beautiful low-stock warning cards.
- [ ] Inventory value cards.
- [ ] Responsive mobile layout with thumb-friendly action buttons.
- [ ] Modern sidebar with active state.
- [ ] Subtle gradients or glow accents.
- [ ] Avoid childish/cartoon style.
- [ ] Avoid overly cyberpunk/terminal look.
- [ ] Make UI feel Apple-like but practical.

---

## 27. First Coding Milestone

Milestone 1 success criteria:

- [x] App runs in Docker.
- [x] User completes first setup.
- [x] User logs in.
- [ ] User creates IRFZ44N.
- [ ] User sets type MOSFET.
- [ ] User sets quantity.
- [ ] User sets location.
- [ ] User optionally sets price.
- [ ] User searches IRFZ44N.
- [ ] User opens detail view.
- [ ] User reserves 2.
- [ ] Available quantity reduces.
- [ ] User consumes 1.
- [ ] Quantity updates correctly.
- [ ] History shows creation, stock addition, reservation, consumption.

---

## 28. Recommended Next Work Order

- [x] Product discovery rounds complete.
- [x] V1 product specification created.
- [x] Checkpoint file created.
- [x] Create implementation roadmap.
- [x] Create database schema.
- [ ] Create API design.
- [ ] Create UI screen-by-screen plan.
- [ ] Create MCP tool contract.
- [x] Start repository/project scaffolding.

---

## 29. Open Questions Remaining

- [ ] Exact first color palette.
- [ ] Exact logo/icon direction.
- [ ] Exact unit list for custom fields.
- [ ] Exact default built-in template fields for every type.
- [ ] Exact session duration.
- [ ] Exact backup retention default.
- [ ] Whether Part Manager also manages tags/locations in V1.
- [ ] Whether reservations page and projects page should share UI components.
- [ ] Whether search should be implemented first with SQLite FTS or simple SQL + fuzzy helper.

---

## 30. Current Best Product Summary

Part Pilot is a Docker-first, self-hosted electronics inventory manager with a premium responsive web UI and MCP integration. It tracks components, modules, electromechanical parts, and mechanical hardware with searchable part numbers, names, tags, custom fields, locations, quantities, prices, reservations, projects, low-stock warnings, out-of-stock handling, structured audit history, and full app backups. Its main differentiator is allowing AI assistants to search inventory, understand what parts are available, reserve parts, and consume stock after confirmation.



---

## 31. Implementation Session Log

### 2026-07-07 — Phase 1 Skeleton Started

Status:

- [x] Phase 1 repository skeleton generated.
- [x] Backend FastAPI app skeleton added.
- [x] `/health` and `/api/health` routes added.
- [x] Basic settings loader added.
- [x] SQLAlchemy database connection setup added.
- [x] CORS configured for local frontend development.
- [x] React + Vite + TypeScript frontend shell added.
- [x] Routing, sidebar, placeholder dashboard, and placeholder pages added.
- [x] Basic frontend API client added.
- [x] Global dark theme variables added.
- [x] Docker Compose added with persistent `./data:/data` mapping.

Decision changes:

- No product decisions changed in this implementation step.

Phase boundary note:

- Authentication, first-run setup, parts tables, inventory APIs, search, projects, reservations, backups, and MCP remain intentionally unimplemented because they are outside Phase 1.

## Implementation Session Log — Configurable Docker Ports

- [x] Docker host/public port is configurable through `.env` using `PARTPILOT_HOST_PORT`.
- [x] Container/app port is configurable through `.env` using `PARTPILOT_CONTAINER_PORT`.
- [x] Default mapping is `7890:8000`.
- [x] Normal self-hosted same-origin Docker use should not require users to manually edit CORS origins when changing the public host port.
- [x] CORS configuration is mainly for development or separated frontend/backend deployments.
- [x] Port changes are deployment-level changes and require recreating/restarting the Docker container.

## Implementation Session Log — Phase 2 Database Foundation

- [x] Phase 2 database foundation started.
- [x] Added SQLAlchemy models for the initial V1 database tables.
- [x] Added first Alembic migration: `0001_database_foundation`.
- [x] Added idempotent built-in part type seeding through `python -m app.db.seed`.
- [x] Initial schema uses integer primary keys, UTC timestamps, SQLite-compatible checks, and JSON columns for flexible metadata/snapshots.
- [x] Quantity foundation stores total/on-hand and reserved quantities; available quantity remains computed as `total_quantity - reserved_quantity`.
- [x] Part validation begins at the database layer with a name-or-part-number check and a unique part number constraint.

## Implementation Session Log — Product Name Spacing

- [x] Product display name changed from `PartPilot` to `Part Pilot`.
- [x] User-facing UI/documentation should use `Part Pilot`.
- [x] Internal identifiers may continue using `partpilot` and `PARTPILOT_*` because spaces are unsuitable for package names, module names, database filenames, environment variable prefixes, and Docker identifiers.

## Implementation Session Log — Phase 2 Schema Hardening

- [x] Added Phase 2 schema-hardening migration `0002_schema_hardening`.
- [x] Added database indexes for common inventory/search/history access patterns.
- [x] Enabled SQLite foreign-key enforcement for runtime database connections.
- [x] Added SQLAlchemy model-level constraints for non-negative prices, quantities, status values, and audit/backup integrity.
- [x] Kept this step inside Phase 2 only: no API, UI, auth, MCP, or inventory workflows added.

## Implementation Session Log — Phase 2.3 Built-in Template Fields

- [x] Added default built-in custom field templates for electronics and mechanical part types.
- [x] Seed logic is idempotent and skips existing `part_type_fields` by `part_type_id + field_key`.
- [x] No UI, API, auth, MCP, reservation, or project behavior was added in this step.
- [x] This remains within Phase 2 database foundation work.

## Implementation Session Log — Phase 2.4 Default App Settings

- [x] Seed default app settings into `app_settings`.
- [x] Default display name is `Part Pilot`.
- [x] Default theme is dark.
- [x] Out-of-stock search section is enabled by default.
- [x] Missing-price warning is enabled by default.
- [x] Default backup path is `/data/backups`.
- [x] Default backup frequency is daily.
- [x] MCP is disabled by default.
- [x] MCP read tools are enabled by default once MCP is enabled.
- [x] MCP write tools are disabled by default.
- [x] First-run setup remains incomplete by default until Phase 3 setup flow creates the first user and required settings.

## Implementation Session Log — Phase 2 Database Smoke Tests

- Added backend database smoke test command: `python -m app.db.smoke_test`.
- Smoke test verifies database connectivity, Alembic head state, built-in part types, template fields, default app settings, SQLite foreign key enforcement, invalid part rejection, and valid sample part rollback.
- This remains Phase 2 database validation only; no API, UI, authentication, or inventory workflow behavior was added.

## Implementation Session Log — Phase 2.6 Backend DB Utilities

- Added reusable backend DB utilities before API development.
- Added text cleanup, lookup normalization, slug generation, location normalization, part display title, and available quantity helpers.
- Added typed constants for field types, movement types, sources, project statuses, reservation statuses, audit actor types, and backup statuses.
- Added app setting get/set helpers with bool/string convenience accessors.
- Extended the Phase 2 smoke test to validate these helpers.

---

## Implementation Session Log — Phase 2 Complete

- Phase 2 database foundation is complete and committed.
- Added and verified migrations through Alembic head `0002_schema_hardening`.
- Added 34 built-in part types.
- Added 153 built-in template fields.
- Added 17 default app settings.
- Added backend database constants, settings helpers, and utility helpers.
- Added database smoke test with checks for connectivity, foreign keys, migration head, seed data, constraints, rollback safety, and backend helpers.
- Phase 3 should start next with first-run setup and authentication.
- Before Phase 3 begins, verify local state with `git status --short`, `git log --oneline -8`, and `docker compose exec -T partpilot python -m app.db.smoke_test`.

---

## Implementation Session Log — Phase 3 Complete

- [x] First-run setup detects fresh and partially configured installations.
- [x] Owner account creation, password hashing, login, logout, session persistence, session expiry, and protected routes are implemented.
- [x] Default currency and timezone are persisted during setup.
- [x] Currency and timezone use selection controls; timezone labels include the current GMT offset.
- [x] Existing installations missing regional settings receive a finish-setup screen.
- [x] Responsive authentication/setup UI was reviewed and polished.
- [x] Temporary development database reset tooling was added for repeated first-run testing.

## Implementation Session Log — Phase 4 Read-only Part Type Foundation

- [x] Added authenticated read-only part type API endpoints.
- [x] Added a real Part Manager page replacing the placeholder.
- [x] Part Manager displays totals, search, built-in/custom filters, template versions, ordered fields, field types, units, options, and required status.
- [x] Extended smoke testing for the Phase 4 service and protected API.
- [ ] Custom type creation and template editing remain for the next Phase 4 batches.

---


## Implementation Session Log — Patch 066 Responsive Application Shell

- [x] Desktop content width expanded so information-heavy pages can use available space.
- [x] Mobile permanent sidebar replaced with a sticky top app bar and hamburger-triggered drawer.
- [x] Drawer closes through navigation, backdrop, close button, route change, and Escape.
- [x] Mobile account details and logout action are compact.
- [x] Shared page, card, typography, Part Manager, and Settings spacing is denser.
- [x] Part Manager remains read-only; no Phase 4 data behavior changed.


## Implementation Session Log — Patch 067 Custom Part Type Creation

- [x] Added authenticated custom part-type creation API.
- [x] Added validation for names, field keys, field types, dropdown options, and duplicate keys.
- [x] Added transactional persistence for custom templates and ordered template fields.
- [x] Added audit-log entry for custom type creation.
- [x] Added responsive Part Manager creation workspace with live preview.
- [x] Added field add/remove/reorder controls during creation.
- [x] Updated smoke coverage to create and roll back a temporary custom type.
- [x] Updated seed smoke validation to count built-in types only, allowing real custom types to exist.


## Implementation Session Log — Patch 085 Custom Part Type Editing UI

- [x] Added frontend PUT support for custom part-type updates.
- [x] Added an Edit custom type action for custom templates only.
- [x] Reused the focused modal for create and edit workflows.
- [x] Loaded persisted field IDs, order, options, units, and help text.
- [x] Added edit-aware modal title, guidance, header state, and save state.
- [x] Refreshed the selected template and version after successful updates.


## Implementation Session Log — Patch 089 Safe Custom Part Type Deletion

- [x] Added protected deletion for custom part types.
- [x] Kept all built-in templates undeletable.
- [x] Blocked deletion while any inventory part references the type.
- [x] Cascaded deletion to unused custom template fields.
- [x] Recorded deletion audit events with the full prior template snapshot.
- [x] Added a typed-name confirmation dialog and API error feedback.
- [x] Added deletion API smoke coverage.


## Implementation Session Log — Patch 093 Inventory Part Creation Backend

- [x] Added authenticated inventory part creation.
- [x] Added dynamic typed values based on the selected part type.
- [x] Validated required, dropdown, URL, numeric, boolean, and unit-aware fields.
- [x] Added base identifiers, quantity, unit price, purchase link, notes, and low-stock settings.
- [x] Added inventory list and detail endpoints.
- [x] Added part-created audit events.
- [x] Added full API smoke coverage with rollback cleanup.


## Implementation Session Log — Patch 094 Dynamic Add Part Modal

- [x] Added the Part Manager Add Part entry action.
- [x] Defaulted the form to the currently selected part type.
- [x] Rendered text, number, boolean, dropdown, URL, and unit-aware template controls.
- [x] Added base identifiers, quantity, unit price, purchase link, notes, and low-stock settings.
- [x] Added client-side validation and backend error feedback.
- [x] Added a viewport-constrained modal with a permanently visible action bar.
- [x] Added a successful-created-part confirmation state.


## Implementation Session Log — Patch 095 Manufacturer Catalogue

- [x] Added manufacturers as reusable first-class records.
- [x] Seeded common electronics manufacturers.
- [x] Added user-created manufacturers with normalized duplicate protection.
- [x] Linked inventory parts to manufacturers.
- [x] Backfilled compatible legacy manufacturer template values.
- [x] Added an inline manufacturer creator to Add Part.
- [x] Kept templates with a manufacturer field backward-compatible without showing a duplicate control.
- [x] Replaced the oversized success screen with a compact inventory receipt.

<!-- PATCH 131 PART DETAILS PACKAGE CHECKPOINT -->

---

## Implementation Checkpoint — Part Details and Package Catalogue

Checkpoint status: **browser approved and committed**

### Completed inventory browsing work

- [x] Stored Parts table backed by `GET /api/parts`.
- [x] Search across part name, part number, type, and manufacturer.
- [x] All / In stock / Low / Out stock filters.
- [x] Contextual Add Part action from the selected template.
- [x] Read-only part details drawer on desktop.
- [x] Responsive bottom-sheet details view on narrow screens.
- [x] Mouse, Enter, Space, Escape, close-button, and backdrop interactions.
- [x] Identification, manufacturer, package, stock, low-stock settings, price,
      purchase link, notes, timestamps, and template fields are visible.
- [x] Numeric custom-field values hide unnecessary decimal padding without
      rounding meaningful precision.

### Completed reusable package/form-factor work

- [x] Alembic head `0005_packages`.
- [x] First-class reusable `packages` catalogue.
- [x] Common electronics packages and module formats seeded.
- [x] Existing non-empty `Part.package` values backfilled.
- [x] Existing `Part.package` text storage preserved for compatibility.
- [x] Protected `GET /api/packages`.
- [x] Protected `POST /api/packages`.
- [x] Normalised duplicate package names rejected.
- [x] Package creation audit events.
- [x] Add Part package/form-factor dropdown.
- [x] Inline creation and immediate selection of new package options.
- [x] Custom package options remain reusable after reopening Add Part.

### Completed Part Manager polish

- [x] Template-field rows use a consistent minimum height.
- [x] Field labels and metadata are vertically centred.
- [x] Longer descriptions can expand naturally.

### Manual browser approval

- [x] Stored Parts rows open the details view.
- [x] Desktop and responsive close interactions work.
- [x] Numeric values display without padded decimal zeros.
- [x] Seeded package options appear in Add Part.
- [x] Custom package creation, selection, and reuse work.
- [x] Only one Package/form-factor control is shown.
- [x] Selected package values appear in part details.
- [x] Template-field row heights are visually consistent.

### Next major implementation slice

Continue Phase 4 with a small stock-movement and quantity-adjustment workflow:

1. Inspect the existing `StockMovement` model and current parts service.
2. Define add, remove, consume, and correction semantics.
3. Add an authenticated quantity-adjustment service and API.
4. Record quantity before/after, delta, reason, note, actor, and timestamp.
5. Add a compact adjustment action from part details.
6. Show recent movement history read-only.
7. Keep reservations, projects, metadata editing, and deletion separate.

The next chat starts with read-only **Diagnostic 132**.

<!-- PATCH 140 STOCK MOVEMENT CHECKPOINT -->

---

## Implementation Checkpoint — Stock Movement and Quantity Adjustment

Checkpoint status: **browser approved and committed**

### Completed backend workflow

- [x] Added authenticated quantity adjustment at
      `POST /api/parts/{part_id}/quantity-adjustments`.
- [x] Added authenticated recent history at
      `GET /api/parts/{part_id}/movements`.
- [x] Added explicit operations for add, remove, consume, and signed correction.
- [x] Mapped add to `restock`, consume to `consume`, and remove/correction to
      `adjust` movement records.
- [x] Rejected zero-value adjustments.
- [x] Rejected results below zero.
- [x] Rejected results below the part's reserved quantity.
- [x] Updated `Part.total_quantity`, `StockMovement`, and `AuditLog`
      atomically.
- [x] Recorded quantity before, quantity after, signed delta, movement type,
      reason, note, source, actor, snapshots, and timestamp.
- [x] Added complete smoke coverage with cleanup.

### Completed part-details workflow

- [x] Added a compact Adjust quantity form to the existing details drawer.
- [x] Added Add stock, Remove stock, Consume stock, and Correction actions.
- [x] Added optional reason and note fields.
- [x] Refreshed the selected part and Stored Parts list immediately after
      success.
- [x] Added recent read-only stock movement history.
- [x] Preserved the desktop drawer and narrow-screen bottom-sheet behaviour.
- [x] Reduced the Apply change button font weight so its label is not visually
      compressed.

### Manual browser approval

- [x] Add stock updates quantity and history.
- [x] Remove stock updates quantity and history.
- [x] Consume stock updates quantity and history.
- [x] Positive and negative corrections work.
- [x] Excessive removal is rejected.
- [x] Reserved stock cannot be crossed.
- [x] Details and history refresh immediately.
- [x] Desktop and narrow layouts remain usable.
- [x] Apply change button typography is visually consistent.

### Next major implementation slice

Continue Phase 4 with editing existing part metadata:

1. Inspect current create/detail schemas, service methods, routes, and dynamic
   field persistence.
2. Define update semantics for base fields and template-field values.
3. Preserve manufacturer and package catalogue behaviour.
4. Preserve duplicate part-number protection.
5. Record before/after audit snapshots.
6. Add one focused Edit details action from the existing drawer.
7. Keep quantity adjustment, deletion, reusable locations, reservations, and
   projects outside this slice.

The next chat starts with read-only **Diagnostic 141**.

<!-- PATCH 149 PART METADATA EDIT CHECKPOINT -->

---

## Implementation Checkpoint — Existing-Part Metadata Editing

Checkpoint status: **terminal verified, browser approved, committed**

### Completed backend workflow

- [x] Authenticated `PUT /api/parts/{part_id}`.
- [x] Dedicated metadata-update schema with forbidden extra fields.
- [x] Part type remains fixed.
- [x] Total and reserved quantities remain unchanged.
- [x] Name, part number, description, package, notes, unit price, purchase
      link, manufacturer, and low-stock settings can be updated.
- [x] Typed template-field values are replaced using existing validators.
- [x] Duplicate part-number and active-manufacturer safeguards are preserved.
- [x] Atomic `part.metadata_updated` before/after audit event.
- [x] Complete smoke coverage and cleanup.

### Completed frontend workflow

- [x] Focused prefilled Edit details modal.
- [x] Manufacturer and package catalogue reuse.
- [x] Typed template-field editing.
- [x] Quantity controls remain separate.
- [x] Details drawer closes before the editor opens.
- [x] Cancel, close, backdrop, Escape, and Save restore the drawer.
- [x] Open details and Stored Parts refresh after save.
- [x] Desktop and narrow layouts are supported.
- [x] Fixed-scale decimal padding is trimmed only for edit-input display.

### Manual browser approval

- [x] Existing values prefill correctly.
- [x] Metadata and typed values save correctly.
- [x] Quantities remain unchanged.
- [x] Duplicate and required-field safeguards work.
- [x] Drawer/editor transition works.
- [x] Padded zeroes are hidden without losing meaningful decimals.
- [x] Remaining workflow and responsive layouts work.

### Next implementation slice

Continue Phase 4 with soft deletion and restoration safeguards. Start with
read-only **Diagnostic 150** to inspect `is_deleted`, `deleted_at`, active-list
filters, restoration conflicts, retained stock history, audit conventions,
confirmation UI, and recoverable deleted-record entry points.

<!-- PATCH 154 PART SOFT DELETE RESTORE CHECKPOINT -->

---

## Implementation Checkpoint — Recoverable Part Deletion and Restoration

Checkpoint status: **terminal verified, browser approved, committed**

### Completed backend workflow

- [x] Added authenticated `DELETE /api/parts/{part_id}`.
- [x] Added authenticated `POST /api/parts/{part_id}/restore`.
- [x] Added authenticated `GET /api/parts/deleted`.
- [x] Reused the existing `is_deleted` and `deleted_at` model fields.
- [x] Required no migration.
- [x] Preserved total and reserved quantities.
- [x] Preserved typed field values.
- [x] Preserved stock movement history.
- [x] Preserved metadata, manufacturer, package, and part type.
- [x] Kept deleted rows hidden from normal list, detail, movement, metadata,
      and quantity workflows.
- [x] Kept the globally unique part number reserved while deleted.
- [x] Added conflict handling for repeated delete/restore transitions.
- [x] Added atomic `part.deleted` and `part.restored` audit events.
- [x] Added complete lifecycle smoke coverage and cleanup.

### Completed frontend workflow

- [x] Added a Delete action to part details.
- [x] Closed the details drawer before opening deletion confirmation.
- [x] Added clear recoverable-operation copy.
- [x] Added Deleted items discovery from Stored Parts.
- [x] Added searchable deleted-item recovery UI.
- [x] Added Restore actions with conflict/error feedback.
- [x] Refreshed active and deleted collections immediately.
- [x] Preserved existing metadata editing, stock adjustment, and movement
      history interactions.
- [x] Added responsive desktop and mobile behaviour.

### Manual browser approval

- [x] Delete confirmation opens cleanly.
- [x] Cancel, close, backdrop, and Escape restore the details drawer.
- [x] Deleted parts leave the active collection.
- [x] Deleted parts appear in Deleted items.
- [x] Deleted-item search works.
- [x] Restore returns the part to Stored Parts.
- [x] Metadata, quantities, template values, and movement history remain.
- [x] Edit details and quantity adjustment continue to work.
- [x] Desktop and narrow layouts are usable.

### Next implementation slice

Continue Phase 4 with reusable location management.

Start with read-only **Diagnostic 155** to inspect:

1. Existing `Location` model fields and constraints.
2. Current `Part.location_id` usage.
3. Location create/list/edit/delete service gaps.
4. Safe deletion behaviour when locations are in use.
5. Inventory creation/edit integration points.
6. Location filtering and details-display targets.
7. Smoke-test cleanup patterns.
8. Existing settings and catalogue UI patterns.

The first implementation after the diagnostic should remain narrow and must
not combine locations with reservations, projects, or dashboard work.

<!-- PATCH 164 REUSABLE LOCATION WORKFLOW CHECKPOINT -->

---

## Implementation Checkpoint — Reusable Location Assignment

Checkpoint status: **terminal verified, browser approved, committed**

### Protected location catalogue

- [x] Added authenticated location list/create/update/delete endpoints.
- [x] Reused the existing `Location` model and `Part.location_id`.
- [x] Required no migration.
- [x] Added normalised duplicate-name protection.
- [x] Added optional location notes.
- [x] Added total, active-part, and deleted-part usage counts.
- [x] Protected locations referenced by active or deleted parts with HTTP 409.
- [x] Allowed safe deletion of genuinely unused locations.
- [x] Added `location.created`, `location.updated`, and `location.deleted`
      audit events.
- [x] Committed independently as `Add reusable location catalogue API`.

### Part creation and metadata editing

- [x] Added optional `location_id` to part creation and metadata updates.
- [x] Added `location_id` and `location_name` to active and deleted part
      responses.
- [x] Validated selected locations during creation and editing.
- [x] Added one shared Location selector to Add Part and Edit details.
- [x] Added inline reusable-location creation.
- [x] Added existing-location preselection.
- [x] Added location change and clearing through `Not specified`.
- [x] Added location to the Part Added confirmation.
- [x] Added location to creation, metadata, deletion, and restoration audit
      snapshots.
- [x] Confirmed location changes do not alter quantities or create stock
      movements.
- [x] Confirmed manufacturer, package, quantity, deletion, and restoration
      workflows remain functional.

### Browser and responsive approval

- [x] Existing reusable locations load in Add Part and Edit details.
- [x] Inline location creation selects the new record.
- [x] Location assignment persists.
- [x] Location changes persist.
- [x] Location clearing persists.
- [x] Location action buttons match the Part Pilot control hierarchy.
- [x] Mobile Delete, Edit details, and Close actions are visible and usable.
- [x] Mobile action labels remain on one line.
- [x] The redundant mobile footer helper text is hidden.
- [x] Desktop behaviour remains intact.

### Overall roadmap estimate

**Part Pilot V1 is approximately 52% complete.**

This is a roadmap-wide working estimate, not a Phase 4-only percentage.

### Next implementation slice

Continue with **Stored Parts location display and filtering**:

1. Inspect exact inventory row/card and filter-state targets.
2. Add optional protected `location_id` filtering to active parts.
3. Show location in desktop rows and responsive cards.
4. Show location in part details.
5. Add a reusable location filter without replacing part-type filtering.
6. Preserve deleted-item, metadata-edit, quantity, and lifecycle behaviour.
7. Preflight every browser-test transformation in memory before source writes.

<!-- PATCH 173 STORED PARTS LOCATION FILTER CHECKPOINT -->

---
## Implementation Checkpoint — Stored Parts Location Display and Filtering

Checkpoint status: **terminal verified, browser approved, committed**

### Completed backend filtering

- [x] Diagnostic 166 mapped the exact route, service, client, smoke-test, and
      responsive UI targets without changing source.
- [x] Added optional positive `location_id` filtering to authenticated
      `GET /api/parts`.
- [x] Applied the filter consistently to collection totals and paginated rows.
- [x] Preserved part-type filtering, active-record filtering, pagination, and
      deleted-part exclusion.
- [x] Preserved unassigned parts in the unfiltered collection.
- [x] Added `locationId` support to the frontend parts client.
- [x] Added complete authenticated smoke coverage for pagination, combined
      filters, missing numeric locations, invalid IDs, location serialization,
      unassigned parts, and soft-deleted rows.
- [x] Committed independently as `Add Stored Parts location filtering API`.

### Completed Stored Parts workflow

- [x] Added an **All locations** selector backed by the reusable location
      catalogue.
- [x] Selecting a location reloads the active collection through the backend
      filter instead of filtering an incomplete client-side page.
- [x] Added location names to Stored Parts text search.
- [x] Added location-aware result counts.
- [x] Added location to desktop inventory rows.
- [x] Added location to Part Details.
- [x] Added correct empty-state behaviour for selected locations with no parts.
- [x] Clear filters returns the view to **All locations**.
- [x] Added desktop, tablet, and mobile toolbar styling.
- [x] Preserved stock filtering, metadata editing, quantity adjustment,
      movement history, deletion, restoration, manufacturer, and package
      workflows.

### Manual browser approval

The user’s Patch 171 browser-test response was exactly:

```text
everything pass
```

The approved checks covered location selection, filtered results, count text,
location-name search, clear filters, table display, details display, and
responsive toolbar usability.

### Overall roadmap estimate

**Part Pilot V1 is approximately 53% complete.**

This remains a roadmap-wide working estimate. Dashboard completion, global
search behaviour, reservations, projects, settings, backups, MCP, history
browsing, accessibility, and public-alpha work remain.

### Next implementation slice

Continue with **low-stock and settings-driven out-of-stock behaviour**.

Start the next chat with read-only **Diagnostic 174** to inspect:

1. Existing low-stock calculations and per-part threshold fields.
2. Current dashboard placeholders and data-loading boundaries.
3. Existing app-setting storage and missing protected settings APIs.
4. The locked out-of-stock search/grouping decision.
5. Stored Parts, dashboard, and future universal-search integration points.
6. Empty, loading, error, and responsive UI patterns.
7. Smoke-test cleanup conventions.
8. A narrow implementation order that avoids combining reservations,
   projects, backups, or MCP work.

The diagnostic must not modify application source.

<!-- PARTPILOT:DASHBOARD_LOW_STOCK_CHECKPOINT:START -->
## Dashboard and out-of-stock grouping checkpoint

**Status:** complete, automated verification passed, browser approval received,
committed, and pushed through Patch 197.

### Completed

- Added the authenticated dashboard low-stock presentation.
- Added dashboard loading, failure, empty, refresh, count, severity,
  threshold, location, and navigation states.
- Active parts with available stock at or below zero appear as out of stock
  even when no low-stock threshold was configured.
- Positive-stock low alerts continue to require an enabled threshold that is
  being reached.
- Added typed frontend contracts and client support for
  `search.show_out_of_stock_section`.
- Added an Inventory Search control on the Settings page.
- Persisted setting changes through the protected backend API.
- Preserved the explicit In stock, Low, and Out filters.
- With All selected and grouping enabled, positive-stock results stay in the
  normal Stored Parts table while matching zero-stock parts appear in a
  dedicated Out of stock section.
- Disabling grouping hides only the separate section; the explicit Out filter
  remains available.
- Search and location filtering apply consistently to both normal and
  out-of-stock result groups.
- Aligned the out-of-stock section width with the main Stored Parts table.
- Preserved part details, quantity updates, deletion/restoration, template
  management, and database-reset workflows.

### Verification

- Docker image build: passed.
- Deployment: passed.
- Alembic head `0005_packages`: passed.
- Complete backend smoke suite: passed.
- Protected search-settings and low-stock routes: passed.
- Dashboard, Settings, and Part Manager SPA routes: passed.
- Deployed frontend marker verification: passed.
- Desktop and responsive browser review: approved.
- Settings persistence, grouping enabled/disabled, explicit Out filtering,
  search, location filtering, and row interaction: approved.

### Current repository state after this checkpoint

The dashboard stock-alert and Stored Parts out-of-stock grouping work is
complete and published. The next implementation batch should be selected from
the remaining Phase 4 roadmap after a narrow repository and documentation
inspection.
<!-- PARTPILOT:DASHBOARD_LOW_STOCK_CHECKPOINT:END -->

<!-- PARTPILOT:INVENTORY_PAGE_MODE_CHECKPOINT:START -->
## Focused Inventory page checkpoint

**Status:** Patch 202 implemented the focused Inventory mode, Patch 203
committed and pushed it, Patch 206 completed the narrow mobile status-pill
fix, the user explicitly approved the browser test, and Patch 207 checkpoints
and publishes the completed batch.

### Completed

- Replaced the obsolete `/inventory` placeholder with the existing live
  Stored Parts workflow.
- Added a typed `inventoryOnly` mode to `PartManager`.
- Preserved one source of truth instead of duplicating inventory logic.
- The `/inventory` route hides part-type statistics, template search,
  template lists, custom-type controls, and template-management actions.
- Added an Inventory-toolbar **Add part** action.
- Preserved the normal `/part-manager` template-management screen and its
  contextual Add Part action.
- Preserved inventory search, location filtering, All/In stock/Low/Out
  filtering, settings-driven out-of-stock grouping, part details, stock
  adjustment, movement history, metadata editing, deletion, restoration, and
  responsive table behaviour.
- Preserved the approved out-of-stock section width alignment.
- Kept the Inventory header part-type count pill content-width on screens up
  to 620 px.
- Restored comfortable mobile vertical padding, line height, and minimum
  height without changing the approved desktop presentation.
- Avoided any Inventory data, behaviour, or workflow changes.

### Verification

- Patch 206 in-memory transformation and exact one-file change set: passed.
- Docker image build and deployment: passed.
- Alembic head `0005_packages`: passed.
- Complete backend smoke suite: passed.
- Protected inventory, part-type, and location routes: passed.
- Dashboard, Inventory, Part Manager, and Settings SPA routes: passed.
- Minification-safe deployed Patch 194, Patch 202, and Patch 206 marker
  verification: passed.
- Desktop browser review: approved.
- Narrow mobile browser review: approved.
- Mobile pill width, padding, line height, and alignment: approved.
- Inventory and Part Manager regression checks: approved.

### Failed attempts retained in history

- Patch 204 failed safely during read-only durable-document preflight and did
  not touch the working tree.
- Patch 205 applied and verified the intended CSS, but its source-form bundle
  marker check did not account for Vite minification; it restored source and
  deployment safely.
- Patch 206 corrected only the verifier, completed all automated checks, and
  retained the same narrow CSS fix.

### Repository state after this checkpoint

The focused Inventory page and its mobile header polish are complete,
browser-approved, committed, and pushed. Continue from the remaining Phase 4
roadmap using the next smallest independently verifiable workflow.
<!-- PARTPILOT:INVENTORY_PAGE_MODE_CHECKPOINT:END -->

<!-- PARTPILOT:UNIVERSAL_SEARCH_BACKEND_CHECKPOINT:V216 -->
## Universal-search backend foundation checkpoint

**Status:** Patch 213 implemented and verified the backend search contract.
Patch 215 made its numeric custom-field smoke fixture deterministic and passed
the complete verification suite. Patch 216 commits and pushes the independently
verified backend batch.

### Implemented

- Added an optional, protected `search` parameter to `GET /api/parts`.
- Preserved existing part-type and location filters.
- Preserved accurate `total`, `limit`, and `offset` pagination metadata.
- Excluded soft-deleted parts from active search results.
- Added case-insensitive partial matching across:
  - part number;
  - name;
  - description;
  - package;
  - notes;
  - part type name and description;
  - manufacturer;
  - location;
  - aliases;
  - tags;
  - custom-field keys and labels;
  - custom text, numeric, JSON, unit, and boolean values.
- Treated SQL wildcard characters as literal search text.
- Used correlated existence queries to avoid duplicate part rows when several
  searchable attributes match.
- Ordered available parts before zero-available-stock parts.
- Added deterministic exact/prefix relevance and recency ordering.
- Added exhaustive authenticated smoke coverage.
- Stabilised numeric-field search testing with `-7319.25`, avoiding
  random large-decimal formatting differences during SQLite text casting.

### Real-inventory safety

Patch 213 and Patch 215 recorded the existing inventory before testing and
isolated fixture queries to a temporary part type. The snapshots reported
eight active parts and one deleted part. Temporary fixtures were removed after
testing, and the user's inventory was not modified.

### Verification

- Python compilation: passed.
- Exact three-file source set: passed.
- `git diff --check`: passed.
- Docker build and deployment: passed.
- Alembic head `0005_packages`: passed.
- Complete backend smoke suite: passed repeatedly after fixture stabilisation.
- Search coverage across all supported fields: passed.
- Stable numeric custom-field matching: passed.
- Filter composition and pagination: passed.
- Duplicate suppression: passed.
- Deleted-record exclusion: passed.
- Available-first ordering: passed.
- Protected API checks: passed.
- SPA route regression checks: passed.
- Deployed Patch 213 and Patch 215 backend markers: passed.

### Failed attempts retained in history

- Patch 210 failed safely because a format-sensitive source anchor was stale.
- Patch 211 implemented the feature but used a common `IRFZ44N` smoke query
  that also matched a real inventory record.
- Patch 212 isolated tests from real inventory but still treated a shared
  temporary location as a one-result field.
- Patch 213 corrected the shared-field expectation and passed completely.
- Patch 214 safely aborted its checkpoint when a fresh random billion-scale
  decimal lost trailing precision during SQLite text casting.
- Patch 215 replaced that unstable fixture with deterministic `-7319.25` and
  passed the complete suite.

### Next implementation boundary

The backend contract is complete and publishable. The next batch should add a
typed frontend `search` option and a focused Dashboard universal-search
experience. Keep Inventory migration from client-only filtering as a separate
small browser-test batch if combining it would make review too broad.

<!-- PARTPILOT:DASHBOARD_UNIVERSAL_SEARCH_CHECKPOINT:V224 -->
## Dashboard universal-search frontend checkpoint

**Status:** Browser approved through Patch 223. Patch 224 commits and pushes
the complete frontend batch.

### Implemented

- Replaced the Dashboard search placeholder with a real universal-search
  launcher and modal workspace.
- Added typed `search` support to the frontend parts client.
- Added 280 ms debounced live search.
- Added stale-response invalidation so older requests cannot replace newer
  results.
- Added loading, error, empty, available, hidden-out-of-stock, and out-of-stock
  states.
- Respected the protected `show_out_of_stock_section` preference.
- Added selected-result details for identity, quantities, location, package,
  notes, description, and custom fields.
- Added `/` keyboard launch and `Escape` close behaviour.
- Added a geometrically centred SVG close icon.
- Rendered Available only when available matches exist.
- Rendered Out of stock only when visible out-of-stock matches exist.
- Preserved the hidden-results settings notice.
- Separated Available and Out of stock into visually distinct teal/red cards.
- Compacted mobile Dashboard summary cards.
- Redesigned mobile low-stock rows as native compact cards.
- Preserved the existing Stored Parts search for a later migration batch.

### Browser approval

The user approved:

- desktop and mobile live search;
- Clear behaviour;
- Available-only results;
- Out-of-stock-only results;
- mixed results;
- no-match states;
- hidden out-of-stock preference behaviour;
- responsive Dashboard cards;
- responsive low-stock inventory;
- centred close icon;
- final separated stock-section design.

### Verification

- Frontend build and Docker deployment: passed.
- Alembic head `0005_packages`: passed.
- Complete backend smoke suite: passed.
- Protected search APIs: passed.
- SPA route regressions: passed.
- Deployed frontend markers: passed.
- Deployed backend search markers: passed.
- `git diff --check`: passed.

### Next implementation boundary

Migrate Stored Parts from client-only filtering over the loaded page to the
backend universal-search contract. Keep that as a separate browser-test batch
so Dashboard search remains an independently reviewable checkpoint.

<!-- PARTPILOT:CHAT9_BOUNDARY_POLICY:V225 -->
## Chat 9 boundary

- Patch 225 is the final Python file of Chat 9.
- The next chat title is `Chat 10: Stored Parts Server Search Migration`.
- Chat 10 starts with Patch 226.
- Patch 250 is the final Python file of Chat 10.
- Every patch number divisible by 25 is a mandatory final patch for its chat and creates the next handoff and starting prompt.
- If a boundary patch fails, no higher-numbered Python file is issued in the same chat.
- Durable workflow instructions are stored in `docs/Part_Pilot_Project_Memory.txt`.
- The handoff is stored in `docs/Chat9_to_Chat10_Handoff.md`.
- The ready-to-paste prompt is stored in `docs/Chat10_Starting_Prompt.txt`.

<!-- PARTPILOT:STORED_PARTS_SERVER_STOCK_FILTER:V231 -->
## Chat 10 checkpoint — server stock-status collection contract

Patch 229 completed and automatically verified the backend prerequisite for
Stored Parts server search:

- `GET /api/parts` accepts `stock_status=all|in|low|out`;
- stock status composes with universal search, part-type and location filters;
- collection totals and pagination are calculated after all active filters;
- deleted parts remain excluded and duplicate suppression is preserved;
- available rows precede out-of-stock rows for ordinary collection requests;
- invalid stock modes return HTTP 422;
- Alembic remains at `0005_packages`;
- the complete smoke suite, protected API checks, SPA routes and deployed
  markers passed;
- real inventory data was unchanged by verification.

Patch 231 records and pushes this backend checkpoint. The next implementation
batch should migrate the Stored Parts client contract, then add bounded
pagination, a part-type filter, debounce and stale-response protection while
preserving `inventoryOnly` and all existing part workflows.

<!-- PARTPILOT:STORED_PARTS_SERVER_SEARCH_FRONTEND:V234 -->
## Chat 10 checkpoint — Stored Parts server-search requests

Patch 233 completed automated verification and received explicit browser
approval on both `/inventory` and `/part-manager`.

Verified behaviour:

- Stored Parts now sends the debounced search text to backend universal search;
- search debounce is 280 ms;
- request sequencing prevents stale responses from replacing newer results;
- `stock_status=all|in|low|out` is sent through the typed frontend client;
- the old five-field client-side query matcher was removed;
- Available and Out of stock presentation grouping remains intact;
- `search.show_out_of_stock_section` behaviour remains intact;
- zero-result searches use the filtered no-results state rather than the empty
  inventory message;
- the search input remains usable while requests are loading;
- Inventory mobile layout and Part Manager management mode were browser
  approved;
- part selection, details, quantity changes, movement history, metadata editing,
  deletion and restoration were browser approved;
- Alembic remains at `0005_packages`, the complete smoke suite passed,
  protected APIs and SPA routes passed, and verification left real inventory
  unchanged.

Patch 234 records, commits and pushes this approved frontend checkpoint. The
next batch should add bounded backend pagination and a dedicated part-type
filter while retaining the approved server-search behaviour.

## Chat 10 boundary recovery - Stored Parts migration

<!-- PARTPILOT:CHAT10_BOUNDARY:V250 -->
<!-- PARTPILOT:CHAT10_BOUNDARY_RECOVERY:V253 -->

Recorded by Patch 253 on `2026-07-27T10:45:09.454380+00:00`.

### Boundary recovery

Patch 250 failed during in-memory documentation generation because
`docs/Chat11_Starting_Prompt.md` did not contain
`PARTPILOT:CHAT10_BOUNDARY:V250`. Patch 251 then failed before writes because the
handoff rendered `Patch **275**` while its validator required plain `Patch 275`.
Patch 252 generated, wrote and staged the documentation, but its staged-diff
validator required the obsolete phrase `Boundary-recovery workflow:` while the
compact memory used `Chat and boundary rules`. Rollback restored the documents
and index after all three failures. Patch 253 completed the boundary recovery
under the revised same-chat recovery rule.

### Committed state before recovery

- Commit: `1f93436ad324b45cc5612cf60e463686d3af1a75`
- Subject: `Migrate Stored Parts search to backend`

### Pending uncommitted source preserved

- `frontend/src/pages/PartManager.tsx`
- `frontend/src/pages/PartManager.css`
- Pending diff SHA-256: `8f5ed1acaef4414ea6f8965932456f1d401d7609ca80f41a46e5206cbe8f67b7`
- Active marker: `stored-parts-preference-v248`

### Temporary fixtures preserved

- Token: `PP241-20260727-075829-0F182174`
- Count: `70`
- Package values: `NULL`
- Cleanup remains pending final browser approval.

### Next chat

- `Chat 11: Stored Parts Search Finalization`
- First patch: `254`
- Mandatory final boundary patch: `275`

<!-- PARTPILOT:DURABLE_CONTEXT_POLICY:V285 -->
## Durable context and chat-boundary policy

`docs/Part_Pilot_Project_Memory.txt` was an unintended duplicate memory file
and has been removed. Do not recreate it.

Durable project continuity now uses:

1. the newest chat handoff;
2. `docs/Checkpoint.md`;
3. `docs/Implementation_Roadmap.md`;
4. `README.md`;
5. the newest relevant `diagonostic_` report.

Boundary and prompt rules:

- Do not create or commit next-chat prompt files in any format.
- Keep the ready-to-paste next-chat prompt only in the current chat response.
- Provide that prompt only after the boundary or boundary-recovery script has
  actually run and its terminal output ends with exactly `Everything PASS`.
- Until then, keep the current chat active for narrow high-safety recovery.
- Failed boundary and recovery scripts consume their patch numbers.
- Future chats own 30 sequential patch numbers.
- A future chat boundary is its starting patch plus 29.
- Calculate the next chat start and boundary only after the current recovery
  succeeds.
- A successful boundary updates durable docs and the handoff, commits and
  pushes, and only then is the next title and prompt supplied in chat.

Current state after Patch 293:

- Chat 11 Stored Parts Search Finalization is complete.
- Approved application source is committed, pushed, deployed and
  browser-approved.
- All 70 manifest-owned PP241 fixture parts and their 70 creation-audit rows
  were removed by Patch 292.
- Real inventory, settings identities and values, application source and the
  verified deployment were preserved.
- Chat 11 boundary recovery is closed.
- Chat 12 starts with Patch 294 and owns patches 294 through 323.

<!-- PARTPILOT:CHAT11_BOUNDARY_RECOVERY:V293 -->
<!-- PARTPILOT:HOMELAB_READ_ONLY_POLICY:V293 -->
## Chat 11 boundary recovery complete — Stored Parts finalization

Recorded by Patch 293 on `2026-07-28T12:36:06.797730+00:00`.

### Completed application checkpoint

- Stored Parts uses backend universal search rather than filtering only a
  loaded frontend page.
- Search composes with part-type, location and stock-status filters.
- Backend totals and pagination remain accurate across the complete filtered
  result set.
- Page sizes of 25, 50 and 100 are supported and the preference is retained.
- Available and Out of stock sections are independently sorted across the full
  filtered result set.
- Supported sorting columns are Part, Type, Manufacturer, Location, Available,
  Total and Status.
- Sort changes reset to page one; independent section sorting preserves the
  other section.
- Available uses the approved teal card and Out of stock uses the approved red
  card.
- Empty sections remain hidden and compact mobile headers are browser-approved.
- Search stale-response guards, selection, part details, quantity adjustment,
  movement history, metadata editing, deletion and restoration remain intact.

### Source and verification

- Approved source commit: `ba721e5` — `Finalize Stored Parts search and sorting`.
- Current diagnostic checkpoint before this boundary:
  `b96e72658a497cbd18c6336b5f409e3d8fdfd501` — `Diagnose duplicate inventory audit event`.
- Alembic head: `0005_packages`.
- Complete backend smoke suite: passed.
- Protected APIs and SPA routes: passed.
- Browser approval: passed.
- Application source hashes: unchanged since Patch 292.
- Running deployment image: unchanged since Patch 292.

### Temporary fixture cleanup

Patch 292 removed only manifest-owned test data:

- PP241 fixture parts removed: 70.
- Matching PP241 `part.created` audit rows removed: 70.
- Remaining PP241 fixture parts: 0.
- Remaining PP241 audit rows: 0.
- SQLite integrity: `ok`.
- Foreign-key violations: 0.
- Default settings: 17.
- Real inventory and every unrelated database row: preserved.

The cleanup originally failed because deleting fixture parts without deleting
their historical creation audits allowed SQLite to reuse a deleted part ID.
The smoke test then counted both the old PP241 audit and the new smoke audit.
Patch 292 validated and removed the exact audit IDs before the exact part IDs,
passed an isolated full smoke suite before the live write, and passed the full
live verification.

### HomeLab Terminal restriction

The assistant may use the HomeLab Terminal tool to scan and inspect the actual
repository, documentation, source, Git state, logs, runtime and databases.

That tool is **read-only only**:

- allowed: listing, reading, searching, hashing, Git inspection, container
  inspection, HTTP reads and SQLite read-only queries;
- forbidden: creating, modifying, deleting, moving or replacing files;
- forbidden: staging, committing, resetting, checking out, merging, rebasing or
  pushing Git state;
- forbidden: writing to databases;
- forbidden: building, restarting, stopping or recreating containers;
- forbidden: changing deployment, fixtures, inventory or system configuration.

All mutations continue through complete downloadable numbered Python patch
files that the user runs explicitly.

### Boundary and next chat

- Chat 11 began with Patch 254.
- Its planned 30-patch boundary was Patch 283.
- Failed boundary-recovery scripts consumed their numbers.
- Narrow recovery continued through successful Patch 293.
- Next title: `Chat 12: Reservations Foundation`.
- Chat 12 starts with Patch 294.
- Chat 12 owns patches 294 through 323.
- Patch 323 is its planned boundary.
- No next-chat prompt file was created.
- The ready-to-paste prompt is supplied only in chat after Patch 293 ends with
  exactly `Everything PASS`.


<!-- PARTPILOT:RESERVATIONS_BACKEND_CHECKPOINT:V310 -->
## Chat 12 checkpoint — Reservation backend lifecycle foundation

Recorded by Patch 310 after Patch 308 committed and pushed commit `802a5f0` —
`Add reservation cancellation workflow`.

### Completed backend foundation

- Patch 294 produced the reservation architecture diagnostic before implementation.
- Alembic `0006_reservation_contract` aligned canonical reservation statuses,
  movement linkage, reserved/available quantity snapshots, constraints and indexes.
- Reservation creation is atomic, normalises duplicate part lines and uses guarded
  stock updates without changing physical `total_quantity`.
- Protected reservation APIs now provide:
  - `GET /api/reservations` with status filtering, pagination and deterministic
    newest-first ordering;
  - `GET /api/reservations/{reservation_id}`;
  - `POST /api/reservations`;
  - `POST /api/reservations/{reservation_id}/cancel`.
- Missing reservations return 404, invalid reservation semantics return 422, and
  inventory or lifecycle conflicts return 409.
- Active reservations can be cancelled atomically.
- Cancellation releases reserved quantity without changing physical stock,
  records `release` movement snapshots and writes one structured
  `reservation.cancelled` audit event.
- Cancelled, consumed and expired reservations cannot be cancelled again.
- Inconsistent reserved-stock cancellation rolls back without partial status,
  stock movement or audit changes.

### Verified commits

- `0e72717` — `Align reservation lifecycle contract`.
- `9c3dfef` — `Add reservation creation service`.
- `12ba5e2` — `Expose reservation read and create API`.
- `802a5f0` — `Add reservation cancellation workflow`.

### Verification and preservation

- Alembic head: `0006_reservation_contract`.
- Complete backend smoke suite: passed.
- Protected reservation API checks: passed.
- Deployed source hashes matched verified source before the Patch 308 checkpoint.
- SQLite integrity and foreign-key checks: passed.
- Real inventory remained unchanged.
- Live reservation and reservation-item tables remained empty after test cleanup.
- Existing physical stock movements and unrelated audit history were preserved.
- No browser test was required for these backend-only slices.

### Current implementation order

1. Implement active-reservation consumption atomically.
2. Implement explicit expiry processing with release semantics.
3. Build and browser-test the responsive Reservations workspace.
4. Keep Projects as a separate later implementation boundary.

Consumption must reduce both physical `total_quantity` and `reserved_quantity`,
preserve available-quantity semantics, record `consume` movement snapshots and
reject every non-active reservation state.

### Current terminal and patch workflow

The HomeLab Terminal tool is read-only only. The assistant may use it to inspect
the repository, documentation, source, Git state, runtime, HTTP endpoints, logs
and databases. It must not create, modify, delete, stage, commit, push, build,
deploy, restart containers or write database data.

All mutations are delivered as one complete downloadable sequential Python
patch at a time. The user runs each patch and reports its result before the next
patch is generated. Commit and push may occur only inside a downloadable patch
run explicitly by the user.

<!-- PARTPILOT:RESERVATIONS_FOUNDATION_CHECKPOINT:START -->
## Reservations Foundation — complete

**Checkpoint:** Patch 335
**Browser approval:** confirmed
**Alembic head:** `0006_reservation_contract`

Completed and verified:

- Reservation schema, items, statuses, constraints and indexes.
- Atomic creation with stock reservation and duplicate-item normalisation.
- Authenticated list, detail and create APIs.
- Cancellation, consumption and due-expiry workflows.
- Stock movements, audit records and inventory-safe rollback behaviour.
- Responsive Reservations workspace with list/detail, filters, pagination,
  server-backed part search and reservation actions.
- Browser-approved desktop/mobile layout and part-picker alignment.
- Existing-data-safe complete smoke coverage.
- Protected APIs, SPA routes and exact inventory preservation.

The browser-created **Weather Station** reservation remains user data and must
not be removed by automated cleanup.

Next: `Chat 13: Reservation Workflow Finalization`, Patch 336 through Patch 365.
<!-- PARTPILOT:RESERVATIONS_FOUNDATION_CHECKPOINT:END -->

<!-- PARTPILOT:RESERVATION_ACTIVITY_EXPERIENCE:V344:START -->
## Reservation activity and mobile workflow checkpoint

**Checkpoint:** Patch 344
**Browser approval:** confirmed
**Alembic head:** `0006_reservation_contract`
**Commit:** `Finalize reservation activity experience`

Completed and verified:

- Authenticated read-only reservation activity endpoint combining audit events
  and reservation-linked stock movements.
- Newest-first ordering, pagination, actor attribution, part metadata and stock
  snapshots.
- Responsive Activity panel with loading, empty, error, retry and stale guards.
- Activity refresh after cancel, consume and expire actions.
- Stronger desktop register hierarchy and separated compact mobile cards.
- Mobile Reservations lands on the register without opening the first record;
  desktop still selects the first reservation in split view.
- Manual mobile selection survives refresh and closes back to the register.
- Complete smoke, SPA, protected API, bundle and browser verification.
- The Weather Station reservation and all real inventory were preserved.

### Roadmap estimate

**Part Pilot is approximately 68% complete toward the full V1/public-alpha
roadmap.** The core inventory product is approximately **82% complete**.

Remaining work is concentrated in reservation editing/settings completion,
Projects, system-wide History, Settings and appearance, backup/restore, MCP,
and final accessibility/security/public-alpha hardening.

### Next implementation boundary

Implement editing for existing active reservations in separate backend and
frontend slices. Define guarded label, notes, expiry and item-change semantics;
preserve stock invariants atomically; record movements/activity; reject edits
to non-active reservations; and add the Edit UI only after backend smoke
coverage passes. Keep Projects outside this edit slice.
<!-- PARTPILOT:RESERVATION_ACTIVITY_EXPERIENCE:V344:END -->

<!-- PARTPILOT:CHAT13_RESERVATION_FINALIZATION_BOUNDARY:V365 -->
## Chat 13 boundary — Reservation Workflow Finalization complete

**Boundary patch:** 365
**Browser approval:** confirmed through Patch 364
**Alembic head:** `0006_reservation_contract`
**Boundary commit subject:** `Complete reservation workflow finalization`

### Completed reservation workflow

- Authenticated read-only reservation activity combines audit events and linked
  stock movements with actor, part and quantity snapshots.
- Desktop uses a stronger register/detail hierarchy; mobile lands on the
  register and opens details only after explicit selection.
- Active reservations support atomic edits to label, notes, expiry and items.
  Stock-affecting edits reconcile reserve/release movements, value snapshots,
  activity and audit history while rejecting non-active records and no-op saves.
- Cancelled, consumed and expired reservations can be permanently deleted only
  after exact-label confirmation. Active reservations cannot be deleted.
  Immutable stock movements are retained and historical audits remain complete.
- Reservation defaults are exposed through authenticated
  `GET/PATCH /api/settings/reservations`. The `none/default` pair is validated,
  updated atomically and audited only for real changes.
- New reservation forms may receive a fresh local-time expiry suggestion. Users
  can clear or change it. Existing reservations and direct API calls are never
  silently defaulted.
- The New/Edit modal has aligned controls, one custom calendar action, no
  redundant native Chromium indicator, and one visible footer Cancel action.
- The live installation was restored to `none/null` after browser testing.

### Completed view-preference and Part Manager polish

- Inventory stock, part-type, location, page-size and independent Available /
  Out-of-stock sort preferences persist safely.
- Invalid or deleted catalogue-backed preferences are removed after catalogue
  validation without request flashing or stale results.
- Part Manager All/Built-in/Custom selection persists and matches the approved
  segmented-filter design.
- The redundant inventory divider and user-facing template-version badge were
  removed; destructive Delete remains the final custom-type action.

### Repository and log hygiene

- `.gitignore` explicitly includes `fixes/logs/` while retaining the broader
  local `fixes/` exclusion.
- Five historical diagnostic Markdown files under `fixes/logs/` are removed
  from Git tracking by Patch 365. Their local copies remain ignored and intact.
- Durable diagnostics belong under `docs/` with the exact `diagonostic_` prefix.

### Verified live data at the boundary

- Weather Station reservation: ID 1, `cancelled`, expiry
  `2026-07-31 12:22:00.000000`.
- Active parts: 7.
- Total quantity: 144.
- Reserved quantity: 0.
- Available quantity: 144.
- Reservation defaults: mode `none`, default days `null`.
- SQLite integrity and foreign keys: clean.

### Proven HomeLab-assisted patch method

The reliable Chat 13 workflow is now mandatory durable project memory:

1. Use the HomeLab terminal to inspect exact local Git/index state, source,
   logs, deployment, HTTP contracts and live SQLite values before designing a
   patch. Local state is authoritative.
2. Generate proposed targets under `/tmp`; never experiment on pending source.
3. Validate target generation twice and compare exact SHA-256 bytes.
4. Overlay those targets onto a clean repository snapshot, run TypeScript/Vite
   and Docker builds, verify production-bundle contracts, and run the complete
   smoke suite against a copied database before issuing the patch.
5. Package the exact tested bytes into one numbered Python script. Runtime
   transforms must not rediscover brittle anchors.
6. Patch scripts require exact HEAD/origin, index, pending-file allowlists,
   source hashes, prerequisite script hashes and successful log evidence.
7. Use clear `[X/N]` phases, full backups, rollback image/database/source
   restoration, protected API and SPA checks, Alembic verification and logical
   live-data preservation.
8. Keep browser-test files unstaged and uncommitted until explicit approval;
   checkpoint them in a separate script and push promptly.

### Next phase

- Next title: `Chat 14: Projects Foundation`.
- Patch range: 366–395 inclusive.
- Planned boundary: Patch 395.
- Patch 366 must be diagnostic-only.
- Projects currently have database models but no protected schemas, services,
  routes, clients or real UI. `/projects` is a placeholder.
- The model constraint uses `draft/reserved/consumed/cancelled`, while
  `PROJECT_STATUSES` currently uses `draft/active/completed/archived`; resolve
  this contract explicitly before implementation.
- Preserve Weather Station, all inventory, reservation defaults and every
  unrelated history row.

<!-- PARTPILOT:PROJECTS_FOUNDATION_CHECKPOINT:V390 -->
## Projects foundation checkpoint — browser approved through Patch 386

**Checkpoint patch:** 390
**Alembic head:** `0007_projects_contract`
**Commit subject:** `Add Projects foundation and derived reservations`

### Completed Projects foundation

- Canonical Project statuses are `draft`, `reserved`, `consumed`, and
  `cancelled`; the schema, constants, migration and API contract agree.
- Authenticated Project list/detail/create/update endpoints provide pagination,
  validation, item reconciliation, price/currency snapshots and no-op-safe
  auditing.
- The responsive Projects workspace supports a register/detail split view,
  Draft creation and editing, server-backed part search, multi-result selection,
  current availability and value snapshots.
- Draft Projects reserve atomically through
  `POST /api/projects/{project_id}/reserve`.
- Reserving a Project creates one linked active Reservation, matching
  Reservation items, one reserve stock movement per part, Project and
  Reservation audit events, and a `draft` to `reserved` status transition.
- Physical stock totals remain unchanged while reserved quantity increases and
  available quantity decreases.
- Project and Reservation pickers display up to 50 server matches with visible
  result counts and persistent multi-selection lists.
- Browser approval covers Draft creation/editing, reservation confirmation,
  linked Reservation creation, multi-result search and responsive layouts.

### Projects and Reservations product boundary

- Users create new planned work in **Projects**.
- **Reservations** is the operational queue for stock commitments generated by
  Reserved Projects.
- Manual Reservation creation is removed from the frontend to avoid duplicate
  and confusing entry paths.
- Active Reservation editing, cancellation, consumption, expiry, deletion and
  activity history remain available.
- The backend Reservation-create API remains temporarily for compatibility and
  smoke coverage; later deprecation requires an explicit API/MCP compatibility
  decision.

### Deferred Settings requirement — MCP server control

A future Settings implementation must add an authenticated control for enabling
or disabling the MCP server. This is **recorded only and not implemented by
Patch 390**.

Before implementation, define and test:

1. persisted setting name, default and migration/seed behavior;
2. whether a change applies immediately or requires service restart;
3. how disabled state gates MCP transport, tool registration and write access;
4. authenticated Settings API and UI behavior;
5. audit events for real setting changes;
6. safe startup behavior when the setting is absent or invalid;
7. clear disabled-state feedback without deleting MCP configuration.

### Verified preservation

- Exact browser-approved source is committed as one checkpoint.
- The complete smoke suite passes against a copied database.
- Protected Projects and Reservations APIs remain authenticated.
- Live inventory, Projects, Reservations, stock movements and audits remain
  unchanged by the checkpoint.
- Git staging uses an explicit allowlist; main is pushed, fetched and verified.

### Next implementation slice

Continue Project lifecycle completion in independently testable backend and
frontend slices:

1. consume a Reserved Project by reusing linked Reservation consumption;
2. cancel a Reserved Project by releasing the linked Reservation;
3. synchronize Project and Reservation statuses atomically;
4. add guarded confirmation UI and activity feedback;
5. decide later whether the backend manual Reservation-create API should be
   deprecated after API and MCP compatibility are defined.

<!-- PARTPILOT:CHAT14_PROJECTS_FOUNDATION_BOUNDARY:V396 -->
## Chat 14 boundary — Projects Foundation complete

**Boundary patch:** 396
**Automated verification:** complete through Patch 394
**Browser approval:** Projects foundation approved through Patch 386
**Alembic head:** `0007_projects_contract`
**Boundary commit subject:** `Complete Projects foundation backend lifecycle`

### Completed Projects foundation

- Canonical Project statuses are `draft`, `reserved`, `consumed`, and
  `cancelled`; model constraints, constants, migration, schemas and API filters
  agree.
- Authenticated Project list, detail, create and Draft-update endpoints provide
  validation, pagination, item reconciliation, price/currency snapshots,
  current inventory snapshots, no-op suppression and audit history.
- The responsive Projects register/detail/create/edit workspace uses
  server-backed part search, supports up to 50 visible matches and preserves
  multi-selection while quantities are planned.
- Draft Projects reserve atomically through
  `POST /api/projects/{project_id}/reserve`.
- Reserving a Project creates exactly one linked active Reservation, matching
  Reservation items, reserve stock movements and paired Project/Reservation
  audits. Physical totals remain unchanged while reserved quantity increases.
- Manual Reservation creation is removed from the frontend. Reservations is the
  operational commitment queue generated by Projects; the backend create API
  remains temporarily for compatibility.

### Completed backend consumption transition

Patch 394 adds the protected endpoint:

```text
POST /api/projects/{project_id}/consume
```

The service:

1. locks the Reserved Project;
2. requires exactly one linked active Reservation;
3. reuses `consume_reservation(..., commit=False)` in the same transaction;
4. reduces physical and reserved quantities together;
5. preserves available quantity;
6. creates one consume stock movement per Reservation item;
7. transitions the Reservation from `active` to `consumed`;
8. transitions the Project from `reserved` to `consumed`;
9. records `reservation.consumed` and `project.consumed`;
10. rolls back all status, inventory, movement and audit changes on conflict.

Missing, duplicate, inactive or already-terminal links are rejected. Repeated
consumption and concurrent quantity/status changes are rejected.

### Diagnostic recovery completed

- Patch 391 failed before writes because it probed the undeployed consume route.
- Patch 392 failed before writes because encoded payloads remained at `V391`
  while its validator expected `V392`.
- Patch 393 created and committed
  `docs/diagonostic_project_consumption_recovery_patch_393.md`.
- Patch 394 was generated fresh with self-validated `V394` service, route and
  smoke payloads and passed the complete copied-database smoke suite.

### Deferred MCP Settings requirement

A future authenticated Settings control must enable or disable the MCP server.
The implementation phase must define persisted default, startup and invalid
value behavior, immediate versus restart-required application, transport/tool
gating, write-tool behavior, audit events and disabled-state feedback. This
requirement remains recorded only.

### Verified boundary state

- The Patch 394 source/build/deployment passed.
- Alembic remains at `0007_projects_contract`.
- The consume route is protected and exposed as `POST` in OpenAPI.
- The complete smoke suite passed against a copied database.
- Live users, catalogues, inventory, Projects, Reservations, movements, audits
  and settings were preserved.
- Patch 396 stages only its explicit application/documentation allowlist, pushes
  `main`, fetches and verifies local HEAD equals `origin/main`.

### Boundary recovery

Patch 395 failed before writes because four generated Checkpoint metadata lines contained Markdown trailing spaces. Patch 396 removes those spaces, performs the same boundary checkpoint, and shifts Chat 15 to Patch 397–426 with Patch 426 as its boundary.

### Next phase

- Next title: `Chat 15: Project Lifecycle Completion`.
- Patch range: 397–426 inclusive.
- Planned boundary: Patch 426.
- No next-chat prompt file is created. The ready-to-paste prompt is provided in
  chat only after Patch 396 ends with `Everything PASS`.

Chat 15 must first read:

1. `docs/Chat_14_Projects_Foundation_Handoff.md`;
2. `docs/Checkpoint.md`;
3. `docs/Implementation_Roadmap.md`;
4. `docs/Part_Pilot_Project_Memory.txt`;
5. `README.md`;
6. `docs/diagonostic_project_consumption_recovery_patch_393.md`.

The immediate implementation order is:

1. atomic Reserved Project cancellation by reusing linked Reservation release;
2. Project client/type support for consume and cancel;
3. guarded confirmation UI for Project consumption and cancellation;
4. clear success/error/activity feedback and terminal-status synchronization;
5. responsive browser testing and checkpointing;
6. system-wide History only after Project lifecycle completion is stable.

<!-- PARTPILOT:PROJECT_LIFECYCLE_CHECKPOINT:V405 -->
## Chat 15 checkpoint — Project lifecycle complete through Patch 403

**Checkpoint patch:** 405
**Browser approval:** complete through Patch 403
**Alembic head:** `0007_projects_contract`
**Commit subject:** `Complete Project lifecycle workflows`

### Completed lifecycle contract

- Reserved Projects consume atomically through exactly one linked active
  Reservation. Physical and reserved quantities decrease together, available
  quantity remains unchanged, both records become `consumed`, and paired
  movements/audits are recorded.
- Reserved Projects cancel atomically through the linked Reservation. Reserved
  quantity returns to available stock without changing physical totals, both
  records become `cancelled`, and paired release movements/audits are recorded.
- Terminal verification snapshots existing movement IDs before the action and
  verifies only movements created by the current transaction. Historical
  reserve/release movements from earlier edits are preserved and cannot cause a
  false terminal-action conflict.
- Reserved Projects are editable from Projects. Quantity increases reserve only
  the delta, decreases release only the delta, and Project/Reservation metadata,
  items, snapshots, values and audits remain synchronized.
- Project-linked active Reservations are also editable from Reservations. Both
  entry points update the same atomic commitment; the Project description remains
  Project-owned.
- Direct Reservation consume, cancel and expiry synchronize the linked Project
  terminal status atomically.
- Project and Reservation terminal actions use accessible in-app dialogs,
  duplicate-submit guards, stale-state refresh and non-interactive explanatory
  hierarchy rather than browser-native confirmation prompts.
- Projects and Reservations use register-first mobile behavior and compact
  two-by-two summary metrics. Long values wrap without horizontal overflow.
- Part history exposes Physical, Reserved and Available before/after snapshots,
  with meaningful reserve/release deltas instead of ambiguous physical-only
  values.

### Verification and recovery history

- Patch 397 added atomic Project cancellation.
- Patch 398 added Project consume/cancel frontend actions.
- Patch 399 synchronized direct Reservation lifecycle actions with Projects and
  corrected mobile, stale-state and part-label behavior.
- Patch 400 failed before writes on a brittle frontend anchor. Patch 401 recovered
  the Reserved Project editing, stock-history and realistic test-fixture slice.
- Patch 402 failed before writes on payload-validation and indentation defects.
  Patch 403 recovered terminal movement-delta verification, two-way editing and
  lifecycle-dialog hierarchy.
- Patch 403 passed source compilation, TypeScript/Vite build, deployment,
  Alembic, protected API/OpenAPI checks, built marker checks and the complete
  copied-database smoke suite.
- Desktop and mobile browser tests passed, including two-way editing followed by
  cancellation in the presence of historical release movements.

### Runtime browser-test inventory

Six realistic manifest-owned test parts remain in the live test database with
manifest:

```text
/projects/Part Pilot/fixes/logs/patch_401_test_fixture_manifest.json
```

Runtime data and logs are ignored by Git. The user plans to reset the database
before production use. Patch 405 validates this exact live state but does not
stage, delete or rewrite any inventory, Project, Reservation, movement or audit
row.

### Next implementation

Project lifecycle work is checkpointed. The next major product area is the
system-wide History and audit browser. Keep it separate from Settings,
backup/restore and MCP implementation.

<!-- PARTPILOT:SYSTEM_HISTORY_CHECKPOINT:V410 -->
## Chat 15 checkpoint — System-wide History complete through Patch 409

**Checkpoint patch:** 410
**Browser approval:** complete through Patch 409
**Alembic head:** `0007_projects_contract`
**Commit subject:** `Add system-wide History workspace`

### Completed History contract

- Protected `GET /api/history` and `GET /api/history/filter-options`
  endpoints provide a unified operational register over `audit_log` and
  `stock_movements`.
- The feed is deterministic and newest-first across both record kinds.
  Pagination uses a stable timestamp, kind and record-ID order.
- Server-backed filters cover record kind, entity, event, actor type,
  individual user, movement type, date range and literal text search.
- Dynamic filter options expose counted facets plus earliest/latest event
  timestamps.
- History entries hydrate readable actor, entity, Part, Reservation and
  Project context without rewriting historical rows.
- Stock records expose Physical, Reserved and Available before/after
  snapshots, movement quantity, signed delta, reason, note and source.
- Audit records expose structured Before, After and expandable metadata
  evidence.
- The responsive History workspace uses a dense register/detail layout,
  280 ms search, pagination reset on filter changes, abort controllers and
  request IDs to prevent stale responses.
- Desktop selects the newest event; mobile remains register-first and opens
  detail only after an explicit tap.
- History uses chronological ordering by design. General sortable columns
  are intentionally omitted because Entity, Event, Actor, Kind, Movement,
  dates and text filters already support investigation without breaking the
  timeline. An Oldest-first option remains a future evidence-based addition,
  not a current requirement.

### Verification and recovery history

- Patch 406 added the backend contract but failed in copied-database smoke
  because its generated username contained a forbidden hyphen. Source and
  deployment were restored.
- Patch 407 corrected the smoke username, replaced brittle historical SQLite
  byte matching with canonical logical-data validation, and passed the
  complete smoke suite.
- Patch 408 added the frontend workspace and built successfully, but its
  deployment verifier searched minified CSS for a source comment that Vite
  removes. The frontend and deployment were restored.
- Patch 409 added a minifier-safe CSS custom property and data-attribute
  selector, then passed Python/TypeScript/Vite build, deployment, Alembic,
  protected API/OpenAPI checks, production bundle checks and the complete
  copied-database smoke suite.
- Desktop and mobile browser testing passed, including exact totals,
  search/stale-response behavior, counted filters, pagination, date
  validation, stock snapshots, structured audit evidence and register-first
  mobile detail behavior.

### Approved live register

The browser-approved test database contains 118 History events: 86 audit
records and 32 stock movements. Existing realistic Patch 401 fixtures,
Projects, Reservations, movements and audits remain intentionally preserved.
Runtime data, logs and fixture manifests are ignored by Git and are not
staged by Patch 410.

### Next implementation

System-wide History is checkpointed. The next major V1 area is Settings and
appearance completion. Keep Settings separate from backup/restore and MCP.
The previously deferred authenticated MCP server enable/disable control
remains part of the later MCP phase unless its runtime contract is designed
explicitly during Settings work.

<!-- PARTPILOT:GLOBAL_APPEARANCE_CHECKPOINT:V417 -->
## Global appearance and Settings checkpoint — Patch 417

The authenticated appearance and Settings product slice is complete,
browser approved and checkpointed.

### Approved product behavior

- Protected `GET` and `PATCH /api/settings/appearance` endpoints persist
  `dark`, `light` or `system`, expose Light-theme availability, validate
  invalid values, recover corrupt reads without silent writes and record
  actor-attributed audit evidence.
- A pre-paint bootstrap applies the stored preference before React renders,
  preventing an opposite-theme flash during direct-route loads.
- The authenticated appearance provider synchronizes server state, stores a
  local pre-paint preference, follows operating-system theme changes in
  System mode and restores the previous theme after failed saves.
- Settings provides responsive Appearance, Inventory, Reservations and Data
  sections. The Inventory and Reservation cards have aligned desktop
  heights and stack naturally on narrow layouts.
- Database reset uses one compact launch action and an accessible in-app
  dialog. The destructive phrase input and final erase action live inside
  the dialog; Escape and the non-destructive action clear and close it.
- Light mode covers the shell, Dashboard, Stored Parts, Part Manager,
  Projects, Reservations, History, tables, forms, drawers and modals.
- Light-mode primary, neutral, destructive, selected, status and genuinely
  disabled states use a consistent hierarchy across workspaces.
- Dark mode retains the previously approved visual system.

### Verification and recovery history

- Patch 411 added and verified the protected appearance backend contract.
- Patch 412 built and deployed the frontend but failed because Vite removed
  quotes from a CSS attribute selector; rollback restored source and
  deployment while SQLite page layout changed without logical data loss.
- Patch 413 failed before writes because its failure-evidence string used
  brittle escaping.
- Patch 414 recovered with semantic evidence checks and minifier-safe quoted
  or unquoted selector validation.
- Patch 415 aligned Settings cards, moved reset confirmation into the dialog
  and corrected screenshot-identified Light-theme contrast leaks.
- Patch 416 unified inventory headings, stock badges, workspace actions,
  active filters, selected rows and real disabled states.
- Python, TypeScript and Vite builds, deployment, Alembic, protected
  API/OpenAPI checks, production bundle markers and the complete copied-
  database smoke suite passed.
- Desktop browser testing approved Dark, Light and System behavior,
  persistence, responsive Settings, reset-dialog safety and the final
  cross-workspace Light-theme interaction hierarchy.

### Approved live state

The operational test database remains intact with 15 Parts, 7 Projects,
9 Reservations, 32 stock movements and 96 audits. The six realistic
Patch 401 fixtures remain intentionally preserved.

### Next implementation

Compact the Out-of-stock results preference so its visual weight matches
its single boolean function. Keep the existing server-backed setting and
switch behavior, then browser-test and checkpoint that focused refinement
before beginning backup/restore.

<!-- PARTPILOT:CHAT15_SETTINGS_BOUNDARY:V426 -->
## Chat 15 boundary — lifecycle, History and Settings complete

**Boundary patch:** 426
**Browser approval:** complete through Patch 425
**Alembic head:** `0007_projects_contract`
**Boundary commit subject:** `Complete Chat 15 Settings and appearance`

### Completed in Chat 15

- The complete Project lifecycle is operational: Draft creation and editing,
  reservation, synchronized Reserved editing from Projects or Reservations,
  consumption and cancellation.
- Project and linked Reservation terminal transitions are atomic, preserve
  inventory invariants, create paired movements/audits and reject invalid or
  repeated actions.
- System-wide History provides a protected newest-first register over audits
  and stock movements with literal search, counted filters, actor/entity
  context, stock snapshots and responsive register/detail behavior.
- Authenticated Dark, Light and System appearance preferences persist on the
  server, apply before React renders and follow operating-system changes in
  System mode.
- Light mode now covers every current workspace and overlay with explicit
  primary, neutral, destructive, active, selected, status and genuinely
  disabled states.
- Settings provides responsive Appearance, Inventory, Reservations and Data
  sections, a guarded database-reset dialog and preserved server-backed
  Inventory/Reservation preferences.
- The Out-of-stock preference is one compact full-width row with visible
  On/Off/Saving state and accessible switch semantics.
- Desktop Settings uses a full-width Appearance card, a full-width compact
  Inventory preference, then equal-height Reservation defaults and Database
  reset cards. Mobile stacks Inventory, Reservations and Data naturally.
- The redundant `Resolved: Dark/Light` pill was removed. The page-level
  runtime status and selected appearance card remain authoritative.

### Verification and recovery history

- Patches 397–405 completed and checkpointed Project cancellation, terminal
  actions, two-way Reserved editing, movement snapshots and realistic
  manifest-owned test fixtures.
- Patches 406–410 implemented and checkpointed system-wide History.
- Patches 411–417 implemented and checkpointed the appearance contract,
  runtime synchronization, Light theme and cross-workspace interaction
  hierarchy.
- Patch 418 compacted the Out-of-stock preference.
- Patches 419 and 420 failed before writes on brittle block matching and an
  incomplete resolved-mode selector cleanup.
- Patch 421 completed the full in-memory composition simulation but stopped
  before writing its report because numbered blank source lines introduced
  trailing spaces.
- Patch 422 created and pushed
  `docs/diagonostic_422_settings_desktop_composition_recovery.md`, recording
  all exact selectors, structural boundaries and candidate hashes.
- Patch 423 applied the diagnostic-backed Settings composition and passed
  build, deployment and the complete copied-database smoke suite.
- Patch 424 built successfully but its verifier rejected Vite's rewrite of
  `@media (min-width: 901px)` to `@media (width>=901px)`; rollback restored
  the exact Patch 423 state.
- Patch 425 accepted authored and minified media-query forms, synchronized
  the lower desktop card heights and passed all automated checks.
- Desktop, mobile, Dark and Light browser testing approved the final
  composition, equal-height lower cards, compact Inventory preference,
  appearance behavior and reset-dialog safety.

### Approved live state

- Users: 1
- Part types: 36
- Manufacturers: 9
- Packages: 23
- Locations: 1
- Parts: 15
- Projects: 7
- Reservations: 9
- Stock movements: 32
- Audits: 96
- App settings: 17
- Appearance preference: `dark`
- Separate Out-of-stock results: enabled

The six realistic Patch 401 parts remain intentionally preserved. Their
manifest is:

```text
/projects/Part Pilot/fixes/logs/patch_401_test_fixture_manifest.json
```

### Boundary state and next phase

Patch 426 stages only its explicit seven-file allowlist, commits and pushes
`main`, fetches and verifies local `HEAD == origin/main`, then revalidates
deployment, Alembic, protected Settings contracts and unchanged live data.

The next chat is `Chat 16: Backup and Restore Foundation`. It owns Patches
427–456 inclusive; Patch 456 is its planned boundary. No starting-prompt
file is created. The ready-to-paste prompt is provided in chat only after
Patch 426 ends with `Everything PASS`.

<!-- PARTPILOT:CHAT16_BACKUP_RESTORE_BOUNDARY_RECOVERY:V457 -->
## Chat 16 boundary — backup and restore foundation complete

**Boundary recovery patch:** 457
**Committed application baseline:** Patch 453
**Core browser approval:** complete through Patch 450
**Alembic head:** `0007_projects_contract`
**Boundary commit subject:** `Complete Chat 16 backup and restore foundation`

### Completed in Chat 16

- Part Pilot now creates versioned `.ppbackup` archives with exactly
  `manifest.json` and `partpilot.db`.
- Backup snapshots use SQLite's online backup API and record format, schema,
  integrity, scope, hashes, sizes, timestamps and restore-policy metadata.
- Protected manual backup downloads use no-store headers, deterministic
  filenames, actor-attributed audits and operation-owned temporary cleanup.
- Restore validation rejects malformed archives, unsafe paths, incompatible
  revisions, hash mismatches, invalid SQLite databases, foreign-key failures,
  missing tables, oversized input and unsafe staged state before live data is
  touched.
- Restore commit uses persistent same-filesystem staging, maintenance/drain
  semantics, a pre-Uvicorn bootstrap, an online rollback snapshot, atomic
  replacement, verification, session invalidation, actor-aware auditing and
  rollback on failure.
- Settings provides functional Appearance, Inventory, Reservations and Data
  section controls, full-width active panels, natural card heights, responsive
  backup/restore controls and a guarded restore-review dialog.
- Desktop and mobile browser testing approved backup download, validation,
  successful restore, forced reauthentication, responsive Settings tabs and
  the complete backup/restore workspace.
- Expired staging cleanup now removes only exact validation-only operations
  and preserves pending, completed, malformed and unknown-extra evidence.
- Protected `GET /api/backups/status` truthfully reports manual-download
  history, scheduling inactive and no retained server copy. The unused
  `backups` table remains unchanged.

### Recovery and diagnostic history

- Patches 427, 430, 432, 434, 436, 440 and 442 failed safely and were recovered
  by the next sequential scripts.
- Patches 433–441 built and checkpointed the backup artifact, download API,
  application lifecycle, strict restore validation, bootstrap and protected
  commit flow.
- Patch 443 delivered the first Settings backup/restore UI and passed terminal
  verification. Browser testing proved real download, validation and restore.
- Patches 444 and 445 failed before writes on brittle session and staging-shape
  assumptions. Patch 446 then failed only while formatting its diagnostic
  report.
- Patch 447 committed
  `docs/diagonostic_447_settings_tabs_restore_staging.md`, documenting exact
  validation-only and completed-success operation shapes.
- Patch 448 failed before writes because historical Patch 444 evidence was
  compared with the newer diagnostic HEAD.
- Patch 449 recovered the functional Settings sections and natural panel
  heights; desktop and mobile browser testing passed.
- Patch 450 committed and pushed the approved four-file frontend workspace.
- Patch 451 preserved completed restore evidence during expiry cleanup.
- Patch 452 failed and rolled back because its schema candidate added a blank
  line at EOF. Patch 453 recovered and pushed the protected manual-backup
  status API.
- Patch 454 failed before writes because its generated Settings marker count
  expected two intentional sites instead of three.
- Patch 455 built and deployed the status UI candidate, but its verifier
  searched for a CSS comment stripped by Vite. Rollback restored the exact
  clean Patch 453 source, deployment, database and staging state.
- Patch 456 failed before documentation writes because its endpoint check
  issued GET requests to POST-only protected routes. Patch 457 corrects
  the method-aware verifier and completes the boundary.

### Authoritative boundary state

- Local `HEAD` and `origin/main` before Patch 457:
  `76c24cdd9a634827e6f0d31f80651ae083000174`
- Deployment image before Patch 457:
  `sha256:c859bc308a8c495498924ba86ff057bf201fc6262769e010a6878367fbea3e27`
- Database SHA-256 before Patch 457: `91b0a498cd75b34f4db2be624cd0652d7cbdf9683ae0e0ff859303f8a099fa7c`
- Users: 1
- Sessions: 2
- Part types: 36
- Manufacturers: 9
- Packages: 23
- Locations: 1
- Parts: 15
- Projects: 7
- Project items: 10
- Reservations: 9
- Reservation items: 14
- Stock movements: 32
- Audits: 100
- App settings: 17
- Backups table rows: 0
- Restore staging operations: 3
- Pending restore jobs: 0

The six realistic Patch 401 parts and all current History remain intentionally
preserved.

### Next chat

The next chat is `Chat 17: Backup Status Finalization and MCP Foundation`.
It owns Patches 458–487 inclusive and Patch 487 is its planned boundary.

Patch 458 must recover the exact Patch 455 status-UI candidate while verifying
the built CSS through the durable custom property
`--partpilot-settings-manual-backup-status-v454`, not the stripped CSS comment.
The four frontend files must remain uncommitted until desktop and mobile
browser approval, followed by a separate checkpoint patch.


<!-- PARTPILOT:CHAT17_MCP_FOUNDATION_CHECKPOINT:V487 -->
## Chat 17 boundary — backup status finalization and MCP foundation

### Authoritative state after Patch 486

- `HEAD` and `origin/main` before this boundary:
  `219c0b9cd39efc2b62b5296a841432c7a0d7d5f4`
- Alembic head: `0009_mcp_direct_auth`
- Deployment image: `sha256:ffd7330722d3150551894ebe24cc95e3275ea3ba9d9860894966388cb54bbcad`
- Deployment health: `healthy` with restart count
  `0`
- Database SHA-256: `1c242eeb874136578ee7d9af8b508c7c7a5a9e396c4b7965d31577cb9136c7b4`
- SQLite integrity: `ok`; foreign-key violations: `0`
- MCP direct-auth rows: `0`
- OAuth clients: `0`
- OAuth tokens: `0`
- Instance-secret file exists: `false`
- Restore staging operations: `3`

### Completed in Chat 17

- Manual-backup status UI was recovered, browser approved and checkpointed.
- MCP OAuth persistence, PKCE/consent, access and refresh token lifecycle,
  protected-resource metadata and authenticated HTTP endpoints are committed.
- `/mcp` is a stateless JSON Streamable HTTP endpoint with host/origin
  validation, OAuth Bearer authentication and disabled/read-scope gating.
- Six read-only tools are committed: inventory search/detail, Project
  list/detail and Reservation list/detail.
- MCP Settings exposes committed global enabled/read/write controls.
- Alembic `0009_mcp_direct_auth` adds encrypted direct-auth persistence.
- Direct Bearer keys use the `pp_mcp_key_` prefix, keyed validation digests,
  encrypted-at-rest recoverable plaintext, rotation, reveal, disable,
  throttled last-use tracking and secret-free audits.
- Protected management endpoints now provide direct-auth status, create/rotate,
  reveal and disable operations with no-store responses.
- No key, direct-auth row or instance-secret file is created automatically.

### Recovery history

- Patches 473–476 failed safely during the MCP Settings slice; Patch 477
  committed a diagnostic, Patch 479 passed browser testing and Patch 480
  checkpointed the controls.
- Patch 481 committed the direct-auth design diagnostic.
- Patch 482 failed because existing smoke tests changed only unrelated setting
  timestamps on a disposable database. Patch 483 isolated mutating smoke and
  committed the backend persistence/service foundation.
- Patch 484 assumed `sqlite_sequence` always existed. Patch 485 corrected that
  assumption but scoped instance-secret creation to the wrong helper. Both
  rolled back cleanly.
- Patch 486 scoped secret creation to rotation, improved error diagnostics and
  committed the five-file authenticated management API.

### Live data preserved

- Users: `1`
- Sessions: `3`
- Part types: `36`
- Manufacturers: `9`
- Packages: `23`
- Locations: `1`
- Parts: `15`
- Projects: `7`
- Project items: `10`
- Reservations: `9`
- Reservation items: `14`
- Stock movements: `32`
- Audits: `105`
- App settings: `17`

### Next chat

The next chat is `Chat 18: Static Bearer MCP Integration`.

- Patch range: 488–517 inclusive
- First patch: 488
- Planned boundary: Patch 517

Patch 488 must inspect the exact committed runtime and tool-audit principal
contract, then connect only `pp_mcp_key_...` Bearer credentials to `/mcp` while
preserving OAuth behavior. Direct-key Settings UI, browser approval,
custom-header mode, trusted-network mode and safeguarded write tools remain
separate later slices.

<!-- PARTPILOT:CHAT18_MCP_AUTHENTICATION_CHECKPOINT:V512 -->
## Chat 18 milestone — MCP authentication stack complete

### Authoritative application state after Patch 511

- Feature commit and `origin/main`:
  `e0241ecc7e51271944867110714b96b4259a09f9`
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Deployment health: `healthy`; restart count: `0`
- Database SHA-256:
  `b720faff64ac220abb4722fe91756e03bbb79b260691c38f9a89373e50740f10`
- SQLite integrity: `ok`; foreign-key violations: `0`
- Parts: `15`; Projects: `7`; Reservations: `9`
- Stock movements: `32`; audits: `114`; app settings: `17`
- MCP direct-auth rows: `1`; OAuth clients/tokens: `0/0`
- Active direct-auth mode: rotated Bearer key
- Active custom header: none
- Active trusted-network JSON: none
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`

### Completed authentication work

- Static `pp_mcp_key_` Bearer credentials are recognized without weakening
  OAuth Bearer validation.
- Direct principals produce compatible tool-call audit attribution.
- Settings supports create, reveal, copy, rotate, disable, and mode switching.
- Custom-header mode has protected management API, runtime dispatch, validation,
  responsive Settings controls, and browser approval.
- Alembic `0010_mcp_trusted_networks` adds trusted-network persistence.
- Trusted-network management canonicalizes IPv4/IPv6 CIDRs and rejects empty,
  malformed, trust-all, multicast, unspecified, duplicate, overlapping, or
  over-limit configurations.
- Uvicorn implicit proxy-header rewriting is disabled.
- The explicit trusted-proxy/client-IP resolver ignores spoofed forwarding
  headers from untrusted peers.
- MCP and OAuth public-origin construction uses the resolver and the configured
  public base URL.
- Trusted-network runtime accepts keyless access only when no explicit
  credential is supplied and the resolved client belongs to an approved CIDR.
- Invalid explicit OAuth or direct credentials never fall back to network trust.
- The trusted-network Settings UI was browser approved and committed by
  Patch 511.
- OAuth, Bearer, custom-header, and trusted-network regression paths coexist.
- The live installation remains in Bearer-key mode; no trusted CIDR is active.

### Remaining MCP work

- External MCP client compatibility testing and connection guidance.
- Independent OAuth/direct-auth administration refinements, if required.
- Safeguarded write-tool contracts, explicit confirmation semantics, stock
  invariants, and destructive-action auditing.
- Accessibility, security, and public-alpha release hardening.

Patch 513 should inspect external-client behavior and the remaining control/write
contracts before another application implementation slice.

<!-- PARTPILOT:CHAT18_BOUNDARY_CHECKPOINT:V517 -->
## Chat 18 boundary — MCP authentication and external-read readiness

### Authoritative state before the boundary commit

- `HEAD` and `origin/main`:
  `f9520747f6123e38ac0f99be273076da79e21b8e`
- Latest subject: `Verify isolated MCP SDK compatibility`
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Deployment: running, healthy, restart count `0`
- Database SHA-256:
  `63ed48d4f96675ec371465515eb7478572b341abc9a85e8fb81f2a9fa85bd9fa`
- Database size: `688128` bytes
- SQLite integrity: `ok`; foreign-key violations: `0`
- Parts: `15`; Projects: `7`; Reservations: `9`
- Stock movements: `32`; audits: `135`; app settings: `17`
- MCP settings: enabled/read/write = `true/true/false`
- Direct-auth row: mode `bearer_key`; cipher/digest/prefix lengths
  `164/64/20`; rotation present; last-use absent
- OAuth clients/codes/consents/tokens: `6/5/5/0`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`

### Completed in Chat 18

- Static Bearer runtime and compatible direct-principal audit attribution.
- Direct-auth Settings management for create, reveal, rotate, disable, and mode
  switching.
- Custom-header management API, runtime, validation, tests, and browser UI.
- Trusted-network persistence, protected management, strict IPv4/IPv6
  validation, runtime dispatch, Settings UI, and browser checkpoint.
- Explicit trusted-proxy/client-IP resolution with Uvicorn proxy rewriting
  disabled.
- Trusted forwarded-origin construction for MCP and OAuth.
- Official MCP SDK proof against a copied database and the exact deployed image.
- Live read-only MCP activation with write authorization left disabled.
- Official SDK `initialize`, all six tools, and real `search_parts` through
  `https://part.devansh.cc/mcp`.
- Public metadata advertises only `mcp:read`.

### External-browser finding

Claude, Google, and ChatGPT successfully performed dynamic registration. Browser
authorization accepted the Part Pilot credentials, granted `mcp:read`, issued
authorization codes, and returned HTTP `302` callbacks. No client completed a
token exchange.

The current standalone consent page uses private inline CSS rather than the
React design system. Browser autofill overrides its field colors. More
importantly, the first Authorize submission succeeds and deletes the one-time
CSRF cookie, while a second click submits the same form again and replaces the
redirect with a raw `Authorization request expired` page.

The security contract is correct; the browser UX is incomplete.

### Exact abandoned external-test evidence

Preserve these rows until an allowlisted cleanup after successful retesting:

- OAuth client IDs `1-3`: Claude
- OAuth client IDs `4-5`: Google
- OAuth client ID `6`: ChatGPT
- Authorization-code IDs `1-5`: issued and unconsumed
- Consent IDs `1-5`: `mcp:read`
- OAuth token rows: none

Do not delete by client name or broad date range. Any cleanup must verify these
exact IDs, zero token ownership, expected redirect URI shapes, and unchanged
unrelated OAuth rows before deletion.

### Next chat

The next chat is `Chat 19: OAuth Connector Completion and MCP Write Foundation`.

- Patch range: `518-547`
- First patch: `518`
- Planned boundary: `547`

Patch 518 must repair the OAuth browser workflow before write-tool work:
consistent standalone Part Pilot styling, autofill treatment, immediate
submit-button locking, clicked-button progress text, duplicate-POST prevention,
and styled expired/invalid/unavailable pages. Preserve one-time CSRF behavior.
The application source remains browser-test pending until Claude, Google, or ChatGPT
completes registration, consent, callback, token exchange, MCP initialization,
tool listing, and a read-only call.

<!-- PARTPILOT:CHAT19_SETTINGS_ADMINISTRATION_CHECKPOINT:V528 -->
## Chat 19 product-direction checkpoint — Settings administration and integration control

### Completed connector milestone

- Patch 527 committed and pushed the browser-approved OAuth connector workflow.
- Claude and ChatGPT are connected through OAuth with read-only MCP access.
- Hermes is connected through direct Bearer authentication.
- The standalone authorization page, duplicate-submit lock, callback-origin CSP,
  and styled OAuth error states are approved.
- MCP and read tools remain enabled; MCP write authorization remains disabled.
- Failed Patches 520-526 are consumed. Patch 527 is the authoritative source
  checkpoint.
- README must describe only implemented behavior. Planned features stay in
  durable project documentation until separately built and approved.

### Locked terminology polish

User-facing technical acronyms must preserve canonical capitalization:

- `MCP`, not `Mcp`
- `OAuth`, not `Oauth`
- `API`, `HTTP`, `HTTPS`, `URL`, `URI`, `ID`, `IP`, `CIDR`, `PKCE`, `UI`,
  `CSV`, and `JSON`

Use the shared formatter in History titles, entity labels, filters,
actor/authentication labels, metadata labels, and selected-event details. Raw
stored identifiers may remain visible in explicitly technical fields.

### Approved Settings information architecture

The Settings page will evolve into an administration console:

1. **General** — instance identity, locale, timezone, currency, date/time
   formats, default landing page, and navigation defaults.
2. **Appearance** — theme, accent, density, font size, reduced motion, contrast,
   table density, sidebar behavior, and display formatting.
3. **Inventory** — result defaults, stock rules, thresholds, required metadata,
   duplicate warnings, quantity precision, confirmations, and default
   catalogues.
4. **Reservations** — expiry defaults, validation, over-reservation policy,
   notes/Project requirements, warning thresholds, sorting, and optional
   expiration automation.
5. **Account & Users** — profile, username, display name, password, built-in
   avatars, sessions, and later multi-user roles/administration.
6. **Integrations** — MCP overview, OAuth clients, direct clients, tool
   permissions, connection guidance, and scoped REST API keys.
7. **Data & Maintenance** — backup, restore, exports, diagnostics, integrity,
   retention, and explicit cleanup utilities.
8. **Advanced** — technical, security-sensitive, and experimental controls.

### Account and user administration

The first account slice must support the current user:

- Change display name and username.
- Change password by providing the current password.
- Revoke other sessions after password change by default.
- Select a built-in Part Pilot avatar; uploaded avatars are a later storage and
  image-processing slice.
- View active sessions and revoke individual or all other sessions.

The design must remain compatible with multiple users. Future roles are Owner,
Administrator, Operator, and Viewer. The last Owner cannot be disabled, deleted,
or demoted.

### General REST API keys

REST API keys are separate from browser sessions, MCP direct keys, OAuth access
tokens, and OAuth client secrets.

Each key must have:

- User-supplied name and optional description.
- Generated `pp_api_...` secret shown exactly once.
- Only a cryptographic hash stored at rest.
- Visible prefix, creator, creation time, expiration, last use, and status.
- Scoped permissions for inventory, Projects, Reservations, History, Settings,
  backups, and user administration.
- Copy-once, rotate, revoke, and audit behavior.
- Dangerous permissions disabled by default.

### MCP administration and direct access

Keep a simple MCP overview and place detailed controls under **Advanced
Settings** or dedicated sub-tabs:

- Overview
- OAuth clients
- Direct clients
- Tools & permissions
- Connection setup
- Advanced

Direct access gains a master switch. When enabled, supported methods are no
authentication, Bearer key, custom header, and trusted network.

No-authentication mode is disabled by default, requires a warning and typed
confirmation, and must not authorize write tools in its first version. Local
loopback use is the intended safe case.

The eventual singleton direct-auth model becomes named clients such as Hermes
Agent, Local Claude Code, n8n Automation, or Workshop Assistant. Each receives
independent credentials/network rules, last-use information, tool policy,
rotation, and revocation.

### OAuth client administration

Settings must distinguish Registered, Connected, Abandoned, and Revoked OAuth
clients.

The connected-client list shows name, client ID, redirect origin,
public/confidential type, authentication method, scopes, connection time, last
use, active token/session count, and revocation control.

Revocation invalidates active token families and unused authorization codes,
records an audit event, and preserves history rather than deleting it.

Manual registration asks for client name, redirect URI(s), client type, and
token-endpoint authentication method. Part Pilot generates the client ID and
one-time client secret when required.

### Global and per-client MCP tool policy

Tool authorization uses this hierarchy:

1. Global MCP enabled switch.
2. Global read/write category switches.
3. Global individual-tool policy.
4. Client-specific `Inherit`, `Allow`, or `Deny` override.
5. Runtime authorization and audit.

A client override cannot exceed the global ceiling. `Deny` wins. Enforce the
policy in both `tools/list` and `tools/call`; hiding a tool alone is not
security.

Write tools require the global write switch, individual tool enablement,
client permission, OAuth `mcp:write` when applicable, and tool-specific
confirmation/idempotency. Per-client policy is implemented before
inventory-mutating MCP tools.

### Preference restoration

Every preference section receives a real **Restore defaults** action that shows
a before/after summary, resets only that section's documented settings, writes
one audit event, applies immediately, and preserves unrelated sections.

A global **Restore all preference defaults** action resets preference keys only.
It must not erase inventory, Projects, Reservations, users, passwords, API keys,
OAuth clients, direct credentials, backups, or audit history.

MCP preference reset and destructive MCP access reset remain separate.

### Locked implementation order

1. Normalize History technical acronyms.
2. Diagnose and clean only exact abandoned OAuth test rows.
3. Add connected OAuth client listing and revocation.
4. Add manual OAuth client registration and one-time secret handling.
5. Add current-user profile, password, session, and built-in-avatar controls.
6. Add scoped REST API keys.
7. Add the direct-client master switch, no-auth mode, and named direct clients.
8. Add global individual-tool and per-client MCP policies.
9. Expand General, Appearance, Inventory, Reservations, and Data settings.
10. Add section-specific and global preference-default restoration.
11. Add multi-user roles and administration.
12. Define and implement safeguarded MCP write tools on top of the permission
    model.
13. Complete accessibility, security, documentation, and public-alpha
    hardening.

<!-- PARTPILOT:CHAT19_ABANDONED_OAUTH_CLEANUP:V532 -->
## Chat 19 abandoned OAuth operational-row cleanup

Patch 532 completed the exact token-free cleanup approved by the Patch 531
diagnostic.

Removed operational rows:

- OAuth client IDs: `1-8, 10-12, 14-17`
- Authorization-code IDs: `1-8`
- Consent IDs: `1-7`
- Token IDs: none

Preserved connected state:

- Claude client `9`, code `9`, consent `8`, token family rows `1` and `3`
- ChatGPT client `13`, code `10`, consent `9`, token row `2`
- All 40 pre-existing OAuth audit-history rows
- Hermes direct Bearer configuration
- MCP enabled/read/write settings `true/true/false`

Post-cleanup operational counts are two clients, two authorization codes, two
consents, and three token rows. SQLite integrity and foreign-key checks passed.
No application source, migration, build, deployment image, credential, README,
inventory, Project, Reservation, user, or restore-staging state changed.

The next implementation slice is connected OAuth client visibility and
revocation in Settings.

<!-- PARTPILOT:CHAT19_BOUNDARY_CHECKPOINT:V548 -->
## Chat 19 boundary — OAuth connector completion and client administration

### Authoritative pre-boundary state

- `HEAD` and `origin/main`: `35be283e7f63306aef29480ae5ab71c08225b32c`
- Latest subject: `Diagnose manual OAuth registration readiness`
- Git/index: clean
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:d601fea120915e2cdfec4d1da166c95f5afc78f5e257d7b0bce5d6ddd9075207`
- Deployment: running, healthy, restart count `0`
- Database SHA-256 at boundary capture:
  `2cf5f4bb7dc8773b1b5122411bb0db63ce9ed891fb2de19bfa955bb9b5844d91`
- Database size: `724992` bytes
- SQLite integrity: `ok`; foreign-key violations: `0`
- Parts: `15`; Projects: `8`;
  Reservations: `10`
- Stock movements: `33`; audits:
  `175`; app settings: `17`
- Users: `1`; sessions: `4`
- MCP enabled/read/write: `true/true/false`
- Direct-auth mode: `bearer_key`; Hermes credential preserved
- OAuth client IDs: `9` Claude and `13` ChatGPT
- Authorization-code IDs: `9, 10`
- Consent IDs: `8, 9`
- OAuth token rows at capture: `4`; one active token
  and one token family for each connected client
- OAuth revocation audit rows: `0`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`

OAuth access and refresh rows can rotate during normal client use. Future
validation must compare connected-client semantics, active consent/token count,
and token-family ownership rather than hard-coding token row counts or
timestamps.

### Boundary recovery

Patch 547 failed before documentation writes because its README validator
searched for a phrase that was split across Markdown source lines. Patch 548
consumes the next sequential number and performs this narrow documentation-only
boundary recovery. No source, index, database, deployment, credential, commit,
or push changed during the failed Patch 547 run.

### Completed in Chat 19

- Rebuilt the standalone OAuth consent and error pages with Part Pilot styling,
  autofill treatment, submit locking, progress labels, callback-origin CSP, and
  duplicate-POST prevention without weakening one-time CSRF behavior.
- Completed real Claude and ChatGPT OAuth token exchange, MCP initialization,
  tool listing, and read-only access.
- Committed the approved OAuth browser workflow in Patch 527.
- Diagnosed and removed only exact abandoned token-free OAuth operational rows
  while preserving connected Claude and ChatGPT state and all audit history.
- Added protected connected-client administration:
  - safe current-user listing;
  - no-store responses;
  - exact client revocation;
  - token-family, consent, and unused-code invalidation;
  - secret-free audit history;
  - copied-database restoration and unrelated-client preservation.
- Added the responsive Connected OAuth clients Settings UI and guarded revoke
  dialog.
- Corrected supplied History labels so `Mcp Oauth Token` renders as
  `MCP OAuth Token` while ordinary entity names remain unchanged.
- Browser-approved and committed the Settings and History frontend batch in
  Patch 545.
- Patch 546 diagnosed manual registration readiness and proved that explicit
  creator ownership is required before registered-but-unconnected clients can
  be managed safely.

### Manual-registration ownership finding

The existing OAuth service already generates `pp_mcp_client_...` identifiers,
generates `pp_mcp_secret_...` values for confidential clients, returns the
plaintext secret once, stores only a digest, validates redirects, and writes a
registration audit.

The `mcp_oauth_clients` table has no creator/owner column. A newly registered
manual client has no consent or token yet, so current-user ownership cannot be
inferred from connected-client rows. Ownership must never be guessed from
client names, redirect origins, timestamps, row order, or audit prose.

### Next chat

The next chat is `Chat 20: Manual OAuth Registration Foundation`.

- Patch range: `549-578`
- First patch: `549`
- Planned boundary: `578`

Patch 549 begins with Alembic `0011_mcp_oauth_client_ownership`, a nullable
`registered_by_user_id` foreign key, protected registration schemas/service/API,
one-time secret handling, and copied-database backend smoke. Existing dynamic
registrations remain nullable; do not backfill ownership by inference.

No `Chat_20_Starting_Prompt.md` file should be created. The ready-to-paste
prompt belongs only in the chat response after Patch 548 succeeds.

<!-- PARTPILOT:CHAT20_BOUNDARY_CHECKPOINT:V580 -->
## Chat 20 boundary — manual OAuth registration and profile foundation

### Authoritative pre-boundary state

- `HEAD` and `origin/main`: `fb5e0275f643a4420914c35093a0afb3f898c6a3`
- Latest subject: `Diagnose password and session administration readiness`
- Git/index: clean
- Alembic: `0012_user_avatar_id`
- Deployment image: `sha256:81808e52e783e7a3807ae1af899a1875aff502236cdbfb40448844cc2a6c0dd0`
- Deployment: running, healthy, restart count `0`
- Database SHA-256 at capture: `d010f1e4bc14333a3d32071220f7c742242a2ebc81fb9c62373e7ae450f258ea`
- Database size: `741376` bytes
- SQLite integrity: `ok`; foreign-key violations:
  `0`
- Parts: `15`; Projects: `8`;
  Reservations: `10`; movements:
  `35`; audits: `201`
- Users: `1`; sessions: `4`;
  active sessions: `4`
- Current owner/profile: user `1`, username `devanshtangri`, display name
  `Devansh Tangri`, avatar `initials`
- MCP enabled/read/write: `true/true/false`
- Direct-auth mode: `bearer_key`; credential digest/ciphertext preserved
- OAuth operational rows at capture: clients `9`,
  codes `6`, consents `6`,
  token rows `6`
- Instance-secret SHA-256: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging: `15` files; fingerprint `6712ba4090860b1ebb77962a343549fa5fd33b45f035fd3bae4cacc4cac1a543`

OAuth token rows can rotate or expire during normal external-client activity.
Future validation must compare ownership, revocation, consent and token-family
semantics rather than hard-coding transient access-token timestamps/counts.

### Completed in Chat 20

- Added Alembic `0011_mcp_oauth_client_ownership` with nullable
  `registered_by_user_id`; historical dynamic registrations were not
  backfilled by inference.
- Added protected manual OAuth registration with public/confidential client
  types, compatible token-endpoint authentication, generated client IDs, and
  one-time confidential secrets stored only as digests.
- Added current-user manageable OAuth client listing with
  registered/connected/revoked semantics.
- Extended exact client revocation to current-user-owned registered clients.
- Added typed frontend registration/manageable contracts.
- Added and browser-approved the responsive manual registration UI,
  one-time credential dialog, client revocation flow, revoked-client hiding,
  submit-attempt validation, and final simplified form layout.
- Patch 570 removed only browser fixture client `14` and its exact test audit
  rows while preserving unrelated historical audit row `156`, then committed
  and pushed the approved UI.
- Real manual OAuth testing verified Claude confidential registration with
  `client_secret_post` and callback
  `https://claude.ai/api/mcp/auth_callback`.
- Gemini/Google DCR reached consent and code issuance, but Google did not
  redeem the issued code; no Part Pilot OAuth weakening was introduced for
  that external-client behavior.
- Added Alembic `0012_user_avatar_id`, built-in avatar catalogue, protected
  profile read/update API, username/display-name/avatar validation, `/auth/me`
  avatar response, secret-free profile audit, and copied-database smoke.
- Preserved the owner's password and all four existing sessions through the
  profile migration.
- Patch 577 documented the exact password/session administration contract for
  Chat 21.

### Boundary recovery

Patch 578 failed before any writes because its preflight contained one mistyped
SHA-256 for `frontend/src/services/settingsClient.ts`.

Patch 579 corrected that fingerprint but also failed before writes. Its
generated Roadmap used bold field labels while the validator searched for an
unbolded `Patch range:` marker, and that Roadmap block still carried stale
first-patch/boundary values `579` and `608`.

Patch 580 is the narrow boundary recovery. It validates both failed script/log
pairs, validates exact formatted Roadmap fields, uses the corrected Chat 21
range `581-610`, and consumes patch number 580 before Chat 21 starts.

### Failure/recovery lessons carried forward

- Patches 572 and 573 failed before writes because validators were stricter
  than the generated source semantics: a pre-existing double-newline EOF and
  an intentionally repeated symbol were treated as errors.
- Patch 575 diagnosed the exact six generated candidate hashes and required
  explicit per-marker counts plus post-transform EOF canonicalization.
- Patch 576 used those locked hashes/counts and completed successfully.
- Always compile the final downloadable patch itself before delivery; Patch
  574 was consumed by an f-string syntax error before any diagnostic logic
  executed.
- Never search internal logs for terminal-only failure summaries.

### Next chat

The next chat is `Chat 21: Account Security and Session Administration`.

- Patch range: `581-610`
- First patch: `581`
- Planned boundary: `610`
- Patch 581 begins from
  `docs/diagonostic_password_session_admin_readiness_patch_577.md`.

No `Chat_21_Starting_Prompt.md` file should be created. The ready-to-paste
prompt is provided only in chat after Patch 580 succeeds.

<!-- PARTPILOT:CUSTOM_AVATAR_AND_NOTIFICATIONS_SCOPE:V595 -->
## Patch 595 scope decision — custom avatars and post-v1 notifications

Custom uploaded profile images are promoted into the current Account/Security
completion slice. The first implementation stores normalized image bytes inside
SQLite so existing database-backed backup/restore semantics preserve them.
`avatar_id` remains the built-in fallback.

The custom-avatar implementation must use server-side image decoding and
normalization, safe size/type limits, secret-free audit metadata, authenticated
image access, and copied-database/backup preservation tests.

The pending Account browser-test source remains uncommitted until approval.
Desktop Profile and Password cards will be equal height, built-in avatar choices
will be icon-only with accessible labels, and the complete sidebar identity block
will navigate to `/settings#settings-account`.

Notifications & Messaging are deferred until after the first release. Future
scope includes optional user email, SMTP configuration with encrypted secrets,
additional pluggable notification channels, per-user event subscriptions,
delivery history/retry state, and event-level notification selection.

<!-- PARTPILOT:RECYCLE_BIN_CONTRACT:V607 -->
## Recycle-bin and custom Part Type dependency contract — Patch 607

Part deletion remains recoverable by default. A part in Deleted items is still a
restorable inventory record, so every resource required for a meaningful restore
must remain protected until the part is restored or permanently purged.

- Custom Part Types cannot be deleted while either active inventory or Deleted
  items reference them.
- The Part Type delete dialog reports active and recoverable dependency counts
  separately. A blocked dialog leads with `Cannot delete <type>`, hides destructive
  confirmation controls, lists up to five blocking part names per dependency class,
  and summarizes any remainder as `+N more`.
- When Deleted items are a blocker, the dominant action opens Deleted items
  directly with an exact Part Type filter already applied.
- Deleted items supports single/multi-select permanent purge plus Select visible.
- Permanent purge is explicit, requires `DELETE`, is atomic for the whole batch,
  releases the part number, removes aliases/tags/custom values, retains audit
  history, and detaches historical movements and terminal Project/Reservation
  rows through existing `SET NULL` foreign keys.
- Permanent purge is blocked by reserved quantity, Active Reservations, and Draft
  or Reserved Projects.
- The invariant is: if Part Pilot offers Restore, the part's Part Type and field
  definitions must still exist so restoration remains meaningful.

Patches 608 and 609 refined the dependency-first dialog and its full-width blocker
presentation. Browser validation then permanently purged ESP01, successfully
deleted the now-unblocked Development Board custom Part Type, and confirmed that
5V Relay remains recoverable in Deleted items.

Patch 610 exposed a historical-audit ID-reuse assumption in the old full smoke;
Patch 611 had a bytes/string recovery-harness failure; Patch 612 omitted a
`tempfile` import; and Patch 613 completed the required diagnostic-only snapshot.
Patch 614 applies only the diagnosed two-function smoke boundary fix and
checkpoints/pushes the complete browser-approved V607-V609 application batch.

<!-- PARTPILOT:CHAT21_EXTENSION_CHECKPOINT:V614 -->
## Chat 21 extension checkpoint

The user explicitly granted a one-chat exception extending Chat 21 through
**Patch 629**. Patch 629 is the new boundary/handoff patch. No Chat 21-to-22
handoff is created at this checkpoint. Patch 615 is the next implementation slot,
and Chat 22 begins at Patch 630 only after Patch 629 succeeds.

Remaining Settings/MCP UX requirements are durable: Settings needs clear visual
section grouping/dividers; `Enable MCP server` must be the first MCP master
control; disabling it must visibly mute/disable every subordinate MCP control;
and read/write/tool authorization belongs in a clear permissions/security group.
Final section names should be chosen during implementation rather than copied
mechanically from this note.

<!-- PARTPILOT:REST_API_KEY_FOUNDATION:V615 -->
## Scoped REST API-key foundation — Patch 615

Patch 615 adds the backend key lifecycle without yet granting API-key access to
application routes. Keys are named, high-entropy `pp_api_key_` credentials shown
only on create/rotate, stored digest-only, explicitly scoped, optionally expiring,
revocable, and last-used tracked. Management remains authenticated user-session
only. The initial scope catalogue covers inventory, catalogues, Projects,
Reservations and History; Auth, Settings, Backup and Restore administration are
intentionally excluded. Alembic advances to `0014_api_keys`, and backup/restore
exact-schema policy includes the new table. Patch 616 attempted the route-scope
follow-up but failed before writes because its frozen tracked diff omitted the new
untracked scope-smoke file. Patch 617 carries that tested smoke as a separate
frozen payload and applies the same route-scope design.

<!-- PARTPILOT:REST_API_KEY_ROUTE_SCOPES:V617 -->
## Scoped REST API-key enforcement — Patch 617

Patch 617 accepts `pp_api_key_` Bearer credentials only on explicitly scoped
Inventory, Catalogue, Project, Reservation and History routes. Browser/user
sessions retain their existing access. Missing/invalid/revoked/expired keys are
401; valid keys missing the route scope are 403; successful key calls update
`last_used_at`. Auth, Settings, Backup and Restore remain session-only. A route
contract smoke introspects every registered eligible method/path so unmapped or
mis-scoped routes fail automatically.


<!-- PARTPILOT:API_UI_AND_INVENTORY_METRICS_PLAN:V618 -->
## API access UI and inventory metrics follow-up — Patch 619 browser-test recovery

- API-key Settings administration must expose create/list/edit/rotate/revoke,
  one-time secret copy, and a persistent `API Documentation ↗` action. The
  create/rotate one-time-secret dialog also includes `Open API docs ↗`, opening
  `/docs` in a new tab. API documentation access policy must be deliberately
  protected before public alpha; API keys do not administer Settings/Auth/Data.
- Currency was already collected and persisted during setup and already belonged
  to the planned General Settings expansion. The missing V1 UI is an explicit
  Settings currency selector using the stored app-wide ISO currency. Changing the
  selector changes formatting only; it never performs live FX conversion.
- Stored Parts needs server-backed whole-inventory summary metrics independent of
  pagination: `Total components` is the sum of active `total_quantity`; `Inventory
  value` is the known sum of `total_quantity × unit_price` in the selected app
  currency. Reserved units remain physically owned and therefore remain included.
  The value metric must disclose price-data coverage rather than presenting
  missing prices as zero-value stock. Supporting metrics are Available, Reserved,
  Low stock, Out of stock and distinct Part-record count.

<!-- PARTPILOT:API_ACCESS_CANONICAL_BUILD_CHECKPOINT:V626 -->
## API Access and canonical-build checkpoint — Patch 626

Patch 620 is browser approved. API Access provides scoped REST key lifecycle,
one-time-secret handling, API-documentation actions, aligned fields/readable scope
chips, hidden revoked records and modal rotate/revoke flows. MCP direct credential
create/rotate/mode-change/disable uses the same consequential-action dialog
language; ordinary reversible settings remain inline. Both browser-test REST keys
remain revoked audit records and MCP direct authentication is Disabled.

Checkpoint recovery exposed two non-Git Docker-context contaminants. Patch 623
diagnosed 112 ignored backend `.pyc` files entering Docker because `.dockerignore`
was absent. Patch 625 then proved 26 tracked Docker-source files (16 backend, 10
frontend) had filesystem mode `0600` while Git canonical mode was `100644`; bytes
were identical, but Docker COPY layer identity changed. Patch 626 adds the minimal
`.dockerignore`, normalizes tracked backend/frontend files to Git-canonical modes
without changing bytes, and requires exact clean/contaminated/live-root image
convergence before commit. This canonical-context rule is now a patch-workflow
invariant for exact Docker image comparisons.

The later broader Settings task must add restrained section dividers/grouping
throughout Settings wherever hierarchy benefits, not only MCP. MCP still requires
`Enable MCP server` first, subordinate controls muted/disabled while off, and
read/write/tool authorization grouped under permissions/security.


<!-- PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_CHECKPOINT:V632 -->
## Named direct MCP clients checkpoint — Patch 632

Patch 627 adds Alembic `0015_mcp_direct_clients` and replaces singleton direct-auth administration with named Bearer, custom-header and trusted-network clients. Each client has independent identity, enable/disable, rotation/revocation and safe usage metadata. OAuth remains separate. `Allow direct MCP clients` is the direct-access master; instance-wide `No authentication` remains off by default, requires typed `ALLOW NO AUTH` confirmation to enable, and is read-only. Explicit OAuth/direct credentials take precedence, then trusted-network identity, then no-auth fallback. MCP write authorization remains disabled.

Browser refinement fixed the named-client typography/card mapping, aligned the MCP server URL/OAuth/direct-client/capability blocks with MCP Access, and removed compounded disabled opacity. Patch 628 failed only because a CSS comment marker was stripped by production minification. Patch 629 failed before writes from a frozen CSS fingerprint mismatch. Patch 631 then detected that its exact intended CSS/image had already been applied by an accidental live rehearsal; no additional source write was performed by the numbered script. Patch 632 formally adopts those exact browser-approved bytes, reruns deterministic build/smoke/preservation checks, and commits/pushes the complete 24-file application batch plus durable docs.

The broader Settings task still owns restrained section dividers/grouping throughout Settings wherever hierarchy benefits. Global individual-tool/per-client MCP permissions remain next after the boundary; safeguarded MCP write tools stay disabled until that policy exists.

Chat 21 boundary is now Patch 633 because Patches 628, 629 and 631 were consumed during visual/recovery work. Patch 633 must create the Chat 21-to-22 handoff; Chat 22 starts at Patch 634 only after that boundary succeeds.

<!-- PARTPILOT:CHAT21_BOUNDARY:V633 -->
## Chat 21 boundary — Patch 633

Chat 21 is complete. Patch 632 checkpointed and pushed the browser-approved named-direct MCP client administration/master/no-auth work at commit `88ca83cd407d63772e027cac409357f5bc192ad0`. Patch 633 is documentation-only: it creates the Chat 21-to-22 handoff, refreshes durable docs/README, and commits/pushes the boundary without changing application source, deployment, database, credentials, fixtures or inventory.

The earlier Patch 629 boundary plan was superseded after Patches 628, 629 and 631 were consumed during visual/recovery work. The authoritative next-chat identity is:

- Title: `Chat 22: MCP Permissions and Settings Organization`
- Patch range: `634-658`
- First patch: `634`
- Planned boundary: `658`
- Patch 634 should be diagnostic-only for the global individual-tool/per-client MCP permission slice before implementation.

Chat 22 must start by reading `docs/Chat_21_to_Chat_22_Handoff.md`, then `docs/Checkpoint.md`, `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`, `README.md`, and the newest relevant diagnostic. Do not create a starting-prompt file.

<!-- PARTPILOT:CHAT22_RESPONSIVE_CHECKPOINT:V642 -->
## Chat 22 responsive regression checkpoint — Patch 642

Patches 634-641 resolved the user-reported intermediate-width Projects/detail
collapse and the related application-shell width pressure before MCP-permission
work resumed.

- Patch 635 recovered the diagnostic after Patch 634's schema-assumption failure
  and proved the Projects defect was CSS flex-size competition: the non-shrinking
  lifecycle action group starved the title while `overflow-wrap:anywhere`
  permitted character-level collapse.
- Patch 637 is browser approved. Draft/Reserved lifecycle actions stack only in
  the intermediate desktop range where they need space, Project titles wrap at
  sensible word boundaries, terminal states stay compact, and the existing
  `<=900px` fixed/mobile detail behavior remains intact.
- Patch 640 is browser approved. The application shell now uses the existing
  navigation drawer from `821-1080px`, retaining desktop content spacing while
  removing the persistent 232px sidebar. Above 1080px the persistent sidebar
  remains; at `<=820px` the existing compact/mobile shell remains unchanged.
- Patches 636, 638 and 639 were consumed by safe pre-write/build-harness
  recoveries. Patch 640 deployed the exact approved V637/V638 source at image
  `sha256:45484acf35311d5efee4f9c38c19d6edbadca137cc0f7b0039110b2ebf50458b`.

Patch 642 commits/pushes the two browser-approved CSS files plus durable docs.
No application bytes, deployment, database, credentials, restore staging or
inventory are changed by the checkpoint itself.

Chat 22 remains bounded at Patch 658. The next patch is Patch 642 and resumes the
deferred diagnostic-only global individual-tool/per-client MCP permissions
slice before any permission implementation.


<!-- PARTPILOT:AUTOSAVE_LIVE_SYNC_TASK:V656 -->
## Autosave and live-synchronization task added — Patch 656

User-requested cross-cutting V1 behavior is now durable before further Settings
work:

- Reversible preferences will no longer require ordinary Save buttons. Discrete
  controls persist immediately; text/number preferences use a short debounce.
  `Reset changes` disappears.
- One explicit `Reset to defaults` action remains for preference restoration.
  It must preserve application/security/business data and is separate from
  destructive access/data reset.
- Create/edit forms and consequential security/data actions remain explicit;
  autosave is not a blanket replacement for submit/confirmation workflows.
- Routine manual Refresh controls should be replaced by live server-driven
  invalidation plus targeted refetch. Preferred V1 transport is authenticated
  SSE with reconnect/resync; polling is fallback only. Manual Retry remains for
  genuine errors.
- The current six MCP permission rows represent the six tools that actually
  exist. Future safeguarded write tools must surface automatically from the
  canonical catalogue once implemented rather than being represented by
  placeholder controls.

Patch 656 is documentation-only and must not consume, stage or modify the
pending Patch 654 browser-test application source. Patch 655 was consumed by a
pre-write durable-log assertion and made no source/deployment/data changes.
Patch 657 resumes the MCP browser-feedback fix; Patch 658 remains the Chat 22
boundary.


<!-- PARTPILOT:CHAT22_BOUNDARY_RECOVERY:V660 -->
## Chat 22 boundary recovery — Patch 660

Chat 22 closes through narrow documentation-only boundary recovery after the
successful Patch 659 diagnostic.

The application working tree remains the authoritative 22-file MCP permission
browser-test batch. Patch 660 does not stage, commit, reset, rewrite or deploy
those files.

Current state carried into Chat 23:

- Alembic `0016_mcp_tool_permissions` is live.
- Global exact-tool permissions and OAuth/named-direct inherit-or-deny APIs are
  implemented in pending source.
- Patch 654 deployed the permission Settings UI.
- Browser testing deliberately left `search_parts=false`; the other five read
  tools are globally enabled and all OAuth/direct client deny lists are empty.
- Call-time authorization already blocks ineffective tools.
- Remaining browser feedback is principal-aware `tools/list` filtering, visibly
  disabled client overrides under a global block, honest Write-tools catalogue
  state, and consistent Add-direct-client field styling.
- Patch 657 attempted that refinement but failed before writes because its
  packaged workspace-smoke formatting did not match the passed rehearsal SHA.
- Patch 658 attempted the boundary but failed before writes because three new
  Roadmap identity lines contained prohibited trailing spaces.
- Patch 659 diagnosed both failures and committed/pushed only its report.

Authoritative next-chat identity:

- Title: `Chat 23: MCP Permission Finalization and Settings Modernization`
- Patch range: `661-685`
- First patch: `661`
- Planned boundary: `685`

Patch 661 resumes the already-rehearsed MCP permission refinement. It must
rehearse and hash the exact packaged bytes before the first live write.


<!-- PARTPILOT:MCP_PERMISSIONS_CHECKPOINT:V662 -->
## Chat 23 MCP permission checkpoint — Patch 662

Patch 661 is browser approved and completes the individual-tool/per-client MCP
permission slice that began in Chat 22.

- Alembic `0016_mcp_tool_permissions` persists the canonical global exact-tool
  policy plus OAuth/named-direct denied-tool overrides.
- Global policy remains the hard ceiling; named clients inherit-or-deny only.
  No-auth keeps global-policy-only semantics and does not invent a client identity.
- Authenticated MCP `tools/list` is now principal-aware. Globally denied tools and
  OAuth/named-direct client-denied tools are omitted from the returned catalogue,
  while existing `tools/call` authorization remains the second enforcement layer.
- The six registered tools are explicitly presented as read tools. The Settings UI
  honestly reports `Write tools — 0 available`; no placeholder write permissions
  are invented before real safeguarded runtime contracts exist.
- Client overrides below a global block are visibly disabled and non-editable.
  Add-direct-client identity/authentication fields now use consistent themed
  sizing, background, borders, focus treatment and alignment.
- Permission smoke tests snapshot real configuration and normalize only disposable
  copied databases. The live browser-test policy is intentionally preserved as
  `search_parts=false` with the other five read tools enabled and empty client
  denied-tool lists.
- Patch 661 deployed image
  `sha256:13b5a639e97a8d53460277290741ef5d408b775f73dfe97781aa09500c731b82`,
  healthy with restart count 0, Alembic 0016 and byte-identical live SQLite/secret.

Patch 662 commits/pushes exactly the 23 approved application files plus durable
Checkpoint, Roadmap and compact project-memory updates. It does not alter the
deployment, database, credentials, restore staging or live MCP configuration.

Patch 665 is browser approved and completes the first Settings hierarchy refinement:
`Allow direct MCP clients` and `No authentication` now live with Named direct clients
under Direct MCP access, while global Server/Read/Write controls remain separate.
Dependency-disabled switches use `not-allowed`; `wait` is reserved for real saves.
Patch 666 checkpoints/pushes that exact three-file batch. Reversible preference
autosave is the next Settings task, followed by authenticated SSE invalidation.


<!-- PARTPILOT:MCP_DIRECT_ACCESS_CHECKPOINT:V666 -->
## Chat 23 Direct MCP access checkpoint — Patch 666

- Patch 665 browser-approved the Direct MCP access hierarchy and disabled/saving cursor semantics.
- Approved source is exactly `Settings.tsx`, `Settings.css` and the repaired configuration-safe `mcp_settings_smoke_test.py`.
- Patch 663 exposed the stale five-field MCP settings smoke contract; Patch 664 then failed pre-write because it searched the durable log for terminal-only failure-summary text. Patch 665 corrected the evidence check and passed the complete copied-database suite.
- Live MCP policy, SQLite, instance secret, Alembic 0016 and deployment data remain preserved.
- Patch 666 commits/pushes the approved three-file batch plus durable documentation only.
- Next: reversible preference autosave and restrained Settings hierarchy cleanup; authenticated SSE invalidation follows.


<!-- PARTPILOT:REVERSIBLE_PREFERENCE_AUTOSAVE_CHECKPOINT:V669 -->
## Chat 23 reversible preference autosave checkpoint — Patch 669

- Patch 668 is browser approved. Appearance and the Stored Parts out-of-stock grouping already autosave discrete changes with rollback; Reservation defaults now follow the same no-ordinary-Save model.
- Reservation expiry mode persists immediately. Switching from no expiry to default expiry uses 30 days only when no prior duration exists. The numeric duration persists after a 550 ms debounce.
- Invalid reservation-day values stay local and are never PATCHed. Mutation/edit-version guards prevent late responses from overwriting newer typing; failed saves restore the last confirmed server value and expose an error state.
- Consequential/security workflows remain explicit: account/password changes, MCP access/tool permissions, OAuth/direct clients, API credentials, backup/restore, revoke/rotate/delete and business lifecycle mutations are not converted to preference autosave.
- Patch 667 was consumed by a pre-write assertion that incorrectly required terminal-only `Everything PASS` text in Patch 666's durable log. Patch 668 recovered with durable commit/push evidence and configuration-safe run-start MCP/database snapshots.
- Deferred dashboard-metrics UX: keep the Stock alert metric card, remove the inline Low stock inventory table, and make the card open a dialog listing all parts currently generating stock alerts. Implement this later with the broader dashboard metrics expansion.
- Patch 669 commits/pushes the exact browser-approved `Settings.tsx` plus Checkpoint, Roadmap and compact project-memory updates only. Live database contents, credentials, MCP policy and deployment are preserved.
- Next Settings slice: one guarded Reset preferences to defaults action that resets only reversible preferences and preserves users, sessions, credentials, inventory, Projects/Reservations, backups and audit/history data.


<!-- PARTPILOT:PREFERENCES_TARGETED_RESET_CHECKPOINT:V674 -->
## Chat 23 Preferences consolidation and targeted reset checkpoint — Patch 674

- Patch 673 is browser approved and replaces the rejected combined-reset design before it was committed.
- Settings now has one `Preferences` workspace for current reversible user-facing defaults: Theme, Inventory display and Reservation defaults. Legacy Appearance/Inventory/Reservations settings hashes redirect to Preferences instead of breaking deep links.
- Autosave semantics remain independent: Theme and Inventory display persist on selection; Reservation expiry mode persists immediately and default-days debounce remains 550 ms.
- Each current preference card has its own `Reset to default` action and target-specific confirmation. The authenticated reset contract accepts exactly one target: `appearance`, `inventory` or `reservations`.
- Targeted reset smoke coverage proves each target preserves the other preference groups, existing Reservation records, security/MCP/API configuration and business data; the two-key reservation reset is atomic.
- Defaults are Dark theme, separate out-of-stock results enabled, and no automatic reservation expiry.
- Currency belongs in Preferences next. Add the already-persisted app-wide ISO currency selector with locale-aware formatting only; do not perform FX conversion or rewrite historical stored numbers.
- Patch 674 commits/pushes exactly the eight browser-approved Patch 673 files plus Checkpoint, Roadmap and compact project memory. It does not redeploy or mutate live SQLite, credentials, MCP policy or the instance secret.

<!-- PARTPILOT:REGIONAL_DISPLAY_CHECKPOINT:V684 -->
## Chat 23 regional display checkpoint — Patch 684

- Patches 675 and 683 are browser approved and complete the regional display preference slice.
- Preferences now exposes a themed `Regional display` card with `Currency & timezone`; the controls use the Part Pilot select treatment, sit in two columns on wider screens and stack below 760 px.
- Currency is a persisted uppercase three-letter ISO display preference. Inventory/Add/Edit formatting follows the selected currency without FX conversion, and historical Project/Reservation currency snapshots remain authoritative.
- Display timezone is a persisted IANA timezone preference. It changes passive timestamp presentation across History, Projects, Reservations, Stored Parts/lifecycle and Settings/API/MCP surfaces without rewriting stored timestamps or changing datetime-local entry semantics.
- Backend currency/timezone APIs are protected and independently autosaved with no-op semantics, rollback/stale protection and targeted audit behavior. Copied-database currency, timezone, preference-reset and complete smokes pass.
- Patch 681 was consumed by a one-byte blank line at `Settings.css` EOF. Patch 682 corrected that byte but exposed an invalid deployment assertion that expected a TypeScript source comment to survive Vite minification. Patch 683 kept the exact application candidate and verified compiled runtime semantics instead.
- Browser-approved runtime image: `sha256:7a285a3ebb7eccf9eddb7c375a2b5616773e5aa40283ce270e41aff445ad23b9`, healthy with restart count 0 and Alembic `0016_mcp_tool_permissions`.
- Patch 684 checkpoints/pushes exactly the 20 approved application files plus durable documentation. It does not redeploy or intentionally mutate live SQLite, credentials, MCP policy or the instance secret.
- Next: Patch 685 closes Chat 23. Authenticated SSE invalidation/targeted refetch begins in the next chat.

<!-- PARTPILOT:CHAT23_TO_CHAT24_BOUNDARY:V685 -->
## Chat 23 complete — Chat 24 next

- Chat 23 owned patches `661-685` and is closed by Patch 685.
- Patch 684 checkpointed the browser-approved Regional display/currency/timezone work at pre-boundary HEAD `0d231871a46f490e4437711b6b9ab658334cd98d` (`Add regional currency and timezone preferences`).
- Chat 23 also checkpointed principal-aware MCP tool permissions, the Direct MCP Settings hierarchy, reversible preference autosave, Preferences consolidation with independent targeted resets, and the themed Regional display card.
- The application working tree and index are clean at the Patch 685 boundary. There is no pending browser-test source to carry forward.
- Approved runtime remains `sha256:7a285a3ebb7eccf9eddb7c375a2b5616773e5aa40283ce270e41aff445ad23b9`, healthy with restart count `0`; Alembic remains `0016_mcp_tool_permissions`.
- Patch 685 is documentation/handoff only. It must not redeploy, mutate live SQLite, change credentials/security configuration, or alter application source.

Authoritative next-chat identity:

- Title: `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
- Patch range: `686-710`
- First patch: `686`
- Planned boundary: `710`

Chat 24 starts with authenticated SSE invalidation plus targeted refetch. Preserve existing stale-request guards, filters, pagination and selection. Use one authenticated stream, reconnect/resync behavior and polling fallback; remove routine Refresh controls only after each path is proven. API docs/OpenAPI hardening follows, then whole-inventory Stored Parts metrics/Dashboard Stock alert dialog, roles, safeguarded MCP writes and final alpha regression.


<!-- PARTPILOT:INVENTORY_HISTORY_LIVE_SYNC_CHECKPOINT:V699 -->
## Authenticated Inventory/History live sync browser-approved — Patch 698

Patch 699 checkpoints the first browser-approved Chat 24 live-synchronization
slice after the Patch 691-697 implementation/recovery sequence.

Browser-approved behavior:
- protected `GET /api/live/events` and `GET /api/live/state`;
- one authenticated fetch/ReadableStream SSE client using the existing Bearer
  session, with no token in the URL;
- generation/sequence state, bounded replay/resync, topic revisions, reconnect
  backoff, heartbeat, lifecycle-aware stream termination and polling only while
  streaming is degraded;
- same-origin `BroadcastChannel` relay with event-ID deduplication so multiple
  open Part Pilot tabs receive the same invalidation promptly while SSE remains
  authoritative;
- successful part create/edit/quantity/delete/restore/purge routes publish only
  post-commit `inventory` + `history` invalidations;
- Stored Parts/Part Manager refreshes server results without resetting local
  search, filters, sorting, pagination or selection, and an already-open
  inventory drawer refreshes selected-part details plus recent movements;
- History refreshes automatically and its responsive filter grid/date controls
  are browser-approved at the previously problematic intermediate widths.

The existing manual Refresh/Retry paths remain available during the broader
migration. This milestone does **not** mark all live synchronization complete.
Projects, Reservations, Dashboard, Settings and API/MCP administration still
need deliberate topic publication/subscription wiring and browser proof.

Next work: continue the Chat 24 live-sync expansion, then public-alpha
OpenAPI/docs hardening and the remaining V1 items in the established roadmap.


<!-- PARTPILOT:PROJECTS_RESERVATIONS_LIVE_SYNC_CHECKPOINT:V702 -->
## Projects and Reservations live sync browser-approved — Patch 702

Patch 702 checkpoints the second browser-approved Chat 24 live-sync slice.

Browser-approved behavior:
- Project create/update publishes `projects` + `history` while stock-affecting
  Project reserve/edit/consume/cancel operations also invalidate `inventory`
  and `reservations`;
- Reservation create/update/lifecycle operations invalidate Reservations,
  History and Inventory, and linked-Project operations also invalidate Projects;
- terminal Reservation deletion invalidates Reservations + History without
  falsely claiming an inventory rewrite;
- Projects subscribes to `projects` and refetches both its current list and
  already-selected detail while preserving local status filter, page and
  selection behavior;
- Reservations subscribes to `reservations` and refetches list, selected detail
  and Activity while preserving each tab's local search/filter/page/selection;
- the browser-approved authenticated SSE/BroadcastChannel transport remains
  shared and unchanged.

Inventory/History plus Projects/Reservations are now browser-approved live-sync
surfaces. Dashboard, Settings/account and API/MCP administration remain to be
migrated deliberately. Routine Refresh controls remain until each remaining
surface is separately proven.


<!-- PARTPILOT:DASHBOARD_LIVE_SYNC_CHECKPOINT:V704 -->
## Dashboard inventory live sync browser-approved — Patch 704

Patch 704 checkpoints the browser-approved Dashboard live-sync slice.

Browser-approved behavior:
- Dashboard subscribes to the existing authenticated `inventory` live topic;
- low-stock summary/count/list refresh automatically after inventory mutations;
- an already-open universal inventory search refetches automatically;
- search text stays local and unchanged during live invalidation;
- selected universal-search part is preserved by ID when it still matches;
- existing stale-request sequencing remains authoritative so older responses
  cannot overwrite a newer live-refreshed result;
- the shared authenticated SSE + BroadcastChannel transport and backend
  inventory publication contract remain unchanged.

Inventory/History, Projects/Reservations and Dashboard are now browser-approved
live-sync surfaces. Settings/account and API/MCP administration remain the
primary live-sync surfaces still pending.


<!-- PARTPILOT:SETTINGS_ACCOUNT_LIVE_SYNC_CHECKPOINT:V706 -->
## Settings, account and preferences live sync browser-approved - Patch 706

Patch 706 checkpoints the browser-approved Settings/account/preferences slice.

Browser-approved behavior:
- reversible search, currency, timezone, reservation-default and appearance
  mutations publish `preferences` + `history` after durable commit;
- account profile/avatar/password/session mutations publish `account` +
  `history` after durable commit;
- manual backup generation publishes `backups` + `history` after the backup
  audit record is durably committed;
- global appearance, currency, timezone and sidebar account identity refresh
  across open authenticated tabs;
- Dashboard and Part Manager refresh the shared out-of-stock display preference;
- Settings refreshes preferences, account/session state and manual-backup status;
- unsaved Account and Reservation drafts are preserved, and live reload defers
  around active save/autosave/reset/avatar/password/session/backup operations.

Inventory/History, Projects/Reservations, Dashboard and non-credential Settings
are now browser-approved live-sync surfaces. REST API key and MCP
administration/integration state remains the final isolated live-sync slice.


<!-- PARTPILOT:CHAT24_DIAGNOSTIC_BOUNDARY:V710 -->
## Chat 24 diagnostic boundary - Patch 710

Chat 24 closes on a documentation-only diagnostic boundary after the final
API-key/MCP live-sync slice exposed stale manageable-OAuth smoke assumptions.

Patches 707-709 did not leave application source pending. The authoritative app
state remains the browser-approved Patch 706 checkpoint.

The exact recovery contract is documented in
`docs/diagonostic_710_oauth_manageable_fixture_contract.md`. The key issue is a
hard-coded assumption that OAuth client IDs 9 and 13 are connected; production
OAuth state is mutable and those identities/statuses are not valid test
invariants.

Next chat: `Chat 25: Integration Live Sync Recovery and Public Alpha Hardening`,
patches `711-735`, starting with a fixture-owned connected-OAuth smoke recovery.


<!-- PARTPILOT:INTEGRATION_LIVE_SYNC_CHECKPOINT:V714 -->
## API-key and MCP integration live sync browser-approved - Patch 714

Patch 714 checkpoints the final browser-approved authenticated live-sync slice.

Browser-approved behavior:
- REST API-key create/edit/rotate/revoke mutations publish
  `integrations.api_keys` plus `history` after durable success without exposing
  plaintext credentials in live payloads;
- MCP settings, global/client permissions, manual OAuth administration, named
  direct clients and direct-auth mutations publish `integrations.mcp` with
  history invalidation where the operation is consequential;
- external OAuth registration/consent/first token exchange/revocation refreshes
  MCP integration state, while routine refresh-token rotation avoids History
  noise;
- observing tabs targeted-refetch API-key/MCP state while preserving unfinished
  local MCP drafts and active local credential dialogs;
- one-time/revealed credentials remain local to the requesting tab and are not
  transported by live sync;
- manageable OAuth and OAuth HTTP smokes now use fixture-owned identities and
  coexist safely with pre-existing copied production OAuth state while proving
  exact logical database restoration.

The current public-alpha live-sync scope is now browser-approved across
Inventory/History, Projects/Reservations, Dashboard, Settings/account,
REST API keys and MCP administration.

The MCP section still uses its existing explicit `Save changes` action. Patch
714 does not change that save semantic; any autosave/removal decision belongs in
a separate UX patch so consequential MCP settings are not silently changed as
part of this checkpoint.


<!-- PARTPILOT:MCP_AUTOSAVE_STABLE_REFRESH_CHECKPOINT:V717 -->
## MCP autosave and stable background refresh browser-approved - Patch 717

Patch 717 checkpoints the browser-approved MCP Settings UX refinement from
Patches 715-716.

Browser-approved behavior:
- reversible MCP server/read/write/direct-access switches autosave immediately;
- global read-tool permission switches autosave individually with rollback and
  stale-request protection;
- enabling no-auth remains consequential and still requires the explicit
  `ALLOW NO AUTH` confirmation before the autosave is issued;
- credential creation, reveal, rotation, revocation and OAuth/client lifecycle
  actions remain explicit;
- MCP settings, tool permissions, OAuth-client lists and named direct-client
  lists keep their last-known-good content mounted during live/background
  refetches instead of replacing it with a blocking loading state;
- cached MCP data is scoped to the active auth token; initial loads still show
  normal loading states;
- cross-tab integration live sync and secret/dialog isolation remain intact.

A follow-up audit found the same initial-load/background-refresh conflation in
other live-sync consumers including Projects, Reservations, History, Dashboard,
Settings preferences/account/backups, API keys and selected inventory details.
The next hardening slice standardizes cache-aware background refresh there before
continuing broader public-alpha feature work.


<!-- PARTPILOT:STABLE_BACKGROUND_REFRESH_CHECKPOINT:V719 -->
## Stable live background refresh browser-approved - Patch 719

Patch 719 checkpoints the browser-approved refresh-stability sweep from Patch
718 across Projects, Reservations, History, Dashboard, Settings/account/data,
REST API keys and selected Stored Parts details/history.

Browser-approved behavior:
- first loads and real data-identity changes may still use blocking loading UI;
- same-token, same-query/page/selection live refreshes keep last-known-good
  content mounted and replace it in place when the new response arrives;
- Projects list/detail, Reservations list/detail/activity and History stay
  visible during matching live refetches;
- Dashboard low-stock and already-open universal-search results stay visible;
- Appearance, currency, timezone, inventory display and Reservation-default
  controls no longer disappear during background preference refreshes;
- Account profile/sessions, manual-backup status and REST API-key lists stay
  mounted during their live refreshes;
- selected Stored Parts detail and recent movement history refresh in place;
- cached state is scoped to the current auth token and relevant query/selection;
- transient background failures preserve the last-known-good snapshot while
  surfacing the error, rather than erasing valid visible data.

The main Stored Parts inventory register already had a cache-aware refresh model
and was intentionally left unchanged. Current live-sync surfaces now share the
same initial-load versus background-refresh UX contract.


<!-- PARTPILOT:OPENAPI_RESTORE_CHECKPOINT:V723 -->
## Public OpenAPI and restore recovery browser-approved - Patch 723

Patch 723 checkpoints the browser-approved Patch 722 recovery.

Public API documentation now:
- publishes Part Pilot API version/description and tag metadata in Swagger/ReDoc;
- exposes one Bearer authorization scheme for session tokens or REST API keys;
- marks all 43 API-key-capable method/path operations with the exact required
  scope plus documented 401/403 behavior;
- labels administrative routes as session-only and MCP OAuth routes as protocol
  endpoints, while `/mcp` remains outside OpenAPI.

Restore safety recovered during the same validation sweep:
- restore validation/staging schema contracts now match Alembic
  `0016_mcp_tool_permissions`;
- restore bootstrap logical hashing deterministically encodes SQLite BLOB values,
  including binary avatar data, and detects changed blobs;
- copied-production restore validation, commit, bootstrap/rollback, backup,
  OpenAPI/API-key, live-sync, OAuth and complete smokes pass.


<!-- PARTPILOT:INVENTORY_METRICS_CHECKPOINT:V728 -->
## Stored Parts whole-inventory metrics browser-approved - Patch 728

Patch 728 checkpoints the browser-approved Stored Parts metrics batch from
Patches 724, 726 and 727. Patch 725 was consumed by a production-asset marker
proof that incorrectly expected a stripped CSS source comment.

Browser-approved behavior:
- Stored Parts shows six whole-inventory cards: Stored parts, Physical units,
  Reserved units, Available units, Stock alerts and Inventory value;
- totals are computed server-side from active inventory and are independent of
  the current search, filters, pagination or visible rows;
- deleted/recycle-bin parts are excluded;
- Inventory value sums priced physical stock and reports pricing coverage; the
  workspace currency is display formatting only and no FX conversion occurs;
- Stock alerts reuse the existing low/out-of-stock service semantics and show
  both low-stock and out-of-stock counts;
- the six-card grid follows Stored Parts container width as 6 -> 3 -> 2 -> 1
  columns, avoiding asymmetric 5+1 or 4+2 rows;
- metrics subscribe to the existing `inventory` live topic and retain cached
  values during same-session background refreshes;
- protected `GET /api/parts/metrics` accepts sessions or `inventory:read` REST
  API keys, bringing the explicit scoped OpenAPI surface to 44 operations.


<!-- PARTPILOT:DASHBOARD_OPERATIONAL_HOME_CHECKPOINT:V731 -->
## Dashboard operational home browser-approved - Patch 731

Patch 731 checkpoints the browser-approved Dashboard Stock alerts dialog from
Patch 729 plus the operational-home cleanup from Patch 730.

Browser-approved behavior:
- the Stock alerts summary card opens an accessible live-synced dialog with total,
  low and out-of-stock counts, alert rows, Escape/backdrop/X close behavior,
  focus restoration, narrow-screen layout and Review inventory navigation;
- background inventory invalidations update the open dialog without replacing it
  with a blocking loading state; Retry remains available only after real errors;
- the permanent Backend/Online card and duplicated inline Low-stock inventory
  table are removed from the Dashboard;
- the Dashboard now presents six compact Quick actions: Add part, New project,
  Stored parts, Reservations, Part Manager and History;
- Add part and New project use one-shot URL intents that open the existing modal
  then consume the query parameter so reload/back navigation does not reopen it;
- routine Refresh controls are removed from Dashboard, Stored Parts, Projects,
  Reservations and History because those surfaces are live-synced; explicit
  Retry/Try again recovery remains for failed requests;
- no backend, API, schema or database semantics changed in this UI cleanup.


<!-- PARTPILOT:USER_ROLES_AUTHORIZATION_CHECKPOINT:V733 -->
## User roles and authorization foundation - Patch 733

Patch 733 establishes the backend authorization foundation for multi-user Part
Pilot workspaces and advances the production schema to `0017_user_roles`.

Security contract:
- users have one of Owner, Administrator, Operator or Viewer roles; all accounts
  that predate this migration are explicitly preserved as Owner;
- Viewer can use operational read paths, Operator adds operational write access,
  Administrator adds workspace/integration/backup and lower-role user
  administration, and Owner additionally controls restore/reset plus Owner
  lifecycle operations;
- every scoped REST API-key request is checked against both the key scope and the
  current owning user's role, so an old high-scope key cannot survive a user
  demotion as an escalation path;
- session-only user administration can list/create users, change lower-role
  access, disable/reactivate accounts, force-reset passwords, revoke sessions and
  delete accounts with exact confirmation;
- Administrators cannot create or administer Owner/Administrator accounts, users
  cannot disable/delete their current account, and the last active Owner cannot
  be disabled, deleted or demoted;
- reversible workspace preference writes and MCP administration require
  Administrator or Owner, backups require Administrator or Owner, and restore or
  debug-reset operations require Owner; each role keeps its own profile/password/
  session controls;
- current OAuth MCP read access remains available to authenticated active users;
  direct MCP credentials retain their independent global/client permission
  ceiling. Safeguarded MCP write tools will layer Operator-or-higher enforcement
  on this foundation in the next slice.

Migration/backup safety:
- SQLite adds/drops `users.role` in place rather than recreating the parent users
  table, preventing ON DELETE cascades into sessions, API keys and OAuth data;
- copied-production upgrade -> downgrade -> re-upgrade testing proves exact
  logical row/sequence restoration and preservation of all existing integrations;
- backup/restore contracts now target Alembic `0017_user_roles`, with the 0016
  schema retained as an explicitly unsupported historical backup contract;
- role, auth/profile/session, 44-route API-key/OpenAPI, MCP OAuth/settings/tool
  permissions, live-sync, backup, restore validation/commit/bootstrap and complete
  copied-production regressions pass on isolated database copies.

This patch intentionally exposes the enforceable user-management API foundation
without adding a role-management Settings UI; that presentation layer can be
added independently without weakening the backend boundary.

<!-- PARTPILOT:SAFEGUARDED_MCP_WRITES_CHAT25_BOUNDARY:V742 -->
## Safeguarded MCP lifecycle writes browser-approved — Patch 742

Patch 742 checkpoints the browser-approved Patch 739 safeguarded MCP write-tool
candidate plus the Patch 740 permission-dialog UX correction and closes Chat 25.

Patch 741 was consumed during boundary validation because the MCP write smoke
incorrectly required mutable live tool policy to equal migration defaults. Patch
742 makes that copied-production smoke policy-agnostic, forces its own isolated
write-off fixture baseline, and restores the copied DB byte-for-byte.

Browser-approved/runtime contract:
- Alembic `0018_mcp_write_intents` adds persistent short-lived write intents;
- the canonical MCP catalogue now contains six read tools plus three lifecycle
  write tools: `reserve_project`, `consume_reservation`, and
  `cancel_reservation`;
- write exposure requires the MCP server, Write authorization, the individual
  global tool permission, any client-level allow/deny ceiling, an authenticated
  principal with `mcp:write`, and an active backing user at Operator-or-higher;
- no-auth access remains permanently read-only;
- consequential calls use the same tool for preview and confirmation, with a
  five-minute one-time confirmation token, client idempotency key, state-drift
  rejection, completed-write replay and existing transactional stock invariants;
- successful MCP lifecycle mutations carry MCP stock/audit attribution and
  publish live invalidation only after commit;
- migration defaults all three write permissions off. Live MCP settings and
  client policies remain mutable configuration and are not frozen by this
  checkpoint;
- OAuth tokens do not silently gain `mcp:write`. During browser testing the
  existing Claude token still had only `mcp:read`, correctly exposing six tools
  until a new authorization is granted after Write authorization is enabled;
- the client Permissions dialog now scrolls within the viewport at desktop and
  narrow sizes, and OAuth client summaries say `allowed by policy` rather than
  implying the policy count equals the active OAuth-scoped tool set.

Deferred deliberately to Chat 26:
- inventory-mutating MCP tools for adding/editing/deleting/restoring parts and
  adjusting stock;
- the dedicated role/user-management Settings UI;
- final public-alpha accessibility/security/responsive/API-MCP regression.

Chat 25 began with planned range `711-735`; recovery/diagnostic work after the
planned boundary was limited to the failed MCP-write packaging sequence and this
approved checkpoint. Patch 742 is the authoritative Chat 25 boundary.

<!-- PARTPILOT:PATCH754_MCP_INVENTORY_STOCK_CHECKPOINT -->
## Chat 26 MCP inventory stock-write checkpoint — Patch 754

Patch 753 was consumed before staging/commit because four generated docs had an
extra blank line at EOF; rollback restored all five docs exactly. Patch 754
checkpoints the unchanged browser-approved guarded inventory stock-adjustment and
Settings autosave-feedback work delivered through Patch 752.

Current contract:
- Alembic `0019_mcp_inventory_stock_write` is a data-only migration over 0018; it
  preserves the live nine-tool boolean policy and adds `adjust_part_quantity`
  disabled by default without freezing later administrator changes.
- The MCP catalogue is ten tools: six reads plus `reserve_project`,
  `consume_reservation`, `cancel_reservation`, and `adjust_part_quantity`.
- Stock adjustment reuses the canonical inventory service and preserves
  nonnegative stock, reserved-stock floors, correction-reason requirements, MCP
  movement/audit attribution, and post-commit inventory/history invalidation.
- All four writes retain server/write/global/client/scope/Operator+ ceilings,
  preview/confirmation, idempotency/replay, and state-drift rejection; no-auth is
  permanently read-only.
- Settings autosave success feedback for Appearance, Currency, Timezone,
  Inventory display, Reservation defaults, MCP access, and MCP tool permissions
  now remains visible for a consistent 3.5 seconds through expected live reloads.

Browser approval is complete. Remaining Chat 26 work is narrower MCP mutation
and final public-alpha hardening/regression; inventory create/edit/delete/restore
should be added only where existing service and recycle-bin invariants remain exact.

<!-- PARTPILOT:MCP_PART_CREATE_HISTORY_CHECKPOINT:V759 -->
## MCP guarded part creation, OAuth write-scope discovery and client-attributed History — Patch 759

Patch 759 checkpoints the browser-approved Chat 26 work delivered through Patches
756-758. Patch 755 was consumed only by a wrapper `python -c` newline-escaping
error and restored the Patch 754 source/database state before Patch 756 deployed
the unchanged rehearsed application candidate.

Approved contract:
- Alembic `0020_mcp_inventory_part_create` is data-only over 0019. It preserves
  the existing ten live tool-policy booleans and adds `create_part` disabled by
  default; the canonical catalogue is now six read + five safeguarded write tools.
- `create_part` reuses canonical part creation validation, previews normalized
  metadata/initial quantity/catalogue choices/template definitions and values,
  requires the same idempotency/short-lived confirmation contract as other MCP
  writes, rejects dependency or argument drift, and publishes inventory/history
  invalidation only after commit.
- OAuth protected-resource challenges advertise the currently enabled MCP scope
  categories (`mcp:read`, `mcp:write`, or both). Existing grants/tokens are never
  upgraded automatically; browser testing proved Claude gained write tools only
  after a new authorization carrying `mcp:write`.
- MCP History presentation uses the connected OAuth/direct-client identity (for
  example `Claude`) instead of displaying the backing human username. The
  `actor_user_id` remains stored for authorization/accountability and user
  filtering. MCP stock movements are classified as MCP, and older unstamped MCP
  business audits can resolve their client from matching tool-call evidence.
- Copied-production write smokes no longer assume an empty live write-intent
  table; they isolate fixture-owned intents so legitimate browser-tested MCP
  evidence remains untouched.

The exact browser-approved runtime image is
`sha256:e545a8ee3234d8441ed1e3ab3f9a63e45595c5a36117f9eb719e3249ce42f815`
and production remains at Alembic `0020_mcp_inventory_part_create`. Browser proof
covered Claude tool discovery/authorization, guarded part creation, replay safety,
and the resulting History actor label.

Next Chat 26 work remains narrow: metadata edit/correction first; delete/restore
only after preserving recycle-bin, dependency, reservation and exact-confirmation
semantics; then optional user-management presentation and final public-alpha
hardening/regression before the planned Patch 767 boundary.

<!-- PARTPILOT:MCP_PART_METADATA_UPDATE_CHECKPOINT:V761 -->
## Guarded MCP inventory metadata editing — Patch 761

Patch 761 checkpoints the browser-approved Patch 760 metadata-edit slice.
Production advances to Alembic `0021_mcp_inventory_part_metadata_update`, a
data-only migration that preserves the existing eleven mutable MCP tool-policy
booleans and adds only `update_part_metadata` disabled by default. The canonical
catalogue is now six read plus six safeguarded write tools.

Approved contract:
- `update_part_metadata` reuses the existing typed/atomic inventory metadata
  service and cannot change physical or reserved stock;
- the MCP tool requires a complete desired replacement state, including explicit
  nulls for fields intentionally cleared, so omitted optional arguments cannot
  silently erase stored metadata;
- part type remains immutable in the edit workflow; manufacturer/location,
  part-number uniqueness and typed template fields use the existing catalogue and
  validation rules;
- preview freezes the exact current metadata, proposed metadata and relevant
  catalogue/template dependencies; concurrent metadata/template/catalogue changes
  reject confirmation, while an unrelated stock-only change does not create a
  false metadata drift failure;
- confirmation retains the five-minute token, stable idempotency key, completed
  replay, global/client permission ceilings, `mcp:write`, active Operator-or-higher
  authority and permanently read-only no-auth behavior;
- confirmed edits create no stock movement, retain the backing authorizing user,
  record the MCP client identity (browser-proved with Claude), and publish only
  `inventory` + `history` after commit.

Browser proof used the previously MCP-created Resistor. Claude first produced the
exact old/new metadata preview, then confirmed the update. The resulting part kept
physical quantity 12 and reserved quantity 0, had zero stock movements, and the
business audit stored `actor_type=mcp` with `mcp_client_name=Claude`.

Checkpoint rehearsal also corrected one test-only historical assumption: the package
catalogue complete smoke had treated the one-time `0005_packages` migration backfill
as a permanent invariant over mutable future `Part.package` values. Runtime package
text remains compatibility-tolerant and the selector can display legacy/non-catalogued
values, so the smoke no longer rejects legitimate post-migration inventory edits. No
production package/part row is rewritten by this correction.

The approved runtime image is
`sha256:e3e8f6e08c44b61ddc7254eda76d7820f47e3d701652d4ca8b87f83ddc8401cb`
and production Alembic is `0021_mcp_inventory_part_metadata_update`.

Next Chat 26 work: inspect delete/restore semantics before exposing any MCP
lifecycle for inventory deletion; preserve recycle-bin, dependency, reservation,
restore and exact-confirmation safeguards. Then complete the remaining prioritized
user-management presentation/final public-alpha regression before Patch 767.

<!-- PARTPILOT:CHAT26_BOUNDARY_CHECKPOINT:V768 -->
## Chat 26 MCP inventory lifecycle + History responsive register — Patch 768

Patch 768 recovers and checkpoints the browser-approved Patch 765 reversible MCP
inventory lifecycle slice together with the Patch 766 History intermediate-width
register correction, then closes Chat 26. Patch 767 was consumed before any writes:
its preflight required the HTTPS spelling of the GitHub origin while the verified
repository uses the equivalent SSH origin. The failed run reached only the origin
read, left the index clean, and preserved all 24 approved pending source files.

Current approved contract:
- Production Alembic head is `0022_mcp_inventory_part_lifecycle`, a data-only
  migration over 0021 that preserves all existing mutable MCP permission values
  and introduces `soft_delete_part` and `restore_part` disabled by default.
- The canonical MCP catalogue contains 14 tools: six reads plus eight safeguarded
  writes. Inventory writes include `adjust_part_quantity`, `create_part`,
  `update_part_metadata`, `soft_delete_part`, and `restore_part`; Project/
  Reservation lifecycle writes remain unchanged.
- Reversible inventory lifecycle calls reuse the canonical soft-delete/restore
  services and the existing MCP Operator+, `mcp:write`, server/write/global/client
  permission ceilings, short-lived confirmation, idempotency/completed replay and
  state-drift protection.
- Soft delete preserves physical/reserved quantity, typed fields, movements and
  History. Restore operates on the same deleted record, checks the frozen deleted
  state and part-number availability, and returns the same part ID. Neither action
  creates stock movement solely for lifecycle transition.
- Permanent purge/hard delete/recycle-bin emptying is intentionally absent from
  the MCP tool catalogue and remains a separately reviewed consequential UI/API
  operation.
- MCP business History continues to show the connected client identity while the
  backing Part Pilot user remains the authorization/accountability authority.
- History's chronological register now horizontally scrolls as one aligned
  header/row region at intermediate widths instead of clipping inaccessible
  columns. The heading and pagination stay stationary; <=680px keeps the existing
  mobile card layout.

Browser proof:
- Claude previewed, confirmed and idempotently replayed `soft_delete_part` on the
  existing MCP test Resistor (part ID 16), preserving physical quantity 12,
  reserved quantity 0 and three typed field values with zero stock movements.
- History showed the lifecycle action as actor `Claude`.
- Claude previewed, confirmed and replayed `restore_part`; the same part ID, part
  number, quantities and fields returned with no duplicate audit or movement.
- Claude's available lifecycle catalogue contained only reversible soft delete +
  restore and no permanent purge tool.
- The Patch 766 History register was manually resized through desktop,
  intermediate and mobile widths and browser-approved after columns remained
  reachable by horizontal scrolling instead of being clipped.

The exact browser-approved source/runtime image before this documentation-only
checkpoint is
`sha256:44a9a7a36907587aecf8d6dae34ff4e0837c24a3b6bce6bcb86c853dda8c17fb`.
Live MCP permission booleans are legitimate mutable administrator state and must
not be normalized to migration defaults by checkpoint/regression work.

Chat 26 is complete. Continue in `Chat 27: User Management UI and Public Alpha
Release Candidate`, patch range `769-793`, first patch `769`, planned boundary
`793`. Primary remaining V1 work is the dedicated Settings user/role-management
UI followed by the final accessibility/security/responsive/backup-restore/REST-
OpenAPI/MCP regression sweep and public-alpha release-candidate checkpoint.
Notifications & Messaging remain post-v1.

<!-- PARTPILOT:USER_MANAGEMENT_PRIMARY_OWNER_CHECKPOINT:V776 -->
## Chat 27 user management + Primary Owner checkpoint — Patch 776

Patch 776 checkpoints the browser-approved Patch 773-775 user-management slice.
The approved implementation adds the dedicated Settings Users & Roles workspace,
hydrates authenticated roles in the frontend, hardens the first-init account as
the permanent Primary Owner, hides Settings workspaces outside each role's
permission ceiling, and keeps consequential account actions explicit.

Approved authorization/presentation contract:
- The account created during initial setup is the only account that may hold
  `owner`. Managed-user create/update request schemas expose only
  `administrator`, `operator`, and `viewer`; service-layer checks independently
  reject creation/promotion of another Owner.
- The Primary Owner cannot be demoted, disabled, or permanently deleted. Restore
  validation also rejects databases whose first user is not the active Owner or
  that contain any additional Owner row, preventing older/malformed backups from
  reintroducing multiple Owners.
- Owner and Administrator can see Users. Administrator can manage/create only
  Operator/Viewer accounts. Operator/Viewer never receive the Users workspace.
- Settings navigation and restricted section rendering now follow the actual
  authorization boundary: Operator/Viewer see only Account + their API access;
  Administrator additionally sees Users, Preferences, MCP and Data, while
  restore and database-reset controls remain Primary-Owner-only.
- Restricted Settings workspaces also stop their background administrative
  fetches instead of merely hiding tabs that would later return 403.
- Users & Roles uses a compact roster with clear identity, role, status,
  last-login and one Manage action. Account creation and consequential status,
  password, session and permanent-delete actions live in focused dialogs.
- The Primary Owner remains visibly identified by its `Primary Owner` role and
  protected Manage state; the redundant `Initial account` badge was removed in
  Patch 775 after browser approval.

Browser approval covered desktop/intermediate/mobile presentation, Primary Owner
protection, assignable-role ceilings, Administrator/Operator/Viewer Settings
visibility, user lifecycle actions and the final badge cleanup. The exact
approved runtime image before checkpoint is
`sha256:a6b6cfa6933c4d98a7b936e5f8cf9257cec7309956cea0828a941fdcf8530e38`;
production remains at Alembic `0022_mcp_inventory_part_lifecycle` with no schema
migration for this slice.

The Patch 774 rehearsal also exposed a pre-existing `restore_commit_smoke_test`
readiness/drain assertion failure. The same failure reproduced against the
already-approved Patch 773 image, so it was not attributed to user management or
folded into this checkpoint. It remains an explicit item for the final
public-alpha regression/hardening sweep.

Next Chat 27 work: run the final public-alpha accessibility, security, responsive,
backup/restore, REST/OpenAPI, MCP OAuth/direct-auth/tool-permission/write and
live-sync regression sweep; resolve only release-blocking findings; then produce
the public-alpha release-candidate checkpoint/handoff. Notifications & Messaging
remain post-v1.


<!-- PARTPILOT:PUBLIC_ALPHA_AUTOMATED_REGRESSION:V777 -->
## Public-alpha automated regression gate — Patch 777

Patch 777 runs the complete automated public-alpha release matrix from the clean
Patch 776 checkpoint without changing application source, production data or the
running deployment. The canonical Docker build reproduced the browser-approved
runtime image `sha256:a6b6cfa6933c4d98a7b936e5f8cf9257cec7309956cea0828a941fdcf8530e38` and production remained at Alembic `0022_mcp_inventory_part_lifecycle`.

Automated gate evidence:
- all 44 current release smoke invocations passed on fresh copied-production
  databases. `custom_avatar_smoke_test` runs its full flow after clearing only the
  copied fixture's existing avatar blob, while `mcp_oauth_admin_smoke_test` uses
  its supported `--check-only` mode because its full-flow fixture hardcodes old
  Claude/ChatGPT rows;
- legacy `mcp_direct_auth_smoke_test` is intentionally excluded because it freezes
  the historical `0015_mcp_direct_clients` migration head and legacy-row count;
  current direct-auth behavior is covered by the API, named-client, Bearer, custom-
  header, trusted-network and transport smokes;
- copied databases retained their exact pre-test 14-key MCP permission values,
  remained at Alembic `0022_mcp_inventory_part_lifecycle`, and passed SQLite quick/foreign-key checks;
- the live deployment stayed healthy with restart count 0 and the same approved
  image while health, protected API, SPA route and OpenAPI checks passed;
- the managed-user OpenAPI request boundary still excludes `owner`, while current
  user responses retain the complete Owner/Administrator/Operator/Viewer enum;
- the browser-approved Users runtime markers, `Primary Owner` presentation and
  removal of the redundant `Initial account` badge survived the canonical build.

The restore-commit concern recorded at Patch 776 was harness invocation drift, not
a restore defect: `restore_commit_smoke_test` deliberately clears the supervisor
contract for one negative check, so its baseline invocation must provide
`PARTPILOT_RESTORE_SUPERVISOR_CONTRACT=compose-restart-v1`. With that canonical
contract the smoke passes its 401/422/503/409/202 sequence, drain recovery, pending
job and pre-Uvicorn restore checks. No restore application source change was needed.

Aggregate module execution time recorded by the patch was 209.5s.
Remaining V1 work is browser-level accessibility/responsive verification and real
external-client OAuth/direct-MCP release verification, followed only by fixes for
actual release blockers and the public-alpha release-candidate checkpoint/handoff.

<!-- PARTPILOT:PUBLIC_ALPHA_RELEASE_POLISH_CHECKPOINT:V786 -->
## Public-alpha release polish checkpoint — Patch 786

Patch 786 checkpoints the cumulative browser-approved Patch 779-785 release-polish
slice on top of the Patch 777 automated regression baseline. No schema migration is
required; production remains at Alembic `0022_mcp_inventory_part_lifecycle` and the
approved V785 runtime image is
`sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`.

Approved release-polish contract:
- Dashboard no longer exposes the redundant Stock alerts launcher/dialog; the
  live-synced operational home remains focused on search, metrics, activity and
  Quick actions without leaving a layout hole.
- Projects and Reservations retain their Updated timestamp column at intermediate
  widths inside aligned horizontal register scrollers instead of deleting/clipping
  that data; their existing mobile card layouts remain unchanged.
- History Part-related records expose `Open part`, which deep-links to
  `/inventory?part=<id>` and opens the exact Part details drawer.
- Generated REST API/MCP credential values, MCP URL and OAuth client ID/secret use
  in-field Copy controls; secret Show/Hide remains integrated with the field.
- MCP Settings is reorganized into Server, Capabilities, Connections and Advanced
  access. Individual read/write tool permissions remain available inside focused
  catalogues, OAuth and named direct clients live under Connections, and no-auth is
  visually isolated as the advanced read-only fallback. Existing permission,
  credential, autosave, live-sync and confirmation semantics are unchanged.
- Account, Users, Preferences, API, MCP and Data now share one Settings information
  architecture: semantic group kicker, title, description, status/action where
  useful, and the existing specialized controls inside each grouped card.
- Built-in avatar choices are fixed 46 x 46 px squares with consistent spacing and
  natural wrapping instead of stretching across wide screens.
- Sequential `01/02/03/04` Settings badges were removed because Settings groups are
  not ordered steps. Sixteen restrained semantic SVG badges now provide visual
  landmarks without a new icon dependency or category colors. The Connections
  glyph receives a 1.5 SVG-unit optical Y correction while its badge box and all
  other icons remain unchanged.

Release evidence beyond the UI checkpoint:
- Patch 777 already passed all 44 current release smoke invocations on fresh
  copied-production databases plus canonical build, OpenAPI, protected-route, SPA,
  restore and MCP regressions.
- Real Claude OAuth verification exposed the canonical six read + eight safeguarded
  write tools, exposed no hard-delete/purge tool, found the existing MCP test part,
  and successfully exercised guarded metadata preview/confirmation.
- The Hermes `MCP event loop is not running` failure was isolated to the Hermes
  agent/runtime wrapper: Part Pilot initialized and executed `search_parts` both
  locally and from inside the Hermes container against the public MCP URL. No Part
  Pilot MCP compatibility workaround is warranted.

All Patch 779-785 browser feedback is approved. Remaining Chat 27 work is the final
public-alpha release-candidate documentation/handoff and fixes only for genuinely
new release blockers. Permanent purge remains outside MCP; Notifications &
Messaging remain post-v1.

<!-- PARTPILOT:PUBLIC_ALPHA_RELEASE_HYGIENE_RECOVERY:V790 -->
## Public-alpha release hygiene recovery — Patch 790

Patches 787 and 788 were consumed by pre-write evidence-contract failures and did
not modify release-facing source. Patch 789 committed a diagnostic-only report that
pinned the actual Patch 786 evidence, the misnamed Patch 788 log, and the safe
recovery plan.

Patch 790 applies the release-facing hygiene from the exact post-P789 checkpoint:
- `.env.example` uses the informational `production` label and documents the public
  base URL and Primary-Owner reset flag without changing the live `.env`;
- README describes the completed MCP permission/write model instead of obsolete
  implementation-era plans;
- README adds deployment guidance for HTTPS, reverse proxies, trusted proxies, MCP
  no-auth exposure, least privilege, data/instance-secret protection, reset safety,
  and backups;
- repository hygiene remains free of tracked database, `.env`, secret, key, PEM or
  certificate artifacts.

No application source, live database, deployment, credentials, settings, or MCP
permission values are changed by this checkpoint. The repository still has no
`LICENSE`; licensing remains an explicit repository-owner decision.


<!-- PARTPILOT:CHAT27_PUBLIC_ALPHA_BOUNDARY:V796 -->
## Chat 27 public-alpha release-candidate boundary recovery — Patch 796

Patch 796 is the authoritative Chat 27 boundary recovery. The planned Patch 793
boundary did not complete, so Chat 27 remained active through narrow high-safety
recovery patches 794-796. Patch 795 is the authoritative diagnostic checkpoint for
the final release-gate fixture drift.

Consumed release-gate/recovery history:
- Patch 791 reached copied-production smoke 11/44 and exposed a migration-era
  singleton assumption in the historical direct-Bearer fixture when the copied live
  database legitimately contained additional named/revoked direct-client history.
- Patch 792 failed pre-write because its evidence assertion searched a command log
  for terminal-only exception text/phase wording that the logger does not persist.
- Patch 793 normalized the three historical direct transport copies and reached
  smoke 20/44, where the named-direct smoke froze the old disabled-default values of
  mutable `mcp.direct_clients_enabled` / `mcp.direct_no_auth_enabled` settings.
- Patch 794 was correctly diagnostic-only but itself failed pre-write by expecting
  terminal exception text inside the P792 command log.
- Patch 795 repaired that evidence model, committed only
  `docs/diagonostic_patch_795_final_release_gate_mutable_fixture_drift.md`, and
  identified the complete five-fixture adapter required for a safe recovery.

Patch 796 implements only that diagnostic fixture adapter on isolated copied databases:
- Bearer, custom-header, trusted-network transport, and trusted-network-management
  historical smokes validate legacy row ID 1 then remove only `mcp_direct_auth`
  rows with `id <> 1` from their private copies;
- `mcp_named_direct_clients_smoke_test` starts from copied values
  `mcp.direct_clients_enabled=false` and `mcp.direct_no_auth_enabled=false`, because
  those are the migration/default values that smoke explicitly tests;
- production direct clients, settings, credentials and permission values are never
  normalized or restored to historical defaults.

Before the full matrix, all five affected fixtures are separately rehearsed. Patch 796
then runs all 44 current copied-production release smoke invocations,
reproduces the exact approved image `sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`, and keeps production at Alembic
`0022_mcp_inventory_part_lifecycle` with SQLite integrity intact.

Final Chat 27 evidence:
- all 44 release smokes pass after comprehensive fixture-only normalization;
- copied fixtures retain their normalized pre-smoke fourteen-key MCP permission
  values and pass SQLite quick/foreign-key checks;
- backup/restore, authentication/profile/sessions, permanent Primary Owner semantics,
  Preferences, inventory/recycle, Projects/Reservations/History/live-sync, API keys,
  OAuth/direct MCP transports, permissions and all eight safeguarded writes remain covered;
- browser-approved Patch 779-785 release polish and real Claude OAuth MCP verification
  remain the accepted manual/external evidence;
- health, protected routes, SPA routes, OpenAPI role boundaries and repository
  sensitive-file hygiene remain intact;
- production data, credentials, mutable MCP settings, direct-client history and the
  running deployment remain untouched by the release gate and boundary documentation.

Aggregate full-matrix smoke execution time recorded by Patch 796: 174.8s.
Chat 27 is complete at the verified Patch 796 boundary. Patch 797 was consumed by a
pre-write publishing-package evidence assertion; Chat 28 recovery continues at Patch 798.


<!-- PARTPILOT:PUBLIC_ALPHA_PUBLISHING_PACKAGE:V798 -->
## Public-alpha publishing package recovery — Patch 798

Patch 798 recovers the intended Chat 28 publishing package from failed Patch 797.
Patch 797 stopped in preflight before writes because it required `Everything PASS`
inside the Patch 796 command log, while Patch 796 records that final success line only
on terminal output. The immutable Patch 796 log instead persists the successful
boundary commit/push and final verification. Patch 798 validates those persisted
markers plus the exact Patch 797 source/log fingerprints before any write.

The recovery adds release-facing documentation only. It does not change application
source, the running image, production data, MCP settings/clients/permissions,
credentials or Alembic state.

The publishing package consists of:
- `docs/Public_Alpha_Release_Notes.md`, a tag-neutral release-notes source describing
  the current V1 public-alpha capabilities, MCP/AI safeguards, validation evidence,
  deployment guidance and known alpha limitations;
- `docs/Public_Alpha_Publishing_Checklist.md`, which separates already-proven release
  evidence from repository-owner decisions and consequential publishing actions.

No release tag, GitHub Release or software license is guessed by this checkpoint. The
repository owner must explicitly choose the release tag/title and either choose exact
licensing terms or intentionally keep the repository without a redistribution license.
Until then, public documentation must not describe Part Pilot as open source.
<!-- PARTPILOT:APPROVED_USER_CHECKPOINT_CUSTOMER_README:V801 -->
## Approved user-dialog checkpoint recovery and customer README — Patch 801

Patch 800 was consumed in preflight before any repository write. Its evidence contract
pinned a stale Patch 799 command-log fingerprint and stale browser-candidate image. The
actual immutable Patch 799 log is
`fixes/logs/799_refine_user_manage_dialog_actions_20260828-101533.log` with SHA-256
`d929c22a126dfcaba8bd4f62b1e128a1c01032d9adc823fd2edf16946b04dd0f`, and that log
records the browser-candidate build/deployment image
`sha256:7fca90c47ce7305089a7055083628776c9b2d16abf4567ee79c2c9b3dd3fce68`.
The approved two-file source hashes remain unchanged after the failed P800 preflight.

Patch 801 checkpoints those exact browser-approved source bytes and rewrites `README.md`
from internal development/checkpoint history into a public-facing product/install guide.
The new README covers product capabilities, source-build installation, first-run setup,
configuration, reverse proxy/HTTPS, users/roles, MCP/AI safeguards, backups, upgrades,
security, troubleshooting and development. It explicitly avoids inventing a registry
image name that does not yet exist.

`v1.0.0` remains the selected first public release identifier. Before that public release,
Part Pilot should publish a prebuilt container-registry image and a ready-made Compose
configuration that pulls the image instead of requiring users to build from source. That
is a later consequential release-packaging step, not part of Patch 801.

Patch 801 creates no software license, Git tag or GitHub Release. Production data,
credentials, mutable MCP state, Primary Owner semantics, the fourteen-tool MCP catalogue
and Alembic `0022_mcp_inventory_part_lifecycle` remain unchanged.

<!-- PARTPILOT:RELEASE_BOOTSTRAP_PORT_FAVICON_BROWSER_CANDIDATE:V812 -->
## Patch 812 browser-test candidate — semantic image equivalence recovery

Patch 811 passed isolated Compose, startup-bootstrap, fresh-database, copied-production, complete-smoke and favicon validation, then stopped after writing the exact candidate because it required the live-root Docker image ID to equal the isolated-snapshot image ID. Rollback restored the browser candidate before deployment. Read-only comparison of the retained P811 images proved the application bytes were identical: frontend path/bytes/modes matched, and backend file bytes matched exactly; the initial backend difference was file mode metadata from `git archive` extraction (`0664`) versus the live checkout (`0644`). After normalizing snapshot modes to Git index modes, backend and frontend path/bytes/mode manifests matched exactly while image IDs still differed because Docker COPY layers retain context/build timestamps.

Patch 812 therefore preserves the exact approved bootstrap/port/README/favicon product scope but validates isolated-versus-live builds by deterministic semantic manifests rather than whole-image IDs. The manifest covers backend and frontend path/bytes/modes, installed Python package versions, Python version and Docker runtime configuration. The actual live-root build is deployed only after semantic equivalence is proven. Source remains unstaged, uncommitted and unpushed for explicit favicon browser approval. No LICENSE, `v1.0.0` tag, GHCR publication or GitHub Release is created.

<!-- PARTPILOT:APPROVED_RELEASE_BOOTSTRAP_FAVICON_CHECKPOINT:V814 -->
## Browser-approved release bootstrap and favicon checkpoint — Patch 814

Patch 812 completed the guarded container-database bootstrap, fixed internal port `8000`, direct default `7890:8000` Compose mapping, customer README cleanup and favicon delivery. Patch 813 then changed only the favicon to mirror Part Pilot's existing in-app brand mark: a restrained dark rounded tile with a mint `P`. The replacement favicon was explicitly browser-approved.

Patch 814 checkpoints those exact application/config/frontend bytes without further product changes. Fresh file-backed SQLite starts by migrating to Alembic head and idempotently initializing built-in/default data; initialized managed databases migrate without seed replay; ambiguous non-empty unversioned SQLite fails closed. Production remains Alembic `0022_mcp_inventory_part_lifecycle`, the fixed container port is `8000`, and the approved favicon is served as `/favicon.svg`.

The checkpoint creates no LICENSE/COPYING file, `v1.0.0` tag, GHCR publication or GitHub Release. Those remain separate consequential release steps.

<!-- PARTPILOT:V1_GHCR_DISTRIBUTION_PACKAGE:V815 -->
## v1.0.0 GHCR distribution package prepared — Patch 815

Patch 815 prepares, validates and checkpoints the stable image-distribution path without publishing it. The registry target is `ghcr.io/devanshtangri/part-pilot`. `docker-compose.release.yml` pulls `v1.0.0`, uses fixed container port `8000`, defaults to host `7890`, mounts configurable persistent host data into `/data`, preserves the readiness healthcheck and intentionally omits `container_name`.

`.github/workflows/publish-container.yml` runs only for tag pushes matching `v*.*.*`, refuses anything except an exact stable `vMAJOR.MINOR.PATCH` tag before registry login/build, is repository-guarded to `devanshtangri/Part-Pilot`, and publishes `linux/amd64` + `linux/arm64` images to GHCR with the exact tag plus `latest`, provenance and SBOM. No license OCI label is added before licensing terms are approved.

P815 validates the release Compose using a locally built image on an isolated fresh data directory and a copied-production data directory; the latter must log seed skip and remain logically unchanged. The workflow is YAML-parsed and structurally checked. P815 creates no `v1.0.0` tag and therefore cannot trigger publication; it creates no LICENSE/COPYING file and no GitHub Release. The next gate is dependency/license-obligation analysis followed by explicit approval of exact Part Pilot licensing terms.

<!-- PARTPILOT:V1_DEPENDENCY_LOCK_CHECKPOINT:V817 -->
## Patch 817 — reproducible v1 dependency lock checkpoint

Patch 816 identified floating application dependencies and floating Docker base tags as a pre-`v1.0.0` blocker. Patch 817 freezes the dependency graph already audited and validated before the tag: Python direct requirements are exact-pinned, `backend/requirements.lock.txt` captures the full approved 44-package non-pip runtime graph, frontend top-level dependencies use the exact P816 versions, the recovered P816 `package-lock.json` freezes the complete npm graph, Docker uses `npm ci`, and both Node/Python base images are pinned by multi-architecture OCI index digest. No product behavior, database schema, license, release tag or GHCR publication is introduced by this checkpoint.
