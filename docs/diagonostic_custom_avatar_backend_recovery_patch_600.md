<!-- PARTPILOT:DIAGONOSTIC_CUSTOM_AVATAR_BACKEND_RECOVERY:V600 -->
# Patch 600 custom-avatar backend recovery diagnostic

## Verdict

**PASS — implementation may resume at Patch 601 using the corrected exact
ten-file candidate.**

This diagnostic was required because Patches 598 and 599 were two consecutive
pre-write failures. Patch 600 does not modify application source, deployment,
database contents, credentials, restore staging, or the pending Account UI.

## Exact baseline

- HEAD/origin: `b387802d5aa10e2259f720a0447f9b76710e8661`
- Commit: `Repair backup restore current schema compatibility`
- Deployment image: `sha256:599071cff163adf92551f91528c41ad600f180db41dfc61d696f625949892e5f`
- Alembic: `0012_user_avatar_id`
- SQLite integrity: `ok`
- Foreign-key violations: none
- Users: `1`
- Sessions: `4` stored / `4` active
- Parts: `15`
- Projects: `8`
- Reservations: `10`
- Stock movements: `35`
- Audit rows at diagnostic start: `203`
- App settings: `17`

## Pending Account browser-test source

These files remain byte-identical and uncommitted:

- `70060d60b64ad1f506dff8b5f117ffb3dbea5a4830425338695f5b634d329422` — `frontend/src/app/AppLayout.tsx`
- `52c60658d3db75d6b176ca68fb05e4d63284721024c87c91eda28b8246e328aa` — `frontend/src/pages/Settings.tsx`
- `57d51e6f5c790bdbd476f8df01536610283d47f2ba73c41705b23f7ad36d781c` — `frontend/src/pages/Settings.css`
- `7a5c950dfc16c52c9b87d8034d9ee0fcfa32e54d2d0f7ecca6d1447cbeb29333` — `frontend/src/styles/global.css`
- `70a48f60cbd0c84a1f243c0810e4514562b32eac1d81c76c6b206df0294d1f3d` — `frontend/src/components/UserAvatar.tsx`

## Patch 598 failure

Patch 598 failed before writes because the packaged
`custom_avatar_smoke_test.py` contained six extra blank lines compared with the
already HomeLab-tested candidate.

- Packaged generated SHA:
  `bb242fcba157ce02ac13d0653970d8582c11019c4ac7e880b77dab53de60324a`
- Tested candidate SHA:
  `7a65e1027eb31e9aa443d18597ad965ed1313bb259d86a7b7e863878fb85ac1a`

No application source or live database migration was performed.

## Patch 599 failure

Patch 599 corrected the candidate bytes, but its preflight attempted to find
the terminal-only final failure summary text `Phase: preflight` inside Patch
598's file log.

The file log contains progress messages and command stdout/stderr written by the
patch logger. The final failure summary printed by the outer exception handler is
not appended to that log. Therefore the evidence predicate was invalid.

Patch 599 also failed before writes.

## Corrected candidate proof

Patch 600 imported Patch 599 and ran only its `build_candidate()` function in
memory against the exact current committed source. No preflight, write, build,
migration, deployment, staging, commit, or push action from Patch 599 was run.

All ten candidate hashes match the already HomeLab-rehearsed candidate:

- `788649083fbc0d66ff0fa05632ad0a2e55648948d5fbd88ee835f0c7cbb6dfc9` — `backend/requirements.txt`
- `fd148f82df39e43e0972c301ff0033dd72a6a5b95d0446336a86d641e0862d73` — `backend/app/models/core.py`
- `73a66d7ee6ba17595dad66efd30cdb1e8f8f1d2e54b77f59e8d27e5880097c9d` — `backend/app/services/auth.py`
- `21e2675518f8df3a116b6eaf14fbe0de1a8fdbd37964a99d3035d540c43e9260` — `backend/app/schemas/auth.py`
- `5d37a218a6cef1b94701138cec56c5f1bf282ccb4bbd95de0cbd15eb20c02df9` — `backend/app/api/routes/auth.py`
- `5673f66cb14b43176c4daad6124bc3d7f9287029e98781969a4f0c358c993bd3` — `backend/alembic/versions/0013_user_avatar_image.py`
- `7a65e1027eb31e9aa443d18597ad965ed1313bb259d86a7b7e863878fb85ac1a` — `backend/app/db/custom_avatar_smoke_test.py`
- `f259543551a6ec80eb3a3ac33d99c0f3b57b91fd7a236b20e36571eee54991b1` — `backend/app/services/backups.py`
- `aedcbd929964a53dd680b825af8baace6b8a1bad85da71c98b5d9150e6122c18` — `backend/app/schemas/restores.py`
- `670657c52ba4f56dd54d9d4377226d8cf44be14887faae1d682ae227bbe9c433` — `backend/app/db/backup_smoke_test.py`

The generated Patch 599 state flags remained:

- written: `False`
- built: `False`
- migrated: `False`
- deployed: `False`
- staged: `False`
- committed: `False`
- pushed: `False`

## Recovery rule for Patch 601

Patch 601 must:

1. pin Patch 598 and Patch 599 scripts/logs by exact SHA-256 only;
2. **not** infer terminal failure summaries from file-log prose;
3. generate the same ten candidate files and fail before writes unless every
   candidate SHA exactly matches this report;
4. preserve the five pending Account files byte-for-byte and unstaged;
5. run the already-rehearsed Docker build, Alembic 0013 copied-DB round trip,
   custom-avatar smoke, backup/restore smoke and full application smoke;
6. migrate live SQLite only after all copied-DB validation passes;
7. prove existing user/session/inventory/MCP data remains unchanged and new
   avatar columns are NULL before deployment;
8. deploy, verify protected avatar routes and Alembic 0013;
9. stage/commit/push only the ten backend files;
10. restore exact source/database/deployment on any failure before push.

## Diagnostic conclusion

The custom-avatar implementation itself is not blocked. The recovery error is
limited to Patch 599's evidence predicate. The corrected ten-file candidate is
fully reproducible from the current source and matches the previously tested
HomeLab candidate byte-for-byte.
