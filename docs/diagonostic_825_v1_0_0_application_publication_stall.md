# Diagnostic 825 - v1.0.0 application publication stall

<!-- PARTPILOT:DIAGONOSTIC_825_V1_0_0_APPLICATION_PUBLICATION_STALL -->

- Generated UTC: `2026-08-29T14:59:15+00:00`
- Release tag: `v1.0.0` -> `16439603e9e44e0622b30fe6357a7259668fbd90` (local and remote)
- Workflow run: `33250212228`
- Run status/conclusion: `in_progress` / `None`
- Run created/updated: `2026-08-29T11:28:39Z` / `2026-08-29T11:28:42Z`
- Publish job status/conclusion: `in_progress` / `None`
- Application publication step observed elapsed seconds: `12570`

## Exact workflow step state

| # | Step | Status | Conclusion | Started | Completed |
|---:|---|---|---|---|---|
| 1 | Set up job | completed | success | 2026-08-29T11:28:42Z | 2026-08-29T11:28:47Z |
| 2 | Validate stable release tag | completed | success | 2026-08-29T11:28:47Z | 2026-08-29T11:28:47Z |
| 3 | Check out release tag | completed | success | 2026-08-29T11:28:47Z | 2026-08-29T11:28:48Z |
| 4 | Set up QEMU | completed | success | 2026-08-29T11:28:48Z | 2026-08-29T11:29:01Z |
| 5 | Set up Docker Buildx | completed | success | 2026-08-29T11:29:01Z | 2026-08-29T11:29:05Z |
| 6 | Log in to GHCR | completed | success | 2026-08-29T11:29:05Z | 2026-08-29T11:29:06Z |
| 7 | Generate application image metadata | completed | success | 2026-08-29T11:29:06Z | 2026-08-29T11:29:07Z |
| 8 | Build and publish corresponding-source image | completed | success | 2026-08-29T11:29:07Z | 2026-08-29T11:29:43Z |
| 9 | Build and publish multi-platform application image | in_progress | None | 2026-08-29T11:29:43Z | None |
| 13 | Post Build and publish multi-platform application image | pending | None | None | None |
| 14 | Post Build and publish corresponding-source image | pending | None | None | None |
| 15 | Post Log in to GHCR | pending | None | None | None |
| 16 | Post Set up Docker Buildx | pending | None | None | None |
| 17 | Post Set up QEMU | pending | None | None | None |
| 18 | Post Check out release tag | pending | None | None | None |

## Anonymous GHCR probes

### `ghcr.io/devanshtangri/part-pilot:v1.0.0`
- Classification: `not-anonymously-pullable-403`
- Exit: `1`
- Digest: `unavailable`
- Platforms observed: `unavailable`
### `ghcr.io/devanshtangri/part-pilot:latest`
- Classification: `not-anonymously-pullable-403`
- Exit: `1`
- Digest: `unavailable`
- Platforms observed: `unavailable`
### `ghcr.io/devanshtangri/part-pilot-source:v1.0.0`
- Classification: `public-anonymous-success`
- Exit: `0`
- Digest: `sha256:28c4084c5e8d60efecb4db5986e204dd240a64efce3f935d3c860c091c81df77`
- Platforms observed: `linux/amd64, linux/arm64, unknown/unknown, unknown/unknown`

## Local source and workflow shape

- publish workflow SHA-256: `ae65d2358caa4c11abcf2a132649629a19cb3e81ca72194ecf18e9fe4b796e81`
- application Dockerfile SHA-256: `e3db5e26672f19f480b0ee3532674744c17e6bd0d5d0bea88c54c489eae54031`
- source publication step count: `1`
- application publication step count: `1`
- exact `linux/amd64,linux/arm64` contract count: `2`
- `docker/build-push-action@v6` count: `2`
- QEMU setup count: `1`
- Dockerfile `FROM` stage count: `2`
- Dockerfile `npm ci` count: `1`
- locked pip install count: `1`
- `EXPOSE 8000` count: `1`

Relevant application publication block shape remains:

```yaml
- name: Build and publish multi-platform application image
  uses: docker/build-push-action@v6
  with:
    context: .
    file: ./backend/Dockerfile
    platforms: linux/amd64,linux/arm64
    push: true
    provenance: mode=max
    sbom: true
```

## Findings

1. The immutable `v1.0.0` ref still resolves exactly to the licensed Patch 821 release boundary.
2. The corresponding-source publication step completed successfully before the application step. Anonymous GHCR inspection is captured above, so registry visibility is distinguished from workflow state.
3. The workflow has a single application publication step and it is the only main build/push step after the already-successful source image publication.
4. Local pre-release application builds in the recorded release patches validate native application semantics, but they do not provide enough evidence to identify the exact subcommand currently responsible for a remote emulated multi-platform stall.
5. Public GitHub API metadata exposes run/job/step state but not enough step log detail here to attribute an in-progress build to npm, pip, QEMU, BuildKit export, provenance/SBOM generation, or GHCR push. No fix should be guessed from timing alone.
6. No GitHub Release should be created while the application image gate is incomplete.

## Safe next-step plan

- If this exact workflow run completes successfully, the next patch should verify `v1.0.0` and `latest` anonymously, require amd64+arm64 manifests, capture immutable digests, and continue payload/source verification without rerunning publication.
- If the run completes with failure/cancellation/timeout, the next patch should consume the exact terminal conclusion and available public evidence before any recovery action.
- Do not delete, move, force-update, or recreate `v1.0.0` automatically. The release tag is already public and immutable for this workflow.
- Do not modify the workflow merely to retry a transient remote failure. A workflow-source defect at the already-tagged commit requires an explicit release-identity/recovery decision because a main-branch workflow edit cannot retroactively change the tagged workflow bytes.
- Do not create the GitHub Release until both application and source GHCR packages pass the public anonymous multi-platform and payload gates.

## Safety result

This diagnostic intentionally changes documentation only. It does not mutate the tag, workflow, application source, production deployment, SQLite data, registry packages, or GitHub Release.
