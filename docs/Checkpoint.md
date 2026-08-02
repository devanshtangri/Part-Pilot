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
