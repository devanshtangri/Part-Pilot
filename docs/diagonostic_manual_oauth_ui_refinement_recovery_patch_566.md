# Patch 566 diagnostic: Manual OAuth UI refinement recovery

`PARTPILOT:DIAGONOSTIC_MANUAL_OAUTH_UI_REFINEMENT_RECOVERY:V566`

## Verdict

**PASS — Patch 567 may resume the same narrow browser-test refinement.**

The pending application source is still the exact browser-approved/tested Patch 563 source. Patches 564 and 565 did not establish a source defect. Both failures were verifier/preflight mistakes.

## Exact repository state

- Branch: `main`
- Baseline HEAD before this diagnostic: `55ce1b6806dca1a003b21e8e022038ab7b302138`
- `origin/main` before this diagnostic: `55ce1b6806dca1a003b21e8e022038ab7b302138`
- Pending `Settings.tsx` SHA-256: `5628562d2b8bed5a8154c9233e671862918630b36524c66c08eaa0d60dfd1226`
- Pending `Settings.css` SHA-256: `eb5173cdf7d74c0a7673b14d5e6553268b695ac193c3a454733665e53dce1e29`
- Git index: clean; only the two Settings browser-test files are modified.
- Deployment image: `sha256:7dfec98f418980756e4a4b1228797e3347b366095b8972e6500e0e1d7d17da93`
- Deployment running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0011_mcp_oauth_client_ownership`
- SQLite integrity: `ok`
- Foreign-key violations: `0`

## OAuth and credential preservation

- Claude client ID 9 remains connected, unrevoked, and unowned by manual registration.
- ChatGPT client ID 13 remains connected, unrevoked, and unowned by manual registration.
- Browser fixture ID 14 (`PP563 Browser Test`) remains revoked and owned by user 1.
- Hermes direct authentication remains `bearer_key` with digest and encrypted ciphertext present.
- Instance-secret fingerprint/size/mode: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b` / `65` / `0o600`.
- Restore staging file count: `15`.

## Patch 564 failure diagnosis

Patch 564 successfully transformed the intended pending UI, passed source validation, built the complete frontend/backend image, ran copied-database smoke, deployed the candidate, and reached browser-asset verification.

Its verifier then required the literal CSS comment `PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_STYLES:V564` in the minified deployed asset. Vite strips that comment, so the assertion was invalid.

Exact Patch 564 script mentions of that CSS comment literal: `2`.

### Candidate-image proof

- Candidate image: `partpilot:patch-564-browser-candidate`
- Candidate image ID: `sha256:995f8ab8baf64d5c1297c216407184e21012036f14f58ab4d9b571edee9aa6a5`
- V564 UI marker occurrences in minified JS: `2`
- Hidden-revoked empty-state text occurrences: `1`
- Removed count-badge class occurrences in minified JS: `0`
- Stripped CSS comment occurrences: `0`
- Minifier-safe CSS custom property occurrences: `1`
- Equal-height `height:38px;min-height:38px` occurrences: `1`

This proves the intended 564 UI refinement compiled: revoked clients were filtered from the normal list, the client-count badge was removed, and the desktop summary height rule was emitted.

## Patch 565 failure diagnosis

Patch 565 failed before source writes because its preflight searched the Patch 564 internal log file for the terminal failure sentence. The patch framework logs commands and phase notes, while the final failure summary is printed to the terminal. Therefore the terminal sentence is not present in that log.

- Patch 565 terminal-log expectation occurrences in its script: `1`
- Patch 564 internal log contains the terminal-only 564 failure sentence: `0`
- Patch 565 internal log contains its own terminal-only exception sentence: `0`

This is the same evidence-class mistake previously identified in Chat 20: **do not require terminal-only failure text to exist inside a patch log.**

## Safe Patch 567 plan

1. Start from the exact pending Patch 563 `Settings.tsx` and `Settings.css` hashes above.
2. Apply only the already-requested three refinements: remove the client-count badge; hide revoked clients from the normal list while retaining their DB/audit records; equalize the confidential/public summary height with the token-auth control on desktop.
3. Preserve mobile wrapping for the summary text.
4. Do not create a new OAuth fixture; keep revoked fixture ID 14 unchanged.
5. Validate source anchors and `git diff --check` before writes/build.
6. Build and run copied-database smoke exactly as before.
7. Verify deployed JavaScript using stable rendered strings/data markers, not local minified variable names.
8. Verify deployed CSS using the minifier-safe custom property `--partpilot-mcp-oauth-manual-registration-v567:1` and semantic CSS output, never comments.
9. Do not search any patch log for a terminal-only failure sentence. Evidence may use exact script hashes, log hashes, source structure, deployment state, candidate assets, and database semantics.
10. Keep the two Settings files unstaged/uncommitted for browser approval.

## Diagnostic conclusion

No backend, schema, OAuth credential, inventory, Project, Reservation, restore-staging, or committed-source recovery is required. The next patch may retry only the frontend browser refinement described above.
