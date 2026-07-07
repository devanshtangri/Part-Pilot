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

- [ ] Channel type dropdown: N-channel/P-channel
- [ ] Max voltage unit value
- [ ] Max current unit value
- [ ] RDS(on) unit value
- [ ] Gate threshold voltage unit value
- [ ] Logic-level boolean
- [ ] Package field

### 8.4 Example Mechanical Hardware Template

- [ ] Size
- [ ] Length
- [ ] Thread type
- [ ] Material
- [ ] Head type
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
- [ ] Length/weight/volume quantities — later.

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
- [ ] Settings API
- [ ] Backup/Restore API
- [ ] MCP API/tool layer

---

## 25. UI Screens to Design Next

Screens likely needed:

- [ ] First-run setup
- [ ] Login
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
- [ ] Part Manager
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

- [ ] App runs in Docker.
- [ ] User completes first setup.
- [ ] User logs in.
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

