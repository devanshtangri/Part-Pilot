# Diagnostic 816 - Dependency, license and image-distribution audit

Generated: 2026-08-29T04:53:40.810846+00:00

## Status

Patch 816 is diagnostic-only. It audits the dependency/license surface after the Patch 815 `v1.0.0` GHCR distribution package was committed, without adding a project LICENSE, creating `v1.0.0`, publishing a container image or changing application/runtime/database state.

## Authoritative baseline

- Branch: `main`
- HEAD/origin before this diagnostic: `8757e35d461054cdbd0269c4c30837c63adf5829`
- Commit: `Prepare v1.0.0 container distribution`
- Approved runtime: `running|healthy|0|sha256:b5dda4a8bda732ccb00aed96d7f20f48e96a3a104e8120084d781a55176ef669`
- Alembic: `0022_mcp_inventory_part_lifecycle`
- SQLite quick check: `ok`
- Foreign-key violations: `0`
- MCP permission shape: `14` Boolean keys
- Primary Owner invariant: first user ID `1` remains the single active Owner
- `v1.0.0` tag: absent
- Project LICENSE/COPYING file: absent
- Release distribution package: present at `docker-compose.release.yml` and `.github/workflows/publish-container.yml`

## Reproducibility blocker before `v1.0.0`

The current dependency manifests are **not reproducible enough for a stable release build**.

### Python

`backend/requirements.txt` has 13 direct requirements:

- exact `==` pins: 4
- unpinned requirements: 9

Pinned:
- `Pillow==11.3.0`
- `passlib[bcrypt]==1.7.4`
- `bcrypt==4.0.1`
- `mcp==1.27.2`

Unpinned:
- `fastapi`
- `uvicorn[standard]`
- `SQLAlchemy`
- `alembic`
- `pydantic-settings`
- `python-dotenv`
- `python-multipart`
- `httpx`
- `cryptography`

### Frontend

`frontend/package.json` has 8 dependency/devDependency entries and all currently use `latest`. No `package-lock.json`, `yarn.lock` or `pnpm-lock.yaml` exists.

Top-level versions resolved during this diagnostic build:
- `@types/react` -> `19.2.17`
- `@types/react-dom` -> `19.2.3`
- `@vitejs/plugin-react` -> `6.0.5`
- `react` -> `19.2.8`
- `react-dom` -> `19.2.8`
- `react-router-dom` -> `7.18.2`
- `typescript` -> `7.0.2`
- `vite` -> `8.2.0`

Because the GHCR workflow builds from these manifests at tag time, a later registry state can produce a different dependency graph from the one tested before the tag. Dependency locking is therefore a release blocker, independent of licensing.

Recommended next implementation: pin/lock the Python release environment and commit a frontend lockfile with exact compatible dependency versions, then use deterministic install commands (for example `npm ci`) in the release build and re-run the complete candidate smoke suite.

## Python package license inventory from the approved runtime

Observed distributions: `45`.

MPL-family distributions: `certifi@2026.7.22`.

GPL/AGPL/LGPL/SSPL metadata findings: `none`.

The current Python environment is predominantly MIT/BSD/Apache/PSF-style licensing. `certifi` is MPL-2.0 and retains its own license obligations. No current Python distribution metadata identified a GPL/AGPL/LGPL/SSPL package.

## Frontend package license inventory

Observed packages in the diagnostic frontend builder: `35`.

License-expression counts:
- `0BSD`: `1`
- `Apache-2.0`: `3`
- `BSD-3-Clause`: `1`
- `ISC`: `1`
- `MIT`: `27`
- `MPL-2.0`: `2`

MPL-family packages: `lightningcss-linux-x64-musl@1.33.0, lightningcss@1.33.0`.

GPL/AGPL/LGPL/SSPL findings: `none`.

The current frontend graph is MIT/Apache/BSD/ISC/0BSD plus MPL-2.0 `lightningcss` components. No GPL/AGPL/LGPL/SSPL frontend package was detected. The result is time-sensitive until the frontend graph is locked.

## Container base-image obligations

The approved runtime contains `87` Debian packages and `84` shipped `/usr/share/doc/*/copyright` files. The copyright corpus includes GPL/LGPL-family material. Representative image-resident evidence includes:

- Bash: GPL-3+
- GNU coreutils: GPL-3+
- glibc (`libc6`): LGPL-2.1+ (with additional file-level terms/exceptions)
- APT: GPL-2+

These are licenses of **third-party components inside the container**, not licenses of Part Pilot's original source. Their presence does not by itself require Part Pilot's original application code to be licensed under GPL/LGPL. However, publishing the complete GHCR image is redistribution of those third-party binaries and requires compliance with their own notice/source-correspondence terms.

The image also contains MPL-2.0 components (`certifi`, and frontend-build `lightningcss` material). MPL is file-level copyleft: Part Pilot may remain separately licensed, but MPL-covered files/components and required notices/source availability must remain compliant.

## Project-license compatibility conclusion

No audited application dependency currently requires Part Pilot's **original application source** to be relicensed under an open-source/copyleft license. A custom source-available/proprietary Part Pilot license matching the repository owner's intent is technically compatible with this dependency set **provided that the license clearly applies only to Part Pilot original code/assets and expressly excludes third-party components, which remain under their own licenses**.

The intended Part Pilot terms recorded before this diagnostic are suitable as the basis for a later draft:

- free permission to download, install, self-host and use Part Pilot;
- operational/backup copies reasonably necessary for permitted use;
- no redistribution, republishing or mirroring of Part Pilot itself;
- no modification or derivative works of Part Pilot itself;
- no sale or incorporation of Part Pilot into another product;
- third-party components are excluded and remain governed by their respective licenses.

This diagnostic does **not** add those terms to the repository.

## Required release-compliance work before the tag

1. **Lock dependencies.** Replace floating Python/frontend resolution with a reproducible release dependency graph and revalidate the complete image.
2. **Create third-party notices.** Generate a durable `THIRD_PARTY_NOTICES`/license inventory for Python, bundled frontend dependencies and runtime/base-image components; do not claim Part Pilot's custom restrictions apply to those components.
3. **Establish source-correspondence handling for redistributed copyleft components.** Before public GHCR publication, define how required source/license materials for GPL/LGPL/MPL components in the distributed image will be supplied or referenced in a compliant way.
4. **Draft the Part Pilot LICENSE separately.** The exact custom terms and copyright-holder wording require explicit repository-owner approval before the LICENSE is written.
5. **Only then create `v1.0.0`.** Tagging triggers the GHCR workflow, so no tag should be created until dependency locking, notices/compliance and the exact project license are complete.

## Files and hashes audited

- `.env.example`: `6f9824b9a7f85e27e3662834f46a491555faeb1c94db886bf5da527a10bf4831`
- `README.md`: `49d2d493ff6d82baa04deb61c9e2110f917e3982d8f6a4ac93d2e4951b355f64`
- `backend/Dockerfile`: `8bc86b315d178e3b8b3bbc2a9f344b5959081c1d279b2a302dae01bdc158e61e`
- `backend/requirements.txt`: `788649083fbc0d66ff0fa05632ad0a2e55648948d5fbd88ee835f0c7cbb6dfc9`
- `docker-compose.release.yml`: `25cdaf7eab605abe820803fab7e878fdc76416d2d90354cf00b01d94466999fc`
- `.github/workflows/publish-container.yml`: `13ed974da3f564a1ccef477de52cb8e4af18cbc460943a48a4690fad2003d4db`
- `frontend/package.json`: `11556665d13373eb1baee1479229e86fafec9465459ed21864b8d9d2fd5ea498`
- `docs/Checkpoint.md`: `c098b909d4d0b1f6e9e3cbc4841a4ac815fdbafe181f4d283e3777a322bfb1df`
- `docs/Implementation_Roadmap.md`: `81813ed92fe540af561d8909dbabfac1bd79c891f6b23fffecd92483e202d90c`
- `docs/Part_Pilot_Project_Memory.txt`: `66814519d30bddeb3a61405cfb78e4f3dde6a8444e4541a29e6a9f2c853e1fa7`

## Diagnostic conclusion

The Patch 815 distribution package is structurally ready, but `v1.0.0` is **not yet ready to tag**. The two concrete pre-tag blockers are dependency reproducibility and third-party distribution compliance. The custom Part Pilot license can remain restrictive for Part Pilot's own code as long as third-party components are explicitly carved out and their licenses are honored independently.
