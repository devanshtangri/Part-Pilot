# Chat 18 MCP Authentication Milestone Handoff

<!-- PARTPILOT:CHAT18_MCP_AUTHENTICATION_HANDOFF:V512 -->

## Purpose

This milestone records the completed MCP authentication stack after Patch 511.
It does not end Chat 18. The planned Chat 18 boundary remains Patch 517.

## Authoritative application checkpoint

- Feature `HEAD` and `origin/main`:
  `e0241ecc7e51271944867110714b96b4259a09f9`
- Latest feature subject:
  `Add MCP trusted-network settings controls`
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Deployment: running, healthy, restart count `0`
- Database SHA-256:
  `b720faff64ac220abb4722fe91756e03bbb79b260691c38f9a89373e50740f10`
- SQLite integrity: `ok`; foreign-key violations: none
- Parts: `15`; Projects: `7`; Reservations: `9`
- Stock movements: `32`; audits: `114`; app settings: `17`
- MCP direct-auth rows: `1`; OAuth clients/tokens: `0/0`
- Active direct mode: `bearer_key`
- Cipher/digest/prefix lengths: `164/64/20`
- Active custom-header name: `null`
- Active trusted-network JSON: `null`
- Rotated timestamp present; last-used timestamp absent
- Instance-secret mode/size: `0600` / `65`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`

## Completed authentication stack

### OAuth

- Protected-resource discovery and authorization-server metadata.
- Authorization code with PKCE S256.
- Public and confidential clients.
- Access/refresh rotation, revocation, consent, and token lifecycle.
- OAuth Bearer credentials remain fully supported by `/mcp`.

### Static Bearer

- Only `pp_mcp_key_...` values enter the direct-key validation path.
- Other Bearer values remain on OAuth validation.
- Keys are encrypted at rest and validated with a keyed digest.
- Create, reveal, rotate, disable, throttled last-use, no-store responses, and
  secret-free audits are implemented.
- Direct principals produce compatible MCP tool-call attribution.
- Responsive Settings controls were browser approved and committed.

### Custom header

- Protected configuration endpoint with strict header-name validation.
- Header mode uses the same encrypted key material and rotation model.
- Runtime dispatch preserves OAuth and Bearer behavior.
- Settings mode selection, warnings, reveal/rotate/disable behavior, responsive
  layout, and browser approval are complete.

### Trusted proxy and public origin

- Uvicorn starts with implicit proxy-header rewriting disabled.
- Host binding remains configurable with the current `0.0.0.0:7890` behavior.
- IPv4/IPv6 trusted-proxy CIDRs are parsed strictly.
- Spoofed forwarding headers from untrusted peers are ignored.
- Forwarded origin data is used only from explicitly trusted proxies.
- The public MCP/OAuth base URL is explicit.
- Trusted proxy CIDRs remain empty because the current reverse-proxy and direct
  published-port paths share the Docker gateway peer.

### Trusted network

- Alembic `0010_mcp_trusted_networks` stores canonical network JSON.
- Management rejects empty, malformed, over-limit, trust-all, multicast,
  unspecified, duplicate, and overlapping networks.
- Runtime accepts keyless MCP access only when no explicit credential is sent
  and the resolved client belongs to an approved network.
- Invalid explicit OAuth/direct credentials never fall back to network trust.
- Last-use tracking and client-IP audit attribution use existing bounded logic.
- Settings accepts one IPv4/IPv6 CIDR per line, shows active networks, provides
  warnings, and supports apply/switch/disable behavior.
- Browser approval and the separate Patch 511 checkpoint are complete.

## Live posture

- Bearer-key mode remains active.
- Trusted-network mode is implemented but inactive.
- No trusted CIDRs are configured.
- OAuth, Bearer, custom-header, and trusted-network regression suites coexist.
- Six read-only MCP tools remain available.
- Write authorization settings exist, but no inventory-mutating MCP tool has
  been enabled merely by completing authentication.

## Remaining work

1. Inspect external MCP client compatibility and connection guidance.
2. Determine whether independent OAuth/direct-auth administration needs another
   control slice.
3. Define safeguarded write-tool confirmation, idempotency, quantity, stock,
   audit, and rollback contracts.
4. Implement writes only in separate narrow slices.
5. Complete accessibility, security, and public-alpha release hardening.
6. Complete the Chat 18 boundary at Patch 517.

## Next patch

Patch 513 should be a narrow external-client/readiness and remaining-contract
diagnostic before another application change.
