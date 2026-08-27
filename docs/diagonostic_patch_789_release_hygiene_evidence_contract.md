# Patch 789 diagnostic — release-hygiene evidence contract

<!-- PARTPILOT:DIAGONOSTIC_RELEASE_HYGIENE_EVIDENCE_CONTRACT:V789 -->

## Status

- Diagnostic-only escalation after two consecutive pre-write failures: Patch 787 and Patch 788.
- Clean baseline before this report: `0461142daa46bfb22c1ea8c6ad8a9d3ed147d439` (`Checkpoint public alpha release polish`).
- `HEAD == origin/main` before diagnostic write.
- Runtime: `running|healthy|0|sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`.
- Alembic: `0022_mcp_inventory_part_lifecycle`; SQLite `quick_check=ok`; foreign-key violations: `0`.
- Application source, live database, deployment, settings, credentials and MCP permissions were not modified by either failed patch.

## Exact evidence fingerprints

| Evidence | SHA-256 |
| --- | --- |
| Patch 786 script | `537176ac20aefba921483edb0a5e9a5b27a02795e87986703ef092b4662ce201` |
| Patch 786 final log | `e8b31cb613c2bb2cbbbeca2063639784de30cce57dad6e0f191c15414bc42d28` |
| Patch 787 script | `f7181ee49e939a955cc8ea953df291ca158185b15901b7f17c184a77ce14df02` |
| Patch 787 failure log | `d46308dab7595b48cb34555600f6aca14cc6bf58a9380b68562705096e571bb8` |
| Patch 788 script | `0644560f1cd5f1395bc87c484690816e29fa7a4bc9f76af529d12c21bf272000` |
| Patch 788 failure log (misnamed with the P787 prefix) | `6631a9d2dc295a901bded613dd034a182b1715c73acb8d98e5744b980ae178c1` |
| committed `.env.example` | `3364f618f6063b4219b1ec6d34989ea1f0ea4c7906d0d9b8b96e3ba665cb46c8` |
| committed `README.md` | `07d783338fd332c38a7fc9f5d7a774e1b948a94c921885dd52b857ab53d489a1` |
| committed `docs/Checkpoint.md` | `4128efe9967fe349e0aa7a7092d6ec4e0159a99030389b7472a4602b85a1b9ac` |
| committed `docs/Implementation_Roadmap.md` | `ae59d053e9a1f9bd1c54f91c6cf1333839fab1a24fc77133a09e0a38188d11de` |
| committed `docs/Part_Pilot_Project_Memory.txt` | `505db8f891a03840ab77ebb91ff3ec7e1dfc8dbffaf2060a39701830dc2cc535` |

## Failure 1 — Patch 787

Patch 787 failed before writes because its embedded `.env.example` baseline was stale:

- embedded P787 fingerprint: `e4562cf74efddbc44be208741ed6f86e9b3078fcb745c2a12384ce0936a0f7a2`;
- actual committed P786 fingerprint: `3364f618f6063b4219b1ec6d34989ea1f0ea4c7906d0d9b8b96e3ba665cb46c8`;
- stale fingerprint anchor count in P787: `1`;
- actual fingerprint anchor count in P787: `0`.

The P787 failure log records `Baseline fingerprint changed: .env.example` and a clean P786 rollback.

## Failure 2 — Patch 788

Patch 788 corrected the `.env.example` baseline but introduced/retained two independent evidence-contract defects before any release-hygiene write:

1. It pinned Patch 786's log to `024b6b725f19608b86ce354c2ddd6c869027cc1316fd100fafdd4b78cf785d96`, while the actual final Patch 786 log is `e8b31cb613c2bb2cbbbeca2063639784de30cce57dad6e0f191c15414bc42d28`. The wrong anchor occurs `1` time(s), and the actual final log hash occurs `0` time(s) in P788.
2. Its `State` logger and backup directory still use Patch 787 names. The bad logger anchor occurs `1` time(s), and the bad backup anchor occurs `1` time(s). Therefore the actual P788 failure log is `fixes/logs/787_harden_public_alpha_release_documentation_20260827-223653.log` rather than a `788_...` log.

The P788 failure log records `Patch 786 log evidence changed` and a clean P786 rollback.

## Source/block shape verified

The P788 preflight sequence is structurally sound around Git/root/branch/origin/HEAD/index/source checks, but the evidence constants above are wrong. Its write/commit path was never reached. The recovery should not weaken preflight; it should replace the incorrect evidence values/names and regenerate the durable-document candidate from the now-authoritative state.

## Safe implementation plan for Patch 790

1. Base Patch 790 on the committed Patch 789 diagnostic checkpoint, not on an assumed P786 HEAD.
2. Require the exact P787 and P788 failure evidence plus this V789 diagnostic report.
3. Use the actual committed `.env.example` hash `3364f618f6063b4219b1ec6d34989ea1f0ea4c7906d0d9b8b96e3ba665cb46c8` and actual final Patch 786 log hash `e8b31cb613c2bb2cbbbeca2063639784de30cce57dad6e0f191c15414bc42d28` only where historical P786 evidence is still needed.
4. Give P790 its own `790_...` log and `patch_790_...` backup paths; assert those names before any writes.
5. Rebuild the five release-hygiene candidates from the exact post-P789 baseline so durable docs accurately say P787 and P788 failed, P789 diagnosed them, and P790 is the recovery. Do not reuse the stale P787/P788 durable-document payload bytes.
6. Keep the change set limited to `.env.example`, `README.md`, `docs/Checkpoint.md`, `docs/Implementation_Roadmap.md`, and `docs/Part_Pilot_Project_Memory.txt`; the V789 diagnostic report remains immutable evidence.
7. Validate release wording, repository hygiene, `git diff --check`, exact staged allowlist, canonical Docker image equivalence, Alembic/SQLite integrity, protected/live health and mutable 14-tool permission shape before commit/push.
8. Preserve the unresolved software-license choice as a repository-owner decision; do not auto-select a license.

## Diagnostic conclusion

The release-hygiene content itself has not reached the live source. Both failures are wrapper/evidence-contract failures, not application, database, MCP, Docker-runtime, or release-feature regressions. The clean P786 application/runtime baseline remains intact; Patch 790 may resume implementation only after this diagnostic checkpoint succeeds.
