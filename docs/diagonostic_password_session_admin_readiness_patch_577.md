# Patch 577 diagnostic: Password and session administration readiness

`PARTPILOT:DIAGONOSTIC_PASSWORD_SESSION_ADMIN_READINESS:V577`

## Verdict

**PASS — password and session administration is ready to begin in Chat 21.**

Patch 576 successfully committed and deployed the current-user profile/avatar backend foundation. Chat 20 has only its mandatory boundary patch remaining, so credential/session mutation is intentionally deferred rather than rushed.

## Exact baseline

- HEAD/origin before this diagnostic: `97b8efc689ef8def21ad67af9e9ffc24908fa73c`
- Branch: `main`
- Deployment image: `sha256:81808e52e783e7a3807ae1af899a1875aff502236cdbfb40448844cc2a6c0dd0`
- Deployment running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0012_user_avatar_id`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Current users: `1`
- Stored sessions: `4`
- Active sessions: `4`
- Existing auth audit events: `0`

No password hash, session token hash, OAuth credential, MCP direct key, or other secret material is included in this report.

## Existing backend primitives

- `users.password_hash` already stores password hashes.
- `hash_password()` and `verify_password()` already exist in the security layer.
- `sessions` already stores user ownership, token hash, expiry, revocation time, user agent, IP address, creation time, and update time.
- Auth service already provides session creation, token hashing, token lookup, active-session checks, single-session logout/revocation, and current-user lookup.
- Protected profile read/update and built-in avatar selection are now committed.
- The current Bearer token can identify the current session by hashing the presented token and matching `sessions.token_hash`; no schema migration is required.

## Missing backend contracts

- No password-change request/response schema.
- No password-change service that verifies the current password.
- No transaction that updates the password hash and revokes all other sessions.
- No safe session-list response schema.
- No protected session-list endpoint.
- No targeted session-revocation endpoint.
- No `revoke all other sessions` endpoint.
- No password/session-specific audit events.

## Required password-change semantics

1. Require the current password and verify it against the stored hash.
2. Require a new password meeting the existing setup minimum and maximum bounds.
3. Reject reuse of the current password.
4. Hash and store the new password only after all validation succeeds.
5. Identify the request's current session from the presented Bearer token.
6. Revoke every other active session by default in the same transaction.
7. Preserve the current session so the user is not unexpectedly logged out.
8. Write one secret-free `auth.password_changed` audit event with the number of other sessions revoked; never store passwords or hashes in audit JSON.

## Required session-list semantics

Return only sessions owned by the authenticated user. Safe fields:

- session database ID
- `is_current`
- `is_active`
- created/updated timestamps
- expiry timestamp
- revoked timestamp
- user-agent string or a bounded display form
- IP address

Never return `token_hash` or any bearer token.

Sort current session first, then other active sessions newest-first, then revoked/expired sessions if retained in the response. The Settings UI may initially show active sessions only while the backend retains history.

## Required revocation semantics

- Targeted revocation must verify `session.user_id == current_user.id`.
- Revoking the current session through the targeted endpoint should be rejected or require an explicit logout flow; do not silently invalidate the request itself.
- `Revoke all other sessions` must exclude the current session by exact session ID.
- Repeated revocation should be idempotent.
- Audit targeted revocation and all-other revocation without token material.

## Frontend gap

The current frontend auth types/client/context have no profile/password/session administration contracts yet. Chat 21 should add typed contracts and an explicit `refreshUser()`/equivalent context action before the Account/Security Settings UI.

## Safe Chat 21 implementation order

1. Password/session backend service, schemas, routes, audit, and copied-database smoke.
2. Frontend auth types/client/AuthContext refresh support.
3. Settings Account/Security browser-test UI for profile, built-in avatars, password change, active sessions, targeted revocation, and revoke-all-other.
4. Browser feedback refinement.
5. Checkpoint/commit the approved UI.
6. Resume scoped REST API keys only after the account/security slice is complete.

## Chat 20 boundary requirement

Patch 578 is the mandatory Chat 20 boundary. It must update durable documentation, record the successful manual OAuth and profile/avatar foundations, carry this password/session readiness contract into the handoff, commit/push, and only then provide the Chat 21 ready-to-paste prompt after terminal `Everything PASS`.
