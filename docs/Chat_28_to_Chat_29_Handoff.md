# Chat 28 to Chat 29 Handoff

<!-- PARTPILOT:CHAT28_TO_CHAT29_HANDOFF:V821 -->

## Boundary

- Closing chat: `Chat 28: Public Alpha Release and Post-v1 Planning`
- Boundary patch: `821_complete_chat28_licensed_release_boundary.py`
- Next chat: `Chat 29: Publish v1.0.0 and Verify GHCR Release`
- Next patch range: `822-846`
- First patch: `822`
- Planned boundary: `846`

After Patch 821 succeeds, inspect exact local Git/index, runtime, Alembic and production
SQLite before trusting volatile hashes. The successful P821 commit hash is intentionally
not pre-guessed in this handoff.

## Read first

1. `docs/Chat_28_to_Chat_29_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `docs/Part_Pilot_Project_Memory.txt`
5. `README.md`
6. `LICENSE`
7. `THIRD_PARTY_NOTICES.md`
8. `docs/Public_Alpha_Publishing_Checklist.md`
9. `docs/Public_Alpha_Release_Notes.md`
10. `docs/diagonostic_816_dependency_license_distribution_audit.md`
11. exact local Git/runtime/Alembic/SQLite state

## Authoritative pre-boundary state

Immediately before P821:

- `main == origin/main == 9b88e6b062cc1482a5622cd6d7624e8cb481179d`
- commit subject: `Add approved Part Pilot license`
- runtime: healthy, restart count 0, image
  `sha256:8e84272208f9a9cd4b8de0c103f9ff825da2ffc5b5a9925f897720d8852c6e5e`
- Alembic: `0022_mcp_inventory_part_lifecycle`
- root `LICENSE` SHA-256:
  `2c429a3b110b87bce60b90b9ef2068909ea60f3269a5d821f27a07b883d16ac7`
- `v1.0.0` tag: absent
- GHCR publication: not triggered
- GitHub Release: absent

P821 is documentation-only and must leave application/config/license/workflow bytes and
production deployment/data unchanged. After it succeeds, use the exact new P821 commit
as the publication candidate only after re-reading local state.

## What Chat 28 completed

### Release bootstrap and browser polish

P812 recovered the Docker-image identity false negative by comparing deterministic image
semantics instead of whole image IDs. It completed guarded fresh SQLite migration/seed,
initialized-database seed skip, fail-closed non-empty unversioned SQLite, fixed container
port `8000`, direct default `7890:8000` mapping and customer README cleanup. P813 changed
only the favicon to match the existing dark/mint Part Pilot `P` mark; the user explicitly
browser-approved it. P814 checkpointed that exact candidate.

### Stable image distribution package

P815 added the no-build release path:
- registry target `ghcr.io/devanshtangri/part-pilot`;
- `docker-compose.release.yml`;
- default host/container mapping `7890:8000`;
- persistent `/data`;
- repository-guarded tag-only GitHub Actions publication;
- `linux/amd64` + `linux/arm64`;
- exact stable tag + `latest`;
- provenance + SBOM.

No tag was created, so the workflow has never published a production package yet.

### Dependency reproducibility

P816 diagnosed floating dependencies and third-party distribution obligations. P817 then
froze the already-audited graph instead of upgrading it:
- all 13 direct Python requirements exact-pinned;
- 44-package Python runtime lock used by Docker;
- exact frontend P816 versions and recovered `package-lock.json`;
- Docker uses `npm ci`;
- Node and Python multi-architecture OCI indexes pinned by digest.

The locked candidate was externally rehearsed for both amd64 and arm64.

### Third-party compliance

P818's candidate was correct but its numbered patch failed pre-write because a generated
validator searched for `${ github.ref_name }` instead of the actual
`${{ github.ref_name }}`. P819 structurally validated the exact unchanged candidate and
checkpointed it.

The release package now includes:
- `THIRD_PARTY_NOTICES.md`;
- collected Python/frontend/Debian license and copyright text;
- 61 Debian source package/version pairs;
- 194 exact source archive URL/size/SHA-256 records totaling 313,263,250 bytes;
- companion `ghcr.io/devanshtangri/part-pilot-source:<version>` scratch image workflow;
- application-image compliance material under `/app/third_party/`.

AMD64 and ARM64 map to the same Debian source package/version set. The full source image
and multi-platform source build were rehearsed before checkpointing.

### Project license

The repository owner explicitly approved the exact custom:
`Part Pilot Source-Available License Version 1.0`
with copyright `2026 Devansh Tangri`. P820 added it as root `LICENSE` and to the image as
`/app/LICENSE`.

The license permits free personal, educational and internal organizational self-hosted
use, necessary operational/backup/migration copies, supported configuration, and builds
of unmodified source. It prohibits redistribution/public mirroring, modification or
derivative works, resale/product incorporation, and offering Part Pilot itself as a
third-party hosted/managed/SaaS product without separate written permission. Part Pilot
is source-available, not open source. Third-party materials retain their own licenses.

Release identity is fixed as:
- tag: `v1.0.0`
- GitHub Release title: `Part Pilot v1.0.0`
- classification: stable/final, **not** pre-release

## Chat 28 patch history

- P797 failed pre-write on stale P796 success evidence.
- P798 recovered the publication documentation package.
- P799 passed and its Users-dialog UI was browser-approved.
- P800 failed pre-write on stale P799 log/image assumptions.
- P801 recovered/checkpointed approved UI and customer README.
- P802 exposed missing fresh-container Alembic/seed bootstrap.
- P803 failed on unsupported host-Python tar `filter=` usage.
- P804 failed on stale baseline hashes; P805 diagnostic passed.
- P806/P807 failed during release-bootstrap recovery; P808/P809 diagnostics also failed
  on guessed schema/evidence assumptions; P810 diagnostic cleared the gate.
- P811 passed functional validation but failed on invalid whole-image-ID equality.
- P812 recovered with semantic image equivalence; P813 favicon passed/browser-approved;
  P814 checkpointed it.
- P815 prepared GHCR/release Compose.
- P816 audited dependency/license obligations.
- P817 locked dependencies/base images.
- P818 failed pre-write on the validator brace mismatch.
- P819 recovered/checkpointed the exact compliance package.
- P820 added/checkpointed the explicitly approved project license.
- P821 closes Chat 28 with documentation/handoff only.

## Product and data invariants to preserve

- Production SQLite is real and must never be treated as disposable.
- Preserve inventory, users, sessions, Projects, Reservations, movements, audits,
  settings, API keys, OAuth/direct-client credentials, backups and restore evidence.
- Legitimate user/admin DB/settings/MCP changes are mutable state; do not freeze or
  restore historical values merely because they changed after a prior patch.
- First-init Primary Owner is the only Owner and cannot be demoted, disabled or deleted.
- MCP remains 14 tools: six reads + eight safeguarded writes; no permanent-purge MCP tool.
- Currency remains display semantics only; timezone changes passive timestamp display
  only; neither rewrites stored historical values.
- Internal HTTP port stays fixed at `8000`; users change only the host side of the Docker
  mapping.
- Keep the browser-approved favicon and existing release-polished UI unchanged unless a
  genuine release blocker is found.

## Chat 29 required publication order

Publication is consequential. Do not collapse these gates.

1. Verify the exact clean P821 boundary, `HEAD == origin/main`, empty index/worktree,
   healthy runtime, Alembic `0022`, production SQLite integrity, exact root LICENSE and
   release/compliance artifacts.
2. Create **only** tag `v1.0.0` at the exact approved boundary commit and push that
   tag. Do not create the GitHub Release yet.
3. Observe the tag-triggered GitHub Actions workflow. Verify successful multi-platform
   publication of both:
   - `ghcr.io/devanshtangri/part-pilot:v1.0.0` and `:latest`;
   - `ghcr.io/devanshtangri/part-pilot-source:v1.0.0`.
4. Confirm both GHCR packages are **Public**. If GitHub creates them Private initially,
   change visibility deliberately before calling anonymous verification complete.
5. From an unauthenticated/clean pull context, verify image manifests include both
   `linux/amd64` and `linux/arm64`, and pull without registry credentials.
6. Verify application image payload:
   - `/app/LICENSE` exact SHA from P820;
   - `/app/third_party/` notice/license/source manifests;
   - fixed container port `8000`;
   - locked runtime/dependencies.
7. Verify source image payload contains all 194 manifest-listed archives with exact sizes
   and SHA-256 values and all 61 source package/version pairs.
8. Rehearse image-based release Compose on fresh data: migrate to 0022, seed exactly once,
   health/readiness, first-init path and SPA/protected routes.
9. Rehearse copied-production upgrade with a copied DB/secret only. Verify seed skip,
   Alembic/integrity, protected APIs, logical data preservation, credentials/settings,
   Primary Owner and 14-tool MCP invariants. Include validated backup/restore using only
   test-owned/copy data.
10. Record the exact published image digests and successful workflow/tag evidence in the
    durable docs.
11. Only after all above gates pass, publish the stable GitHub Release titled
    `Part Pilot v1.0.0` using the reconciled release notes.
12. Verify the public Release/tag/README/install links and absence of secrets/database
    artifacts.

If publication reveals a genuine blocker, fix it in the next sequential patch and
re-verify. After two consecutive pre-write failures/repeated anchor mismatch/uncertain
pending source, return to diagnostic-only escalation.

## Patch workflow

- Chat 29 owns exactly patches `822-846`; planned boundary is 846.
- Every implementation/fix/diagnostic/docs/checkpoint/commit/push/release action remains
  one complete sequential Python file under `fixes/`.
- Failed user-run scripts consume their patch number; never reuse one.
- A successful patch prints exactly `Everything PASS` as its final line.
- Normally the user runs numbered patches. Do not execute a numbered patch unless the
  user explicitly asks to execute that exact patch; if asked, run that exact command once
  and return raw terminal output only.
- Stage exact allowlists and verify `git diff --cached --check`.
- Browser-test source stays uncommitted until explicit approval.
- Preserve private `.env`, production DB and credentials; never reveal or rotate secrets.

## Immediate Chat 29 task

Start with Patch **822**. Re-read state and prepare the **tag/publication gate**. The first
consequential action should create/push only the exact `v1.0.0` tag after proving the
licensed P821 boundary. Then wait for and verify GHCR publication before any GitHub
Release is created.

## Ready prompt for the next chat

`Continue Part Pilot as Chat 29: Publish v1.0.0 and Verify GHCR Release. Start at Patch 822. Read docs/Chat_28_to_Chat_29_Handoff.md first, then docs/Checkpoint.md, docs/Implementation_Roadmap.md, docs/Part_Pilot_Project_Memory.txt, README.md, LICENSE, THIRD_PARTY_NOTICES.md, docs/Public_Alpha_Publishing_Checklist.md, docs/Public_Alpha_Release_Notes.md, docs/diagonostic_816_dependency_license_distribution_audit.md and exact local Git/runtime/Alembic/SQLite state. Treat Patch 821 as the authoritative licensed release-candidate boundary. Release identity is fixed as v1.0.0 / Part Pilot v1.0.0, stable not pre-release. First create/push only the exact v1.0.0 tag after proving the clean boundary; do not create the GitHub Release yet. Verify the tag-triggered amd64+arm64 application and corresponding-source GHCR packages, make/confirm both Public, prove anonymous pulls, validate /app/LICENSE and /app/third_party, verify all 194 SHA-pinned source archives, then run clean image-based fresh-install and copied-production upgrade/backup/restore verification. Publish the GitHub Release only after all remote artifact gates pass. Preserve real data/credentials, Primary Owner semantics, the 14-tool MCP model and mutable administrator state. Every change remains one sequential fixes/ Python patch; do not execute numbered patches unless I explicitly ask.`
