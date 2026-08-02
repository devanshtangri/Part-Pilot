# Diagnostic 462: MCP Runtime and Tool Contract

## Status

- Diagnostic type: documentation-only, no application implementation.
- Baseline commit: `c22b99f4e2bbc32da704f57240890c3f0ea765e7` (`Show manual backup status in Settings`).
- Branch/origin: `main` / `git@github.com:devanshtangri/Part-Pilot.git`.
- Patch 461 evidence: hash-validated and ends with `Everything PASS`.
- Live deployment: `sha256:39e8e6502613a44775ee01c26936d4c08be14bdac19f059d324656089960e6da`, health `healthy`, restart count `0`.
- Live database SHA-256: `b625e8d4fe626b72dfecd34de16d63250a70266bd1038ae956071fe85f68eeae`.
- SQLite: integrity `ok`, foreign-key check empty, Alembic `0007_projects_contract`.
- Live counts: users=1, sessions=2, parts=15, projects=7, project_items=10, reservations=9, reservation_items=14, stock_movements=32, audit_log=101, app_settings=17, backups=0.
- Restore staging: `19` fingerprint entries, no pending job, fingerprint `3e11760b7ce7d200941bdb4431a65c5cb603d6b19450df644278eeff41dd3d4c`.

## Official protocol research basis

Research date: 2026-08-02.

- Current MCP specification: `2026-07-28`.
- Transport reference: `https://modelcontextprotocol.io/specification/2026-07-28/basic/transports`.
- Authorization reference: `https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization`.
- Tool reference: `https://modelcontextprotocol.io/specification/2026-07-28/server/tools`.
- Official Python SDK: `https://github.com/modelcontextprotocol/python-sdk`.
- Current stable package observed during design: `mcp 1.28.1`; the SDK v2 line that targets the 2026-07-28 protocol remains pre-release. The first Part Pilot implementation must therefore pin the stable v1 line and must not claim native 2026-07-28 support until a separately tested v2 upgrade.

## Exact repository and runtime findings

### Existing process boundary

- Part Pilot is one FastAPI/Starlette ASGI process in the `partpilot` Compose service.
- Host port `7890` maps to container port `8000`.
- The SPA fallback is the final root mount. Any MCP mount must be registered before it.
- The application already has a composed lifespan for lifecycle state, request draining and SQLAlchemy engine disposal.
- The MCP session manager must be entered inside that existing lifespan; a second Uvicorn process or second public port is not justified for V1.

### Runtime package baseline

- `fastapi`: `0.141.1`
- `httpx`: `0.28.1`
- `mcp`: `not installed`
- `pydantic`: `2.13.4`
- `sqlalchemy`: `2.0.51`
- `starlette`: `1.3.1`
- `uvicorn`: `0.52.1`

- `mcp` is not installed in the image.
- `backend/app/mcp/__init__.py` exists and is empty.
- No MCP route, transport, token model, token service or MCP audit service exists.

### Persisted MCP defaults already present

- `mcp.enabled` = `false` (updated `2026-07-23 14:34:29.699962`)
- `mcp.read_tools_enabled` = `true` (updated `2026-07-23 14:34:29.699963`)
- `mcp.write_tools_enabled` = `false` (updated `2026-07-23 14:34:29.699965`)

These defaults match the product contract: MCP disabled by default, read tools enabled once MCP is enabled, write tools disabled by default.

### Reusable application services

- Inventory: `list_parts`, `get_part`, `list_low_stock_parts`; the MCP tool named `search_parts` will adapt `list_parts`.
- Projects: `list_projects`, `get_project`.
- Reservations: `list_reservations`, `get_reservation`.
- Existing responses already include quantities, availability, notes, custom fields, linked project/reservation data and pagination metadata.
- Existing service functions must remain the source of truth. MCP adapters must not reproduce SQL or inventory calculations.
- `AuditLog.actor_type` already accepts `mcp`, but no dedicated MCP event contract exists.

## Frozen V1 MCP runtime decisions

### 1. Transport and process model

- Endpoint: `/mcp` on the existing Part Pilot origin and port.
- Transport: Streamable HTTP.
- Initial SDK: pin stable `mcp>=1.28,<2`; use `stateless_http=True` and JSON responses.
- Mount the MCP ASGI application before the root SPA mount.
- Run the MCP session manager inside the existing FastAPI lifespan using one combined async exit stack.
- Do not add a second container, second Uvicorn process, sidecar or second public port in the initial implementation.
- Isolate SDK-specific construction in `backend/app/mcp/server.py` so a future SDK v2/2026-07-28 migration does not leak through inventory services.

### 2. Runtime enable/disable behavior

- Keep the `/mcp` transport mounted at process startup.
- Read `mcp.enabled`, `mcp.read_tools_enabled` and `mcp.write_tools_enabled` on every authorized request/tool call.
- Changes apply immediately; no restart is required.
- Missing/invalid bearer token returns HTTP `401`.
- Valid token while `mcp.enabled=false` returns HTTP `503` with `Cache-Control: no-store` and a clear retryable disabled-state payload.
- When reads are disabled, read tools are omitted and direct calls are rejected.
- When writes are disabled, write tools are omitted and direct calls are rejected.
- Invocation-time checks are mandatory even if the advertised tool list is filtered.

### 3. Authentication and token storage

The product specification explicitly requires an API token. V1 therefore uses a high-entropy pre-shared bearer token and does not claim full OAuth authorization-spec compliance.

- Add Alembic migration `0008_mcp_access` with an `mcp_tokens` table.
- Store only a SHA-256 token hash plus non-secret display metadata such as prefix, label, created time, last-used time and revoked time.
- Generate at least 32 random bytes with a recognizable `pp_mcp_` prefix.
- Return plaintext exactly once at generation/rotation.
- Require `Authorization: Bearer <token>` on every MCP HTTP request.
- Never accept a token in a query string, cookie or tool argument.
- Never log plaintext tokens.
- Token generation, rotation and revocation remain protected REST actions authenticated by the existing Part Pilot user session.
- A later OAuth resource-server mode may be added without removing pre-shared-token support, but it is outside the read-tool foundation.

### 4. Origin, host and proxy security

- Validate every present `Origin` header before handing a request to the MCP SDK.
- Missing `Origin` is allowed for non-browser MCP clients.
- Reject an unapproved present Origin with HTTP `403`.
- Use an explicit MCP origin/host allowlist derived from deployment configuration; do not treat broad application CORS as MCP authorization.
- Production remote access must terminate TLS at the existing reverse proxy or a secure tunnel.
- Preserve the existing lifecycle middleware so restore maintenance drains MCP calls with the rest of the application.

### 5. Initial read-tool contract

The first tool release contains only deterministic, bounded, read-only tools:

1. `search_parts`
   - Arguments: `query`, optional `stock_status`, `part_type_id`, `location_id`, `limit`, `offset`, optional sort field/direction.
   - `limit` range: 1-100.
   - Result: `total`, `limit`, `offset`, and serialized parts.
2. `get_part_details`
   - Argument: `part_id`.
   - Includes notes, quantities, availability, catalogue names, aliases/tags and typed custom fields already exposed by `PartResponse`.
3. `list_low_stock`
   - Optional `part_type_id`, `location_id`, `limit` capped at 100.
   - Includes low-stock and out-of-stock counts.
4. `list_projects`
   - Optional status, `limit` 1-100 and non-negative `offset`.
5. `get_project`
   - Argument: `project_id`.
6. `list_reservations`
   - Optional status, `limit` 1-100 and non-negative `offset`.
7. `get_reservation`
   - Argument: `reservation_id`.

Tool lists must be deterministic. Results must provide structured JSON and a compact text fallback. Tool adapters may format responses but may not change inventory semantics.

### 6. MCP auditing

Every MCP tool attempt, including reads and failures, must become visible in system History.

- Event type: `mcp.tool_called`.
- Actor type: `mcp`.
- Entity type: `mcp_tool`; entity ID may be null unless a single domain record is targeted.
- Metadata: tool name, success/failure, token record ID/prefix, sanitized argument summary, result count or entity ID, client name/version when available, duration and error class.
- Do not store bearer tokens, confirmation secrets, raw authorization headers or unbounded result payloads.
- Separate events: `mcp.token_generated`, `mcp.token_rotated`, `mcp.token_revoked`, `settings.mcp_updated`.

### 7. Safeguarded write contract for a later slice

No write tool belongs in the first MCP implementation.

When writes are added:

- Reuse existing reservation/project lifecycle services and their transactions.
- Add explicit `actor_type='mcp'` / `created_by='mcp'` support instead of treating MCP as system/manual.
- Require both a client-supplied idempotency key and a short-lived one-time confirmation token bound to token ID, tool name and normalized argument hash.
- Use a preview/confirm pattern so the user can approve the exact inventory delta in the AI chat without a second web-app confirmation.
- Recheck `mcp.enabled`, write permission, token validity, confirmation binding, idempotency and inventory invariants inside the same transaction immediately before mutation.
- Never expose add-part, edit-part, delete-part, restore, backup, reset or settings mutation as V1 MCP tools.
- `create_project` appears in the older product-spec ideas but is not part of the first write set; it needs a separate product decision after reservation/consumption tools are proven.

### 8. Settings UI sequencing

Do not add the MCP Settings card before the runtime and protected token REST contract are operational.

The later card must show:

- enabled/disabled state;
- read/write permission state;
- endpoint path;
- token presence, creation time and last-used time;
- one-time generate/rotate flow;
- copy warning because plaintext cannot be recovered;
- immediate-apply behavior and no restart requirement;
- clear remote-access/TLS guidance.

## Required implementation order

1. Patch 463: add the `0008_mcp_access` migration, token model/service and copied-database smoke coverage only.
2. Patch 464: add the stable SDK dependency and a disabled/authenticated `/mcp` transport shell with origin checks, no inventory tools.
3. Patch 465: prove lifecycle, route ordering, unauthenticated/disabled behavior and rollback; checkpoint backend foundation if approved.
4. Patch 466: add `search_parts`, `get_part_details` and `list_low_stock` adapters plus structured schemas and MCP audit events.
5. Patch 467: add project and reservation read tools.
6. Patch 468: run complete MCP client/Inspector, copied-database, protected-API and live-preservation smoke coverage; checkpoint reads.
7. Later patches: protected MCP Settings REST/token UI, then safeguarded write previews/idempotency/confirmation, each as separate browser/checkpoint slices.

## Testing contract

- Use copied SQLite databases and unique manifest-owned fixtures.
- Preserve all real inventory, the six Patch 401 fixtures and restore evidence.
- Test no token, invalid token, revoked token, disabled MCP, invalid Origin, read-disabled and write-disabled paths.
- Test deterministic `tools/list`, every pagination boundary, deleted-part exclusion, available quantity and low-stock calculations.
- Test that every tool attempt emits one bounded audit event without leaking credentials.
- Test restore maintenance drains/rejects MCP requests consistently with REST requests.
- Test the exact deployed route `/mcp` before the SPA fallback.
- Do not claim ChatGPT-specific compatibility until a real remote/tunnel client scan is performed against the deployed endpoint.

## Exact source hashes inspected

- `backend/app/main.py`: `5909b7845bb5be5b78943f086dd4873880d9b03f61220949755dbb5418c4ab6b`
- `backend/requirements.txt`: `fc37944ad1f2808725295d4e2020dbc8df04afcdbcea7cfa9d756e47e040d0fb`
- `backend/app/mcp/__init__.py`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `backend/app/db/seed.py`: `6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de`
- `backend/app/models/core.py`: `8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679`
- `backend/app/services/parts.py`: `5134c49324eba35004421dcd24b4df39cab1ac2a80c32aa4483be21d6f386ad6`
- `backend/app/services/projects.py`: `d558f0343670c477364230853af381bf0ceee8812439606b30b15ed012de82e8`
- `backend/app/services/reservations.py`: `bc73bd161f1b60e4ad57e0ecb71dcafddb64dec73413eb54b21de77f3d13200a`
- `backend/app/services/history.py`: `5ec4dcfbd0cc1584f646f53ad3e3b8e67c497ac5a79f95a82a9ddebaa71e5a80`
- `backend/app/api/routes/app_settings.py`: `afa370046b06e54ebc8a211e504b63a0b6ddec2d5339617a669e584d5546c3c4`
- `backend/app/services/app_settings.py`: `8676698c61df0e8ac50f53a54a33caeb183c4e2ffecab5c18e708dbd909b18d1`
- `backend/app/schemas/app_settings.py`: `d9ee4d6ffde49d0cb5bd0aa0f52d3f97c21a7131894b55a5de9911bad86c7ad4`
- `docker-compose.yml`: `934bad061fbfe00cb05eb1d1cebb800d311a9c3f7b87c5f90a495c44c627b903`
- `backend/Dockerfile`: `3fe0cad81ca7900d3f29b0d0eecbba3de32b976f3c9954ee64c0cbe7969b22ae`

## Safe conclusion

Part Pilot is ready for an MCP foundation without a new service boundary. The safe path is a stable-SDK, same-process, stateless Streamable HTTP adapter with immediate persisted gating, hashed pre-shared bearer tokens, strict Origin validation, service reuse, bounded structured read tools and complete MCP audit visibility. Writes and the Settings UI remain deliberately separate until the read foundation is deployed and tested.
