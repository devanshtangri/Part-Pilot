# Patch 531 Diagnostic — Abandoned OAuth Row Cleanup

<!-- PARTPILOT:DIAGONOSTIC_ABANDONED_OAUTH_CLEANUP:V531 -->

Generated: `2026-08-06 10:57:55Z`

## Verdict

**PASS — an exact token-free abandoned-row cleanup boundary is proven.**

The live database contains 17 OAuth client registrations. Exactly two
registrations completed authorization and own token families: Claude
client ID 9 and ChatGPT client ID 13. The other 15 registrations own
no token rows and can be removed only through the explicit allowlists
below.

This diagnostic changed no database row, application source, credential,
setting, deployment, or restore artifact.

## Exact baseline

- HEAD/origin: `df17966a7572e6d88661f279077ca4ed1e37c0de`
- Subject: `Normalize History technical acronyms`
- Git working tree/index before report: clean
- Deployment image: `sha256:41374c2471001cc9fcd38438e1a122ae19b0bd4dfc5330e2a1167e4098cdd602`
- Deployment: `running/healthy`, restart `0`
- Alembic: `0010_mcp_trusted_networks`
- Database SHA-256 at inspection: `eae6c6bcf110e4984d046c892302024fd6a73224aa77e706fe9bf5eea6575bfb`
- MCP enabled/read/write: `true/true/false`
- Direct authentication: Hermes Bearer configuration preserved
- Instance secret: exact expected hash, size, and mode `0600`
- Restore staging: safe with no pending operation

## Current OAuth row counts

- Clients: `17`
- Authorization codes: `10`
- Consents: `9`
- Token rows: `3`
- OAuth audit rows: `40`

## Connected rows that must be preserved

- Client `9` — `Claude`, origin `https://claude.ai`, auth `client_secret_post`, codes `9`, consents `8`, token rows `1, 3`
- Client `13` — `ChatGPT`, origin `https://chatgpt.com`, auth `none`, codes `10`, consents `9`, token rows `2`

Preserve exact primary-key allowlists:

- Clients: `9, 13`
- Authorization codes: `9, 10`
- Consents: `8, 9`
- Tokens: `1, 2, 3`

Claude token rows 1 and 3 are one rotation family: row 1 is the revoked
predecessor and points to active row 3. ChatGPT row 2 is active. All
three rows are part of legitimate connected-client history and remain.

## Exact cleanup allowlists

- Client rows: `1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17`
- Authorization-code rows: `1, 2, 3, 4, 5, 6, 7, 8`
- Consent rows: `1, 2, 3, 4, 5, 6, 7`
- Token rows: `(none)`

Candidate clients by label:

- Claude: `1, 2, 3, 7, 8`
- Google: `4, 5, 10, 11, 12, 14, 15, 16, 17`
- ChatGPT: `6`

Every candidate authorization code is unused and expired. No candidate
client has a consumed authorization code, active token, revoked token,
refresh family, or replay record.

## Foreign-key and deletion behavior

- Authorization codes reference clients with `ON DELETE CASCADE`.
- Consents reference clients with `ON DELETE CASCADE`.
- Tokens reference clients with `ON DELETE CASCADE`.
- Token replacement links use `ON DELETE SET NULL`.
- `sqlite_sequence` is not present.

The cleanup implementation should nevertheless delete exact code and
consent IDs first, verify their row counts, then delete exact client IDs.
It must not issue a broad name-, origin-, age-, or token-count-based
DELETE.

## OAuth audit-history preservation

- `mcp.oauth_client_registered`: `17`
- `mcp.oauth_code_issued`: `10`
- `mcp.oauth_consent_granted`: `10`
- `mcp.oauth_tokens_issued`: `2`
- `mcp.oauth_tokens_refreshed`: `1`

All 40 OAuth audit rows must remain untouched. Audit rows are historical
records and are not foreign-key children of operational OAuth rows.
Their summaries and metadata preserve the registration/authorization
history even after exact abandoned operational rows are removed.

## Expected post-cleanup operational state

- OAuth clients: `2`
- OAuth authorization codes: `2`
- OAuth consents: `2`
- OAuth tokens: `3`
- OAuth audit rows: `40`
- Connected clients: Claude ID `9`, ChatGPT ID `13`
- MCP enabled/read/write: `true/true/false`
- Hermes direct Bearer configuration: unchanged

## Safe Patch 532 implementation plan

1. Validate the Patch 531 diagnostic commit as exact HEAD/origin.
2. Revalidate every preserve and cleanup ID plus all child mappings.
3. Fail before writes if any candidate gains a token, consumed code,
   changed relationship, or if a new OAuth registration appears.
4. Create and integrity-check an online SQLite backup.
5. Begin one immediate transaction with foreign keys enabled.
6. Delete only authorization-code IDs `1-8`.
7. Delete only consent IDs `1-7`.
8. Assert no cleanup client owns any token, then delete only client IDs
   `1-8, 10-12, 14-17`.
9. Preserve all OAuth audit rows; do not rewrite their entity IDs.
10. Verify post-cleanup counts `2/2/2/3`, integrity and foreign keys.
11. Verify active Claude and ChatGPT authorize pages and read-only
    connection semantics, Hermes Bearer state, MCP write-disabled state,
    protected application data, deployment, secret, and restore staging.
12. Restore the exact database backup on any failure before commit.

## Conclusion

Patch 532 may safely remove only the exact token-free abandoned rows
listed above. No application-source change is required for cleanup.
