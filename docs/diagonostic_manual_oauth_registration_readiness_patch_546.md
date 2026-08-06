# Patch 546 Diagnostic — Manual OAuth Registration Readiness

<!-- PARTPILOT:DIAGONOSTIC_MANUAL_OAUTH_REGISTRATION_READINESS:V546 -->

Generated: `2026-08-06 15:58:27Z`

## Verdict

**PASS — the existing OAuth service already provides secure opaque
client IDs, one-time plaintext client-secret return, hash-only secret
storage, redirect validation, and registration auditing. Manual
registration must not be added directly to Settings yet because
registered-but-not-connected clients have no current-user ownership
field. Patch 548 must begin with an ownership migration and protected
backend contract before any browser UI.**

## Exact baseline

- HEAD/origin: `55ea9bf19c5c306fae2d66365d4fc10cb95007bd`
- Subject: `Add OAuth client Settings UI and normalize History labels`
- Working tree: clean
- Index: empty
- Deployment image: `sha256:d601fea120915e2cdfec4d1da166c95f5afc78f5e257d7b0bce5d6ddd9075207`
- Deployment: `running/healthy`, restart `0`
- Alembic: `0010_mcp_trusted_networks`
- Database SHA-256 at inspection: `f9054b3a15806c0ec6e12150792b59c3b3a1dc4a5e16727cec4249f2802bb057`

## Source hashes inspected

- `backend/app/models/core.py`: `56c4f76497eacf8d5bdc7924c3a1d562ad5277c3bbd8cdf4b299541fdf9a4f28`
- `backend/alembic/versions/0008_mcp_oauth.py`: `c2cee34a6a2c155b79e659a6c5ef88039788c32f6bd9969858789d849d71cb76`
- `backend/app/services/mcp_oauth.py`: `d0f46c56923b38fcd7c80c9610c073963561538fc967bbf4e8d36fa57b792824`
- `backend/app/api/routes/mcp_oauth.py`: `09ae198f1d1df39dadf22b69cfadb794dc84ad8df88b48fa75d502d244b1cf3c`
- `backend/app/api/routes/app_settings.py`: `1561bc9d90ff29f828f1e63f0d6364a9d72a0a85e52852104478d1798972f38a`
- `backend/app/schemas/app_settings.py`: `03079a92a315b4f175d623b7d18ab79a5ab32bac26bbfe2573359ca4194cc032`
- `backend/app/schemas/mcp_oauth.py`: `251825dba4b3fd04bc6deb24af3e9a3613b7f006419faf1746dbb5a51769c3c9`
- `backend/app/db/mcp_oauth_http_smoke_test.py`: `b0525f05880d7e0428daeea2e3f12656ddcc7f8019316e5d5d2a96fd7a870aa2`
- `backend/app/db/mcp_oauth_admin_smoke_test.py`: `b8684e37a5a951827e0e1e8ee2e9eafd5362fd4bec6e00a64df86f40f2d2aa71`
- `frontend/src/pages/Settings.tsx`: `e6b3be4f68fa5aaddbd81ece398452d43037a24a6c384f749d4e3b1c2e10db90`
- `frontend/src/pages/Settings.css`: `e4884e51233d644f6f3d41bf3bc1e63ea012a2a813eb433fba5bdb39cfcd81d7`
- `frontend/src/services/settingsClient.ts`: `6272f9bab6a1267b04106e9060c62a5b0573338dda6a23370b87bce18fb71e3a`
- `frontend/src/types/settings.ts`: `73e51010b6180f3b9df096e7feb8c482223eabfa2dded07d1f4ecc7e2c3cfd94`

## Existing reusable OAuth registration foundation

- `register_client()` generates `pp_mcp_client_...` identifiers.
- Confidential clients receive a generated `pp_mcp_secret_...` value.
- Only the SHA-256 digest of the high-entropy secret is stored.
- The plaintext secret is returned by the service result only at
  creation time.
- Redirect URIs require HTTPS, except loopback HTTP for local native
  clients; user information and fragments are rejected.
- Grant and response types are normalized and restricted.
- Registration appends `mcp.oauth_client_registered` audit history.
- The public `/oauth/register` route already supports dynamic client
  registration and no-store responses.

## Blocking ownership gap

The `mcp_oauth_clients` model and migration contain no
`registered_by_user_id`, `created_by_user_id`, or `owner_user_id`
column. Connected clients can currently be scoped through their active
consent and token rows. A newly registered manual client has neither.
Therefore a Settings list, reveal, revoke, or edit action cannot safely
prove which user owns an unconnected registration.

Existing dynamic registrations are audited as `system` with no
`actor_user_id`. The current registration service already accepts an
optional user actor, but the public dynamic route intentionally does
not pass one.

## Current live state

- Client `9` — `Claude`, origin `https://claude.ai`, auth `client_secret_post`, active consents `1`, active tokens `1`, token families `1`
- Client `13` — `ChatGPT`, origin `https://chatgpt.com`, auth `none`, active consents `1`, active tokens `1`, token families `1`
- Historical registration audit rows: `17`
- Registration audit actor types: `['system']`
- Registration audit user IDs: `[]`
- OAuth revocation audits: `0`
- MCP enabled/read/write: `true/true/false`
- Hermes direct Bearer configuration: preserved

## Required backend design

### Migration and ownership

1. Add Alembic `0011_mcp_oauth_client_ownership`.
2. Add nullable `registered_by_user_id` on `mcp_oauth_clients` with a
   named foreign key to `users.id` and an index.
3. Keep existing dynamically registered clients nullable; do not infer
   ownership from names, callback origins, dates, or audit text.
4. Manual Settings registration must set the authenticated user ID.
5. Connected existing clients remain current-user scoped through active
   consent/token ownership until a separately verified backfill is
   designed.

### Protected Settings API

Add `POST /api/settings/mcp/oauth-clients` with no-store headers.
The request contains:

- `client_name`
- one to twenty exact `redirect_uris`
- `client_type`: `public` or `confidential`
- `token_endpoint_auth_method`

Validation rules:

- Public clients must use `none`.
- Confidential clients must use `client_secret_post` or
  `client_secret_basic`.
- Grant types are fixed to authorization code plus refresh token.
- Response type is fixed to code.
- The service receives `actor_user_id=current_user.id` and manual
  registration metadata.

The creation response returns the database ID, generated client ID,
one-time client secret when confidential, redirect URIs, type,
authentication method, and creation time. No GET endpoint may return
the plaintext secret.

## Administration-list requirement

The current GET response is connected-only. Manual registration would
disappear after the one-time result dialog unless the administration
list is extended. The next backend slices must expose only clients that
the current user may manage:

- clients registered by that user; or
- clients connected to that user through active consent/token rows.

Initial statuses may be derived as `registered`, `connected`, and
`revoked`. `Abandoned` requires a separately documented age threshold
and must not be inferred by broad cleanup logic.

## One-time secret UI contract

- Keep the secret only in component memory.
- Never write it to local storage, session storage, URLs, logs, audit
  metadata, History details, screenshots, or error messages.
- Show the client ID and secret in a dedicated completion dialog.
- Provide Show/Hide and Copy controls.
- Warn that the secret cannot be retrieved after closing.
- Require explicit acknowledgement before closing a confidential-client
  result if the secret has not been copied.
- Public clients show no secret field.

## Copied-database smoke contract

1. Create one public and one confidential manual client in an isolated
   database copy.
2. Verify ownership is the authenticated test user.
3. Verify the audit actor is that user.
4. Verify the confidential plaintext secret is returned once and only
   its digest exists at rest.
5. Verify the plaintext secret is absent from every database text/JSON
   column and from subsequent list responses.
6. Verify public/auth-method mismatch and confidential/auth-method
   mismatch are rejected without partial rows.
7. Verify invalid redirect URIs are rejected.
8. Verify unauthenticated POST returns `401`.
9. Verify existing Claude, ChatGPT, and Hermes state is unchanged.
10. Restore the copied database and prove complete logical equality.

## Safe Chat 20 implementation sequence

1. Patch 548 — migration, model ownership, protected registration
   schemas/service/POST API, and copied-database backend smoke.
2. Patch 549 — current-user manageable-client list with
   registered/connected/revoked status and exact ownership tests.
3. Patch 550 — Settings registration dialog and one-time credential
   result UI as an uncommitted browser-test patch.
4. Patch 551 — browser feedback or approved checkpoint.
5. Continue profile/security only after manual registration is
   committed and pushed.

## Boundary decision

Patch 547 must update durable documentation and create the Chat 19 to
Chat 20 handoff. It must not begin application implementation. Chat 20
starts at Patch 548. The planned 30-patch boundary is Patch 577.

## Conclusion

Manual OAuth registration is technically feasible with substantial
reuse, but secure current-user administration requires explicit client
ownership first. The next implementation must not infer ownership from
client names, redirect origins, audit prose, timestamps, or connected
row order.
