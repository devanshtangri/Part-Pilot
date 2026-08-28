# Chat 27 to Chat 28 Handoff

<!-- PARTPILOT:CHAT27_TO_CHAT28_HANDOFF:V796 -->

## Boundary

- Closing chat: `Chat 27: User Management UI and Public Alpha Release Candidate`
- Planned boundary was Patch 793; it failed during the final copied-production gate.
- Authoritative recovered boundary patch: `796_recover_final_release_gate_and_complete_chat27_boundary.py`
- Authoritative diagnostic: `docs/diagonostic_patch_795_final_release_gate_mutable_fixture_drift.md`
- Next chat: `Chat 28: Public Alpha Release and Post-v1 Planning`
- Next patch range: `797-821`
- First patch: `797`
- Planned boundary: `821`

After Patch 796 succeeds, inspect exact local Git/index, runtime, Alembic, production
SQLite, this handoff and the Patch 795 diagnostic before trusting volatile hashes. The
successful boundary commit hash is intentionally not pre-guessed here.

## Authoritative release-candidate state

- Branch `main`; working tree/index clean; local HEAD must equal `origin/main`.
- Runtime image remains `sha256:fa265f69c32b784172f8fc46819ea484c0170dbd4df13b3c8fbd6bcd86711f37`, healthy with restart count 0.
- Production Alembic remains `0022_mcp_inventory_part_lifecycle`.
- MCP catalogue remains 14 tools: six reads + eight safeguarded writes; there is no
  permanent purge/hard-delete/recycle-bin-empty MCP tool.
- Live MCP permission booleans, OAuth/direct clients, no-auth/direct-client settings
  and normal application data are mutable administrator/user state. Never pin or
  restore historical defaults merely because copied smoke fixtures expect them.
- The first-init Primary Owner remains the only Owner and cannot be demoted, disabled
  or deleted. Managed-user role assignment never offers Owner.
- Settings role visibility, Users & Roles UI, browser-approved release polish,
  responsive registers, History deep-links, in-field credential copy controls,
  semantic Settings icons and Connections optical centering are approved.
- Patch 777 and recovered Patch 796 provide the full automated release matrices; real
  Claude OAuth verification provides external MCP discovery/read/write-preview-confirm evidence.

## Final-gate recovery lessons

P791/P793 failures were caused by historical smoke fixtures freezing legitimate mutable
production state, not by a Part Pilot runtime regression. Patch 795 identified the
complete adapter before another gate attempt:
- four historical singleton smokes (`mcp_direct_bearer_transport_smoke_test`,
  `mcp_direct_custom_header_transport_smoke_test`,
  `mcp_direct_trusted_network_transport_smoke_test`, and
  `mcp_trusted_network_management_smoke_test`) receive isolated copies where legacy
  row ID 1 is validated and only `id <> 1` rows are removed;
- `mcp_named_direct_clients_smoke_test` receives an isolated copy where only
  `mcp.direct_clients_enabled` and `mcp.direct_no_auth_enabled` are set to false so
  it can verify opt-in/default semantics;
- all five adapters are rehearsed before the 44-smoke matrix;
- production rows/settings are never changed by fixture normalization.

P792/P794 were evidence-model failures: terminal exception text is not automatically
stored in command logs. Future evidence contracts must validate what the patch actually
persists—exact scripts, command logs, diagnostics and committed state—not assumed console text.

## Public-alpha release evidence

- 44 copied-production backend release smoke invocations pass at the recovered P796 boundary.
- Canonical build reproduces the approved V785 image and Alembic head.
- Backup/restore, roles, sessions, API scopes, inventory lifecycle, Projects,
  Reservations, History/live-sync, MCP OAuth/direct transports, permissions and all
  safeguarded writes are covered.
- Browser release-polish batch P779-P785 is approved.
- Claude exposed all six reads + eight safeguarded writes and successfully exercised
  guarded metadata preview/confirmation; no permanent delete tool was exposed.
- Hermes event-loop failure remains client/runtime-side after Part Pilot MCP worked
  from inside the Hermes container against the public endpoint.
- Repository release hygiene is complete. No `LICENSE` is present; do not choose one
  without an explicit repository-owner decision.

## Chat 28 priorities

1. Inspect this handoff first, then Checkpoint, Roadmap, repository memory, README,
   the Patch 795 diagnostic and exact local state.
2. Prepare the public-alpha publishing/release package and release notes from the
   verified P796 candidate. Do not redesign product behavior merely for release ceremony.
3. Ask for and record the repository-owner licensing decision before adding a license.
4. Preserve production data, credentials and mutable MCP settings. Fix only genuine
   release blockers found during publishing/distribution.
5. Notifications & Messaging remain post-v1 unless explicitly reprioritized.

## Ready prompt for the next chat

`Continue Part Pilot as Chat 28: Public Alpha Release and Post-v1 Planning. Start at Patch 797. Read docs/Chat_27_to_Chat_28_Handoff.md first, then docs/Checkpoint.md, docs/Implementation_Roadmap.md, docs/Part_Pilot_Project_Memory.txt, README.md, docs/diagonostic_patch_795_final_release_gate_mutable_fixture_drift.md and exact local Git/runtime/Alembic/SQLite state. Treat Patch 796 as the authoritative recovered Chat 27 public-alpha release-candidate boundary. Prepare the public-alpha publishing/release package and release notes without changing product behavior unless a genuine release blocker is found. Do not add a LICENSE until I explicitly choose licensing terms. Preserve the 14-tool MCP model, Primary Owner semantics, approved browser polish, real data/credentials and mutable MCP settings. Every change remains one sequential fixes/ Python patch; do not execute numbered patches unless I explicitly ask.`
