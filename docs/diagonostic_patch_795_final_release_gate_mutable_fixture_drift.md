# Patch 795 diagnostic — final release-gate mutable fixture drift recovery

<!-- PARTPILOT:DIAGONOSTIC_FINAL_RELEASE_GATE_MUTABLE_FIXTURE_DRIFT:V795 -->

## Boundary status

- This is the diagnostic-only recovery after repeated P791/P792/P793 release-gate failures and the consumed P794 diagnostic preflight failure.
- Patch 793 was the planned Chat 27 boundary but failed before documentation writes; **Chat 28 is not active yet**.
- Narrow high-safety recovery may continue beyond the planned numeric boundary until the failed boundary is recovered.
- Clean baseline: `91a188c33ac61371ddba71dac98062fba745b2df` (`Harden public alpha release documentation`), with `HEAD == origin/main` before this report.
- Runtime: `running|healthy|0|sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`.
- Production Alembic: `0022_mcp_inventory_part_lifecycle`; SQLite `quick_check=ok`; foreign-key violations `0`.
- No application source, deployment, database, settings, credentials, direct-client rows, or MCP permission values are changed by this diagnostic.

## Exact failure chain

### Patch 791

P791 reached copied-production smoke 11/44 and failed in `mcp_direct_bearer_transport_smoke_test`. The historical transport smoke requires the copied `mcp_direct_auth` table to contain only the migrated disabled legacy row. The current production database legitimately contains the legacy row plus a revoked named direct-client row, so a raw copied-production fixture violates that historical fixture assumption.

### Patch 792

P792 failed in preflight before build/smoke execution. Its evidence check searched for the literal phase label `copied-production regression 11/44 mcp_direct_bearer_transport_smoke_test`, but P791's log records the failing Docker command and traceback rather than that phase-label string. This was an evidence-contract defect, not a product failure.

### Patch 793

P793 corrected the P791/P792 issues, normalized the three legacy direct-transport copies, and progressed to smoke 20/44. It then failed in `mcp_named_direct_clients_smoke_test` because that smoke asserts `direct_clients_enabled == false` and `direct_no_auth_enabled == false` at fixture start. Production currently has `mcp.direct_clients_enabled=True` and `mcp.direct_no_auth_enabled=False`. These are legitimate mutable administrator settings, so the smoke is freezing migration/default state as though it were a production invariant.

### Patch 794

P794 correctly switched to diagnostic-only, but its own preflight incorrectly required the P792 *log file* to contain `Patch 791 failing smoke evidence is missing`. P792's logger records the commands completed before the failed in-memory assertion; the exception text exists in terminal output, not in that log. P795 therefore proves the P792 defect from the immutable P792 script plus the exact P792 log fingerprint, and proves the P794 defect from the immutable P794 script plus its exact log fingerprint.

## Current mutable MCP observation

- `mcp.enabled=True`
- `mcp.direct_clients_enabled=True`
- `mcp.direct_no_auth_enabled=False`
- `mcp.read_tools_enabled=True`
- `mcp.write_tools_enabled=True`
- `mcp.tool_permissions` retains the canonical fourteen-key boolean shape.
- Direct-client rows observed: `[(1, 'Legacy direct client', 'disabled', 0, None), (2, 'Public Alpha Direct Test', 'bearer_key', 0, '2026-08-27 10:25:24.348961')]`. This is mutable live state and must not be restored to older defaults merely to satisfy a smoke.

## Additional frozen-fixture assumptions found

The P793 normalization covered only three transport smokes. Source inspection found a fourth historical singleton assumption in `mcp_trusted_network_management_smoke_test`, so simply fixing smoke 20 would likely have produced another later failure.

- `backend/app/db/mcp_direct_bearer_transport_smoke_test.py`: historical-singleton anchor count `2`.
- `backend/app/db/mcp_direct_custom_header_transport_smoke_test.py`: historical-singleton anchor count `2`.
- `backend/app/db/mcp_direct_trusted_network_transport_smoke_test.py`: historical-singleton anchor count `2`.
- `backend/app/db/mcp_trusted_network_management_smoke_test.py`: historical-singleton anchor count `2`.

`mcp_named_direct_clients_smoke_test` separately contains the explicit `Direct clients/no-auth were not safely disabled by default` assertion.

## Evidence fingerprints

| Evidence | SHA-256 |
| --- | --- |
| `fixes/791_final_public_alpha_release_candidate_gate.py` | `e9882047408179097c7260b113f9c534e6f9e170aa73e428d75feb0224e847fa` |
| `fixes/logs/791_final_public_alpha_release_candidate_gate_20260828-064020.log` | `12b07165657e0b8c3539a9ddb6af3d8f2252e3277caa9d8a857d5c08aac7f8d0` |
| `fixes/792_recover_final_public_alpha_release_candidate_gate.py` | `ef8cf55bd1f3ae4aec53bc3a8c02e090558bf2234d1a5edefcf00272f8992448` |
| `fixes/logs/792_final_public_alpha_release_candidate_gate_20260828-064535.log` | `6e5b91be9f57b2fc4102d58630f68f9e25f8f5cc2671e1ea993c09e65495e8c0` |
| `fixes/793_recover_release_gate_and_complete_chat27_boundary.py` | `0b6dc17d932614d6f25d7d45ade99d0d3d1e9408746ada863b6eb298250fe3f8` |
| `fixes/logs/793_recover_release_gate_and_complete_chat27_boundary_20260828-065135.log` | `6dff88e90ab3bd3142174d6f88965d80429bb31890d53b3b031708f9d3d9cc0c` |
| `fixes/794_diagnose_final_release_gate_mutable_fixture_drift.py` | `2f9b40d3bca4c87f97677576d86e89300ad24da9feba2a2d450e7630a6bf1840` |
| `fixes/logs/794_diagnose_final_release_gate_mutable_fixture_drift_20260828-081055.log` | `197bd7d861e1f2b9341a64acea8e4d295b6466ee2c596deb95c1de51f3dfd78b` |

## Source/baseline fingerprints

| File | SHA-256 |
| --- | --- |
| `backend/app/db/mcp_direct_bearer_transport_smoke_test.py` | `bc91819c949132f74eecebbd5186c97e53085cd1bb9504f6eea05e035c4852ce` |
| `backend/app/db/mcp_direct_custom_header_transport_smoke_test.py` | `afa928f61e16270d84b8c1845c3107e8c1364afc56c984b75128749cb489271f` |
| `backend/app/db/mcp_direct_trusted_network_transport_smoke_test.py` | `4e9344f8294ba72b771ec8410cf98224de8968e99b9c227070b66b4c396862c2` |
| `backend/app/db/mcp_named_direct_clients_smoke_test.py` | `d6862720cd8016d614313538d148ccfded553266ff7ff465cde20e093b5b51de` |
| `backend/app/db/mcp_trusted_network_management_smoke_test.py` | `2726a9ea3b5c0e25b17d75eab28da4c5ebe10d244f4ad7591c663ca1a6a4ebc3` |
| `docs/Checkpoint.md` | `78c16afaf4510a1af52b41248648b56a3b4c3dd030a03b9dfe5cc4df41c01199` |
| `docs/Implementation_Roadmap.md` | `c5daa259b0c49ec5fbf51bf11438664892456ea2d81c3d048706aec5c7d3ada2` |
| `docs/Part_Pilot_Project_Memory.txt` | `d2d33b80a014ff8aaa15e9eab01727d11d5a991b1fb6229d0aceb39925c790ca` |
| `README.md` | `29c8f3c8aac8312148a3d436fd3ebd41a8c4339fe3772b117d19a6e2d36ca2e7` |
| `.env.example` | `86f0e298c584bb9c6e71447d6038c44f2c9a9efed15e66953449508eac56bbd2` |

## Safe Patch 796 recovery plan

1. Base recovery on the committed P795 diagnostic checkpoint, not on guessed P791/P792/P793/P794 state.
2. Keep product source and live data untouched. Treat `mcp.direct_clients_enabled`, `mcp.direct_no_auth_enabled`, named/revoked direct clients, and fourteen permission booleans as mutable administrator state.
3. Normalize **only isolated copied-production fixtures**:
   - for Bearer, custom-header, trusted-network transport, and trusted-network-management historical smokes, validate legacy row ID 1 then delete only `mcp_direct_auth` rows with `id <> 1` inside that smoke's copy;
   - for `mcp_named_direct_clients_smoke_test`, set only the copied fixture's `mcp.direct_clients_enabled` and `mcp.direct_no_auth_enabled` settings to false before the smoke so it starts from the historical default state it explicitly tests;
   - never apply those fixture normalizations to production.
4. Before launching the whole matrix, run those five affected smokes against separately normalized copied fixtures and require each to pass. This prevents another 20+-smoke delay from a known fixture adapter defect.
5. Then run the complete 44-smoke release matrix. Each smoke still receives an independent production copy; verify Alembic, SQLite, and the pre-smoke fourteen-key permission values for that normalized copy after execution.
6. Only after the entire release matrix passes should the boundary patch build final README/Checkpoint/Roadmap/repository-memory updates plus `docs/Chat_27_to_Chat_28_Handoff.md`, stage an exact allowlist, commit/push, and declare Chat 28 active.
7. The repository license remains an explicit owner decision. Do not auto-select licensing terms during boundary recovery.

## Conclusion

The observed failures are release-harness fixture drift against legitimate mutable production state, not evidence of a Part Pilot runtime regression. The next recovery must fix the fixture adapter comprehensively instead of adding one-off exceptions after each failed smoke.
