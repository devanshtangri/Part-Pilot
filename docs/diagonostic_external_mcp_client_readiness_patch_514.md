# Patch 514 Recovery Diagnostic — External MCP Client Readiness

<!-- PARTPILOT:DIAGONOSTIC_EXTERNAL_MCP_CLIENT_READINESS:V514 -->

## Diagnostic verdict

**The public protocol surface is structurally ready, but the live installation
is not currently operational for an external MCP client.**

The Nginx TLS path serves valid protected-resource and authorization-server
metadata, and unauthenticated MCP requests receive a Bearer challenge pointing
to the correct resource metadata. However, all three live MCP switches are
currently disabled:

- `mcp.enabled = false`
- `mcp.read_tools_enabled = false`
- `mcp.write_tools_enabled = false`

That disabled state explains why both metadata documents advertise an empty
`scopes_supported` list. It also means a valid OAuth, Bearer, custom-header, or
trusted-network credential cannot currently obtain read-tool access.

No live credential was used in this diagnostic. Doing so would update
`last_used_at` and could create tool-call audit evidence. No OAuth client was
registered because that would create persistent client rows. Those checks must
run against a copied database or as a deliberately approved live test.

## Exact repository and runtime state

- Branch: `main`
- Diagnostic baseline `HEAD` and `origin/main`:
  `d1e959639e8c5218f2db95244885588ac515f274`
- Baseline subject: `Document MCP authentication milestone`
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image: `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Deployment health: `healthy`
- Restart count: `0`
- Uvicorn implicit proxy handling: disabled with `--no-proxy-headers`
- Published port: `0.0.0.0:7890`
- Public base URL: `https://part.devansh.cc`
- Trusted proxy CIDRs: empty
- Active direct-auth mode: `bearer_key`
- Active trusted-network JSON: `null`
- Database SHA-256: `b720faff64ac220abb4722fe91756e03bbb79b260691c38f9a89373e50740f10`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Parts/Projects/Reservations: `15/7/9`
- Stock movements/audits/app settings: `32/114/17`
- Direct-auth rows: `1`
- OAuth clients/tokens: `0/0`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`

## Public Nginx TLS path

The local Nginx Proxy Manager TLS listener was tested using the real
`part.devansh.cc` hostname and SNI.

### Protected-resource metadata

```json
{
  "authorization_servers": [
    "https://part.devansh.cc"
  ],
  "bearer_methods_supported": [
    "header"
  ],
  "resource": "https://part.devansh.cc/mcp",
  "resource_name": "Part Pilot MCP",
  "scopes_supported": []
}
```

### Authorization-server metadata

```json
{
  "authorization_endpoint": "https://part.devansh.cc/oauth/authorize",
  "client_id_metadata_document_supported": false,
  "code_challenge_methods_supported": [
    "S256"
  ],
  "grant_types_supported": [
    "authorization_code",
    "refresh_token"
  ],
  "issuer": "https://part.devansh.cc",
  "registration_endpoint": "https://part.devansh.cc/oauth/register",
  "response_types_supported": [
    "code"
  ],
  "revocation_endpoint": "https://part.devansh.cc/oauth/revoke",
  "scopes_supported": [],
  "token_endpoint": "https://part.devansh.cc/oauth/token",
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "client_secret_post",
    "none"
  ]
}
```

### Unauthenticated MCP challenge

`GET /mcp` and a standards-shaped `POST initialize /mcp` both returned
HTTP `401` with:

```text
Bearer resource_metadata="https://part.devansh.cc/.well-known/oauth-protected-resource/mcp", scope="mcp:read"
```

Response body:

```json
{"error":"invalid_token","error_description":"The MCP request source is not trusted."}
```

This proves that the public route, TLS virtual host, resource metadata pointer,
and basic authorization bootstrap are connected.

### Public DNS and hairpin limitation

Resolved addresses:

```text
122.176.152.33
```

The HomeLab could not complete a request through its own public DNS path during this run (`curl: (28) Connection timed out after 5000 milliseconds`). The local Nginx TLS path with the real hostname/SNI passed, so this is treated as a NAT hairpin limitation, not proof of an Internet outage.

A genuine WAN test must therefore be run from outside the premises, such as a
mobile connection or an external MCP client host.

## OpenAPI management and OAuth surface

| Path | Methods |
|---|---|
| `/.well-known/oauth-authorization-server` | `get` |
| `/.well-known/oauth-protected-resource` | `get` |
| `/.well-known/oauth-protected-resource/mcp` | `get` |
| `/api/settings/mcp` | `get, patch` |
| `/api/settings/mcp/direct-auth` | `delete, get` |
| `/api/settings/mcp/direct-auth/bearer-key` | `post` |
| `/api/settings/mcp/direct-auth/custom-header` | `post` |
| `/api/settings/mcp/direct-auth/reveal` | `post` |
| `/api/settings/mcp/direct-auth/trusted-network` | `post` |
| `/oauth/authorize` | `get, post` |
| `/oauth/register` | `post` |
| `/oauth/revoke` | `post` |
| `/oauth/token` | `post` |

`/mcp` is intentionally mounted as a raw Streamable HTTP route and does not
appear in OpenAPI.

## Installed runtime and tool registry

```json
{
  "fastapi": "0.141.1",
  "httpx": "0.28.1",
  "mcp": "1.27.2",
  "starlette": "1.3.1"
}
```

Registered tools:

```text
- get_part_details
- get_project_details
- get_reservation_details
- list_projects
- list_reservations
- search_parts
```

All six registered tools are read-only. Current tool annotations declare
read-only, non-destructive, idempotent, closed-world behavior. There are no
inventory-mutating MCP tools in the registry.

## Critical source hashes

| File | SHA-256 |
|---|---|
| `backend/app/mcp/runtime.py` | `57ed9ba8e77f9fe3e21e213b3f5c34a46594fd63c45ffb1b18f53048e0299950` |
| `backend/app/core/client_ip.py` | `e09c598b8eb4a3ba2ea63b6c6d361357b8e569e2b7f7dc7b2eb3b96313283781` |
| `backend/app/api/routes/mcp_oauth.py` | `434d5ded5e2716bbcde37a3d7d4c22946fc87588b7c4e6413e9ba59321b90942` |
| `backend/app/services/mcp_oauth.py` | `c99b36f95ae1c0a1f413a9905f7d85377449b256397df2aaa636008510b1af51` |
| `backend/app/services/mcp_direct_auth.py` | `2c8d6a8ff45dd3556046462a55e9042ca8db461bb5332bb0d8b2c6d684e9ef0b` |
| `backend/app/mcp/part_tools.py` | `11eff6646ea9d85ec45c38a1f7d9abfefba2b95c25e1b64f96fe938b2e925a8e` |
| `backend/app/mcp/workspace_tools.py` | `e0e9916ca8345a1e822fe63650ce84648d6fbc30a0b71156eeff1538c1c942a6` |
| `backend/app/main.py` | `5070f3f2643e43f847192f7232bb602ce58df50c3bb0e2bed39ee357ac8c2cd1` |
| `backend/app/core/config.py` | `ca0a39a16b8d145e19e2de151f4f1d106e282cd52add94c09a24ebd7b630f040` |
| `docker-compose.yml` | `90024234bae81fa67ff3997bd9ad9388532b6ef934ec5796c98e06df0fa1b8ce` |
| `backend/Dockerfile` | `37841e343fcf891b0e3c6ba30d047388ed0f15861a2e33a17ed9bc426805d506` |
| `.env.example` | `3364f618f6063b4219b1ec6d34989ea1f0ea4c7906d0d9b8b96e3ba665cb46c8` |

## Marker and block-shape counts

| File | Marker/block | Count |
|---|---|---:|
| `backend/app/api/routes/mcp_oauth.py` | `@router.get("/.well-known/oauth-protected-resource/mcp")` | `1` |
| `backend/app/api/routes/mcp_oauth.py` | `@router.get("/.well-known/oauth-authorization-server")` | `1` |
| `backend/app/api/routes/mcp_oauth.py` | `@router.post(
    "/oauth/register"` | `1` |
| `backend/app/core/client_ip.py` | `PARTPILOT:MCP_TRUSTED_PROXY_RESOLVER:V506` | `1` |
| `backend/app/core/client_ip.py` | `class TrustedProxyResolver` | `1` |
| `backend/app/core/client_ip.py` | `def resolve_public_origin` | `1` |
| `backend/app/main.py` | `PARTPILOT:MCP_OAUTH_HTTP_REGISTRATION:V467` | `1` |
| `backend/app/main.py` | `PARTPILOT:MCP_STREAMABLE_HTTP_ROUTE:V469` | `1` |
| `backend/app/mcp/runtime.py` | `PARTPILOT:MCP_STREAMABLE_HTTP_RUNTIME:V509` | `1` |
| `backend/app/mcp/runtime.py` | `PARTPILOT:MCP_FORWARDED_ORIGIN_RUNTIME:V508` | `1` |
| `backend/app/mcp/runtime.py` | `PARTPILOT:MCP_TRUSTED_NETWORK_RUNTIME:V509` | `1` |
| `backend/app/mcp/runtime.py` | `class PartPilotMcpGateway` | `1` |

## Relevant source excerpts

### Public base URL and proxy configuration

```text
13:     container_port: int = Field(default=8000, alias="PARTPILOT_CONTAINER_PORT")
14:
15:     # PARTPILOT:MCP_TRUSTED_PROXY_CONFIG:V506
16:     bind_address: str = Field(
17:         default="0.0.0.0",
18:         alias="PARTPILOT_BIND_ADDRESS",
19:     )
20:     trusted_proxy_cidrs: str = Field(
21:         default="",
22:         alias="PARTPILOT_TRUSTED_PROXY_CIDRS",
23:     )
24:
25:     # PARTPILOT:MCP_PUBLIC_BASE_URL:V467
26:     public_base_url: str | None = Field(
27:         default=None,
28:         alias="PARTPILOT_PUBLIC_BASE_URL",
29:     )
30:
31:     # PARTPILOT:MCP_INSTANCE_SECRET:V482
32:     instance_secret: str | None = Field(
33:         default=None,
34:         alias="PARTPILOT_INSTANCE_SECRET",
35:     )
36:
37:     instance_secret_file: str = Field(
38:         default="/data/.partpilot-instance-secret",
39:         alias="PARTPILOT_INSTANCE_SECRET_FILE",
```

### MCP authentication selection and challenge

```text
357:     return _oauth_principal(token, resource_uri)
358:
359:
360: # PARTPILOT:MCP_TRUSTED_NETWORK_RUNTIME:V509
361: class PartPilotMcpGateway:
362:     async def __call__(self, scope, receive, send) -> None:
363:         if scope.get("type") != "http":
364:             await _SDK_APP(scope, receive, send)
365:             return
366:
367:         headers = _header_map(scope)
368:         try:
369:             public_origin = _public_origin(scope)
370:             resource_uri = validate_resource_uri(f"{public_origin}/mcp")
371:         except (McpOAuthValidationError, RuntimeError) as exc:
372:             await _send_json(
373:                 send,
374:                 status=400,
375:                 content={"error": "invalid_request", "error_description": str(exc)},
376:             )
377:             return
378:
379:         origin = headers.get("origin")
380:         if origin is not None and _normalise_origin(origin) != public_origin:
381:             await _send_json(
382:                 send,
383:                 status=403,
384:                 content={
385:                     "error": "invalid_origin",
386:                     "error_description": "The MCP request Origin is not allowed.",
387:                 },
388:             )
389:             return
390:
391:         metadata_url = (
392:             f"{public_origin}/.well-known/oauth-protected-resource/mcp"
393:         )
394:         challenge = (
395:             'Bearer resource_metadata="'
396:             + metadata_url
397:             + '", scope="'
398:             + MCP_SCOPE_READ
399:             + '"'
400:         )
401:         try:
402:             bearer_present, token = _bearer_credential(scope)
403:             custom_header_name = await asyncio.to_thread(
404:                 _configured_custom_header_name
405:             )
406:             custom_present, custom_key = _custom_header_credential(
407:                 scope,
408:                 custom_header_name,
409:             )
410:         except McpOAuthValidationError as exc:
411:             await _send_json(
412:                 send,
413:                 status=400,
414:                 content={
415:                     "error": "invalid_request",
416:                     "error_description": str(exc),
417:                 },
418:             )
419:             return
420:
421:         if bearer_present and custom_present:
422:             await _send_json(
423:                 send,
424:                 status=400,
425:                 content={
426:                     "error": "invalid_request",
427:                     "error_description": (
428:                         "MCP requests must use exactly one authentication credential."
429:                     ),
430:                 },
431:             )
432:             return
433:
434:         auth_method: str
435:         credential: str | None
436:         if custom_present:
437:             auth_method = "direct_custom_header"
438:             credential = custom_key
439:         elif bearer_present:
440:             auth_method = (
441:                 "direct_bearer"
442:                 if token is not None and token.startswith(DIRECT_KEY_PREFIX)
443:                 else "oauth"
444:             )
445:             credential = token
446:         else:
447:             auth_method = "direct_trusted_network"
448:             credential = None
449:
450:         if auth_method != "direct_trusted_network" and credential is None:
451:             await _send_json(
452:                 send,
453:                 status=401,
```

### Protected-resource metadata

```text
373:
374: @router.get("/.well-known/oauth-protected-resource")
375: @router.get("/.well-known/oauth-protected-resource/mcp")
376: def protected_resource_metadata(
377:     request: Request,
378:     db: Session = Depends(get_db),
379: ) -> JSONResponse:
380:     origin = _public_origin(request)
381:     return _json_response(
382:         {
383:             "resource": _resource_uri(request),
384:             "authorization_servers": [origin],
385:             "scopes_supported": _scope_values(db),
386:             "bearer_methods_supported": ["header"],
387:             "resource_name": "Part Pilot MCP",
388:         }
389:     )
390:
391:
392: @router.get("/.well-known/oauth-authorization-server")
393: def authorization_server_metadata(
394:     request: Request,
395:     db: Session = Depends(get_db),
396: ) -> JSONResponse:
397:     origin = _public_origin(request)
398:     return _json_response(
399:         {
400:             "issuer": origin,
401:             "authorization_endpoint": f"{origin}/oauth/authorize",
402:             "token_endpoint": f"{origin}/oauth/token",
403:             "registration_endpoint": f"{origin}/oauth/register",
404:             "revocation_endpoint": f"{origin}/oauth/revoke",
405:             "response_types_supported": sorted(SUPPORTED_RESPONSE_TYPES),
406:             "grant_types_supported": sorted(SUPPORTED_GRANT_TYPES),
407:             "token_endpoint_auth_methods_supported": sorted(
408:                 SUPPORTED_CLIENT_AUTH_METHODS
409:             ),
410:             "code_challenge_methods_supported": ["S256"],
411:             "scopes_supported": _scope_values(db),
412:             "client_id_metadata_document_supported": False,
413:         }
```

### Disabled-state scope calculation

```text
263:     return result
264:
265:
266: def available_scopes(db: Session, *, require_enabled: bool = True) -> frozenset[str]:
267:     enabled = get_bool_setting(db, MCP_ENABLED_KEY, False)
268:     if require_enabled and not enabled:
269:         raise McpOAuthDisabledError("MCP is disabled.")
270:     scopes: set[str] = set()
271:     if get_bool_setting(db, MCP_READ_ENABLED_KEY, True):
272:         scopes.add(MCP_SCOPE_READ)
273:     if get_bool_setting(db, MCP_WRITE_ENABLED_KEY, False):
274:         scopes.add(MCP_SCOPE_WRITE)
275:     return frozenset(scopes)
276:
277:
278: def normalise_scopes(
279:     db: Session,
280:     scopes: Iterable[str],
281:     *,
282:     require_enabled: bool = True,
283: ) -> list[str]:
284:     requested = _normalise_unique_strings(
```

### Raw `/mcp` route registration

```text
146: app.include_router(restores_router, prefix="/api")
147: # PARTPILOT:MCP_OAUTH_HTTP_REGISTRATION:V467
148: app.include_router(mcp_oauth_router)
149:
150: # PARTPILOT:MCP_STREAMABLE_HTTP_ROUTE:V469
151: app.router.routes.append(
152:     Route(
153:         "/mcp",
154:         endpoint=mcp_http_endpoint,
155:         methods=["GET", "POST", "DELETE"],
156:         name="mcp-streamable-http",
157:         include_in_schema=False,
158:     )
159: )
160:
161: frontend_dist = Path("/app/frontend_dist")
162: if frontend_dist.exists():
163:     app.mount(
164:         "/",
165:         SPAStaticFiles(directory=frontend_dist, html=True),
166:         name="frontend",
167:     )
```

## Findings

### 1. Protocol discovery path: pass

The TLS virtual host, protected-resource metadata, authorization-server
metadata, dynamic registration endpoint, token endpoints, and resource
challenge are present and internally consistent with
`https://part.devansh.cc`.

### 2. Operational availability: intentionally blocked

The global MCP and read-tool switches are both false. This is the immediate
reason an external client cannot complete an authenticated read session.

### 3. Scope-advertisement retest required

While disabled, metadata advertises `scopes_supported: []`, but the resource
challenge requests `mcp:read`. That combination reflects the current disabled
configuration. It must be retested after enabling MCP and read tools to confirm
that both metadata documents advertise `mcp:read` and that common clients do
not cache the earlier empty scope list.

### 4. Real SDK session: not yet proven across the deployed TLS route

Existing transport smokes validate OAuth, Bearer, custom-header, and
trusted-network dispatch inside the application test environment. They do not
yet prove a real `mcp.ClientSession` over Streamable HTTP through Nginx using a
copied database and temporary credential.

### 5. WAN reachability: not proven by the HomeLab

The local Nginx TLS path passed. A test from the same HomeLab through public DNS
is not a reliable WAN test because NAT hairpin behavior is router-dependent.

### 6. Live credential posture: safe and unchanged

The rotated Bearer key remains active. No plaintext key was printed, logged, or
used by this diagnostic. `last_used_at` remains absent.

### 7. Write tools: deliberately out of scope

The write setting exists but is false, and no write tool is registered. The
current six-tool surface is read-only. Write contracts require a separate
design for confirmation, idempotency, quantity invariants, audit attribution,
conflict handling, and rollback.

## Safe implementation plan

### Patch 515 — copied-database SDK compatibility harness

1. Start an isolated Part Pilot container on a temporary host port with a copied
   database and copied instance secret.
2. Enable MCP and read tools only in the copied database.
3. Create a manifest-owned temporary direct credential in the copied database.
4. Connect with the installed official `mcp.ClientSession` and
   `streamablehttp_client`.
5. Run `initialize`, `tools/list`, and one bounded read-only tool call.
6. Verify the six expected tools, structured output, protocol version, response
   headers, and audit attribution.
7. Destroy the temporary container and copied data.
8. Prove the live database, secret, deployment, and Git state are byte-for-byte
   unchanged.

### Patch 516 — connection guidance and approved WAN test

1. Document exact client configuration for direct Bearer and OAuth.
2. Temporarily enable MCP and read tools only after explicit approval.
3. Test from an off-site network or external MCP client.
4. Confirm discovery, authorization, initialize, tools/list, and a read call.
5. Record client/version-specific compatibility results without exposing
   credentials.

### Patch 517 — Chat 18 boundary

Resolve only defects discovered by Patches 515-516 if they are mandatory for
the handoff, then update durable documents, authoritative state, next-chat
title/range, and the ready prompt. Safeguarded write tools move to the next chat.

## External standards references

- MCP Authorization specification:
  `https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization`
- MCP Streamable HTTP transport:
  `https://modelcontextprotocol.io/specification/2025-11-25/basic/transports`
- OAuth Protected Resource Metadata, RFC 9728:
  `https://www.rfc-editor.org/rfc/rfc9728`
- OAuth Authorization Server Metadata, RFC 8414:
  `https://www.rfc-editor.org/rfc/rfc8414`

## Diagnostic conclusion

Do not alter authentication code based solely on the current empty scope list.
First prove a real copied-database SDK session with MCP/read enabled. The safest
next patch is the isolated Patch 515 compatibility harness described above.
