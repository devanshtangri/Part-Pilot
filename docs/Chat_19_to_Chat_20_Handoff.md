# Chat 19 to Chat 20 Handoff

<!-- PARTPILOT:CHAT19_TO_CHAT20_HANDOFF:V548 -->

## Chat transition

- Completed chat: `Chat 19: OAuth Connector Completion and MCP Write Foundation`
- Planned Chat 19 range: `518-547`
- Patch 547: failed before writes on a line-wrapped README assertion
- Boundary recovery: Patch `548`
- Completed patch sequence: `518-548`
- Next chat: `Chat 20: Manual OAuth Registration Foundation`
- Next patch: `549`
- Chat 20 patch range: `549-578`
- Chat 20 planned boundary: `578`

No `Chat_20_Starting_Prompt.md` file should be created. The ready-to-paste prompt
belongs only in the chat response after Patch 548 succeeds.

## Exact pre-boundary repository and deployment

- Branch: `main`
- `HEAD` and `origin/main`: `35be283e7f63306aef29480ae5ab71c08225b32c`
- Subject: `Diagnose manual OAuth registration readiness`
- Git/index: clean
- Alembic head: `0010_mcp_trusted_networks`
- Deployment image:
  `sha256:d601fea120915e2cdfec4d1da166c95f5afc78f5e257d7b0bce5d6ddd9075207`
- Deployment: running, healthy, restart count `0`
- Database SHA-256 at boundary capture:
  `2cf5f4bb7dc8773b1b5122411bb0db63ce9ed891fb2de19bfa955bb9b5844d91`
- Database size: `724992` bytes
- Restore staging fingerprint:
  `ed92d9fb6d964aec1a23558e27b24fa6b16d3f0d1c503e5ab9ef2b4da8c75ce6`
- Instance-secret mode/size: `0600` / `65`
- Instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`

## Exact live data snapshot

- Parts: `15`
- Projects: `8`
- Reservations: `10`
- Stock movements: `33`
- Audits: `175`
- App settings: `17`
- Users: `1`
- Sessions: `4`
- MCP enabled/read/write: `true/true/false`
- Direct-auth rows: `1`
- Direct-auth mode: `bearer_key`
- OAuth clients: `2`
- Authorization codes: `2`
- Consents: `2`
- Token rows: `4`
- Client IDs: database `9` Claude and database `13` ChatGPT
- Authorization-code IDs: `9, 10`
- Consent IDs: `8, 9`
- Active token IDs at capture: `2, 4`
- Each client has one active consent, one active token, and one token family.
- OAuth revocation audits: `0`
- Historical registration audits: `17`

OAuth token rows and timestamps can rotate during normal client use. Validate
the two connected clients, active-consent count, active-token count, token-family
count, scope, and resource URI rather than hard-coding stale token totals.

## Chat 19 completed work

### OAuth connector completion

- Replaced the unfinished standalone OAuth presentation with a cohesive Part
  Pilot consent/error shell.
- Styled browser autofill, focus, disabled, selection, error, and progress
  states.
- Locked the form on first submit, disabled both actions, displayed
  `Authorizing...` or `Denying...`, and prevented duplicate POSTs.
- Preserved one-time CSRF, no-store, CSP, frame denial, no-referrer, and secure
  cookie behavior.
- Claude and ChatGPT completed registration, consent, callback, token exchange,
  MCP initialization, tool listing, and read-only tool calls.
- Patch 527 committed and pushed the browser-approved OAuth workflow.

### OAuth hygiene and administration

- Diagnosed and deleted only exact abandoned token-free client/code/consent
  rows. Connected Claude, ChatGPT, token families, credentials, and all audit
  history were preserved.
- Added protected connected-client metadata without exposing secrets, token
  hashes, token-family IDs, or callback paths.
- Added exact current-user revocation that invalidates the selected client,
  active token family, consent, and unused codes while preserving unrelated
  clients and history.
- Added copied-database backup/restore smoke proving Claude revocation and
  ChatGPT preservation without changing the live database.
- Added the responsive Connected OAuth clients Settings list and guarded revoke
  dialog.
- Corrected supplied History entity labels to canonical `MCP OAuth Token`.
- Patch 545 committed and pushed exactly the approved Settings and History files.

## Patch 546 diagnostic conclusion

The current OAuth registration foundation already provides:

- collision-resistant `pp_mcp_client_...` IDs;
- generated `pp_mcp_secret_...` secrets for confidential clients;
- one-time plaintext secret return;
- hash-only secret persistence;
- strict redirect URI validation;
- fixed OAuth grant/response support;
- secret-free registration audit metadata.

The blocking gap is ownership. `mcp_oauth_clients` has no creator/owner column.
A manual client has no consent or token before first authorization, so current
user ownership cannot be inferred safely.

Existing dynamic registrations must remain nullable. Never backfill ownership
using name, origin, timestamp, row order, connected status, or audit prose.

## Patch 549 required implementation

Patch 549 is a backend foundation patch. It must:

1. Add Alembic `0011_mcp_oauth_client_ownership`.
2. Add nullable `registered_by_user_id` with a named foreign key to `users.id`
   and an index.
3. Keep existing Claude, ChatGPT, and historical dynamic registrations nullable.
4. Add strict Settings request/response schemas.
5. Add protected `POST /api/settings/mcp/oauth-clients`.
6. Set `registered_by_user_id=current_user.id`.
7. Pass `actor_user_id=current_user.id` to registration audit.
8. Enforce:
   - public client → auth method `none`;
   - confidential client → `client_secret_post` or `client_secret_basic`;
   - authorization-code plus refresh-token grants;
   - code response type.
9. Return the generated client ID and one-time confidential secret only from
   the creation response.
10. Never expose plaintext or hashed secrets through GET, logs, audits, History,
    errors, or OpenAPI examples.
11. Add copied-database smoke for ownership, one-time secret, digest-only
    storage, secret absence across database text/JSON columns, validation
    failures, unauthenticated `401`, rollback, migration, and complete
    preservation.
12. Build/deploy, verify Alembic, protected APIs, OpenAPI, complete smoke, and
    unchanged live Claude/ChatGPT/Hermes state.

## Following Chat 20 sequence

- Patch 550: manageable-client list for clients registered by or connected to
  the current user; statuses `registered`, `connected`, and `revoked`.
- `Abandoned` remains deferred until an explicit age threshold is approved.
- Patch 551: browser-test registration form and one-time credential result
  dialog; keep secrets only in component memory.
- Patch 552: browser feedback or exact approved checkpoint.
- Continue profile/security only after manual registration is committed.

## Safety and workflow

- Preserve Claude database client `9` and ChatGPT database client `13`.
- Preserve Hermes Bearer without reveal, rotation, disablement, or replacement.
- Keep MCP write authorization disabled.
- Do not combine manual OAuth registration with profile, REST API key, named
  direct-client, tool-policy, or write-tool implementation.
- Use unique copied-database fixtures and restore exact logical state.
- Browser-test source remains uncommitted until explicit approval.
- Every patch is one downloadable sequential Python file and success ends with
  exactly `Everything PASS`.
