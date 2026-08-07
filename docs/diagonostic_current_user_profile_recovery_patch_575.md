# Patch 574 diagnostic: Current-user profile recovery

`PARTPILOT:DIAGONOSTIC_CURRENT_USER_PROFILE_RECOVERY:V575`

## Verdict

**PASS — Patch 576 may retry the same current-user profile backend foundation.**

Patches 572 and 573 both failed before source writes. The application, database, migration level, deployment, owner account, sessions, and credentials remain at the exact Patch 571 baseline.

## Exact baseline

- HEAD/origin before this diagnostic: `842a255e78e2030801e3e8383a82e997cd36175d`
- Branch: `main`
- Deployment image: `sha256:7f07e5091caac82bca92a230ef7d4c3619ef7d344fea0cb88ebc480d20f4ba2b`
- Deployment running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0011_mcp_oauth_client_ownership`
- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Existing users: `1`
- Existing sessions: `4`
- Active sessions: `4`
- `users.avatar_id`: absent, proving neither failed implementation wrote the migration.

## Patch 572 failure

Patch 572 failed in memory because its candidate validator required every generated file to end with exactly one newline, while the committed baseline `backend/app/schemas/auth.py` already ended with two newlines.

- Baseline auth schema ends with two newlines: `True`
- Patch 572 script SHA-256: `b68d1127e5b235fec568486355be4dbb73a778cf71f12dfd02ee86b65a7167af`
- Patch 572 internal log SHA-256: `9a5039cdd25bf9837c784e62ea2a7a4062c1d60f1a96d19db0d2a351f0c047fd`
- No writes, migration, build, deployment, commit, or push occurred.

Patch 573 correctly fixed this by canonicalizing every generated candidate after all semantic transforms with `rstrip(CR/LF) + one newline`.

## Patch 573 failure

Patch 573 then failed on a second validator mistake. Its semantic-check loop used one blanket rule: every listed marker must occur exactly once.

For `backend/app/services/auth.py`, it listed the broad symbol `BUILTIN_AVATAR_IDS`. The exact generated candidate legitimately contains it twice:

- catalogue definition: `1`
- membership-validation use: `1`
- total `BUILTIN_AVATAR_IDS` references in auth service: `2`

Therefore the generated service was correct and the `count == 1` assertion was wrong.

- Patch 573 script SHA-256: `f772ba2d7f58c26dd1a1216044761369aba9af17755e16dd2f09b148854f5733`
- Patch 573 internal log SHA-256: `48bb6672e42696b38619986427a81b7d78409c04e3eac42bf4ce3bd0f5a51fc6`
- No writes, migration, build, deployment, commit, or push occurred.

## Patch 574 diagnostic recovery failure

Patch 574 was the mandatory diagnostic escalation, but the diagnostic script itself failed at Python parsing before any preflight or inspection logic ran.

- Patch 574 script SHA-256: `c2fc701b183e307f4139c101f92f79115fa435447cfc633c649c1c41cc6e6589`
- Failure class: Python `SyntaxError` in an f-string expression containing a backslash escape.
- Failure line: `442`.
- No diagnostic report, source write, database write, deployment, commit, or push occurred.

Patch 575 fixes only the diagnostic script construction by precomputing the newline boolean outside the f-string. The underlying candidate inspection remains unchanged.

## Exact generated candidate evidence

- `backend/alembic/versions/0012_user_avatar_id.py` — SHA-256 `360689c52b28844e421f1210c7f7913e72232c31e14f330e2f279a7f4a63dc98`, 61 lines, syntax/AST PASS, canonical EOF
- `backend/app/api/routes/auth.py` — SHA-256 `a940e13b30b0b89c7e768c3a3d652497255379f0aba59f5cd1bbb04c212c1627`, 288 lines, syntax/AST PASS, canonical EOF
- `backend/app/db/user_profile_smoke_test.py` — SHA-256 `1eae5f78abad57c9ebcf5a1812a769b024c670acc61734a7d6b875d873bdce6d`, 340 lines, syntax/AST PASS, canonical EOF
- `backend/app/models/core.py` — SHA-256 `6da28c4345399467ed40af45da8de6ba0da73682f70f9f7a5c30c7ed0575dfd0`, 808 lines, syntax/AST PASS, canonical EOF
- `backend/app/schemas/auth.py` — SHA-256 `7f3517492c987e3386604436d4a6a3ec85dbe8d3987536981e82b6a8a6f85f7e`, 121 lines, syntax/AST PASS, canonical EOF
- `backend/app/services/auth.py` — SHA-256 `3682792306e14f1dfe9bd25bb2bd8b0f65959190ad8d0280683ff6520dd0801b`, 300 lines, syntax/AST PASS, canonical EOF

Additional semantic counts:

- profile service function: `1`
- profile audit event: `1`
- route catalogue references: `2`
- GET `/profile`: `1`
- PUT `/profile`: `1`
- profile response avatar mapping: `1`
- profile update schema: `1`
- profile response schema: `1`
- built-in avatar literal type: `1`
- model avatar column: `1`
- Alembic 0012 revision marker: `1`
- profile smoke marker: `1`

All six exact generated Python candidates compile and parse successfully.

## Safe Patch 576 recovery plan

1. Start from the exact clean Patch 571 application baseline and the new Patch 574 diagnostic commit.
2. Rebuild the same six-file backend profile foundation only: model, auth service, auth schemas, auth routes, Alembic `0012_user_avatar_id`, and profile smoke test.
3. Preserve Patch 573's post-transform EOF canonicalization.
4. Replace the blanket `marker count == 1` loop with explicit expected counts per semantic marker, or use narrower markers such as the catalogue definition and membership-validation expression independently.
5. Validate every transformed file in memory, lock its SHA-256, compile/AST parse every Python candidate, and only then back up/write.
6. Run copied-database migration, profile API smoke, downgrade/re-upgrade, complete smoke, live migration/deployment, protected API/OpenAPI checks, and preservation checks.
7. Do not change the live username, display name, password, or any session.
8. Keep password/session administration out of Patch 576.

## Remaining Chat 20 boundary plan

Because Patches 572-575 were consumed by two pre-write implementation failures and their diagnostic recovery, Chat 20 now has Patches 576-578 remaining.

- Patch 576: recover and commit the backend profile/avatar foundation.
- Patch 577: password/session backend readiness or implementation checkpoint, depending on Patch 576 stability and remaining boundary risk.
- Patch 578: mandatory Chat 20 boundary and handoff. Remaining Account/Security backend/frontend work continues in Chat 21 rather than violating the boundary.

No REST API keys, named direct clients, MCP tool policy, or MCP writes should be started before the boundary.
