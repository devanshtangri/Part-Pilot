# Patch 583 diagnostic: Password/session backend recovery

`PARTPILOT:DIAGONOSTIC_PASSWORD_SESSION_ADMIN_RECOVERY:V583`

## Verdict

**PASS — the backend implementation remains safe to retry after this diagnostic is inspected.**

Patches 581 and 582 both failed before writes. No application source, database,
deployment, credential, session, inventory, Project, Reservation, or OAuth state
was modified by either failed patch.

## Exact baseline

- HEAD/origin: `de53cdfce779459ea5a78cbdebe95eb6bdf7f437`
- Branch: `main`
- Commit subject: `Finish Chat 20 boundary recovery`
- Deployment image: `sha256:81808e52e783e7a3807ae1af899a1875aff502236cdbfb40448844cc2a6c0dd0`
- Deployment running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0012_user_avatar_id`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Users / sessions / active sessions: `1` / `4` / `4`
- Parts / Projects / Reservations / stock movements: `15` / `8` / `10` / `35`
- Audit rows / app settings: `201` / `17`
- OAuth clients / consents / codes / tokens: `9` / `6` / `6` / `6`

No password hash, bearer token hash, OAuth secret, MCP direct key, or other
credential material is written to this report.

## Failure 1 — Patch 581

Patch 581's preservation validator built its OAuth-client lookup with the public
string `mcp_oauth_clients.client_id` as the dictionary key. However,
`mcp_oauth_consents.client_id`, `mcp_oauth_authorization_codes.client_id`, and
`mcp_oauth_tokens.client_id` are integer foreign keys to `mcp_oauth_clients.id`.

Therefore valid live consent rows were compared across two different identifier
domains and rejected. The live OAuth state was not corrupt; the validator was wrong.

## Failure 2 — Patch 582

Patch 582 corrected the OAuth identifier-domain bug, but its preflight copied the
Patch 577 diagnostic SHA incorrectly:

- actual: `2db9921a95be581cdc39d1ab43da81602ecece8e6bab48245a25c8e1d720f819`
- Patch 582 expected: `2db9921a95be582cdc39d1ab43da81602ecece8e6bab48245a25c8e1d720f819`

The difference is the accidental `...581...` -> `...582...` digit change inside
the SHA literal. Patch 582 therefore failed in preflight before any write.

## Correct OAuth foreign-key contract

- `mcp_oauth_clients.id` is the integer primary key.
- `mcp_oauth_clients.client_id` is the generated public OAuth client identifier.
- consent/code/token `client_id` columns reference the integer primary key.
- Corrected semantic validation passes all `9` clients, `6` consents, `6` codes, and `6` token rows.
- Token-family validation also passes across `4` families.

## Exact auth source state

The committed Chat 20 source is still authoritative. No Patch 581/582 backend
marker or dedicated password/session smoke file exists in the worktree.

Verified existing block/anchor counts:

- `update_user_profile`: `1`
- `hash_session_token`: `1`
- `get_session_by_token`: `1`
- `is_session_active`: `1`
- `logout_session`: `1`
- `revoke_session`: `1`
- `profile_get`: `1`
- `profile_put`: `1`
- `logout_route`: `1`
- `change_password_route`: `0`
- `sessions_get_route`: `0`

Current backend primitives remain:

- profile update service plus protected profile GET/PUT
- password hashing and verification
- session token hashing and lookup
- active-session checks
- logout/single-token revocation

Password/session administration remains absent, so the intended implementation
can still be applied cleanly without reconciling partial source.

## Safe next implementation plan

After this diagnostic passes and the report is inspected, the next sequential patch
may retry the backend implementation. It should:

1. Use the exact Patch 577 diagnostic hash ending in `...581...`.
2. Preserve the corrected OAuth validator keyed by integer `mcp_oauth_clients.id`.
3. Revalidate exact clean HEAD/origin and unchanged auth source hashes before writes.
4. Add password change with current-password verification and password-reuse rejection.
5. Identify the current session from the presented Bearer token and preserve it.
6. Revoke every other active session transactionally on password change.
7. Add safe session listing without bearer tokens or token hashes.
8. Add targeted revocation with ownership checks and current-session rejection.
9. Add revoke-all-other with exact current-session exclusion.
10. Add secret-free password/session audit events.
11. Exercise all mutations only against copied SQLite databases before deployment.
12. Run the complete existing smoke suite, deploy without a migration, preserve live
    data/credentials/sessions, then stage/commit/push only the intended backend files.

## Escalation state

This report satisfies the required diagnostic-first escalation after two consecutive
pre-write failures. No further implementation should be issued until Patch 583
finishes with terminal `Everything PASS` and this report has been inspected.
