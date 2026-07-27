# Patch 282/283 Boundary Recovery Diagnostic

<!-- PARTPILOT:PATCH283_DIAGNOSTIC_RECOVERY:V284 -->

## Status

- Diagnostic patch: 283
- Current HEAD: `5aa80c6c86e6e571baa5102ee7552fd98a749976`
- Current HEAD message: `Normalize Part Pilot boundary prompt policy`
- Local HEAD equals `origin/main`: yes
- Pending working-tree change:
  `D docs/Part_Pilot_Project_Memory.txt`
- Application source modified: no
- Checkpoint modified: no
- Live inventory modified: no
- Deployment modified: no
- Next-chat prompt created: no

## Patch 283 failure

Patch 283 failed because its report path is intentionally ignored by Git. It
created the report and then checked ordinary untracked paths before
force-staging. Ignored files are omitted from that query, so only the pending
memory-file deletion appeared.

Patch 283 removed the report during rollback. It did not stage, commit or push
anything and did not modify application source, inventory or deployment.

## Patch 282 failure

Patch 282 failed in `documentation backup and checkpoint write` with:

```text
NameError: name 'shutil' is not defined
```

The failure occurred when `atomic_write()` attempted to call
`shutil.copymode()`. The script did not import `shutil`.

Patch 282 created its ignored backup/log artifacts, but it did not write
`docs/Checkpoint.md`, stage files, commit, push, modify application source,
change inventory, or alter deployment.

## Verified repository state

- Pending paths: exactly `docs/Part_Pilot_Project_Memory.txt`
- Pending change type: deletion
- Staged paths: none
- Untracked paths: none
- Unmerged paths: none
- Checkpoint SHA-256: `3760562b0eee37b826175587b5fe420143d345e60bb00db63fc84d4627837275`
- Memory file SHA-256 in HEAD: `17172f1059f6a8cd436b3424d26e67d778eaf2b3fd060e4ff22ebff0404685e9`
- Patch 282 backup: `/projects/Part Pilot/fixes/backups/patch_282_20260727-232407`
- Patch 282 log: `/projects/Part Pilot/fixes/logs/282_remove_project_memory_20260727-232407.log`

## Application source hashes

- `backend/app/api/routes/parts.py`: `2501759a082a12e74dfab3ec9cc48be8e19bb426a96f0ef0ed3035fd2e3460b4`
- `backend/app/db/smoke_test.py`: `511b9f757f4129ef84846ead97c113760fb4a473ced62c34e78a736a0c4c6ad4`
- `backend/app/services/parts.py`: `34e448f514ed2f115cfc24b27a35667fbd7fdbec8472fd2d4101dcb0ed470998`
- `frontend/src/pages/PartManager.css`: `b3c64207fa1c171e8770f46790cd693df41413f5fe5d242d52d4e5727bff10de`
- `frontend/src/pages/PartManager.tsx`: `1122bb8b9525775cc794b404875a49b5dc28a2ff9f89fb5df85607176ec793b9`
- `frontend/src/services/partsClient.ts`: `8dc0f4a07610807427e9bc56050ea84b76d504b5466ba377cdc4470f715fa43f`
- `frontend/src/types/parts.ts`: `755bb9817dd6e4363ddab11ae34896b68a22b32543832f09b5fbd64c67bca930`

## Deployment and inventory

- Container ID: `5f84a320d363a8471ff0589cd1ddb75693d6415df0d0df017ee153fe48dcaa46`
- Container image: `sha256:ebc8e959373c7ecd51df93b433148156567ed07d312446371385dc9d98825416`
- Database path: `/projects/Part Pilot/data/partpilot.db`
- Alembic head: `0005_packages`
- Inventory-bearing tables snapshot: captured and unchanged

## Exact Patch 285 recovery plan

1. Start from the current clean index with only the intended memory-file
   deletion pending.
2. Reissue Patch 282's documentation-only normalization as Patch 285.
3. Add `import shutil` before any code references `shutil.copymode`.
4. Add an artifact-level validation that fails generation when `shutil.` occurs
   without an `import shutil` statement.
5. Validate the current HEAD, origin, pending deletion, application hashes,
   deployment and inventory before backup/write.
6. Back up `Checkpoint.md` and the deleted memory file from HEAD.
7. Append the durable-context policy to `docs/Checkpoint.md`.
8. Keep `docs/Part_Pilot_Project_Memory.txt` deleted.
9. Stage only:
   - `docs/Checkpoint.md`
   - `docs/Part_Pilot_Project_Memory.txt`
10. Run staged `git diff --check`, commit and push.
11. Verify local HEAD equals `origin/main`, the repository is clean, application
    bytes are unchanged, inventory-bearing tables are unchanged, and deployment
    is unchanged.
12. Do not create or commit any next-chat prompt file.
13. Keep Chat 11 active after Patch 285; the deferred fixture-cleanup diagnostic
    will continue with Patch 286.
14. Provide no next-chat prompt until a later boundary-recovery script actually
    ends with exactly `Everything PASS`.

## Boundary policy retained

- Future chats own 30 sequential patch numbers.
- Failed scripts consume their patch number.
- Next-chat prompts exist only in the current chat response.
- A next-chat prompt is supplied only after successful boundary recovery.
