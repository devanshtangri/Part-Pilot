# Diagnostic 463: Claude Website OAuth Contract

## Status

- Diagnostic type: documentation-only contract correction.
- Baseline commit: `db42f08ef53fbe4382a6c84ddec1b1ebfa8d6da0` (`Document MCP runtime contract`).
- Patch 462 script, log and diagnostic report: hash-validated.
- Live deployment: `sha256:39e8e6502613a44775ee01c26936d4c08be14bdac19f059d324656089960e6da`, health `healthy`, restart count `0`.
- Live database SHA-256: `b625e8d4fe626b72dfecd34de16d63250a70266bd1038ae956071fe85f68eeae`.
- SQLite: integrity `ok`, foreign-key check empty, Alembic `0007_projects_contract`.
- Live counts: users=1, sessions=2, parts=15, projects=7, project_items=10, reservations=9, reservation_items=14, stock_movements=32, audit_log=101, app_settings=17, backups=0.
- Restore staging: `19` fingerprint entries, no pending job, fingerprint `3e11760b7ce7d200941bdb4431a65c5cb603d6b19450df644278eeff41dd3d4c`.
- Application source, dependency set, database and deployment remain unchanged.

## Why the Patch 462 auth decision is superseded

Patch 462 correctly froze the process, transport, runtime gating, tool, audit and
write-safety boundaries. It selected a pre-shared bearer token because the
product specification said "API token."

The user then selected **Claude on the website** as the first real acceptance
client. Claude custom web connectors accept a remote MCP URL and optionally an
OAuth client ID/secret; they do not provide a UI for arbitrary custom
`Authorization` headers. Claude connects from Anthropic cloud infrastructure,
so a local-only or private-network endpoint is also insufficient.

Part Pilot inventory is private. An unauthenticated public MCP endpoint is not
acceptable. Therefore the first remote-compatible authentication path must be
OAuth, and the bearer-token-only implementation order in Diagnostic 462 must not
be followed.

This addendum supersedes only the authentication, persistence and implementation
order sections of Diagnostic 462. The same-process `/mcp`, stateless Streamable
HTTP, immediate setting gates, read-tool list, service reuse, auditing and
safeguarded-write decisions remain valid.

## Official research basis

Research date: 2026-08-02.

- Claude custom connector setup:
  `https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp`
- Current MCP authorization specification:
  `https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization`
- MCP authorization tutorial:
  `https://modelcontextprotocol.io/docs/tutorials/security/authorization`
- Official Python SDK:
  `https://github.com/modelcontextprotocol/python-sdk`

The current MCP authorization model uses OAuth 2.1 roles, RFC 9728 Protected
Resource Metadata and RFC 8414 Authorization Server Metadata. Authorization Code
with PKCE is the appropriate user-delegated flow for Claude website.

## Frozen Claude-first V1 authentication contract

### 1. One portable MCP endpoint

- MCP URL: `https://<part-pilot-origin>/mcp`.
- Transport: stateless Streamable HTTP with JSON responses.
- The endpoint stays in the existing Part Pilot ASGI process and port.
- The endpoint is mounted before the SPA fallback.
- The same endpoint and tool schemas remain usable by Claude, Hermes, MCP
  Inspector and other standards-compliant clients.
- Client-specific Part Pilot tool implementations are forbidden.

### 2. Part Pilot acts as both authorization server and resource server

For V1, the same Part Pilot origin hosts:

- the MCP resource server at `/mcp`;
- OAuth Protected Resource Metadata;
- OAuth Authorization Server Metadata;
- dynamic client registration;
- authorization;
- token and refresh-token exchange;
- the user-facing consent screen.

This avoids a second identity service while preserving a standards-based
boundary. OAuth-specific code must remain isolated under `backend/app/mcp/` so
an external identity provider can replace the built-in authorization server
later without changing inventory services or MCP tool schemas.

### 3. OAuth discovery endpoints

The first implementation must expose and test:

- `/.well-known/oauth-protected-resource/mcp`
- `/.well-known/oauth-protected-resource` as a compatibility fallback
- `/.well-known/oauth-authorization-server`
- `/oauth/register`
- `/oauth/authorize`
- `/oauth/token`

Unauthorized `/mcp` requests must return `401` with a `WWW-Authenticate: Bearer`
challenge containing the exact `resource_metadata` URL. Discovery documents
must use the configured public HTTPS origin rather than trusting an arbitrary
request `Host` or forwarded header.

### 4. Authorization Code with PKCE

- Supported grant types: `authorization_code` and `refresh_token`.
- Supported response type: `code`.
- PKCE method: `S256`; PKCE is mandatory.
- No implicit grant.
- No resource-owner password grant.
- No client-credentials grant for the Claude user connector.
- Authorization codes are single-use, short-lived and stored only as hashes.
- Access and refresh tokens are high entropy and stored only as hashes.
- Refresh tokens rotate on use; replay revokes the affected token family.
- Access tokens are short-lived and scoped to the exact Part Pilot MCP resource.
- Bearer tokens are never accepted in query strings, cookies or MCP tool
  arguments.
- OAuth secrets, codes and tokens are never written to logs or audit metadata.

### 5. Existing Part Pilot login and consent

- The resource owner is the existing active Part Pilot user.
- `/oauth/authorize` reuses the existing Part Pilot web session.
- An unauthenticated authorization request redirects through the existing login
  flow and safely resumes the exact OAuth request afterward.
- After login, Part Pilot shows a first-party consent screen identifying:
  - client name;
  - redirect origin;
  - requested scopes;
  - read-only or write capability;
  - the Part Pilot instance being authorized.
- The user may approve or deny.
- Consent must not silently enable MCP or write tools.
- OAuth authorization succeeds only while `mcp.enabled=true`.
- Read scopes can be granted only while `mcp.read_tools_enabled=true`.
- Write scopes cannot be granted while `mcp.write_tools_enabled=false`.

### 6. Client registration for Claude website

Claude allows optional manually supplied client credentials, but the default
Part Pilot test must require only the MCP URL. Therefore V1 supports RFC 7591
Dynamic Client Registration.

- Public clients use `token_endpoint_auth_method=none`.
- Confidential clients may use `client_secret_post` or
  `client_secret_basic` only when a secret was issued.
- Redirect URIs are exact-match, HTTPS-only except loopback HTTP for local
  development/Inspector clients.
- Registration rejects wildcard redirects, fragments, userinfo, non-loopback
  plain HTTP and malformed metadata.
- Client metadata is bounded and sanitized.
- Client secrets are shown once and stored only as hashes.
- Registration is rate-limited and audited without recording secrets.
- A later Settings flow may pre-register Claude and display a client ID/secret,
  but it is not required for the first Claude website test.

### 7. OAuth scopes and MCP tool gating

Initial scopes:

- `mcp:read` — discover and call the seven approved read tools.
- `mcp:write` — reserved for later safeguarded write tools; not granted or
  advertised while writes are disabled.
- `offline_access` — allows refresh-token issuance when requested.

The effective tool set is the intersection of:

1. `mcp.enabled`;
2. valid, unrevoked OAuth access token;
3. access-token resource/audience binding;
4. access-token scopes;
5. current `mcp.read_tools_enabled` / `mcp.write_tools_enabled` settings;
6. invocation-time tool policy.

Changing MCP settings applies immediately. Existing access tokens do not bypass
a newly disabled MCP server or permission.

### 8. Persistence contract for Alembic `0008_mcp_oauth`

The former single `mcp_tokens` proposal is replaced with explicit OAuth records:

- `mcp_oauth_clients`
  - client ID;
  - hashed client secret when present;
  - client name/URI;
  - exact redirect URI list;
  - grant/response types;
  - token endpoint auth method;
  - created, updated and revoked timestamps.
- `mcp_oauth_authorization_codes`
  - hashed code;
  - client/user IDs;
  - redirect URI;
  - scopes;
  - PKCE challenge/method;
  - resource URI;
  - expiry and consumed timestamp.
- `mcp_oauth_tokens`
  - hashed access token and optional hashed refresh token;
  - token family ID;
  - client/user IDs;
  - scopes and resource URI;
  - access/refresh expiry;
  - last-used and revoked timestamps;
  - replacement/replay metadata needed for rotation safety.
- `mcp_oauth_consents`
  - user/client binding;
  - approved scopes;
  - created, updated and revoked timestamps.

All foreign keys, uniqueness rules, expiry indexes and revocation indexes must be
explicit. Migration tests run only against copied databases. No live token or
client fixture is created by the migration.

### 9. Auditing

Required bounded audit events:

- `mcp.oauth_client_registered`
- `mcp.oauth_authorized`
- `mcp.oauth_denied`
- `mcp.oauth_token_issued`
- `mcp.oauth_token_refreshed`
- `mcp.oauth_token_revoked`
- `mcp.tool_called`
- `settings.mcp_updated`

Audit metadata may include client ID, client name, user ID, scopes, result,
reason class and tool name. It must never include plaintext client secrets,
authorization codes, access tokens, refresh tokens, PKCE verifier values,
authorization headers or complete unbounded payloads.

### 10. Public HTTPS and proxy contract

Claude connects from Anthropic cloud infrastructure, not from the user's
browser. The final acceptance test therefore requires:

- a stable public HTTPS origin;
- reverse-proxy routing of `/mcp`, `/oauth/*` and `/.well-known/*`;
- no redirect from HTTPS back to HTTP;
- correct configured issuer/resource URLs;
- no dependency on LAN IPs, localhost, VPN-only access or browser cookies for
  MCP API calls;
- existing Part Pilot login cookies only for the interactive authorization and
  consent pages.

Public-origin configuration must be explicit, validated and fail closed. The
server must not derive security-critical issuer or redirect URLs from
untrusted forwarded headers.

## Revised implementation order

1. **Patch 463** — commit this Claude website OAuth correction only.
2. **Patch 464** — add Alembic `0008_mcp_oauth`, OAuth models and copied-database
   migration smoke coverage; no transport.
3. **Patch 465** — add OAuth client/code/token/consent services and security
   unit/smoke coverage on copied databases.
4. **Patch 466** — add stable MCP SDK dependency, discovery endpoints and a
   disabled OAuth-protected `/mcp` transport shell.
5. **Patch 467** — add login-resume, consent, authorize/register/token flows and
   full local MCP Inspector OAuth tests.
6. **Patch 468** — add `search_parts`, `get_part_details` and `list_low_stock`
   with structured results and bounded MCP audit events.
7. **Patch 469** — add project and reservation read tools.
8. **Patch 470** — enable the Settings MCP control/token status required to
   perform the first public Claude website test.
9. **Patch 471** — deploy through the public HTTPS origin and run the Claude
   website browser acceptance test.
10. Later patches — checkpoint reads, then design safeguarded writes separately.

No MCP write tool is implemented or advertised during this sequence.

## Claude website acceptance test

The user will test:

1. Claude → `Customize` → `Connectors`.
2. `Add custom connector`.
3. Enter only the public Part Pilot MCP URL.
4. Complete the Part Pilot login and consent flow.
5. Enable Part Pilot for a conversation.
6. Ask Claude to search inventory, retrieve part details and list low stock.

Acceptance requires:

- OAuth discovery succeeds without manually pasting a bearer token;
- Claude reaches a Part Pilot-branded login/consent flow;
- no credentials appear in URLs or logs;
- the connector lists only currently allowed tools;
- read results match REST/service truth;
- disabling MCP immediately blocks further calls;
- reconnecting/refreshing works without re-entering the Part Pilot password
  until consent or refresh authorization is revoked;
- all OAuth and tool activity appears in History without secret leakage.

## Exact source hashes preserved

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

The Claude website is the first acceptance client, but Part Pilot remains a
portable MCP server. The correct foundation is one public HTTPS `/mcp` endpoint
protected by OAuth Authorization Code with mandatory PKCE, built-in discovery,
dynamic client registration, existing-user login and explicit consent. A
bearer-token-only endpoint and an unauthenticated public endpoint are both
rejected. Diagnostic 462 remains authoritative for transport, tools, service
reuse, runtime gating, auditing and write safety except where this addendum
explicitly supersedes authentication, persistence and implementation order.
