# Chat 22 Patch 659 diagnostic — boundary recovery

<!-- PARTPILOT:CHAT22_BOUNDARY_RECOVERY_DIAGNOSTIC:V659 -->

## Status

Patch 659 is diagnostic-only. It exists because Patches 657 and 658 were two
consecutive pre-write failures and the project workflow requires a diagnostic
before any further implementation or boundary rewrite.

The authoritative application state remains the exact Patch 654 browser-test
batch plus the already-live Patch 653 permission administration backend:

- HEAD/origin before this diagnostic:
  `3a7e86e40d0a944c6042ea8751ef2bf23b721890`
- subject: `Add autosave and live sync roadmap`
- Git index: clean
- pending application files: exactly 22
- deployment:
  `sha256:06018f157cdad0af9132a224fa0ad9e58579edbedc863f912bc5661aec4cd2c6`
  healthy, restart count 0
- Alembic: `0016_mcp_tool_permissions`
- SQLite SHA-256:
  `0d07bfbc3541a3611fd5660d47bc3df18ea9759a934a9eda772d02034badd424`
- instance-secret SHA-256:
  `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- live global policy keeps `search_parts=false` and the other five read tools
  true
- OAuth/direct denied-tool lists remain empty

No application, database or deployment write occurred in Patch 657 or 658.

## Patch 657 failure

Patch 657 failed before writes while validating its packaged candidate against
the already-passed isolated rehearsal hashes.

For `backend/app/db/mcp_workspace_tools_smoke_test.py`:

- passed rehearsal SHA-256:
  `29cd1e227674114e49b21eab2d6ba8f7b90bcaf60bf9479f179814184b46ec8b`
- packaged Patch 657 candidate SHA-256:
  `53305a21b4691f83a14b48eae2bdb914b07f2785f3a029973d9e73baf93ddac2`

Read-only comparison proved the difference was formatting only. The rehearsal
used compact single-line expressions while the downloadable patch emitted
equivalent multiline expressions. No live source was written.

Patch 657 script SHA-256:

`279a4c8c77b234503e681aeda85e55e3a5bafa0e569eabc13d8cfdbf3d33279e`

Patch 657 log SHA-256:

`05315d70846c0dfc9b2b728e6e4906aa88f93654c75c22290f648953b835b8ad`

## Patch 658 failure

Patch 658 attempted the mandatory Chat 22 documentation boundary but failed
during candidate-document validation before any write.

The existing `docs/Implementation_Roadmap.md` has zero trailing-whitespace
lines and 3099 lines before the boundary candidate is appended.

Patch 658's `ROADMAP_BLOCK` contained exactly three trailing-whitespace lines:

- line 6: `**Required title:** ...` followed by two spaces
- line 7: `**Patch range:** ...` followed by two spaces
- line 8: `**First patch:** ...` followed by two spaces

After appending the block, those became Roadmap lines 3105, 3106 and 3107, which
matches the terminal failure exactly.

This was caused by using Markdown hard-break spaces in a repository whose
durable-document validation forbids all trailing whitespace. The intended
content is valid; the formatting violates the project invariant.

Patch 658 script SHA-256:

`f4025ee8807676a7ae4f4a457b8f61f9b668b50215c5b4f885f040c53bc671d0`

Patch 658 log SHA-256:

`2bd4cb7d574f5ea61f07479d0da83cf2a6b29e45cc3eac6c1041e5e6454671d9`

## Exact Patch 658 correction

The four Chat 23 identity lines must be ordinary Markdown lines without trailing
spaces:

```text
**Required title:** `Chat 23: MCP Permission Finalization and Settings Modernization`
**Patch range:** `<resolved after boundary recovery>`
**First patch:** `<resolved after boundary recovery>`
**Planned boundary:** `<first patch + 24>`
```

Do not use two-space Markdown hard breaks anywhere in the boundary candidates.

## Pending application source invariants

Patch 659 must not stage, commit, reset, rewrite or otherwise modify the 22
pending application files. They remain the authoritative browser-test source.

The relevant exact current fingerprints include:

- `backend/app/db/mcp_workspace_tools_smoke_test.py`
  `d25b4f4f797ff75bde597bbb926910d1edbd0b1ba05f7f515e5ca494b50cbf60`
- `backend/app/mcp/runtime.py`
  `07835598a918ad6e7527fcb53dd523b9be9ec485bca14dc05ecaf4ce3b97b6e0`
- `backend/app/services/mcp_permissions.py`
  `28251c36511c71acae86b298a92b87043ff71bb5b72d16f4f4a5f425d5e01c56`
- `frontend/src/pages/Settings.tsx`
  `1b22e5da6c90fd9d9de056f888e141ad82ec600f089d482cbb4fe5f8327b6979`
- `frontend/src/pages/Settings.css`
  `16ab5c1d129c9fe1e855379da7db5d2d60cd661b1ef7fc580215c2eb2bc09927`
- `frontend/src/components/McpClientPermissionsDialog.tsx`
  `f956c08038798e39a334f8d06a808af37dea47cc7e5ac98ba6e1c6fa608699f0`

## Boundary recovery plan

After this diagnostic report is committed, pushed and re-read:

1. Patch 660 may attempt the narrow Chat 22 boundary recovery if the diagnostic
   passes.
2. It must rebuild all five boundary documents entirely in memory.
3. It must reject any candidate line whose `rstrip()` differs from the original
   line before the first write.
4. It must stage only README, Checkpoint, Roadmap, project memory and the new
   Chat 22-to-23 handoff.
5. It must prove all 22 pending application files remain byte-identical and
   unstaged before and after the documentation commit/push.
6. It must preserve the exact SQLite, instance secret, restore staging,
   deployment and Alembic state.
7. The next-chat patch range must be resolved from the first unused patch number
   only when the boundary recovery actually succeeds. If Patch 660 succeeds,
   Chat 23 starts at Patch 661 and its 25-patch range is 661-685. If another
   boundary recovery patch is consumed, recalculate accordingly instead of
   freezing a stale range.
8. Do not send the ready-to-paste Chat 23 prompt until a boundary recovery patch
   succeeds.

## Patch 659 conclusion

The boundary failure is fully explained. There is no application-source
uncertainty. The only Patch 658 defect was prohibited trailing whitespace in
three newly generated Roadmap lines.

Patch 659 therefore commits and pushes only this diagnostic report.
