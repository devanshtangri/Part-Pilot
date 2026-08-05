# Patch 515 Diagnostic — Isolated MCP SDK Compatibility

<!-- PARTPILOT:DIAGONOSTIC_MCP_SDK_COMPATIBILITY:V515 -->

## Verdict

**PASS.** The official Python MCP SDK successfully connected to the exact
deployed Part Pilot image over Streamable HTTP using an isolated copied
database and a manifest-owned temporary Bearer credential.

The harness completed protected-resource discovery, authorization-server
discovery, `ClientSession.initialize()`, `ClientSession.list_tools()`, and
`ClientSession.call_tool("search_parts", ...)`.

No live setting was enabled, no live key was used, and no live database row was
changed.

## Exact baseline

- Baseline `HEAD` and `origin/main`: `50d46fe21dc4e9ce1e07759bb3a83fe8a8ae2cfa`
- Baseline subject: `Recover external MCP client readiness diagnostic`
- Deployed image: `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Alembic head: `0010_mcp_trusted_networks`
- Live database SHA-256: `b720faff64ac220abb4722fe91756e03bbb79b260691c38f9a89373e50740f10`
- Live MCP settings: `false/false/false`
- Live direct mode: rotated Bearer key
- Live `last_used_at`: absent
- Live OAuth clients/tokens: `0/0`

## Isolation model

- Copied database and instance secret existed only under `/tmp`.
- The copied instance secret and temporary key used mode `0600`.
- The temporary server and client used the exact deployed image.
- Both containers used a private labelled Docker network.
- No host port was published.
- The live database and secret were never mounted.
- The temporary key was never printed or logged.
- All temporary containers, networks, key material, and copied data were removed.

The server advertised an HTTPS resource identity while the private container
transport remained HTTP. This preserves the HTTPS-only resource URI contract;
Patch 514 separately verified the real Nginx TLS edge.

## SDK negotiation

- SDK/server package: `1.27.2`
- Negotiated protocol: `2025-11-25`
- Server name: `Part Pilot`
- Session ID: `null` as expected for stateless HTTP
- Tool error: `false`
- Content type: `TextContent`

## Enabled copied-database metadata

### Protected-resource metadata

```json
{
  "authorization_servers": [
    "https://partpilot-patch515-sdk-1163428-162318:8000"
  ],
  "bearer_methods_supported": [
    "header"
  ],
  "resource": "https://partpilot-patch515-sdk-1163428-162318:8000/mcp",
  "resource_name": "Part Pilot MCP",
  "scopes_supported": [
    "mcp:read"
  ]
}
```

### Authorization-server metadata

```json
{
  "authorization_endpoint": "https://partpilot-patch515-sdk-1163428-162318:8000/oauth/authorize",
  "client_id_metadata_document_supported": false,
  "code_challenge_methods_supported": [
    "S256"
  ],
  "grant_types_supported": [
    "authorization_code",
    "refresh_token"
  ],
  "issuer": "https://partpilot-patch515-sdk-1163428-162318:8000",
  "registration_endpoint": "https://partpilot-patch515-sdk-1163428-162318:8000/oauth/register",
  "response_types_supported": [
    "code"
  ],
  "revocation_endpoint": "https://partpilot-patch515-sdk-1163428-162318:8000/oauth/revoke",
  "scopes_supported": [
    "mcp:read"
  ],
  "token_endpoint": "https://partpilot-patch515-sdk-1163428-162318:8000/oauth/token",
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "client_secret_post",
    "none"
  ]
}
```

Both metadata documents advertise only `mcp:read`. `mcp:write` remains absent.

## Tool registry returned by the official SDK

```text
- search_parts
- get_part_details
- list_projects
- get_project_details
- list_reservations
- get_reservation_details
```

All six tools were returned. No write tool was registered.

## Read-only call result

- Tool: `search_parts`
- Total matching active parts: `13`
- Returned: `1`
- Has more: `true`
- Next offset: `1`
- First part ID: `15`
- First display name: `Wi-Fi and Bluetooth Module`
- Available quantity: `12`
- Stock status: `available`

## Copied-database evidence

- Candidate database SHA-256: `44b0c81904ab8c8b6ad2abfee1144fc72f05020b87110886062296eeaef13b86`
- Parts/Projects/Reservations:
  `15/7/9`
- Audit rows: `116`
- OAuth clients/tokens:
  `0/0`
- Temporary `last_used_at`: present
- Tool audit: `search_parts`
- Audit auth method: `direct_bearer`
- Plaintext key present in copied SQLite bytes: no

The copied database gained exactly two audit rows: one temporary key rotation
and one successful `mcp.tool_called` event.

## Live preservation

After cleanup, the live database SHA, row counts, MCP settings, Bearer bundle,
`last_used_at`, instance secret, restore staging, deployment, and application
source remained exact.

## Conclusion

The read-only MCP stack is compatible with the installed official Python SDK
and protocol `2025-11-25`. The prior empty scope list was solely the
live disabled-state configuration; when MCP and read tools are enabled on the
copy, both metadata documents correctly advertise `mcp:read`.

Patch 516 should not change authentication code. It should provide exact client
connection guidance and perform an explicitly approved off-site test through
`https://part.devansh.cc/mcp` after temporarily enabling only MCP and read
tools. Patch 517 remains the Chat 18 boundary.
