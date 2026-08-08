# Chat 21 Patch 625 diagnostic — backend mode drift in Docker context

## Status

Patch 620 remains the browser-approved application state. Patch 623 diagnosed the
first Docker-context mismatch: the repository had no `.dockerignore`, so 112
Git-ignored backend `.pyc` files participated in `COPY backend`.

Patch 624 added a candidate `.dockerignore` and proved in isolated clean and
bytecode-contaminated clones that the ignored bytecode no longer affected the
image. Its live-root build still produced
`sha256:fe9531d52af6e2458ae4b3c0fd2ccf89692f34c734c05693e426c79a61dea8f7`
instead of the browser-approved
`sha256:a78b116c1efb96d20db9d326fc63ea6b9a9442521671b6a8b35ea8b1b7853c9c`.
Patch 624 rolled back its candidate durable docs and `.dockerignore`; the exact
Patch 620 browser-approved pending source, deployment, database, credentials and
inventory remain unchanged.

## Git and pending browser-approved source

- Branch: `main`
- HEAD/origin before this diagnostic:
  `c199585addc05f6d341a0783c8e061b8fa9db0ba`
- HEAD subject: `Diagnose Docker build context contamination`
- Git index: clean
- Pending browser-approved files: exactly eight
- Chat 21-to-22 handoff: absent
- `.dockerignore`: absent after Patch 624 rollback

Pending source fingerprints remain:

- `docs/Checkpoint.md`
  `a2be7c01c26b7c3e056d3f89686caa5fa5a9e0254829855c24462f7293d43cc6`
- `docs/Implementation_Roadmap.md`
  `0aa028a529438c9d4c4adcc559c6eeeeffe05b11760305293e4658ec0f74014a`
- `docs/Part_Pilot_Project_Memory.txt`
  `89a75c3283b85b357b1e17a4d0337927019bc09d934996955f774601a1b0b703`
- `frontend/src/pages/Settings.css`
  `d77329691d8630f720b2bf070b7e28623925f334eb40e68d3b8f015b0dc7d377`
- `frontend/src/pages/Settings.tsx`
  `92999e6a6414f5da4474b6297f189d6f193c08c0a18020cd41e2deb83ad73fcd`
- `frontend/src/components/ApiKeySettingsSection.tsx`
  `a3d4023667f5d4fe599fc8e2dd46d78406676bf6511df0c752b281709705ed4a`
- `frontend/src/services/apiKeysClient.ts`
  `e066f89a2025b7990f01cbcb6fde347bc9b329184ac67bdd42543890f5cb63c2`
- `frontend/src/types/apiKeys.ts`
  `0168881e04c7f3effe4036948caed42db3d87394687b6afb3a0e1afb7b379a88`

## Patch 624 failure evidence

- Patch 624 script SHA-256:
  `90f7cd5f8e9faf84c89c5a8fbe18b3fdc05a95cf646f11379e15548910209cf7`
- Patch 624 failure log SHA-256:
  `f507e6547b3541b9d1ab77db951f8e4e922f63faf5de5213cfa52f1c6399bad4`

With the candidate `.dockerignore` active, Patch 624's frontend Docker stages were
cached. `COPY backend /app/backend` rebuilt, followed by the dependent
`COPY --from=frontend-builder` layer. This localizes the second difference to
effective backend source metadata.

## Exact backend mode drift

At the current HEAD, `git ls-files -s backend` reports zero tracked backend files
with a Git mode other than `100644`.

The live working tree nevertheless contains 16 tracked backend files at filesystem
mode `0600`. Their bytes are identical to the corresponding clean Git checkout at
mode `0644`. Git does not report this difference because the executable bit is
unchanged.

Mode-drift manifest SHA-256:
`12721d14219d0b9419d861bfee34d2696d6b375a15c08f5c9764993a319862d9`

The 16 paths are:

1. `backend/alembic/versions/0006_reservation_contract.py`
2. `backend/alembic/versions/0007_projects_contract.py`
3. `backend/alembic/versions/0008_mcp_oauth.py`
4. `backend/alembic/versions/0013_user_avatar_image.py`
5. `backend/app/db/custom_avatar_smoke_test.py`
6. `backend/app/db/mcp_oauth_service_smoke_test.py`
7. `backend/app/db/password_session_admin_smoke_test.py`
8. `backend/app/db/restore_validation_smoke_test.py`
9. `backend/app/schemas/auth.py`
10. `backend/app/schemas/backups.py`
11. `backend/app/schemas/mcp_oauth.py`
12. `backend/app/schemas/projects.py`
13. `backend/app/schemas/reservations.py`
14. `backend/app/services/auth.py`
15. `backend/app/services/mcp_oauth.py`
16. `backend/requirements.txt`

## Causality proof

Two isolated candidates used the same tracked/pending bytes and the same
`.dockerignore`. Only the 16 source modes differed:

- exact 16 files at `0600`:
  `sha256:fe9531d52af6e2458ae4b3c0fd2ccf89692f34c734c05693e426c79a61dea8f7`
- exact 16 files at `0644`:
  `sha256:a78b116c1efb96d20db9d326fc63ea6b9a9442521671b6a8b35ea8b1b7853c9c`

The `0600` candidate exactly reproduces Patch 624's failed live-root image. The
`0644` candidate exactly reproduces the browser-approved image. This proves the
remaining image divergence is the 16-file permission drift.

## Why Dockerfile chmod alone is not sufficient

A disposable Dockerfile experiment used:

```dockerfile
COPY --chmod=0755 backend /app/backend
RUN find /app/backend -type f -exec chmod 0644 {} +
```

The final in-container permissions were correct (`0755` directories, `0644`
files), and application import/compile succeeded. However Docker still hashed the
source metadata into the parent `COPY` layer:

- source modes `0600`: image `af995c77262d...`
- source modes `0644`: image `056cf604f783...`

Therefore Dockerfile chmod cannot make the full image ID independent of the host
source modes. Canonicalizing the build context before `docker build` is required
when exact image identity is an invariant.

## First diagnosis remains valid

Patch 623's bytecode diagnosis also remains valid:

- `.dockerignore` absent in current source
- 112 ignored backend `.pyc` files
- 10 `__pycache__` directories
- 2,303,166 bytes
- ignored-bytecode manifest SHA-256:
  `1088f591317610f29108c4ea51322afc9f55334b91158e7c11ecce7024a761e6`

Both contamination classes must be handled:

1. ignored generated files must be excluded from Docker context;
2. tracked source file modes must be canonical before an exact live-root build.

## Deployment and live data

- deployed image: browser-approved `a78b116c...`
- container: running, healthy, restart count 0
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
- restore staging remains preserved

## Root cause

The exact-image checkpoint harness assumed that byte-identical Git source implied
a canonical Docker input tree. It did not.

Git ignores non-executable permission differences such as `0600` versus `0644`,
but Docker includes those permission bits in `COPY` layer identity. Historical
patch writes left 16 tracked backend files at `0600`, so the live repository
differed from a clean checkout even after ignored `.pyc` files were excluded.

## Safe Patch 626 implementation plan

1. Preflight the exact Patch 625 diagnostic HEAD, the eight browser-approved
   pending source fingerprints, the Patch 623/624 evidence, live deployment,
   Alembic, database, credentials, restore staging and no-handoff invariant.
2. Revalidate the exact 112-file ignored-bytecode manifest and the exact 16-file
   mode-drift manifest before any write.
3. Build the Patch 626 durable docs and minimal `.dockerignore` entirely in memory.
4. Back up the three durable docs and record the original modes and content hashes
   of every tracked backend build-context file.
5. Normalize tracked backend files to their Git-canonical modes before the
   live-root exact-image build. At this HEAD every tracked backend file is
   `100644`, so the filesystem target is `0644`. Do not change file contents.
6. Write the minimal `.dockerignore` so the 112 ignored `.pyc` files never enter
   Docker context. Do not delete the host caches.
7. Prove every normalized file's SHA-256 is unchanged, `git diff --check` is
   clean, and Git still reports only the intended pending browser-approved files
   plus `.dockerignore`/durable docs.
8. Rebuild from the live root. It must reproduce the exact browser-approved
   `a78b116c...` image. Also repeat clean/contaminated candidate convergence and
   the API-key lifecycle, 43-route scope and complete copied-database smokes.
9. Stage only the browser-approved eight-file batch plus `.dockerignore`. The
   durable docs are already part of those eight because Checkpoint/Roadmap/memory
   are pending. Do not restage the Patch 623 or Patch 625 diagnostic reports.
10. Commit/push only after all preservation, image, Alembic, staged-allowlist and
    no-handoff checks pass. On failure before an authoritative push, restore the
    durable docs, remove `.dockerignore`, restore every original filesystem mode,
    and prove live data/deployment/source preservation.
11. Record a durable workflow invariant: exact Docker image comparisons require a
    canonical build context. Future patch scripts must either normalize tracked
    build-context modes before a live-root build or build from an isolated
    canonical clone/overlay.
12. No additional browser test is required; Patch 620 remains the approved UI.

Do not resume named/direct MCP client administration until this checkpoint
recovery succeeds.
