# Chat 24 to Chat 25 Handoff

<!-- PARTPILOT:CHAT24_TO_CHAT25_HANDOFF:V710 -->

## Chat 25 identity

- Title: `Chat 25: Integration Live Sync Recovery and Public Alpha Hardening`
- Patch range: `711-735`
- First patch: `711`
- Planned boundary: `735`

## Authoritative starting state

Patch 710 is documentation/diagnostic-only. After it succeeds:

- local `HEAD` and `origin/main` are the authoritative Chat 25 starting commit;
- application source/index are clean;
- runtime remains `sha256:b5463f3510d38abd50851a391528abf53fe6f926485069e7f5a74c27bbff5d53`;
- Alembic remains `0016_mcp_tool_permissions`;
- live SQLite/security/settings/MCP state remain mutable and must not be frozen.

Read these first:

1. `docs/Chat_24_to_Chat_25_Handoff.md`
2. `docs/diagonostic_710_oauth_manageable_fixture_contract.md`
3. `docs/Checkpoint.md`
4. `docs/Implementation_Roadmap.md`
5. `docs/Part_Pilot_Project_Memory.txt`
6. `README.md`

## Chat 24 completed milestones

Browser-approved/checkpointed live sync:

- Patch 699: Inventory / Part Manager + History
- Patch 702: Projects + Reservations
- Patch 704: Dashboard
- Patch 706: Settings preferences/account/manual-backup status

Shared transport remains authenticated fetch/ReadableStream SSE with
generation/sequence replay/resync, degraded polling fallback and same-origin
BroadcastChannel relay/deduplication.

## Consumed integration recovery sequence

- **707:** stale manageable response-field smoke contract.
- **708:** pre-write durable-log evidence-contract mistake.
- **709:** hard-coded historical connected OAuth client IDs 9 and 13.

All three rolled back to the clean Patch 706 application checkpoint.

## Patch 711 first objective

Recover the final REST API-key + MCP integration live-sync slice.

First make `mcp_oauth_manageable_smoke_test` fixture-owned:

- create a registered fixture;
- create a separate connected fixture with
  `register_client -> grant_consent -> issue_authorization_code ->
  exchange_authorization_code`;
- assert generated fixture IDs only;
- revoke the registered fixture for revoked-state coverage;
- clean only manifest-owned session/client/consent/code/token/audit rows;
- prove the copied DB logical snapshot is restored exactly.

Then reapply the already-rehearsed integration live-sync candidate and rerun the
full copied-DB smoke set.

## Integration behavior intended by the pending slice

REST API keys:

- create/edit/rotate/revoke publish `integrations.api_keys + history`;
- no secret value enters an invalidation event;
- other Settings tabs refetch API-key summaries without clearing local dialogs.

MCP:

- settings/global permissions/client permissions/direct-client lifecycle and
  OAuth registration/revocation publish `integrations.mcp + history`;
- credential reveal operations update History only;
- external OAuth registration/consent/first token/revocation updates MCP state;
- routine refresh-token rotation updates `integrations.mcp` without noisy
  History invalidation;
- unsaved MCP server/tool-permission drafts survive cross-tab refetch.

Browser-test source remains uncommitted until approval.

## After integration live sync

Continue public-alpha work in this order unless new diagnostic evidence requires
a narrower recovery:

1. API docs/OpenAPI exposure/schema hardening
2. whole-inventory Stored Parts metrics + Dashboard Stock alert dialog
3. Owner/Admin/Operator/Viewer roles
4. safeguarded MCP write tools
5. final alpha regression

Notifications & Messaging remain post-v1.
