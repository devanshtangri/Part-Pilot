# Patch 539 Diagnostic — OAuth Client Administration Smoke Recovery

<!-- PARTPILOT:DIAGONOSTIC_OAUTH_CLIENT_ADMIN_SMOKE_RECOVERY:V539 -->

Generated: `2026-08-06 13:16:45Z`

## Verdict

**PASS — Patch 537 and Patch 538 failed for two independent test/
evidence defects. The repository and runtime remain clean. Patch 540
may retry the same read-only administration foundation only with both
defects removed and without adding revocation.**

## Exact baseline

- HEAD/origin: `22956ab3579fbb314d3a96d28e79934ca6106096`
- Subject: `Recover OAuth administration diagnostic`
- Working tree: clean
- Index: empty
- New administration smoke file: absent
- Deployment image: `sha256:41374c2471001cc9fcd38438e1a122ae19b0bd4dfc5330e2a1167e4098cdd602`
- Deployment: `running/healthy`, restart `0`
- Alembic: `0010_mcp_trusted_networks`
- Database SHA-256 at inspection: `d3391a8e2de66bd32fd8c9b9c17290e57bb78bb4712e47629f075377e8b9d038`

## Restored source hashes

- `backend/app/schemas/app_settings.py`: `fbedc504006ac2f16e774fafcda50873fe02f7e062353e58320a56b482524e32`
- `backend/app/services/mcp_oauth.py`: `c99b36f95ae1c0a1f413a9905f7d85377449b256397df2aaa636008510b1af51`
- `backend/app/api/routes/app_settings.py`: `5cbf3933ce75349f85f64ed194843d035095ee5cec83da2adc4e2d16c7489824`
- `frontend/src/types/settings.ts`: `644472539b51827090a2d69ba11a14655b35f3194a5a623ef5b3d745084e484c`
- `frontend/src/services/settingsClient.ts`: `b377a503bbe7bd1476f5226570724de1c2b200109bc87c50b89f832002c03e42`

## Failure 1 — Patch 537 smoke false positive

Patch 537's copied-database smoke serialized the full response and
looked for the generic substring `client_secret`. The same expected
payload legitimately contains the OAuth authentication-method value
`client_secret_post`. Therefore the generic substring matched a safe
enumerated value and produced a false leak failure.

- Generic substring anchors in script: `1`
- Legitimate value anchors in script: `3`
- Exact smoke command occurrences in log: `1`
- Exact false-positive failure occurrences: `1`

Patch 540 must validate the exact response key set, not scan all JSON
values for partial secret-like words. It may separately reject complete
callback paths and unexpected response fields.

## Failure 2 — Patch 538 persistent-log mismatch

Patch 538 never reached source write, build, or smoke. Its baseline
validator required the invented phrase:

```text
candidate smoke app.db.mcp_oauth_admin_smoke_test
```

The Patch 537 persistent log does not record phase labels. It records
the actual command, which ends with:

```text
python -m app.db.mcp_oauth_admin_smoke_test
```

- Invented phrase anchors in Patch 538 script: `1`
- Invented phrase present in Patch 537 log: `False`
- Exact smoke command present in Patch 537 log: `True`

Patch 540 must not validate prose labels from prior logs. The committed
Patch 539 diagnostic, exact script/log hashes, exact restored source
hashes, clean Git state, and absent smoke file are sufficient.

## Current OAuth state — rotation-safe

- Client `9` — `Claude`, origin `https://claude.ai`, auth `client_secret_post`, active consents `1`, active tokens `1`, token families `1`, historical token rows `3`
- Client `13` — `ChatGPT`, origin `https://chatgpt.com`, auth `none`, active consents `1`, active tokens `1`, token families `1`, historical token rows `1`
- Authorization-code IDs: `[9, 10]`
- Consent IDs: `[8, 9]`
- Refresh audit count at inspection: `2`
- MCP enabled/read/write: `true/true/false`
- Hermes direct Bearer configuration: preserved

Historical token rows, token IDs, last-used timestamps, database SHA,
and refresh-audit count remain volatile. Patch 540 must validate only
the stable one-client/one-consent/one-active-token/one-family contract.

## Safe Patch 540 implementation plan

1. Require the committed Patch 539 report as exact HEAD/origin.
2. Validate exact restored source hashes and absence of the smoke file.
3. Do not parse Patch 537/538 logs for descriptive phase prose.
4. Build all six candidates in memory and run no-index diff checks.
5. Preserve the corrected single-final-newline service transform.
6. Replace generic serialized-substring leak checks with exact top-level
   and per-client response-field allowlists.
7. Add explicit regression cases:
   - accept `client_secret_post`;
   - reject an unexpected `client_secret_hash` field;
   - reject complete callback paths.
8. Compile Python candidates before any write.
9. Write exactly the six read-only foundation files and immediately run
   `git diff --check` before building.
10. Build and run administration, OAuth HTTP, and complete copied-DB
    smoke tests.
11. Deploy and verify unauthenticated `401`, GET-only OpenAPI, no-store
    headers, safe origins, and no secret/token transport fields.
12. Stage, commit, and push exactly the six files.
13. Keep OAuth revocation out of Patch 540.

## Conclusion

Patch 540 may retry the same read-only connected OAuth client
administration foundation with exact response-field validation and no
brittle prior-log prose assertions.
