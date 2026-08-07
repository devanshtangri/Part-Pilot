# Patch 571 diagnostic: Current-user profile and security readiness

`PARTPILOT:DIAGONOSTIC_CURRENT_USER_PROFILE_SECURITY_READINESS:V571`

## Verdict

**PASS — Patch 572 may begin the current-user profile/security foundation.**

Patch 570 completed and pushed the browser-approved manual OAuth registration UI. The locked roadmap now advances to current-user profile, password, session, and built-in-avatar controls.

## Exact baseline

- HEAD/origin before this diagnostic: `36792568571d4b4851ce20d96d16b3b3199b6698`
- Branch: `main`
- Deployment image: `sha256:7f07e5091caac82bca92a230ef7d4c3619ef7d344fea0cb88ebc480d20f4ba2b`
- Deployment running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0011_mcp_oauth_client_ownership`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Existing users: `1`
- Existing sessions: `4`
- Non-revoked sessions at capture: `4`
- Existing owner user ID: `1`
- Existing owner username: `devanshtangri`
- Existing owner display name: `Devansh Tangri`
- Instance-secret fingerprint/size/mode: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b` / `65` / `0o600`
- Restore staging file count: `15`

No password hash, session token hash, OAuth secret, MCP direct key, or other credential material is included in this report.

## Existing auth capabilities

- `users` already stores normalized `username`, `display_name`, `password_hash`, `is_active`, and login timestamps.
- `sessions` already stores server-side session IDs, token hashes, expiry, revocation time, user agent, and IP address.
- Auth service already provides username/display-name normalization, password verification, session creation, token-to-session lookup, active-session checks, and single-session logout.
- Protected `GET /auth/me` already returns current-user identity.
- Login/setup/logout flows already use Bearer session tokens stored by the frontend.
- The frontend AuthContext already owns the current user/token state and is the correct place to refresh identity after profile changes.

## Missing contracts

- No protected profile update endpoint.
- No username/display-name update service with explicit conflict semantics.
- No password-change endpoint requiring the current password.
- No session list endpoint and no targeted/all-other session revocation endpoint.
- No way to identify the current session in a returned session list.
- No `avatar_id` column or built-in avatar catalogue.
- No Settings Account/Profile/Security UI.
- No frontend auth contracts for profile mutation, password mutation, or session administration.

## Security requirements

1. Username changes must reuse the existing lowercase normalization and uniqueness rules; never silently rewrite another user's identity.
2. Password changes must verify the current password before hashing/storing the new password.
3. Password changes should revoke all **other** sessions by default while preserving the current session unless the user explicitly signs out.
4. Session APIs must identify the current session by hashing the presented Bearer token server-side. Token hashes must never be returned to the client.
5. Session list responses may expose only safe metadata: database session ID, current flag, created/updated/expiry/revoked status, user-agent summary, and IP.
6. Targeted revocation must be limited to sessions owned by the current user.
7. `Revoke all other sessions` must preserve the session making the request.
8. Profile/password/session mutations require secret-free audit events attributed to the current user.
9. Existing OAuth grants/tokens, MCP credentials, inventory, Projects, Reservations, backups, and restore staging must remain independent of account preference changes.

## Built-in avatar design

No existing image/avatar assets are present in the frontend. Keep this slice storage-safe by using a small code-defined built-in avatar catalogue rather than uploaded files.

Recommended persistence contract:

- Alembic `0012_user_avatar_id`.
- Nullable or defaulted `users.avatar_id` string with a narrow documented built-in identifier set.
- API validates IDs against the built-in catalogue; arbitrary paths/URLs are rejected.
- Frontend renders the selected built-in avatar from local UI primitives/assets.
- Uploaded avatar storage/cropping remains deferred exactly as the roadmap states.

## Safe remaining Chat 20 sequence

1. **Patch 572:** backend profile foundation — Alembic `0012_user_avatar_id`, built-in avatar catalogue, protected profile read/update service/API, audit, copied-DB smoke, commit/push.
2. **Patch 573:** password + session administration backend — current-password verification, current-session identification, list/revoke one/revoke all other sessions, audit, copied-DB smoke, commit/push.
3. **Patch 574:** frontend typed auth contracts/AuthContext refresh support for profile/password/session APIs, commit/push.
4. **Patch 575:** Settings Account/Security browser-test UI with built-in avatars, profile editing, password change, and session management.
5. **Patch 576:** browser feedback refinement or approved UI checkpoint.
6. **Patch 577:** final Chat 20 documentation/readiness consolidation.
7. **Patch 578:** Chat 20 boundary, durable docs/handoff, commit/push, and next-chat ready prompt only after terminal `Everything PASS`.

MCP writes, REST API keys, named direct clients, and per-client tool policy remain out of this slice.
