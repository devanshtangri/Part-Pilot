# Chat 18 to Chat 19 Handoff

<!-- PARTPILOT:CHAT18_TO_CHAT19_HANDOFF:V517 -->

## Chat transition

- Completed chat: `Chat 18: Static Bearer MCP Integration`
- Completed patch range: `488-517`
- Next chat: `Chat 19: OAuth Connector Completion and MCP Write Foundation`
- Next patch: `518`
- Chat 19 patch range: `518-547`
- Chat 19 planned boundary: `547`

No `Chat_19_Starting_Prompt.md` file should be created. The ready-to-paste prompt
belongs only in the chat response after Patch 517 succeeds.

## Exact pre-boundary repository and deployment

- Branch: `main`
- `HEAD` and `origin/main`:
  `f9520747f6123e38ac0f99be273076da79e21b8e`
- Subject: `Verify isolated MCP SDK compatibility`
- Git/index: clean
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:49ae754788fb82dc9c81bb12a7cde62194ea89d0e9628969f37faeb00d8b8fde`
- Deployment: running, healthy, restart count `0`
- Public MCP URL: `https://part.devansh.cc/mcp`
- Public scopes: `mcp:read`
- Trusted proxy CIDRs: empty
- Uvicorn proxy-header rewriting: disabled

## Exact live data state

- Database SHA-256:
  `63ed48d4f96675ec371465515eb7478572b341abc9a85e8fb81f2a9fa85bd9fa`
- Size: `688128` bytes
- Integrity: `ok`; foreign-key violations: none
- Parts: `15`
- Projects: `7`
- Reservations: `9`
- Stock movements: `32`
- Audits: `135`
- App settings: `17`
- MCP enabled/read/write: `true/true/false`
- Direct-auth rows: `1`
- Direct-auth mode: `bearer_key`
- Direct key lengths: cipher/digest/prefix `164/64/20`
- Direct rotation present; last-use absent; no header or networks active
- OAuth clients: `6`
- Authorization codes: `5`
- Consents: `5`
- Tokens: `0`
- Instance-secret mode/size: `0600` / `65`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`

## Chat 18 completed work

### Direct authentication

- Static Bearer keys are routed separately from OAuth Bearer tokens.
- Direct principals produce compatible MCP audit attribution.
- Key material is encrypted at rest and validated with a keyed digest.
- Status, create, reveal, rotate, disable, no-store responses, bounded last-use,
  and secret-free audits are implemented.
- Custom-header mode is fully managed and dispatched.
- Trusted-network mode has Alembic persistence, strict CIDR validation,
  management APIs, runtime enforcement, client-IP audits, and Settings UI.
- Bearer-key direct mode is active again after a user rotation. Preserve that
  exact credential state and never print or rotate it automatically.

### Proxy and public origin

- Uvicorn implicit proxy rewriting is disabled.
- Bind address and trusted proxies are explicit.
- Untrusted forwarding headers are ignored.
- Public MCP and OAuth origins use the strict resolver and configured public URL.
- Current trusted-proxy CIDRs remain empty because Nginx and direct published
  port traffic share the Docker gateway peer.

### SDK and public read-only MCP

- Official Python MCP SDK version `1.27.2` passed on copied data.
- The exact deployed image passed `initialize`, six-tool listing, and a
  structured `search_parts` call.
- Patch 516 enabled live MCP/read and kept write authorization disabled.
- The official SDK repeated the flow through Nginx TLS at the public URL.
- Live inventory part `15`, `ESP32-WROOM-32E-T400`, was returned.
- Public metadata advertises only `mcp:read`.

## External connector browser test

### What passed

Claude, Google, and ChatGPT reached Part Pilot using dynamic registration.

- Claude registrations: client row IDs `1`, `2`, `3`
- Google registrations: client row IDs `4`, `5`
- ChatGPT registration: client row ID `6`
- Claude/Google use `client_secret_post`; ChatGPT uses public-client method `none`
- Claude callback:
  `https://claude.ai/api/mcp/auth_callback`
- Google rows contain the six expected Google OAuth redirect variants
- ChatGPT callback: `https://chatgpt.com/connector/oauth/0oXWJa1hP-5W`
- Consent accepted normal Part Pilot username/password
- `mcp:read` consents were persisted
- Authorization codes were issued
- Part Pilot returned HTTP `302` to the registered callback

### What failed

No external client called `/oauth/token`; token rows remain `0`.

The OAuth route generates a standalone inline-HTML page rather than using the
React design system. The current CSS does not cover browser autofill. Raw
invalid/unavailable/expired responses contain only a title and `<h1>`.

The first Authorize click succeeds, issues a code, and deletes the one-time CSRF
cookie. A second click resubmits the same form. That second request correctly
fails CSRF and replaces the redirect with the unstyled
`Authorization request expired` response.

Do not weaken CSRF or allow a one-time form to be reused. Fix the browser
interaction instead.

## Exact abandoned test-row allowlist

Do not delete these rows during Patch 518. Preserve them as diagnostic evidence
until one fresh connector completes end to end.

- `mcp_oauth_clients.id`: `1,2,3,4,5,6`
- `mcp_oauth_authorization_codes.id`: `1,2,3,4,5`
- `mcp_oauth_consents.id`: `1,2,3,4,5`
- `mcp_oauth_tokens`: none

Later cleanup must:

1. Revalidate exact row IDs and client names.
2. Verify the expected redirect URI shapes.
3. Verify all listed codes are expired and unconsumed.
4. Verify none of the listed clients owns a token.
5. Delete only the exact allowlist in foreign-key-safe order.
6. Preserve the newly successful connector and every unrelated OAuth row.
7. Prove inventory, settings, audits, credentials, and sequences remain valid.

## Patch 518 required implementation

Patch 518 is a browser-test application patch. It should modify only the exact
OAuth route and directly relevant smoke coverage unless inspection proves
another file is necessary.

Required behavior:

- Create one shared standalone OAuth document shell for consent and all errors.
- Match Part Pilot's flat dark UI: subtle borders, restrained radii, dense
  readable spacing, and teal primary action.
- Style text/password autofill, selection, focus, disabled, and error states.
- Add a no-dependency inline script allowed by the CSP hash or nonce strategy.
- On first submit, detect the clicked action, disable both buttons, lock the
  form, and show `Authorizing...` or `Denying...`.
- Prevent a second POST while navigation is pending.
- Restore controls on browser back/forward cache where appropriate.
- Keep username/password autofill and accessible labels.
- Keep one-time CSRF comparison and cookie deletion unchanged.
- Replace raw expired, invalid, unavailable, and server-error pages with the
  shared shell.
- Expired state must explain that the request was already used or timed out and
  direct the user to return to the connector and start again.
- Preserve no-store, CSP, no-referrer, frame denial, and HTTPS cookie behavior.
- Add copied-database tests for initial GET, invalid login, first approve,
  duplicate POST, denial, error pages, callback query, and token exchange.
- Build/deploy and verify the existing complete smoke suite.
- Leave browser-test source uncommitted until user approval.

## Browser approval required

After Patch 518 terminal success:

1. Remove or disregard the failed connector entry.
2. Start one fresh Claude, Google, or ChatGPT connector registration.
3. Inspect desktop/mobile consent styling and autofill.
4. Click Authorize exactly once.
5. Verify the connector returns to its host and reports connected.
6. Verify Part Pilot receives `/oauth/token`.
7. Verify one OAuth token row exists.
8. Run tools/list and a read-only inventory query.
9. Confirm write authorization remains disabled.
10. Only then checkpoint and plan exact abandoned-row cleanup.

## Work after external OAuth approval

- Separate checkpoint of approved OAuth source.
- Exact allowlisted cleanup of abandoned Chat 18 test rows.
- Connector administration/revocation visibility if the real clients require it.
- Diagnostic contract for safeguarded writes.
- Independent write-tool implementation with explicit confirmation,
  idempotency, stock invariants, conflicts, audit evidence, and rollback.
- Accessibility, security, and public-alpha hardening.
