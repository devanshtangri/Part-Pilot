# Chat 21 boundary recovery diagnostic — Patch 613

<!-- PARTPILOT:CHAT21_BOUNDARY_DIAGNOSTIC:V613 -->

## Verdict

**PASS — diagnostic only.** The repository is actually on `main`. Patch 611
reported a false branch mismatch because its `State.run()` returned byte streams
while its preflight helper compared `.stdout.strip()` directly with Python
strings. Its exception reporter then hit a second bytes/string concatenation
error. Patch 611 performed no source, documentation, database, deployment,
staging, commit, or push mutation.

Patch 612 was the required diagnostic-first attempt but failed while writing
its one diagnostic report because `tempfile.mkstemp()` was used without
`import tempfile`. Rollback removed that report and preserved every pending
browser-approved byte. Patch 613 is therefore diagnostic-only again. After
this report passes and is inspected, Patch 614 may perform the narrow
boundary recovery.

## Exact Git and deployment state

- Branch: `main`
- Pre-diagnostic HEAD/origin: `153d13b97adb22c7dc27a21fe852373402f2f117`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Git index before diagnostic: clean
- Pending browser-approved V607-V609 file count: `20`
- Deployed image: `sha256:f19f753d40ea00aa8e6a6cc6545c57e1fccfd570ff2bb055f21dda8fc2614aa7`
- Compose image: `partpilot-partpilot`
- Container running/health/restarts: `true` / `healthy` / `0`
- Alembic: `0013_user_avatar_image`
- Full smoke current SHA-256: `96dabad556c32ce133b5680a91a198911578281db59c70e2d1a1891e2fb13268`
- Rehearsed two-function ID-reuse-safe full-smoke SHA-256:
  `881c409fb4f0f796b406d645edafb21b444a3cf183fc5f67c278d1b16c697412`

## Patch 610 evidence

- Script: `fixes/610_close_chat21_and_checkpoint_recycle_bin.py`
- Script SHA-256: `8aff4a77213f529685dbe5804c08b7b5faf511ee3565c7145e5e4e298599bb45`
- Log: `fixes/logs/610_chat21_boundary_20260808-043831.log`
- Log SHA-256: `22572f35cf0a8770d001d86dfbbee6f0daf79fc1d5c220cdfbfe8fd16c3e62a8`
- Failure: complete smoke reused deleted custom Part Type ID 35 and the old
  `part_type.updated` assertion counted historical rows plus the fixture row.

## Patch 611 evidence and exact failure shape

- Script: `fixes/611_recover_chat21_boundary_audit_id_reuse.py`
- Script SHA-256: `d0ceb1ea0e49ed56463c36d26b20db03ea14bb7b59fde95687b900a64268675b`
- Log: `fixes/logs/611_chat21_boundary_recovery_20260808-045228.log`
- Log SHA-256: `205c92d342a211a1e5c9a662e1d83a9dad3ba2495d6b2bcb3ca23f39a3a3c519`
- Actual branch verified by Git: `main`
- `subprocess.run(..., text=True)`: `False`
- Preflight helper returned raw `.stdout.strip()`: `True`
- Branch comparison used a Python string: `True`
- Failure reporter concatenated command stdout into a string path:
  `True`

Safe correction: every Patch 613 subprocess wrapper must return decoded text
(`text=True`) consistently. Failure reporting must therefore also receive strings.

## Patch 612 diagnostic harness failure

- Script: `fixes/612_diagnose_chat21_boundary_recovery.py`
- Script SHA-256: `e540f0d7f7f3cc8e67e7d910b0303a412de0ca8e543e0c7fe88ffcb72415c7fc`
- Log: `fixes/logs/612_chat21_boundary_diagnostic_20260808-054738.log`
- Log SHA-256: `779b61ca8f09b33c631a097c4452ad98aafafd6e1ebb16198f683c9a4c29dd65`
- Exact defect: one `tempfile.mkstemp()` call and no `import tempfile`.
- Failure occurred before staging/commit/push. Rollback removed the temporary
  diagnostic report and preserved all approved pending source/docs bytes.
- Patch 613 repair: import `tempfile`; otherwise retain diagnostic-only scope.

## Live post-browser database state

- Integrity: `ok`
- Foreign-key violations: `0`
- Counts: `{"app_settings": 17, "audit_log": 211, "part_types": 34, "parts": 14, "projects": 8, "reservations": 10, "sessions": 4, "stock_movements": 35, "users": 1}`
- Audit max ID: `213`
- Deleted items: `[(8, '5V Relay', 17, 0, 0)]`
- ESP01 rows: `[]`
- Development Board rows: `[]`
- Owner profile: `[(1, 'devanshtangri', 'Devansh Tangri', 'storage', None)]`
- MCP enabled/read/write settings: `[('mcp.enabled', 'true', None), ('mcp.read_tools_enabled', 'true', None), ('mcp.write_tools_enabled', 'false', None)]`
- MCP direct-auth security fingerprint:
  `a27a5327005c0504b4a53b65d9499920d7c921b2a77a112c2dc8bbb8ded8d9cd`
- Browser audit evidence: `[(212, 'part.purged', 'part', 1), (213, 'part_type.deleted', 'part_type', 35)]`

### Historical Part Type entity-ID 35 rows

- audit `1`: `part_type.created` / `part_type` / entity `35`
- audit `2`: `part_type.updated` / `part_type` / entity `35`
- audit `3`: `part_type.deleted` / `part_type` / entity `35`
- audit `4`: `part_type.created` / `part_type` / entity `35`
- audit `5`: `part_type.updated` / `part_type` / entity `35`
- audit `7`: `part_type.updated` / `part_type` / entity `35`
- audit `213`: `part_type.deleted` / `part_type` / entity `35`

This history proves that an entity ID cannot identify smoke-owned audit rows.

## Full-smoke block shape

- Update fixture broad Part Type audit cleanup anchors:
  `1`
- Update fixture unbounded audit assertion anchors:
  `1`
- Delete fixture broad Part Type audit cleanup anchors:
  `1`
- Delete fixture unbounded audit assertion anchors:
  `1`

Safe Patch 613 transform:

1. In each of the two Part Type smoke functions, capture
   `max(audit_log.id)` after pre-cleanup and before creating the fixture.
2. Count only the expected event/entity rows with `id > audit_floor`.
3. Cleanup only Part Type audit rows for the reused entity ID with
   `id > audit_floor`.
4. Keep all historical audit rows byte-for-byte.
5. The disposable Docker rehearsal against a copied post-browser database has
   already passed the complete smoke with exactly this two-function transform.

## Pending browser-approved hashes

- `README.md` — `e62c830b685852dcc20893f0db42be723b269336f44c585dfc54299b41cf0575`
- `backend/app/api/routes/part_types.py` — `df531049413a90cc8835597c09d1cd059fef542ea150c374ddc54756c5d74580`
- `backend/app/api/routes/parts.py` — `833ba1dd0b6ca24e1cd11336ef00fc7b01abf889f441910fa2a9d9839dfdd440`
- `backend/app/db/recycle_bin_smoke_test.py` — `cf7206be5be4693817700c2dd3470ca9785ea5bf1f583e4068aac5f8e7c01713`
- `backend/app/schemas/part_types.py` — `2cdd0bbfd78d38cfaf05cd0512df944347a9da1e2b5c97757e824adb12a60982`
- `backend/app/schemas/parts.py` — `27d061c76200b15f7755596e3bf66aa542c4751c7e05c53e730919eb612b49d5`
- `backend/app/services/part_types.py` — `7d569dbf422596f12f1675bf10758914f6661dbcb10d55205789b8e8f05e63b4`
- `backend/app/services/parts.py` — `3c0d4911e8bfda0a99b053a8aff65e09c194d94cbeb91f19260f32fc55c393c8`
- `docs/Checkpoint.md` — `6525236df4619a28a431d14a75aadbffd2b8e5f471a4cd2066aea2cb9983e212`
- `docs/Implementation_Roadmap.md` — `3fe7daa45f538a16de5272d05aba4b7d060a86ae0075c5e1dab26d68a6b4c279`
- `docs/Part_Pilot_Project_Memory.txt` — `6693e9fd6c70c87a537c2aa789d5b0b1a8674ad334084617b0094939d6013615`
- `frontend/src/components/PartLifecycleModal.css` — `eae0219f60d6d87b7dcd2212679d9129d4b89a84da702e821d159312419cc504`
- `frontend/src/components/PartLifecycleModal.tsx` — `5fac5b475c5df7f4dd6978fddc910b9d57592b66b28e9d76f26b5853df13bd93`
- `frontend/src/pages/History.tsx` — `9c4b8de14f1603e170caa783cf25d8d42fd8fb08d1ff5749357b7d3356a5b87f`
- `frontend/src/pages/PartManager.css` — `2cee4eb982f74e2137e9cf7df4baba043c7e6626a626450fa329b558d51523c3`
- `frontend/src/pages/PartManager.tsx` — `07b8b75cf1eeb9548a052a9847bd28d7eaa6c77a8449f20f7a6b3c57118366e2`
- `frontend/src/services/partTypesClient.ts` — `06379e94321cb9185e46090b3c9b125eb00c5967c45885880b003ce26f83a6c5`
- `frontend/src/services/partsClient.ts` — `c427eebb3db3620f22ada7fe8d46bf0b22837946642738261d1e970b0af28521`
- `frontend/src/types/partTypes.ts` — `aebb58230e1944be35ae6e446cb0a675c90e92d3b0c30fc086f2081833ce44b9`
- `frontend/src/types/parts.ts` — `0a543d56981ba8e3d96e66a9a7e90f5a59d400ee37cc745fb4af2a94d1e919ca`

## Safe boundary-recovery plan

Patch 614 should:

1. Validate this diagnostic commit plus unchanged pending V607-V609 hashes/index.
2. Apply only the two-function full-smoke audit-boundary fix.
3. Build all durable Chat 21 boundary docs/handoff in memory.
4. Reconstruct the exact candidate from the local pending source, not GitHub.
5. Run canonical Docker/Vite build, Recycle Bin smoke and complete smoke on
   separate copied databases.
6. Preserve the live post-browser database, credentials, restore staging and
   deployed V609 application.
7. Stage only the approved browser batch, the smoke-test fix, durable docs, and
   Chat 21-to-22 handoff; verify the staged allowlist/diff.
8. Commit/push/fetch and verify clean Git/index.
9. Declare the Chat 22 start/range only after Patch 614 succeeds, so failed
   recovery numbers cannot make the durable boundary metadata stale.

## Settings/MCP requirement to preserve in boundary docs

- Add clear section grouping/dividers throughout Settings.
- Put `Enable MCP server` first as the MCP master control.
- When MCP is disabled, subordinate MCP controls must be visibly muted/disabled
  and non-interactive.
- Group read-tool/write-authorization/tool-permission controls under a clear
  permissions/security section; choose final names during implementation.

No application source is changed by Patch 613.
