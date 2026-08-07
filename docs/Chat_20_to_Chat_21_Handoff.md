# Chat 20 to Chat 21 Handoff

<!-- PARTPILOT:CHAT20_TO_CHAT21_HANDOFF:V580 -->

## Next chat identity

- Title: `Chat 21: Account Security and Session Administration`
- Patch range: `581-610`
- First patch: `581`
- Planned boundary: `610`
- Start by inspecting this handoff, `docs/Checkpoint.md`,
  `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`,
  `README.md`, and
  `docs/diagonostic_password_session_admin_readiness_patch_577.md`.

Do not create a `Chat_21_Starting_Prompt.md` file.

## Exact pre-boundary state

- Branch: `main`
- Pre-boundary HEAD/origin: `fb5e0275f643a4420914c35093a0afb3f898c6a3`
- Latest subject: `Diagnose password and session administration readiness`
- Git/index: clean
- Deployment image: `sha256:81808e52e783e7a3807ae1af899a1875aff502236cdbfb40448844cc2a6c0dd0`
- Deployment: running, healthy, restart count `0`
- Alembic: `0012_user_avatar_id`
- Database SHA-256: `d010f1e4bc14333a3d32071220f7c742242a2ebc81fb9c62373e7ae450f258ea`
- Database size: `741376` bytes
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Parts: `15`
- Projects: `8`
- Reservations: `10`
- Stock movements: `35`
- Audits: `201`
- Users: `1`
- Sessions: `4`; active: `4`
- Current owner: ID `1`, `devanshtangri`, display name `Devansh Tangri`,
  avatar `initials`
- MCP enabled/read/write: `true/true/false`
- Direct auth: `bearer_key`; digest and ciphertext present
- Instance-secret SHA-256: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Restore staging: `15` files, fingerprint `6712ba4090860b1ebb77962a343549fa5fd33b45f035fd3bae4cacc4cac1a543`

## Important source hashes

- Settings.tsx:
  `bf68c35cc7bce92a098fecf0a6247d1924f6024ce8677674174cf2cd9b4629ca`
- Settings.css:
  `0df5fb34b53db7b3ca986c4d2cfde505ff7abcc0772f52f83dbb4c12141f0d63`
- auth model:
  `6da28c4345399467ed40af45da8de6ba0da73682f70f9f7a5c30c7ed0575dfd0`
- auth service:
  `3682792306e14f1dfe9bd25bb2bd8b0f65959190ad8d0280683ff6520dd0801b`
- auth schemas:
  `7f3517492c987e3386604436d4a6a3ec85dbe8d3987536981e82b6a8a6f85f7e`
- auth routes:
  `a940e13b30b0b89c7e768c3a3d652497255379f0aba59f5cd1bbb04c212c1627`
- Alembic 0012:
  `360689c52b28844e421f1210c7f7913e72232c31e14f330e2f279a7f4a63dc98`
- profile smoke:
  `1eae5f78abad57c9ebcf5a1812a769b024c670acc61734a7d6b875d873bdce6d`
- Patch 577 diagnostic:
  `2db9921a95be581cdc39d1ab43da81602ecece8e6bab48245a25c8e1d720f819`

## Chat 20 completed work

### Manual OAuth registration

- Alembic `0011_mcp_oauth_client_ownership` adds nullable
  `registered_by_user_id`; no ownership was inferred for historical dynamic
  registrations.
- Protected manual registration accepts client name, redirect URI(s),
  public/confidential client type and compatible token auth.
- Public uses `none`; confidential supports `client_secret_post` and
  `client_secret_basic`.
- Client IDs are generated; confidential secrets are returned once and only
  their digest is stored.
- Manageable-client API returns only clients owned by or related to the current
  user, with registered/connected/revoked semantics.
- Current-user-owned registered clients can be revoked even before first
  authorization.
- Settings has the browser-approved manual registration UI, one-time credential
  dialog, Show/Hide/Copy controls, submit-attempt validation and exact
  registered/connected revocation.
- Revoked clients are hidden in the normal Settings list without deleting
  backend audit/manageable history.
- Patch 570 cleaned only the exact PP563 browser fixture client `14` and audit
  rows `178/179`; unrelated historical audit row `156` was preserved.

### External-client observations

- Manual Claude registration works with callback
  `https://claude.ai/api/mcp/auth_callback`, confidential client type and
  `client_secret_post`.
- OAuth consent is still expected for manually registered clients; the client
  secret authenticates the client and does not replace user authorization.
- Gemini/Google DCR successfully reached Part Pilot consent and authorization
  code issuance, but Google did not redeem the code. Do not alter Part Pilot's
  OAuth security contract merely to compensate for that external callback
  behavior.

### Current-user profile backend

- Alembic `0012_user_avatar_id`.
- Built-in avatar IDs: `initials`, `chip`, `circuit`, `terminal`, `storage`,
  `rocket`.
- Protected `GET /api/auth/profile`.
- Protected `PUT /api/auth/profile`.
- Username normalization and uniqueness.
- Display-name and avatar validation.
- `/api/auth/me` now returns `avatar_id`.
- Secret-free `auth.profile_updated` audit.
- Profile smoke verifies validation, conflict handling, audit, `/auth/me`
  refresh, password/session preservation and exact copied-DB restoration.
- Live owner profile was not changed by implementation; all four existing
  sessions remain active.

## Live OAuth operational summary

- DB client `9` — `Claude`; owner `NULL`; auth `client_secret_post`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `13` — `ChatGPT`; owner `NULL`; auth `none`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `15` — `Gemini`; owner `1`; auth `none`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `16` — `Gemini`; owner `1`; auth `client_secret_post`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `17` — `Google`; owner `NULL`; auth `client_secret_post`; active registration; active consents `1`; unrevoked token rows `0`; token families `0`.
- DB client `18` — `Claude`; owner `NULL`; auth `client_secret_post`; active registration; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `19` — `Claude`; owner `NULL`; auth `client_secret_post`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `20` — `Claude`; owner `1`; auth `client_secret_post`; revoked; active consents `0`; unrevoked token rows `0`; token families `0`.
- DB client `21` — `Claude`; owner `1`; auth `client_secret_post`; active registration; active consents `1`; unrevoked token rows `1`; token families `1`.

The operational token/code rows above are a boundary snapshot only. OAuth
clients can rotate or expire token rows during normal use. Validate active
consent, revocation, ownership and token-family semantics rather than requiring
these transient row counts to remain fixed.

## Recovery history that matters

- Patch 572 failed before writes because the committed auth schema already had
  a double-newline EOF and the candidate validator required exactly one.
- Patch 573 fixed EOF canonicalization but failed before writes because it
  required every semantic marker to occur exactly once; the generated auth
  service intentionally referenced `BUILTIN_AVATAR_IDS` twice.
- Patch 574, the first mandatory diagnostic, was consumed by a Python f-string
  syntax error before any code ran.
- Patch 575 successfully diagnosed the exact six generated candidates, hashes,
  syntax and explicit semantic counts.
- Patch 576 rebuilt that exact candidate using per-marker expected counts and
  succeeded.
- Patch 577 intentionally stopped before password/session mutation because
  Chat 20 had only the boundary patch left.

Carry these rules forward:
- Canonicalize generated EOFs after transforms.
- Validate broad symbols with explicit expected counts or narrower semantic
  markers, never blanket `count == 1`.
- Compile the final downloadable patch before delivery.
- Internal logs do not necessarily contain terminal-only final failure prose.

## Patch 577 password/session contract

No password/session administration APIs exist yet. Existing primitives already
support password hash/verify, session creation, token hashing, token lookup,
active-session checks and single-session logout.

Patch 581 should implement:

1. Password-change schema/service/route requiring current password.
2. Reject reuse of the current password.
3. Identify the current session from the presented Bearer token by hashing it;
   never expose `token_hash`.
4. Change password and revoke every other active session in one transaction,
   preserving the current session.
5. Secret-free `auth.password_changed` audit with revoked-session count.
6. Safe session-list schema/API returning session ID, current/active flags,
   timestamps, user agent and IP only.
7. Targeted revocation scoped to `session.user_id == current_user.id`.
8. `Revoke all other sessions` excluding the exact current session.
9. Idempotent revocation and secret-free audit.
10. Copied-database smoke with exact restoration and preservation of unrelated
    inventory/OAuth/MCP state.

After the backend is stable:
- add frontend auth types/client methods;
- add an explicit `refreshUser()` or equivalent AuthContext action;
- build the Account/Security Settings browser-test UI;
- keep browser source uncommitted until approval;
- checkpoint promptly after approval.

## Deferred work

Do not combine Patch 581 with:
- scoped REST API keys;
- named direct clients/no-auth mode;
- global/per-client MCP tool policy;
- multi-user roles;
- inventory-mutating MCP writes.

MCP write authorization must remain disabled until the permission model and
safeguarded write-tool contracts are complete.
