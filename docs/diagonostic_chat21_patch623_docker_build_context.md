# Chat 21 Patch 623 diagnostic — Docker build-context contamination

## Status

Patch 620 remains the browser-approved application state. Patch 621 failed before
writes because its Checkpoint.md fingerprint represented one extra separator
newline. Patch 622 corrected that documentation issue, wrote only candidate
durable docs, then failed during approved-source build because the live repository
produced Docker image `sha256:a96cb88f5a8a3ae8e2555e979c7689b98c03e720b7e278dcd25c536133ef7d56`
instead of the clean-rehearsal/browser-approved image
`sha256:a78b116c1efb96d20db9d326fc63ea6b9a9442521671b6a8b35ea8b1b7853c9c`.
Patch 622 rolled the durable docs back to the exact Patch 620 browser-approved
pending bytes. No application source, database, deployment, credentials or
inventory state was changed.

## Git and pending browser-approved source

- Branch: `main`
- HEAD: `faa9e09411142f91b77ac474dcfe50071151fdcb`
- origin/main: `faa9e09411142f91b77ac474dcfe50071151fdcb`
- Git index: clean
- Pending browser-approved files: exactly eight
- Chat 21-to-22 handoff: absent

Pending file fingerprints:

- `docs/Checkpoint.md`:
  `a2be7c01c26b7c3e056d3f89686caa5fa5a9e0254829855c24462f7293d43cc6`
- `docs/Implementation_Roadmap.md`:
  `0aa028a529438c9d4c4adcc559c6eeeeffe05b11760305293e4658ec0f74014a`
- `docs/Part_Pilot_Project_Memory.txt`:
  `89a75c3283b85b357b1e17a4d0337927019bc09d934996955f774601a1b0b703`
- `frontend/src/pages/Settings.css`:
  `d77329691d8630f720b2bf070b7e28623925f334eb40e68d3b8f015b0dc7d377`
- `frontend/src/pages/Settings.tsx`:
  `92999e6a6414f5da4474b6297f189d6f193c08c0a18020cd41e2deb83ad73fcd`
- `frontend/src/components/ApiKeySettingsSection.tsx`:
  `a3d4023667f5d4fe599fc8e2dd46d78406676bf6511df0c752b281709705ed4a`
- `frontend/src/services/apiKeysClient.ts`:
  `e066f89a2025b7990f01cbcb6fde347bc9b329184ac67bdd42543890f5cb63c2`
- `frontend/src/types/apiKeys.ts`:
  `0168881e04c7f3effe4036948caed42db3d87394687b6afb3a0e1afb7b379a88`

## Failure evidence

- Patch 621 log SHA-256:
  `f23dbc94d8069bf3252efb23e7a3ee2da9ec43b5860f4523abdb2b2d56541f47`
- Patch 622 log SHA-256:
  `03bbf8ec889bf9dd1980fe5a48c709508f5635c235cfd979fb491b78ea2014d1`

Patch 622's frontend build itself succeeded and emitted the same production asset
names as the browser-approved build:

- CSS: `index-Ch1L2iK0.css`
- JavaScript: `index-Di86dMxR.js`

The image diverged because Docker rebuilt the live `COPY backend /app/backend`
layer, not because TypeScript/Vite output or the approved frontend bytes changed.

## Docker build-context diagnosis

Repository `.dockerignore` is absent.

The Dockerfile contains exactly one each of these broad copy instructions:

```dockerfile
COPY frontend/ ./
COPY backend /app/backend
```

The repository `.gitignore` correctly ignores Python bytecode:

```text
__pycache__/
*.py[cod]
```

Git therefore reports a clean backend source tree, but Docker does not inherit
`.gitignore`. The live `backend/` tree currently contains:

- 112 files not tracked by Git
- all 112 are `.pyc` files
- 10 `__pycache__` directories
- 2,303,166 bytes of ignored bytecode
- host bytecode ABI: CPython 3.11
- host Python: 3.11.2
- ignored backend manifest SHA-256:
  `1088f591317610f29108c4ea51322afc9f55334b91158e7c11ecce7024a761e6`

Because `.dockerignore` is absent, these ignored files participate in the live
Docker `COPY backend` context. Clean rehearsal clones do not contain them.

This explains the observed build split:

- clean clone/rehearsal builds: approved image `a78b116c...`
- Patch 622 live-root build with ignored bytecode: `a96cb88f...`

The failed Patch 622 image was removed during rollback. The deployed image remains
the browser-approved `a78b116c...`.

## Relevant source shape and counts

- Dockerfile `COPY frontend/ ./`: 1 occurrence
- Dockerfile `COPY backend /app/backend`: 1 occurrence
- `.dockerignore`: absent
- `.gitignore` SHA-256:
  `48f16bb3f8be5b25b363be3523c8b257228f9b88553bbceb85dc727b7998aed9`
- backend Git-ignored `.pyc`: 112
- backend Git-ignored `__pycache__` directories: 10
- frontend non-tracked files: exactly the three intentional Patch 619/620 API
  Access files; no generated frontend build artifacts are present in the live
  source tree.

## Deployment and live data

- Deployed image:
  `sha256:a78b116c1efb96d20db9d326fc63ea6b9a9442521671b6a8b35ea8b1b7853c9c`
- Container: running, healthy, restart count 0
- Alembic: `0014_api_keys (head)`
- users: 1
- sessions: 4
- API-key audit records: 2, both revoked
- parts: 14
- Part Types: 34
- Projects: 8
- Reservations: 10
- stock movements: 35
- audit rows: 227; max audit ID 229
- app settings: 17
- MCP direct authentication: Disabled
- recoverable deleted item: `5V Relay`
- ESP01 remains permanently purged
- Development Board Part Type remains permanently purged
- database integrity: OK
- foreign-key check: empty
- instance secret unchanged
- restore staging file count: 15

## Root cause

The checkpoint image-ID assertion was conceptually valid only when both rehearsal
and live builds consumed the same source context. They did not.

Git cleanliness did not imply Docker-context cleanliness because `.dockerignore`
was absent. Host-generated `__pycache__/*.pyc` files were invisible to normal Git
status but visible to `COPY backend`. The exact browser-approved tracked/pending
application bytes remained unchanged.

## Safe implementation plan

1. Patch 624 adds a minimal repository `.dockerignore` that excludes generated
   Python bytecode/cache directories and other already-Git-ignored local build
   artifacts from Docker contexts, without excluding required backend/frontend
   source.
2. Validate `.dockerignore` semantics and counts before writes. Do not delete or
   mutate the host caches as part of the fix; they are only build-context noise.
3. Rebuild the exact browser-approved pending source from:
   - a clean clone plus the pending files, and
   - the live repository containing the 112 ignored `.pyc` files.
   Both builds must converge to the same application image.
4. Run `git diff --check`, canonical Docker/Vite build validation and the relevant
   API-key/security regression checks. Preserve the live database, deployment,
   credentials and inventory throughout pre-commit validation.
5. Update Checkpoint/Roadmap/project memory with the accurate Patch 621/622/623
   chronology and the already-approved Settings-wide divider/grouping requirement.
6. Stage only the intended checkpoint set: the browser-approved eight files,
   `.dockerignore`, and the three durable docs. The Patch 623 diagnostic report is
   already committed separately and must not be re-staged.
7. Commit/push only after local HEAD/source, staged allowlist, image convergence,
   Alembic, protected routes, inventory preservation and no-handoff checks pass.
8. No additional browser test is required for `.dockerignore`; Patch 620's UI
   remains the browser-approved application bytes.

Do not resume named/direct MCP client administration until this checkpoint
recovery succeeds.
