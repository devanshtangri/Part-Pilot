# Part Pilot — Public Alpha Release Notes

<!-- PARTPILOT:PUBLIC_ALPHA_RELEASE_NOTES:V798 -->

These notes describe the verified Part Pilot V1 public-alpha release candidate. They
are intentionally tag-neutral: a Git tag and GitHub Release title have not been chosen
yet. The authoritative product boundary is Patch 796; this publishing-documentation
recovery is Patch 798.

## What Part Pilot is

Part Pilot is a self-hosted electronics-parts inventory application for makers, repair
benches and small technical labs. It combines structured component metadata, stock
workflows, Projects/Reservations, audit History, user roles and AI-accessible MCP tools
in a responsive web interface.

## Public-alpha highlights

### Inventory and catalogues

- Typed part templates with reusable manufacturers, packages/form factors and locations.
- Universal search, server-backed filters, independent Available/Out-of-stock sorting,
  pagination and responsive part details.
- Metadata editing plus explicit add/remove/consume/correction stock workflows with
  reservation-floor safeguards.
- Soft delete and restore preserve part metadata/history; permanent purge remains a
  separate, explicitly confirmed UI/API operation with dependency protection.
- Unified History combines audit events and stock movements with search, filtering,
  pagination, responsive detail inspection and direct Part deep-links.

### Projects and Reservations

- Draft/Reserved Project lifecycle with atomic Reservations and inventory availability.
- Reservation cancellation and consumption use canonical stock/lifecycle rules.
- Desktop, intermediate-width and mobile layouts preserve complete register data.

### Accounts, roles and administration

- First-run account setup and authenticated sessions.
- Permanent first-init Primary Owner; no other account can become Owner.
- Administrator, Operator and Viewer ceilings with role-disallowed Settings workspaces
  hidden rather than merely disabled.
- User creation, access changes, password/session administration and explicit destructive
  protections.
- Preferences, REST API keys, backups/restores and responsive Settings administration.

### Live synchronization and UI polish

- Authenticated server-sent events plus cross-tab relay drive targeted live refreshes
  while preserving local drafts, search/filter/page/selection state.
- Flat, dense enterprise UI with responsive Inventory, Projects, Reservations, History
  and Settings layouts.
- Generated API/MCP/OAuth values provide in-field Copy controls; secret fields retain
  integrated Show/Hide behavior.

## MCP and AI assistant integration

Part Pilot exposes 14 MCP tools when permitted: six reads and eight safeguarded writes.

Reads:
- `search_parts`
- `get_part_details`
- `list_projects`
- `get_project_details`
- `list_reservations`
- `get_reservation_details`

Safeguarded writes:
- `reserve_project`
- `consume_reservation`
- `cancel_reservation`
- `adjust_part_quantity`
- `create_part`
- `update_part_metadata`
- `soft_delete_part`
- `restore_part`

MCP writes require the applicable server/read-write category, global tool permission,
client ceiling, authorization scope and active Operator-or-higher authority. Consequential
writes use preview, short-lived confirmation, idempotency/completed replay and state-drift
checks. MCP deliberately exposes no permanent purge, hard delete or recycle-bin-empty tool.

Supported access paths include OAuth and named direct clients using Bearer keys, custom
headers or trusted networks. No-auth access is an explicit typed-confirmed fallback, is
read-only, and is off by default.

Real Claude OAuth testing discovered the complete six-read/eight-write catalogue and
successfully exercised guarded write preview/confirmation. A Hermes `MCP event loop is
not running` result was isolated to the Hermes client/runtime wrapper after the same
Part Pilot MCP endpoint initialized and executed `search_parts` from inside that container.

## Release validation

The Patch 796 boundary provides the final automated release evidence:

- 44 current backend release smoke invocations pass on independent copied-production
  databases. Historical fixtures that test migration defaults are normalized only in
  their private copies; live mutable settings and direct-client history are untouched.
- Canonical Docker/Vite build reproduces runtime image
  `sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`.
- Production Alembic remains `0022_mcp_inventory_part_lifecycle`.
- SQLite quick/foreign-key integrity, backup/restore, auth/session/role boundaries,
  Inventory/Projects/Reservations/History/live-sync, API keys, OAuth/direct MCP
  transports, permissions and all safeguarded MCP writes are covered.
- Browser release polish from P779-P785 is approved.

## Deployment notes

Follow the README and `.env.example` for deployment. For an internet-facing instance:

- terminate HTTPS at a trusted reverse proxy;
- set the public base URL correctly for OAuth/MCP flows;
- configure trusted-proxy boundaries deliberately and avoid exposing the application
  port directly when the reverse proxy is the intended boundary;
- keep no-auth MCP disabled unless its read-only exposure is explicitly intended;
- protect persistent `/data`, the instance secret, backups and `.env`;
- create a verified backup before upgrades or restore operations.

Changing display currency does not perform FX conversion or rewrite historical numeric
prices. Changing workspace timezone changes passive display semantics only and does not
rewrite stored timestamps.

## Known alpha limitations / intentional boundaries

- Notifications & Messaging are post-v1.
- MCP does not expose permanent inventory purge/hard delete.
- Currency selection is display/formatting semantics, not currency conversion.
- Repository licensing has not yet been selected. Until the repository owner explicitly
  chooses licensing terms, do not describe the repository as open source or assume
  redistribution rights.
- No public-alpha Git tag or GitHub Release title is assigned by these notes.

## Upgrade and rollback

Before changing an existing deployment, back up persistent data and retain the current
working image/configuration until the upgraded instance passes health and application
checks. Restore operations are consequential and should use the product's validated
backup/restore workflow rather than replacing production database files casually.
