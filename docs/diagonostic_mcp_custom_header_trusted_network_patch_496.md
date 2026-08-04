# Patch 496 MCP Custom Header and Trusted Network Diagnostic

Generated: `2026-08-04T13:00:17.697378+00:00`

## Result

Static Bearer authentication is complete, committed and pushed. The live key
was rotated after browser approval. This report records only non-secret shape
information; it contains no plaintext key, stored prefix value, ciphertext or
validation digest.

Custom-header authentication can be the next independent implementation slice.
The existing `0009_mcp_direct_auth` schema anticipated the mode and header-name
field, but service, protected API, runtime and smoke support do not yet exist.

Trusted-network authentication must **not** be enabled from the existing mode
field alone. There is no persisted allowed-network list, no explicit
trusted-proxy CIDR contract and no verified client-IP resolver. The current MCP
origin helper also consumes forwarded host/protocol headers without first
proving that the immediate peer is a trusted proxy.

## Authoritative state

- Branch: `main`
- HEAD and `origin/main`: `55a73f98c5d9b000811778cf3aa4e49118951957`
- Latest subject: `Add static Bearer MCP settings controls`
- Git/index: clean
- Deployment image: `sha256:c91d2e05dd413088f68b3fb5cd651361740677a0961133f229f5387c72320db0`
- Deployment: `running`, health
  `healthy`, restart count `0`
- Alembic: `0009_mcp_direct_auth`
- Database SHA-256 at execution: `3113b2ccc60019f31ca4ed3238ebfa1aae3a5b79bc3d29798a0cc727d22a11fe`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Users/sessions: `1` / `3`
- Parts/Projects/Reservations: `15` /
  `7` / `9`
- Stock movements/audits: `32` /
  `114`
- App settings: `17`
- OAuth clients/tokens: `0` /
  `0`
- Direct-auth rows: `1`
- Direct-auth mode: `bearer_key`
- Encrypted credential length: `164`
- Validation digest length: `64`
- Stored prefix length: `20`
- Rotation audit rows: `4`
- Latest rotation timestamp: `2026-08-04 12:39:06.481269`
- Last-use timestamp present:
  `no`
- Instance-secret file: present, 65 bytes, mode `0600`
- Instance-secret SHA-256: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint: `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`
- Restore operations: `3`

## Current deployment trust boundary

- Compose network: `partpilot_default`
- Container address: `172.20.0.2/`
  `16`
- Docker bridge gateway: `172.20.0.1`
- `PARTPILOT_PUBLIC_BASE_URL`: not configured
- Compose publishes
  `${PARTPILOT_HOST_PORT:-7890}:${PARTPILOT_CONTAINER_PORT:-8000}`
  without an explicit bind-address setting.
- Uvicorn starts without explicit `--proxy-headers`,
  `--no-proxy-headers` or `--forwarded-allow-ips`.
- Installed Uvicorn documents the default forwarded allowlist as
  `127.0.0.1`.
- `runtime._public_origin` independently reads the first
  `X-Forwarded-Proto` and `X-Forwarded-Host` values when a public base URL is
  absent. It does not verify the immediate peer before trusting them.
- `_header_map` case-folds names and keeps only the first duplicate value.
  Security credentials must instead reject duplicate fields.

In a host-port/reverse-proxy topology, the ASGI peer may be the Docker gateway
or proxy rather than the original client. Trusting that peer grants every
request it forwards. Trusting an unverified `X-Forwarded-For` value lets a
caller claim an allowed address. Trusted-network mode therefore requires both
allowed-client networks and a separate operator-controlled trusted-proxy
boundary.

## Existing persistence and API shape

Alembic `0009_mcp_direct_auth` and the model already permit `disabled`,
`bearer_key`, `custom_header` and `trusted_network`. The singleton contains
`custom_header_name`, and its constraints require encrypted key material for
custom-header mode.

Current gaps:

- The service defines only disabled and Bearer behavior.
- Credential generation, encryption, reveal and validation are Bearer-specific.
- The protected API exposes Bearer create/rotate, reveal, status and disable.
- Status omits `custom_header_name` and trusted-network configuration.
- The runtime reads only `Authorization: Bearer`.
- No client-IP resolver, trusted-proxy setting or trusted-network list exists.
- No smoke test covers duplicate credential headers, proxy spoofing or CIDRs.

## Safe custom-header contract

1. Add a distinct generated prefix such as `pp_mcp_header_`.
2. Default to canonical lowercase `x-partpilot-mcp-key`.
3. Validate names against HTTP field-name token grammar and the column limit.
4. Reject reserved names: `authorization`, `proxy-authorization`, `cookie`,
   `set-cookie`, `host`, `origin`, `forwarded`, every `x-forwarded-*`,
   `connection`, `content-length`, `transfer-encoding`, `te`, `trailer`,
   `upgrade` and `x-real-ip`.
5. Store the canonical lowercase name in `custom_header_name`.
6. Generalize the existing stable-secret encryption and keyed-digest pattern.
7. Rotation atomically switches direct mode to `custom_header` and immediately
   invalidates the previous direct credential.
8. OAuth remains available regardless of direct mode.
9. Require exactly one non-empty configured custom-header value.
10. Reject requests carrying both a recognized OAuth/Bearer credential and the
    configured custom header as ambiguous.
11. Preserve MCP enabled/read-tool gates, Host/Origin checks and all six
    read-only tools.
12. Use principal `auth_method: direct_custom_header`, actor type `mcp`, no
    fabricated user/OAuth client, and `direct_auth_id: 1`.
13. Keep responses and audits secret-free and `no-store`.
14. Status may expose only mode, configured state, canonical header name,
    masked prefix, rotation time and last-use time.
15. UI must warn that reverse proxies must pass the header unchanged and must
    never log it.

## Trusted-network persistence required first

Recommended later migration:

- Add nullable `trusted_networks_json` to the direct-auth singleton.
- Store a canonical JSON array of normalized IPv4/IPv6 CIDRs.
- Require at least one CIDR in `trusted_network` mode.
- Require null in disabled, Bearer and custom-header modes.
- Reject `0.0.0.0/0`, `::/0`, multicast, unspecified and blanket ranges.
- Keep trusted-proxy CIDRs out of the database/UI. They define deployment
  perimeter and belong in an environment variable such as
  `PARTPILOT_TRUSTED_PROXY_CIDRS`.
- Add `PARTPILOT_BIND_ADDRESS` so operators can prevent direct-port bypass.

## Required proxy and client-IP resolver

1. Make proxy handling explicit. Prefer Uvicorn `--no-proxy-headers` and one
   application resolver rather than split trust.
2. Treat `scope["client"]` as the immediate peer.
3. Read forwarded identity/origin only when that peer belongs to configured
   trusted-proxy CIDRs.
4. Support one documented forwarding format and reject conflicting evidence.
5. Parse `X-Forwarded-For` right-to-left, remove only trusted proxies and use
   the first untrusted address as the client.
6. Reject malformed, empty, duplicate, obfuscated or ambiguous values.
7. Prefer `PARTPILOT_PUBLIC_BASE_URL`; otherwise trust forwarded host/proto only
   from a trusted immediate proxy.
8. Never authenticate the Docker bridge gateway merely because it forwards.
9. Record resolved client IP and resolution method in secret-free tool audits.
10. Fail closed when forwarded identity is required but proxy trust is absent.

## Required smoke matrix

### Custom header

- Correct, wrong, missing, empty and duplicate values.
- Case-insensitive name matching.
- Invalid/reserved name rejection.
- Rotation, reveal and disable.
- OAuth coexistence and credential ambiguity rejection.
- MCP/read gates and all six tools.
- Principal/audit identity and total secret redaction.
- Exact copied-database and instance-secret cleanup.

### Trusted network

- Direct peer inside/outside allowed CIDRs.
- IPv4/IPv6 normalization.
- Untrusted peer spoofing forwarding headers.
- Trusted one-proxy and multi-proxy chains.
- Malformed, duplicate and conflicting forwarding fields.
- Docker gateway not mistaken for client.
- Direct host-port bypass.
- MCP/read gates, all six tools, OAuth coexistence and audit IP.
- Exact copied-database cleanup and live preservation.

## Safe implementation order

1. **Patch 497:** custom-header service and protected management API only.
   Generalize credential cryptography, add strict name validation, extend
   status schemas, and add copied-database service/API smoke. Do not modify
   runtime, frontend or trusted-network behavior.
2. Integrate custom-header dispatch into `/mcp`; reject duplicates and mixed
   credentials while preserving OAuth/Bearer behavior.
3. Add custom-header Settings controls, browser-test and checkpoint.
4. Separately add trusted-network persistence, explicit proxy configuration,
   client-IP resolution and host-bind control.
5. Add trusted-network runtime/UI only after spoofing and bypass smokes pass.
6. Keep safeguarded MCP write tools separate.

## Documentation drift

README still says static Bearer runtime and the direct-key UI are unfinished.
Project memory still says OAuth is the only `/mcp` runtime path. Roadmap and
Checkpoint retain completed MCP items as unchecked. Do not update those files
in this diagnostic commit; update them at the next public milestone or no
later than the Chat 18 boundary.

## Exact inspected source hashes

- `backend/app/mcp/runtime.py`: `45387f55d02a75990e32d3574ed2f495e3d72df529d35e76f212acc934b792a2`
- `backend/app/mcp/part_tools.py`: `280c5803593b49a7cbad0254b1290e17bf597224e0c4456bd1fecadcae10f141`
- `backend/app/mcp/workspace_tools.py`: `e0e9916ca8345a1e822fe63650ce84648d6fbc30a0b71156eeff1538c1c942a6`
- `backend/app/services/mcp_direct_auth.py`: `b802b07e3f22f043d6dfb244efa5f20e8264128494705c6c5cc039becb4eda5f`
- `backend/app/services/mcp_oauth.py`: `c99b36f95ae1c0a1f413a9905f7d85377449b256397df2aaa636008510b1af51`
- `backend/app/api/routes/app_settings.py`: `17400e3c7ccf36b2ecd7988b2712142af37f9979f6e7368df2ab979b4ce7cfd0`
- `backend/app/schemas/app_settings.py`: `30afe072635f232ef15fa3f948d7fdb038e27278f50dec0a4c586f43a2fae9ca`
- `backend/app/models/core.py`: `da3e30621b7760811673adb7d10365ec7a90d4e0264d6dd18f4874611271e65e`
- `backend/app/core/config.py`: `a5d4ff2354e7e45bbd2a79a58c2acd0af769bb40867bec7d83e736ce0595d2cd`
- `backend/app/main.py`: `5070f3f2643e43f847192f7232bb602ce58df50c3bb0e2bed39ee357ac8c2cd1`
- `backend/app/db/mcp_direct_bearer_transport_smoke_test.py`: `aeb52a9b452f0df7c7e7dd78a11d0764150ec0bedacaaf6fccbf40e79560f60e`
- `backend/app/db/mcp_direct_auth_smoke_test.py`: `57dd221e6ad826526f28b4c87161583a9e7ed8f3ae1a446fa74d8f1adbfd6df9`
- `backend/app/db/mcp_direct_auth_api_smoke_test.py`: `f5b98cd00ab8b4ff0311591a72ac2911db854fa6e89b8a50ec4ce81079b9a08d`
- `backend/app/db/mcp_transport_smoke_test.py`: `428d11db9d060c06e33c9d5c2e8b9237c7058455e474659b90ee295fb121dec4`
- `backend/app/db/mcp_workspace_tools_smoke_test.py`: `9300d5f1b088648164485bd8860d9011cad507d6510651dd974eb5101b1f0380`
- `backend/alembic/versions/0009_mcp_direct_auth.py`: `2e5ef4cbc02e53b3e077b0f16b643f4605410ef810759275064f2bac0fa6ea2b`
- `backend/Dockerfile`: `3fe0cad81ca7900d3f29b0d0eecbba3de32b976f3c9954ee64c0cbe7969b22ae`
- `docker-compose.yml`: `934bad061fbfe00cb05eb1d1cebb800d311a9c3f7b87c5f90a495c44c627b903`
- `frontend/src/pages/Settings.tsx`: `bddc13f119b4c638a86f5721fe7b9dbff6c46b26c34c82a38a15b4c3a1cd912f`
- `frontend/src/pages/Settings.css`: `31753aee52660be4563156ea1a82d062cb6d16400e155bc0231f58f38927e759`
- `frontend/src/services/settingsClient.ts`: `464cfb751837c3ad08d1397d8c1312303208f22525a8cee2a68c4b8ce9c94b2e`
- `frontend/src/types/settings.ts`: `166a4b97f6af34babee01fd44d76b49a9804c3284b2a0a53e11a344409cd6684`

## Exact inspected documentation hashes

- `docs/Checkpoint.md`: `958eae35d29d7e1f751cf811948d454a34fe4ac67d57b59accc2a708f696b564`
- `docs/Implementation_Roadmap.md`: `c8b28b0ee43d786743ee5bbe071c021e010c2b3f2410728b68970f7b4b52d75e`
- `docs/Part_Pilot_Project_Memory.txt`: `2f6a3a027e635a57a092c8f691a95167531f6ee7caa4c3e4316e0f516b93bafb`
- `README.md`: `e2eb68c20d9dbb47deba361af748e5200e57193751aba129ff26f18d567e02b0`
- `docs/Chat_17_MCP_Foundation_Handoff.md`: `9bdc55ff95338ac2790a4126f0bdf059a6e57e16b020967d77af411320daee96`
- `docs/diagonostic_mcp_direct_auth_patch_481.md`: `2cddc884211f48acbaf1e04fc34c1352fa7f9391a9b074f266ae89f52b3b8a3e`
