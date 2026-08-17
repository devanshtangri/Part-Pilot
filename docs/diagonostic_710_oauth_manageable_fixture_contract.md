# Diagnostic 710 - OAuth Manageable Smoke Fixture Contract

<!-- PARTPILOT:OAUTH_MANAGEABLE_FIXTURE_DIAGNOSTIC:V710 -->

## Boundary state

- Chat: `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
- Patch: `710`
- Baseline HEAD/origin: `5b2ba66a8e95c1e28c37db3b0039f7bb637cbea5`
- Runtime: `image=sha256:b5463f3510d38abd50851a391528abf53fe6f926485069e7f5a74c27bbff5d53 health=healthy restart=0`
- Alembic: `0016_mcp_tool_permissions`
- Git/index: clean before this documentation-only diagnostic
- Application source: exact Patch 706 checkpoint; no Patch 707/708/709 app source survived rollback

## Failure chain

### Patch 707

The integration live-sync candidate reached copied-database smoke testing.
`mcp_oauth_manageable_smoke_test` rejected the current response schema because
its `EXPECTED_FIELDS` omitted `denied_tools` and `tool_permissions`.

The application schema/service already exposed those fields. This was a stale
smoke contract, not an integration-live-sync behavior failure.

### Patch 708

Patch 708 attempted to recover the smoke contract but failed in preflight before
writes. It incorrectly required terminal-only `Phase:` and rollback-summary
text to be present inside the durable Patch 707 log.

Durable logs contain patch progress plus command stdout/stderr; terminal-only
exception/rollback prose must not be required as persisted evidence.

### Patch 709

Patch 709 corrected the evidence contract and updated the manageable response
field validation. It then exposed a second independent stale smoke assumption:

```text
by.get(9, {}).get("status") == "connected"
by.get(13, {}).get("status") == "connected"
```

The copied database is intentionally based on real mutable production data.
Hard-coding historical client IDs/statuses is therefore invalid.

## Read-only live observation at Patch 710

This state is diagnostic evidence only and is explicitly mutable. Future patches
must not freeze these IDs/statuses as prerequisites.

```json
{
  "active_consents": [
    {
      "client_id": 17,
      "count": 1
    },
    {
      "client_id": 24,
      "count": 1
    },
    {
      "client_id": 25,
      "count": 1
    }
  ],
  "clients_9_13": [
    {
      "client_name": "Claude",
      "id": 9,
      "registered_by_user_id": null,
      "revoked_at": "2026-08-07 10:37:52.738533"
    },
    {
      "client_name": "ChatGPT",
      "id": 13,
      "registered_by_user_id": null,
      "revoked_at": "2026-08-07 10:42:00.916069"
    }
  ],
  "token_counts": [
    {
      "client_id": 9,
      "total": 3,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 13,
      "total": 1,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 19,
      "total": 1,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 21,
      "total": 1,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 22,
      "total": 2,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 23,
      "total": 1,
      "unrevoked": 0,
      "user_id": 1
    },
    {
      "client_id": 24,
      "total": 1,
      "unrevoked": 1,
      "user_id": 1
    },
    {
      "client_id": 25,
      "total": 2,
      "unrevoked": 1,
      "user_id": 1
    }
  ]
}
```

At this observation, clients 9 and 13 are revoked, while currently active
consent/token state belongs to other client IDs. That directly explains Patch
709's `legacy connected clients missing` failure.

## Exact diagnosed smoke shape

`backend/app/db/mcp_oauth_manageable_smoke_test.py` currently:

- creates one test-owned **registered** OAuth client;
- verifies **connected** status by assuming historical clients 9 and 13;
- revokes the test-owned registered fixture to cover **revoked** status;
- restores the copied database to its original logical snapshot.

The connected-status assertion is the only portion that depends on unrelated
live OAuth identities.

## Safe Patch 711 recovery plan

Patch 711 must start from this clean boundary and recover the final integration
live-sync slice without depending on any existing OAuth client ID.

1. Keep the existing test-owned registered fixture and registered-to-revoked
   endpoint coverage.
2. Add a separate test-owned connected fixture using canonical OAuth services:
   `register_client` -> `grant_consent` -> `issue_authorization_code` ->
   `exchange_authorization_code`.
3. Capture the generated client ID and assert that exact fixture reports
   `status="connected"`.
4. For the connected fixture, validate active consent/token counts, scopes,
   permission fields and ownership semantics from the fixture's own setup.
5. Remove all `by.get(9, ...)` / `by.get(13, ...)` assumptions.
6. Maintain a manifest of only test-owned session/client/consent/code/token/audit
   IDs and clean those exact rows.
7. Prove the copied database's logical snapshot is equivalent after cleanup.
8. Reapply the already rehearsed six-file Patch 709 candidate:
   API-key route, MCP Settings route, MCP OAuth route, API-key component,
   Settings page, and corrected manageable OAuth smoke.
9. Rerun API-key, MCP settings/permissions/direct/OAuth, live-sync and complete
   copied-database smoke before deployment.
10. Leave browser-test application source uncommitted until explicit approval.

## Live-sync implementation status

Browser-approved and checkpointed in Chat 24:

- Inventory / Part Manager + History
- Projects + Reservations
- Dashboard
- Preferences / Account / manual-backup status

Still pending browser proof:

- REST API-key administration via `integrations.api_keys`
- MCP administration/OAuth lifecycle via `integrations.mcp`

No routine Refresh-control removal should occur until the final integration
slice is browser-proven.

## Public-alpha work after integration recovery

After the integration live-sync slice is approved/checkpointed:

1. `/docs`, `/redoc`, `/openapi.json` public-alpha hardening
2. whole-inventory Stored Parts metrics + Dashboard Stock alert dialog
3. Owner/Admin/Operator/Viewer roles
4. safeguarded MCP write tools
5. final alpha accessibility/security/responsive/API/MCP regression

Notifications & Messaging remain post-v1.
