# Part Pilot V1 Product Specification

Generated: 2026-07-07  
Project: Part Pilot  
Owner/Initiator: Devansh  
Stage: Pre-implementation product specification

---

## 1. Product Identity

### 1.1 Name

**Part Pilot**

The name is locked for now. It fits the product because the app is not only an inventory database; it is intended to guide users and AI assistants through part discovery, reservations, and project preparation.

### 1.2 One-line Description

Part Pilot is a self-hosted electronics inventory manager for makers, hobbyists, small labs, and repair shops, with MCP integration so AI assistants can understand, reserve, and consume available parts.

### 1.3 Core Product Promise

Part Pilot helps users know exactly what parts they have, where those parts are, how many are available, what is reserved, and how much inventory/project stock is worth.

### 1.4 Core Problem

The initiating real-world problem: the user ordered a buck converter for a project, later discovering that two identical buck converters had already been purchased earlier and were already available in storage.

Part Pilot exists to prevent this by giving the user a searchable, trustworthy source of truth for available parts.

### 1.5 Unique Selling Point

The main USP is the **MCP integration**. AI assistants should be able to query the user's inventory during project planning and help answer questions like:

- Do I already have this part?
- Do I have enough quantity for this build?
- What equivalent or useful part do I already own?
- Can this available component be used in the current circuit?
- Can these parts be reserved for this project?
- Can the reserved project now be consumed from stock?

---

## 2. Target Users

Part Pilot is intended for:

- Hobbyists
- Makers
- Small electronics labs
- Repair shops
- Small technical teams
- Users with growing electronics inventories

It is not initially designed as an enterprise inventory/ERP product. Self-hosting and personal-lab usefulness are higher priorities than enterprise scalability.

---

## 3. Product Scope

### 3.1 Inventory Items Included in V1

V1 should support tracking:

- Electronic components
- Modules
- Electromechanical parts
- Mechanical hardware
- Connectors
- Development boards
- Motors and actuators
- Relays, buzzers, speakers, switches, encoders, etc.

### 3.2 Inventory Items Excluded from V1

V1 should not focus on tracking:

- Tools
- Consumables such as solder, flux, IPA, tape, glue, etc.
- 3D printed parts
- Photos
- Datasheets
- Manuals
- STEP files
- 3D models
- Symbols/footprints
- Import/export integrations
- Barcode/QR labels

These may be revisited in later versions.

---

## 4. Platform and Deployment

### 4.1 Deployment Priority

The first-class deployment target is:

- Docker Compose

### 4.2 Deployment Philosophy

Part Pilot should run as a self-hosted service. The web app, backend API, database, and MCP integration should all operate as part of the service.

### 4.3 Recommended V1 Runtime Shape

Recommended structure:

```text
partpilot/
  backend/
  frontend/
  data/
    partpilot.db
    uploads/
    backups/
    config/
```

The Docker container should use a persistent mounted data volume so migration and restore are straightforward.

### 4.4 Future Deployment Targets

Not V1, but planned later:

- Home Assistant add-on
- Windows `.exe` desktop software
- Linux one-click installer
- Possibly PWA installability

---

## 5. Recommended Tech Stack

### 5.1 Frontend

Recommended:

- React
- Vite
- TypeScript

Reasoning:

- User knows HTML, CSS, and JavaScript.
- React is a practical production-ready next step.
- Vite keeps setup simpler than Next.js.
- TypeScript will help as API contracts and typed custom fields grow.
- Easier to support a polished responsive web app and later PWA behavior.

### 5.2 Backend

Recommended:

- Python
- FastAPI

Reasoning:

- User is comfortable with Python.
- FastAPI is suitable for clean REST APIs.
- Python is a good fit for future AI, search, MCP, and automation logic.

### 5.3 Database

Recommended for V1:

- SQLite
- SQLAlchemy
- Alembic migrations

Reasoning:

- V1 is single-user.
- Self-hosting simplicity is more important than enterprise scale.
- SQLite avoids extra database service configuration.
- Backups are easier with a single-file database.
- SQLAlchemy keeps the door open for PostgreSQL support later.

---

## 6. Authentication and Setup

### 6.1 Authentication

V1 should require login even though it is single-user.

### 6.2 Account Creation

On first launch, Part Pilot should show an onboarding/setup flow.

Initial setup should collect:

- Username
- Password
- Currency
- Timezone
- Optional app preferences

### 6.3 Session Behavior

Use session tokens so the user does not need to log in repeatedly. Session expiration should exist, but it should not be annoying during normal use.

### 6.4 Single-user Scope

V1 is single-user only.

No multi-user permissions in V1.

---

## 7. UI and UX Direction

### 7.1 Visual Style

Part Pilot should feel:

- Modern
- Premium
- Polished
- Mobile-friendly
- Apple-like in polish, but still clearly an inventory management tool
- Dark-theme-first, with light theme available in settings
- Sleek, clean, pleasing, and designed with care

It should avoid feeling like a plain database table or lifeless admin panel.

### 7.2 Theme Direction

Default theme:

- Dark premium
- Matte black / graphite panels
- Subtle gradients
- Premium accent colors selected during design
- Clean rounded cards
- Smooth interactions
- High-quality typography
- Responsive mobile layouts

Light theme:

- Available from settings
- Clean and polished
- Not the primary visual target for first design exploration

### 7.3 Layout

Desktop layout should use a sidebar plus dashboard content.

Sidebar items:

- Dashboard
- Inventory
- Projects
- Reservations
- History
- Part Manager
- Settings

Note: "Component Types" has been renamed to **Part Manager**.

### 7.4 Dashboard

Preferred dashboard style:

- Big universal search bar at the top
- Quick action cards below
- Recent activity
- Low-stock summary
- Inventory value summary
- Reservation/project summary

Most visually prominent action:

1. Search parts
2. Reserve/consume/project workflow

### 7.5 Quick Action Cards

Dashboard quick actions may include:

- Add Part
- Add Stock
- Create Project
- Reserve Parts
- Consume Parts
- View Inventory
- View Low Stock
- View History

### 7.6 Inventory View

Default layout:

- Desktop: table view
- Mobile: card view

A manual view toggle can be added later, but V1 defaults should be device-appropriate.

Desktop table columns:

- Part number / display title
- Name
- Type
- Available quantity
- Reserved quantity
- Total quantity
- Location
- Unit price
- Total value
- Tags
- Actions

Mobile card important fields:

- Part number/name
- Available quantity
- Reserved quantity
- Location
- Out-of-stock warning if applicable
- Low-stock warning if applicable

Expandable mobile/card detail can show:

- Type
- Price/value
- Tags
- Package
- Notes preview
- Custom fields

---

## 8. Search Behavior

### 8.1 Search Targets

Search should query:

- Part number
- Name
- Aliases
- Description
- Type
- Subtype
- Tags
- Location
- Notes
- Custom fields
- Package
- Value-like fields, such as 10k, 100uF, 0603, etc.

### 8.2 Fuzzy Search

Search should be forgiving of spelling mistakes.

V1 can start with strong text search and progressively add fuzzy matching.

### 8.3 Out-of-stock Search Behavior

Chosen behavior: **Option B with a special section**.

Search results should show in-stock/available matches first.

Out-of-stock items should appear in a visually separate section such as:

```text
Out of Stock
- IRFZ44N
- XL4015 Buck Converter
```

If no in-stock results exist, the search dialog can show:

```text
No available results found.

Out of Stock
- Matching item 1
- Matching item 2
```

This behavior should be toggleable from settings.

Settings option:

- Show out-of-stock items in search: on/off

---

## 9. Component Identity and Naming

### 9.1 Name and Part Number Requirements

Part number should be optional.

Name should also be optional only if a part number is provided.

Final validation rule:

```text
Either name OR part number must be provided.
```

Allowed examples:

- Name: ESP32-CAM, Part number: empty
- Name: empty, Part number: IRFZ44N
- Name: N-channel MOSFET, Part number: IRFZ44N

Invalid example:

- Name: empty, Part number: empty

### 9.2 Display Title Rule

Default rule:

- If part number exists, show part number as the primary title.
- If part number does not exist, show name as the primary title.

### 9.3 Same Name and Part Number Shortcut

During add-part flow, provide a button or checkbox:

```text
Use same value for name and part number
```

This helps with parts where the common name and part number are effectively the same.

Example:

- Name: ESP32-CAM
- Part number: ESP32-CAM

or

- Name: IRFZ44N
- Part number: IRFZ44N

Implementation detail: this should be optional and user-controlled, not automatic in all cases.

---

## 10. Part Creation vs Stock Addition

### 10.1 Important Distinction

Part Pilot must separate:

1. Creating a part definition
2. Adding stock to an existing part

### 10.2 Creating a Part

Creating a part means adding a new inventory item/stock entry to the database.

Example:

- Create IRFZ44N MOSFET
- Set type: MOSFET
- Set package: TO-220
- Set initial quantity: 10
- Set unit price: ₹20

This creates both:

- A component record
- An initial stock movement

Audit should record:

- New part created
- Initial stock added

### 10.3 Adding Stock

Adding stock means increasing quantity for an existing part.

Example:

- Existing IRFZ44N quantity: 10
- Purchased 5 more
- Add stock: +5

Audit should record:

- Stock added to existing part

### 10.4 Add Stock Flow Can Create Missing Part

The Add Stock/restocking workflow should support creating a new part without losing the current workflow.

Desired UX:

1. User starts Add Stock workflow.
2. User searches for a part.
3. Part does not exist.
4. UI shows `Create new part`.
5. User creates the part.
6. App returns user to Add Stock workflow.
7. Newly created part appears in the restocking list.

Audit behavior:

- Newly created part logs as `part_created`.
- Its initial stock logs as `stock_added_initial` or equivalent.
- Existing parts in the same restocking session log as regular `stock_added`.

This keeps creation and restocking conceptually separate while making the workflow practical.

---

## 11. Component Types and Part Manager

### 11.1 Built-in Types

Initial built-in component/part types:

- Resistor
- Potentiometer
- Capacitor
- Inductor
- Diode
- Zener Diode
- Schottky Diode
- LED
- RGB LED
- Optocoupler
- NPN Transistor
- PNP Transistor
- MOSFET
- Voltage Regulator
- IC
- Microcontroller
- Relay
- Motor
- Servo Motor
- Stepper Motor
- Solenoid
- Buzzer
- Speaker
- Push Button
- Switch
- Rotary Encoder
- Connector
- Pin Header
- Terminal Block
- Fuse
- Mechanical Hardware
- Module
- Sensor
- Custom

### 11.2 Custom Types

Users can create custom part types in V1.

### 11.3 Editing Built-in Templates

Users can edit built-in templates.

### 11.4 Restore Defaults

Built-in templates must be restorable to defaults.

### 11.5 Part Manager Page

The **Part Manager** page should manage:

- Built-in part type templates
- Custom part types
- Custom fields
- Template restoration
- Possibly tags and reusable locations later, if it makes UX sense

---

## 12. Custom Fields

### 12.1 Purpose

Custom fields allow different part types to collect different technical information.

Examples:

MOSFET fields:

- Channel type
- Maximum voltage
- Maximum current
- RDS(on)
- Package
- Logic-level gate: yes/no

Mechanical hardware fields:

- Size
- Length
- Thread type
- Material
- Head type

### 12.2 Field Types

V1 should support typed custom fields:

- Text
- Number
- Boolean yes/no
- Dropdown
- URL
- Unit-aware value

Unit-aware examples:

- V
- A
- W
- Ω
- kΩ
- uF
- nF
- pF
- mH
- mm
- cm
- m

---

## 13. Add Component Flow

### 13.1 Preferred Order

Chosen: Option A.

Flow:

1. Choose part type.
2. Enter part number/name.
3. Fill type-specific fields.
4. Enter quantity.
5. Enter optional location.
6. Enter optional pricing.
7. Enter tags/notes/aliases/purchase info.
8. Save.

### 13.2 Required Fields

Required:

- Type
- Quantity
- Name or part number

Optional:

- Location
- Price
- Purchase link
- Purchase date
- Tags
- Aliases
- Notes
- Custom fields, unless configured as required by template

### 13.3 No Quick Add in V1

No quick-add mode is needed in V1 because adding components is not expected to be extremely frequent, and good data quality matters.

---

## 14. Locations

### 14.1 V1 Location Model

Use a simple location text field.

Examples:

- Box 1
- Blue electronics box
- MOSFET ziploc
- Drawer A3

### 14.2 Reusable Suggestions

Locations should behave like an autocomplete/dropdown with typing support.

If the user types `Drawer A3` once, it should appear as a selectable suggestion later.

### 14.3 No Location Hierarchy in V1

No room/cabinet/drawer/compartment hierarchy in V1.

This may be added later if needed.

---

## 15. Quantity Model

### 15.1 V1 Quantity Type

V1 uses integer quantities.

### 15.2 Quantity Fields

Each part should show:

- Total/on-hand quantity
- Reserved quantity
- Available quantity

Formula:

```text
Available = Total/on-hand - Reserved
```

### 15.3 Decimal/Measured Quantities

Not V1.

Future possible units:

- meters of wire
- grams of solder
- milliliters of liquid

---

## 16. Out of Stock vs Deletion

### 16.1 Out of Stock

Out of stock means the component still exists, but available quantity is zero.

Out-of-stock parts:

- Stay in the database
- Keep all details
- Keep pricing
- Keep tags
- Keep location
- Keep notes
- Keep history
- Can be restocked later
- Should be clearly marked as out of stock if shown
- Should appear in a separate search result section or be deprioritized

### 16.2 Deletion

Actual deletion means removing the component from active inventory as if it no longer exists.

Deletion should be rare and intentional.

Actual deletion removes active:

- Part record
- Quantity settings
- Component fields
- Price info
- Search visibility

But keeps:

- Audit logs
- Historical stock movements
- Snapshot of deleted component

### 16.3 Deletion UX

Deletion should live in a danger/admin area, not on normal part cards.

Suggested location:

```text
Settings → Advanced → Danger Zone
```

or a component-level danger section requiring confirmation.

---

## 17. Stock Movements

### 17.1 Principle

Inventory changes should be recorded as movements, not silently overwritten.

### 17.2 Movement Types

V1 movement types:

- Initial stock added
- Stock added
- Stock consumed
- Stock adjusted
- Component deleted snapshot

### 17.3 Consumption Rules

Consumption should only be allowed if available quantity is sufficient.

If insufficient:

- Show warning
- Do not consume

### 17.4 Consumption Inputs

Consumption should allow multiple parts at once.

Optional fields:

- Project name
- Reason/note

Project label/reason should not be strictly required.

---

## 18. Projects

### 18.1 V1 Projects Are Lightweight

Projects are included in V1, but they are not full project-management boards.

A project is a simple container for planned/reserved/consumed inventory.

### 18.2 Project Fields

Project fields:

- Name
- Optional description
- Status
- Created date
- Updated date
- Items list
- Notes/reason
- Created manually or through AI/MCP

### 18.3 Project Statuses

Chosen statuses:

- Draft
- Reserved
- Consumed
- Cancelled

### 18.4 No Mixed Reserved and Consumed State

A project should not support both reserved and consumed items at the same time in V1.

It should be one of:

- Draft
- Reserved
- Consumed
- Cancelled

### 18.5 Project Workflow

Flow:

1. Create project.
2. Add project items.
3. Choose reserve or consume.
4. If reserved, available stock reduces immediately.
5. Reserved project can later be executed/consumed with one action.
6. If consumed, stock movements are created.

### 18.6 Project Cost

Project cost should be calculated based on historical price at the time the item was added/reserved/consumed, not only the latest live component price.

This means the project item should snapshot unit price and currency when added to the project.

---

## 19. Reservations

### 19.1 Reservation Behavior

Reserved parts immediately reduce available quantity.

Example:

- Total: 5
- Reserved: 2
- Available: 3

### 19.2 Who Can Reserve

Reservations can be created from:

- UI
- MCP/AI assistant

### 19.3 Reservation Fields

Reservations should have:

- Project/name label
- Notes
- Expiry date
- Created by AI/manual
- Status

### 19.4 Reservation Expiry

Reservation expiry should be configurable.

Possible settings:

- No expiration
- Custom expiration period
- Manual expiry date

### 19.5 Reservations Page

The Reservations page should show all currently active and historical reservations.

It should be useful because reservations may be created by both UI and AI.

Recommended contents:

- Active reservations
- Expired reservations
- Consumed reservations
- Cancelled reservations
- Project name/label
- Reserved parts and quantities
- Created by: manual or MCP/AI
- Created date
- Expiry date
- Status
- Estimated reserved value
- Actions:
  - Convert to consumption
  - Cancel reservation
  - Extend expiry
  - Open linked project

The Reservations page acts like the control center for reserved inventory.

---

## 20. Pricing and Currency

### 20.1 Price Fields

V1 should include pricing.

Fields:

- Unit price
- Total purchase price
- Quantity purchased
- Currency
- Purchase date
- Purchase link
- Optional price note/source

### 20.2 Price Interpretation

The user originally wanted to see total purchased price and project cost.

Final model:

- Unit price should be stored for project costing.
- Total purchase price and quantity purchased can be accepted as input.
- If total purchase price and quantity purchased are provided, the app can calculate unit price.
- If unit price is provided directly, the app can calculate total value using quantity.

Even though Round 5 initially selected simple unit-price behavior, the later clarification confirms total purchase price and quantity purchased should exist.

### 20.3 Price Optionality

Price is optional.

If price is missing, the app should show an alert/warning when saving:

```text
You did not enter a price. Save anyway?
```

This warning should be toggleable in settings.

### 20.4 Currency Setup

There should be no hardcoded default currency.

During first setup/account creation, the user chooses:

- Currency
- Timezone

### 20.5 Currency Scope

V1 uses one global app currency.

Individual parts should not use different currencies in V1.

Multi-currency support and conversion can be V2.

### 20.6 Inventory Value

The app should be able to show:

- Total inventory value
- Available inventory value
- Reserved inventory value
- Project estimated cost
- Component total value

### 20.7 Project Cost Snapshot

Project cost should use price at the time the part is added to the project/reservation/consumption.

Reason:

- Prices can change over time.
- Historical project cost should remain accurate.

---

## 21. Low Stock

### 21.1 Low Stock Rule Scope

Low-stock thresholds are per component only in V1.

### 21.2 Fields

Each part can have:

- Low-stock enabled
- Low-stock threshold

### 21.3 Dashboard

Dashboard should show low-stock parts.

Example:

- ESP32 DevKit: 1 available, threshold 2
- IRFZ44N: 5 available, threshold 10

---

## 22. History and Audit

### 22.1 Principle

Everything important should be logged forever.

### 22.2 Structured Logs, Not Plain Files

Use structured database logs, not plain `.log` files as the main source of truth.

The UI can later export logs if needed.

### 22.3 Audit Categories

Audit/history should cover:

- Component created
- Component edited
- Component renamed
- Component deleted
- Stock added
- Stock consumed
- Stock adjusted
- Reservation created
- Reservation cancelled
- Reservation consumed
- Project created
- Project changed
- Settings changed
- Backup created
- Backup restored
- MCP action performed
- Login/security relevant events

### 22.4 History UI

History page should support filtered views:

- All activity
- Stock activity
- Reservation activity
- Project activity
- Edit activity
- MCP activity
- Backup/settings activity

### 22.5 Undo

No undo from history in V1.

Backups provide restore functionality instead.

---

## 23. Backups

### 23.1 Default Behavior

Automatic daily backups should be on by default.

### 23.2 Configurability

User can configure:

- Backups enabled/disabled
- Backup frequency
- Backup retention
- Backup location

### 23.3 Default Backup Location

Chosen: Option C.

Default:

```text
/data/backups
```

This should be configurable later.

### 23.4 Backup Contents

Backups should include a complete app snapshot:

- Database
- Uploaded files if future versions add them
- Settings
- MCP settings
- Audit/history data
- Component templates
- Custom fields
- Theme/settings
- Config files

### 23.5 Restore Philosophy

Migration should not be a hassle.

Restore should feel like cloning the old instance.

---

## 24. MCP Integration

### 24.1 MCP as First-class Feature

MCP is central to the product identity.

### 24.2 MCP Access Protection

MCP should be protected by an API token.

Settings should include:

- MCP enabled/disabled
- API token generation
- API token rotation
- Write tools enabled/disabled
- Allowed actions

### 24.3 Default MCP Permissions

Default should be safe:

- Read/search tools enabled
- Write tools disabled until user enables them

### 24.4 MCP Allowed Actions

AI/MCP can:

- Search inventory
- Read part details
- See notes
- See reservations
- Reserve parts if write actions enabled
- Consume parts if write actions enabled
- Convert reserved project to consumed if write actions enabled

AI/MCP cannot:

- Add parts
- Edit parts
- Delete parts

### 24.5 Confirmation Model

For AI actions:

- Reserving requires confirmation in the AI chat.
- Consuming requires confirmation in the AI chat.
- Additional confirmation inside the web app is not required for V1.

### 24.6 Suggested MCP Tools

Initial MCP tools:

- `search_parts`
- `get_part_details`
- `list_low_stock`
- `list_projects`
- `get_project`
- `create_project`
- `create_reservation`
- `consume_parts`
- `convert_reservation_to_consumption`
- `cancel_reservation`

Write tools should check server settings before executing.

---

## 25. Mechanical Hardware

Mechanical hardware is included in V1.

Fields that matter:

- Size
- Length
- Thread type
- Material
- Head type
- Quantity
- Location

Examples:

- M3 screw
- M4 nut
- Washer
- Spacer/standoff
- Bolt
- Hex screw

---

## 26. Final V1 Included Scope

V1 includes:

- Project name: Part Pilot
- Docker Compose deployment
- React + Vite + TypeScript frontend
- FastAPI backend
- SQLite database
- Single-user login
- First-run setup
- Currency and timezone setup
- Dark theme + light theme
- Responsive desktop/mobile UI
- Dashboard
- Sidebar navigation
- Inventory table/cards
- Universal search
- Out-of-stock search grouping
- Add component flow
- Part creation vs stock addition separation
- Add Stock flow with create-missing-part support
- Built-in part types
- Custom part types
- Editable/restorable templates
- Custom typed fields
- Tags
- Aliases
- Reusable autocomplete locations
- Integer quantity tracking
- Total/reserved/available quantities
- Low-stock threshold per component
- Out-of-stock handling
- Projects
- Reservations
- Consumption flow
- Unit price
- Total purchase price
- Quantity purchased
- Global currency
- Inventory value summary
- Project cost snapshots
- Full structured audit/history
- Automatic configurable backups
- MCP API token
- MCP read/search/reserve/consume tools

---

## 27. Explicit V1 Exclusions

Not in V1:

- Broken/partial parts
- Photos
- Datasheets
- Manuals
- STEP files
- 3D models
- Symbols/footprints
- Import/export
- Supplier integrations
- Automatic currency conversion
- Multi-user accounts
- Home Assistant add-on
- Desktop app
- Barcode/QR labels
- Offline local-first mode
- Decimal/measured quantities
- Full project-management features

---

## 28. First Successful Prototype Milestone

Milestone 1 is successful when:

```text
I can add IRFZ44N, set quantity/location, search it, reserve 2, consume 1, and see history.
```

Expanded milestone checklist:

- Create account/setup app
- Add IRFZ44N MOSFET
- Set quantity
- Set optional location
- Set optional price
- Search IRFZ44N
- Open component detail
- Reserve 2
- See available quantity reduce
- Consume 1
- See quantity update
- See stock movements/history
- See audit log entries

---

## 29. Recommended Next Outputs

Recommended order:

1. Full product specification — this document
2. Implementation roadmap
3. Database schema
4. API design
5. UI screen-by-screen plan
6. MCP tool contract
7. First coding milestone implementation

