# Diagnostic: Patches 734-736 MCP write recovery failures

## Status

- Repository: `/projects/Part Pilot`
- Branch: `main`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- HEAD/origin-main: `3dd0767b31288bb978227e8b4a3806068b98973c`
- Commit: `Add user roles and authorization`
- Runtime: `sha256:55da963bf36233cecaedcf0c606188eb4cc51788061ef082321cab8d6b3eda40`, healthy, restart 0
- Production Alembic: `0017_user_roles`
- Instance-secret SHA-256 only: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- Git/index: clean before this documentation-only diagnostic
- Application/database/deployment writes from Patches 734, 735 and 736: none

## Evidence fingerprints

- Patch 734: `e68c227d7fbabc32fa81b8cfb4f001a824dc465a37fc4bc1355fe47e0f0e5fb7`
- Patch 734 failure log: `f5876bbf9f9f7d7f031d09ee83fdc49ea950ec11419f338a98b94f503c6672d4`
- Patch 735: `8e5a73d0cb6864946ec9d5d56aa01f8fef44737c39eef9c23c23dfa2e659faee`
- Patch 735 failure log: `fd86a1ea339dca08e4ad7a0bbf0b19d0796209a4dd77a298d538afd5020f0ee9`
- Patch 736: `9b31ac99133e8598debc4d2f28c1aeeba47d6e3a97e1fac432aa943985ae06be`
- Patch 736 failure log: `4660def28c3e57fc5588b7b7e87cafce51735437b35dbf472acb6d62d6fb6329`

## Root cause 1 — Patch 734 false runtime mismatch

Patch 734 generated a Docker Go-template with single braces instead of the required doubled braces:

```text
image={.Image} health={if .State.Health}{.State.Health.Status}{else}none{end} restart={.RestartCount}
```

The Patch 734 log contains that malformed template exactly **2** times: once in the command and once as literal Docker output. The real runtime was independently verified as the unchanged Patch 733 image.

## Root cause 2 — Patch 735 impossible recovery-evidence predicate

Patch 735 corrected the Docker runtime template itself:

```text
image={{.Image}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restart={{.RestartCount}}
```

However, its preflight reads the Patch 734 log and then requires that same log to contain both `Patch 735 failed.` and `Patch 733 runtime changed`. Those strings are console failure-summary output, not content in the Patch 734 command log. The predicate therefore cannot pass for the exact expected Patch 734 log.

Relevant predicate shape:

```python
require(malformed in failure_evidence and "Patch 735 failed." in failure_evidence and "Patch 733 runtime changed" in failure_evidence, ...)
```

## Root cause 3 — Patch 736 wrong canonical origin form

Patch 736 hard-coded the HTTPS origin while the repository and preceding successful patches use the SSH origin.

```text
actual:   git@github.com:devanshtangri/Part-Pilot.git
patch736: https://github.com/devanshtangri/Part-Pilot.git
```

This explains `DiagnosticFailure: Origin changed` without any repository mutation.

## Candidate identity

- Patch 734 and Patch 735 baseline hashes identical: **yes** (24 tracked baseline files)
- Embedded candidate hashes identical: **yes** (28 candidate files)
- Embedded candidate byte payloads identical: **yes**
- New-file set identical: **yes** (4 files)
- Candidate image identical: `sha256:68fab8ba255843ab4d2d398aa828f94629351dea95f7af301b7105abd6aacada`
- Target Alembic identical: `0018_mcp_write_intents`

New files:

- `backend/alembic/versions/0018_mcp_write_intents.py`
- `backend/app/db/mcp_write_tools_smoke_test.py`
- `backend/app/mcp/write_tools.py`
- `backend/app/services/mcp_write_safeguards.py`

Candidate SHA-256 map:

- `backend/alembic/versions/0018_mcp_write_intents.py` — `60d44cbf8f874c06bf0d28954a7c43aabaf39c4ad7975b409267bdcd6c649636`
- `backend/app/db/backup_smoke_test.py` — `71f35473be99057e217eedbc962c72e6e41e931df44a084259a23e82aa233158`
- `backend/app/db/mcp_direct_bearer_transport_smoke_test.py` — `7554e9f9fffafa06067911d9f9ee077fda5d6b473bda849b039750387c6fcfa6`
- `backend/app/db/mcp_direct_custom_header_transport_smoke_test.py` — `0cb3daa92240dd7e058d6d4af38b217375bfbdfd637802a7a8ec3eb8b9d75d66`
- `backend/app/db/mcp_direct_trusted_network_transport_smoke_test.py` — `f54246b39c9e9e0c8a9bbbcc0704950a49a1661683746ffdf624f6023ced7ef1`
- `backend/app/db/mcp_oauth_smoke_test.py` — `b7db18561dc1956604ff4996e2add42df549c5dda69067ca1e737698e6baa3a7`
- `backend/app/db/mcp_permission_admin_smoke_test.py` — `38383e05bb7920646613b8858b8c9e52b591a1cad3193c500a63de88fc3bf06c`
- `backend/app/db/mcp_tool_permissions_smoke_test.py` — `3eabbf6e186b87494591cd8a64d784e7977eb0ba1cfbd50b71ae9b5eab6ed9c6`
- `backend/app/db/mcp_transport_smoke_test.py` — `9f2280a1b448dcbe6816fa4d6f0150f2a6b038bda911815e1f60e1385e070470`
- `backend/app/db/mcp_workspace_tools_smoke_test.py` — `bdc95fd17c255c717323b961fe13b70e453eddc2fba7e2bfd225c5c43222ccb2`
- `backend/app/db/mcp_write_tools_smoke_test.py` — `56148876ebb2219514ea61f94a4b78b658af870739d12b774b04d71b1f456889`
- `backend/app/db/user_roles_smoke_test.py` — `9b6882a95ac259fb2b704d23cb2d32b8f4fb8a34403e435abc33c8af238ee566`
- `backend/app/mcp/part_tools.py` — `79de22b68a01b1652a7eb6e32d9afc98d28a1da5073c51d7e9de4c0eaa9244f7`
- `backend/app/mcp/runtime.py` — `237babf29e18222be934dbb66a5da8a20dbc51d6a53a4ed788b26833c50aca1a`
- `backend/app/mcp/write_tools.py` — `540bbaf760b555c80f0ee906146633587bfb28b15e9faf71b6ac6d0a000b7b39`
- `backend/app/models/__init__.py` — `eaf8ce38d3cf3c14ecce0cfdf0e5ed4910fc18ef6a3c5e37fc400b6bbf2198f4`
- `backend/app/models/core.py` — `c994c83f3b92d0501adee1f913c444dc59c4019a453f0d3dd0f40b903562bb92`
- `backend/app/schemas/app_settings.py` — `974616f48b56023df7779f7c6e0a3ded8326764bc56b254bfcfed9a8ce28ef6c`
- `backend/app/schemas/restores.py` — `1f84e2ef3a0e745654341d640489dc23efea21b18f6af893aa20772a7252c0b9`
- `backend/app/services/backups.py` — `4bf3acd57f2dc28d6ea9db9365fcfbf304323dc6ed8661d1497493f15a722242`
- `backend/app/services/mcp_permissions.py` — `5ef2969c6593d4e6a7c46fb118fe19fa7911fb8a26fe0f87b277ad306158b5d1`
- `backend/app/services/mcp_write_safeguards.py` — `7ffdc831553f792592712b4689e2ce178e455585b7a90f060dbfffb27a05a51f`
- `backend/app/services/projects.py` — `82ad30f6f72412696eca7384f6199d635b92aaf83fff58347fa6c682b7e6b595`
- `backend/app/services/reservations.py` — `8e99e5f9f428e40535eddcd2962dcd5457d009f4a97a37d3b536ff617e171fce`
- `frontend/src/components/McpClientPermissionsDialog.tsx` — `cdc2542be7414d5863515856d4e2b2f5bba6f334279ce9f05f5c5bef660fe190`
- `frontend/src/pages/Settings.css` — `d2cab89875e8fc18691e541a8c1ad4496cbbedc6dd97282727621de31374bcab`
- `frontend/src/pages/Settings.tsx` — `9e4bea1a3b222b0c1b986a90e044f6dbfb0d61ea5bdb72e75157a318f5fbb774`
- `frontend/src/types/settings.ts` — `854179734dbd1f6bab4a661e93e064e0015b186fb6080c08d2fda41d1d174a0d`

## Safe recovery plan

1. Do not regenerate or redesign the 28-file MCP-write candidate; reuse the exact Patch 735 embedded candidate bytes and hashes.
2. The next implementation recovery must validate the exact Patch 734/735/736 script and log hashes above, but only require evidence that is actually present in those files.
3. Use the established SSH origin `git@github.com:devanshtangri/Part-Pilot.git`.
4. Keep the corrected doubled-brace Docker inspect template and compare it to the exact Patch 733 runtime image before writes.
5. Revalidate the clean Patch 733 source hashes, absence of all four 0018 new files, production `0017_user_roles`, SQLite integrity and instance-secret hash before any write.
6. Reconstruct the exact candidate in memory, verify every embedded hash, then run the already-defined canonical build/migration/copy-DB regression sequence before live transition.
7. Because the candidate is a browser-test boundary, leave application source unstaged/uncommitted/unpushed after a successful deployment until browser approval.
8. After browser approval, use a separate narrow checkpoint/boundary patch to update durable docs, commit/push, and hand off to the next chat.

## Diagnostic conclusion

No evidence indicates a failure in the safeguarded MCP write implementation itself. All three consumed patches failed in preflight/recovery packaging logic before application source, database or deployment writes. The exact Patch 734/735 candidate remains recoverable from the verified embedded payload.
