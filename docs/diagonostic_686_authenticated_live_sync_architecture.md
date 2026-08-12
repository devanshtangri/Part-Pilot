# Diagnostic 686 — Authenticated live-sync architecture

Generated: `2026-08-12T13:55:51+00:00`

## Boundary and safety state

- Chat: `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
- Patch range: `686-710`
- Diagnostic baseline: `da17de4bd46899ee3185e1dcca6610b48fcdc42b` (`Complete Chat 23 boundary`)
- Runtime: `image=sha256:7a285a3ebb7eccf9eddb7c375a2b5616773e5aa40283ce270e41aff445ad23b9 health=healthy restart=0`
- Alembic: `0016_mcp_tool_permissions (head)
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.`
- Production SQLite passed `PRAGMA quick_check` and `PRAGMA foreign_key_check` at diagnostic start.
- Working tree and index were clean before the report write.
- Patch 686 performs **no application-source, database, deployment, credential, Settings, or MCP-policy mutation**.
- The only tracked write is this diagnostic report. The report is committed and pushed with an explicit one-file staged allowlist.

## Verified frontend authentication shape

`frontend/src/auth/AuthContext.tsx` owns the signed-in session token. The token is persisted under `AUTH_TOKEN_STORAGE_KEY` in `localStorage`, hydrated on startup, cleared on logout, and passed to API clients as a Bearer credential.

That makes native browser `EventSource` the wrong transport for Part Pilot: the current auth contract requires an `Authorization: Bearer ...` header, while native `EventSource` does not provide a general custom-request-header hook. Putting the session token in a query string would weaken the existing auth model and is rejected.

**Chosen transport:** an SSE-compatible response consumed with authenticated `fetch()` plus `ReadableStream` parsing.

Recommended browser request shape:

```text
GET /api/live/events
Authorization: Bearer <existing session token>
Accept: text/event-stream
Last-Event-ID: <generation>:<sequence>   # reconnect only
Cache-Control: no-cache
```

The stream must never carry the token, API keys, MCP credentials, record bodies, audit metadata containing secrets, or other sensitive full records.

## One shared frontend stream

The application currently mounts `AuthProvider` above `AppearanceProvider` and all authenticated routes. The implementation should introduce one `LiveSyncProvider` inside the authenticated provider tree, not one stream per page.

Required provider behavior:

1. Start exactly one stream when a valid auth token is present.
2. Abort the old stream immediately on logout, token replacement, provider unmount, or auth loss.
3. Parse standard SSE fields (`id`, `event`, `data`) from the authenticated fetch body.
4. Keep the last accepted event ID in memory for same-page reconnects. A full browser reload already performs fresh page queries and does not need stale replay persisted across sessions.
5. Reconnect with bounded exponential backoff and jitter.
6. Coalesce repeated topic invalidations briefly so a batch mutation does not create a refetch storm.
7. Use polling only while streaming is degraded; stop polling when streaming recovers.
8. Keep current explicit `Retry` behavior and routine `Refresh` controls during the browser-test phase.

## Reconnect, replay and polling fallback

Use a small in-process broker with:

- a process-generation identifier,
- a monotonically increasing sequence,
- a bounded replay ring,
- per-topic revision counters,
- subscriber queues,
- heartbeat/keepalive output.

Recommended event ID: `<process-generation>:<sequence>`.

Recommended compact event:

```text
id: <generation>:<sequence>
event: invalidate
data: {"topics":["inventory","history"],"resource":{"type":"part","id":123}}
```

`resource` is optional and may contain only non-sensitive type/ID hints. The topics are the authoritative refetch signal.

Add a protected lightweight `GET /api/live/state` endpoint returning only the process generation and topic revisions. It serves two purposes:

- polling fallback compares revisions and dispatches the same local topic invalidations;
- reconnect can resynchronize when the previous event ID is from another process generation or has fallen out of the replay ring.

If the reconnect ID is still in the ring, replay later matching events. If it cannot be replayed safely, emit a resync signal rather than pretending no events were missed.

A practical starting fallback cadence is about 30 seconds while streaming remains unavailable, while the stream itself continues retrying with a capped backoff. Exact timings belong in the implementation constants and smoke/browser evidence rather than in user preferences.

## Current deployment topology

The canonical `backend/Dockerfile` launches:

```text
exec uvicorn app.main:app --host 0.0.0.0 --port ... --no-proxy-headers
```

There is no configured Gunicorn layer and no Uvicorn `--workers` option. Therefore the verified production topology is currently one application process, so an in-memory invalidation broker is suitable for this V1 deployment.

**Future constraint:** if Part Pilot later runs multiple application workers/containers, the broker must move to shared pub/sub or an outbox-style mechanism. Do not silently scale the current in-memory broker across workers.

## Critical maintenance/restore interaction

`LifecycleRequestMiddleware` counts every non-probe HTTP request as active until its ASGI response finishes. Restore commit enters maintenance and waits for all requests except its own (`max_active_requests=1`) to drain.

A normal infinite SSE response would therefore block restore.

The live stream must remain lifecycle-accounted **and cooperatively terminate when `application_lifecycle` leaves `ready`**. Do not exempt `/api/live/events` from request accounting. The stream loop should wake frequently enough to observe maintenance/shutdown, close the response, let the middleware decrement `active_requests`, and allow restore/shutdown to drain normally.

The backend live-sync smoke must explicitly prove:

- authenticated stream admission,
- unauthenticated rejection,
- event framing,
- replay/resync behavior,
- state/poll revisions,
- disconnect cleanup,
- maintenance causes a connected stream to exit and drain,
- no database mutation is required for broker operation.

## Existing stale-request and manual-recovery seams

The current pages already expose reload/version seams and, on the highest-risk list/detail surfaces, request IDs and/or `AbortController` cancellation. Live invalidation should increment/call those existing seams rather than replacing their stale-response defenses or resetting UI state.

| Surface | Refresh literals | Retry literals | AbortController refs |
|---|---:|---:|---:|
| `frontend/src/pages/Dashboard.tsx` | 2 | 0 | 0 |
| `frontend/src/pages/PartManager.tsx` | 2 | 0 | 0 |
| `frontend/src/pages/Projects.tsx` | 2 | 0 | 2 |
| `frontend/src/pages/Reservations.tsx` | 1 | 1 | 4 |
| `frontend/src/pages/History.tsx` | 1 | 0 | 2 |
| `frontend/src/pages/Settings.tsx` | 0 | 6 | 0 |
| `frontend/src/components/McpDirectClientsSection.tsx` | 0 | 1 | 0 |
| `frontend/src/components/ApiKeySettingsSection.tsx` | 0 | 1 | 0 |

`Refresh`/`Retry` counts above are architecture evidence only; they are not a removal list. Routine Refresh controls remain until each corresponding live path is browser-proven. Retry remains for explicit errors.

## Topic contract

Use compact semantic topics rather than endpoint names:

| Topic | Primary invalidators | Primary subscribers |
|---|---|---|
| `inventory` | part create/edit/quantity/delete/restore/purge; reservation/project stock transitions | Dashboard stock alert/search, Stored Parts/Part Manager, open stock-dependent pickers/details |
| `catalogues` | Part Types, Locations, Manufacturers, Packages | Part Manager and create/edit selectors |
| `projects` | Project create/edit/reserve/consume/cancel/delete lifecycle | Projects, Reservation/stock-dependent project details |
| `reservations` | Reservation create/edit/cancel/consume/expiry transitions | Reservations, Projects where status/availability is shown |
| `history` | business/audit-producing mutations | History |
| `preferences` | Search/Inventory/Reservation/Appearance/Currency/Timezone preference changes and resets | Settings, Appearance/Auth regional state, affected page formatting/defaults |
| `account` | profile/avatar/password/session administration | Auth/account Settings |
| `integrations.api_keys` | API key create/edit/rotate/revoke | API-key administration |
| `integrations.mcp` | MCP server/permission/OAuth/direct-client administration | MCP Settings/administration |
| `backups` | backup creation/status mutations and restore lifecycle | Data/backup Settings |

One successful business mutation may publish several topics in one event. For example a stock-changing reservation consume can invalidate `reservations`, `inventory`, `projects` when applicable, and `history`.

## Publishing boundary

Publish invalidation **after the durable mutation has committed**. Never emit before commit and never make successful business writes depend on whether a browser subscriber exists.

For the current codebase, the safest first implementation is explicit publish calls at the successful route/service boundary after the existing committing operation returns. Keep the topic mapping centralized so nested business actions emit one coherent multi-topic invalidation instead of duplicating endpoint-specific knowledge everywhere.

The same helper must later be used by safeguarded MCP write tools; otherwise browser clients would miss external MCP mutations.

Same-tab post-mutation reload plus a received invalidation may temporarily cause a duplicate safe refetch. Correctness takes priority in the first browser-proven slice. Do not add a cross-client origin-ID protocol unless real request-volume evidence justifies it.

## Targeted frontend behavior

- **Dashboard:** `inventory` invalidates the current low-stock/stock-alert data and any currently active inventory search without clearing the search query.
- **Stored Parts / Part Manager:** `inventory` increments the existing inventory refresh sequence; `catalogues` reloads only affected catalogue choices. Preserve search, filters, sort, page size/offset and selected record.
- **Projects:** `projects` refreshes the current list/detail through existing request guards. Relevant `inventory`/`reservations` changes may refresh selected stock-dependent detail without resetting status filter/page/selection.
- **Reservations:** `reservations` refreshes current list/detail/activity through existing request guards. Preserve section/filter, offset and selected reservation.
- **History:** `history` reloads the current page and filter options through existing request guards without forcing page/filter reset.
- **Settings:** subscribe by subtopic so Preferences, Account, API keys, MCP administration and Backup status do not all refetch for unrelated changes.
- **Appearance/Auth regional state:** `preferences` must keep the shared theme/currency/timezone presentation synchronized across tabs without rewriting stored timestamps or historical currency snapshots.

## Verified mutation surfaces

The current mutation decorators found in the authoritative baseline are listed below. They are an implementation map, not a requirement to wire every route in one risky patch.

### `backend/app/api/routes/parts.py`

- `POST /api/parts`
- `POST /api/parts/deleted/purge`
- `POST /api/parts/{part_id}/restore`
- `DELETE /api/parts/{part_id}`
- `POST /api/parts/{part_id}/quantity-adjustments`
- `PUT /api/parts/{part_id}`

### `backend/app/api/routes/part_types.py`

- `POST /api/part-types`
- `PUT /api/part-types/{part_type_id}`
- `DELETE /api/part-types/{part_type_id}`

### `backend/app/api/routes/manufacturers.py`

- `POST /api/manufacturers`

### `backend/app/api/routes/packages.py`

- `POST /api/packages`

### `backend/app/api/routes/locations.py`

- `POST /api/locations`
- `PUT /api/locations/{location_id}`
- `DELETE /api/locations/{location_id}`

### `backend/app/api/routes/projects.py`

- `POST /api/projects`
- `PUT /api/projects/{project_id}`
- `POST /api/projects/{project_id}/reserve`
- `POST /api/projects/{project_id}/consume`
- `POST /api/projects/{project_id}/cancel`

### `backend/app/api/routes/reservations.py`

- `POST /api/reservations`
- `PUT /api/reservations/{reservation_id}`
- `DELETE /api/reservations/{reservation_id}`
- `POST /api/reservations/{reservation_id}/cancel`
- `POST /api/reservations/{reservation_id}/consume`
- `POST /api/reservations/{reservation_id}/expire`

### `backend/app/api/routes/app_settings.py`

- `PATCH /api/settings/search`
- `PATCH /api/settings/currency`
- `PATCH /api/settings/timezone`
- `PATCH /api/settings/reservations`
- `PATCH /api/settings/appearance`
- `POST /api/settings/preferences/reset`
- `PATCH /api/settings/mcp`
- `PATCH /api/settings/mcp/tool-permissions`
- `PATCH /api/settings/mcp/oauth-clients/{client_database_id}/permissions`
- `PATCH /api/settings/mcp/direct-clients/{client_id}/permissions`
- `POST /api/settings/mcp/oauth-clients`
- `DELETE /api/settings/mcp/oauth-clients/{client_database_id}`
- `POST /api/settings/mcp/direct-clients`
- `PATCH /api/settings/mcp/direct-clients/{client_id}`
- `POST /api/settings/mcp/direct-clients/{client_id}/rotate`
- `POST /api/settings/mcp/direct-clients/{client_id}/reveal`
- `PUT /api/settings/mcp/direct-clients/{client_id}/trusted-networks`
- `DELETE /api/settings/mcp/direct-clients/{client_id}`
- `POST /api/settings/mcp/direct-auth/bearer-key`
- `POST /api/settings/mcp/direct-auth/custom-header`
- `POST /api/settings/mcp/direct-auth/trusted-network`
- `POST /api/settings/mcp/direct-auth/reveal`
- `DELETE /api/settings/mcp/direct-auth`

### `backend/app/api/routes/api_keys.py`

- `POST /api/settings/api-keys`
- `PUT /api/settings/api-keys/{key_id}`
- `POST /api/settings/api-keys/{key_id}/rotate`
- `DELETE /api/settings/api-keys/{key_id}`

### `backend/app/api/routes/auth.py`

- `POST /api/auth/setup`
- `POST /api/auth/complete-setup`
- `POST /api/auth/debug/reset-database`
- `POST /api/auth/login`
- `PUT /api/auth/profile`
- `PUT /api/auth/profile/avatar-image`
- `DELETE /api/auth/profile/avatar-image`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- `POST /api/auth/sessions/revoke-all-other`
- `DELETE /api/auth/sessions/{session_id}`

### `backend/app/api/routes/backups.py`

- `POST /api/backups/download`

### `backend/app/api/routes/restores.py`

- `POST /api/restores/validate`
- `POST /api/restores/{validation_token}/commit`

### `backend/app/api/routes/mcp_oauth.py`

- `POST /oauth/register`
- `POST /oauth/authorize`
- `POST /oauth/token`
- `POST /oauth/revoke`

## Source fingerprints

These hashes capture the exact architecture inspected by Patch 686. Future implementation patches should still validate their own authoritative baseline and source shape rather than blindly treating these hashes as permanent project state.

- `frontend/src/auth/AuthContext.tsx` — `6b62b20b03ccbcf4554518d92298dd0724447b1eb1589509713bc3d7eff430fe`
- `frontend/src/app/App.tsx` — `e1fff5a6e572fd985c3b686cb1f45addb6ef5f078558737fd9e214967cf20011`
- `frontend/src/appearance/AppearanceContext.tsx` — `a7cd0e48a2374e1358f895432f6856306dd4ff4c189b8974c25e2703b139f7d7`
- `frontend/src/pages/Dashboard.tsx` — `2f6b3e41784cdcd77116074b52cd981aeaedbfb6fc849035c42d2cdc2f067161`
- `frontend/src/pages/PartManager.tsx` — `e43a0231b566c879826d16a9d94cee51000ab16e386adbd2ad9509a6dabaaa87`
- `frontend/src/pages/Projects.tsx` — `2649dd8eaedf4900538d34411d42ccee9c5b7fb7caf4984839021e89f4a5218a`
- `frontend/src/pages/Reservations.tsx` — `e2714bbdd5edae16430e2ceb2b85ef916fa2022f4864eb06b843d0deafa260de`
- `frontend/src/pages/History.tsx` — `dee1456dad47c620cd91aae4e8d664724ed6954bc04142818dd096e47a730784`
- `frontend/src/pages/Settings.tsx` — `3f048a2ee982d949f739d314188c69ec07c62fe6faa5c306000577a7a4c622a8`
- `frontend/src/components/McpDirectClientsSection.tsx` — `4d123539f3e0a1da0489c15ddd56da5d3c9fee4c19231f20acae3b481b1189b0`
- `frontend/src/components/ApiKeySettingsSection.tsx` — `6ce327e7154772ec937571dc8af813c4b6429caf050fd6902d2fd8ae7f94fedc`
- `frontend/src/services/partsClient.ts` — `c427eebb3db3620f22ada7fe8d46bf0b22837946642738261d1e970b0af28521`
- `frontend/src/services/projectsClient.ts` — `e1b49ed81e5953dea54bb2a07682e7f9316aa104b676c3b8fe03fb975b0ffce8`
- `frontend/src/services/reservationsClient.ts` — `ea63ba39a5f420a61c9781096035fa0d22f5ab2bb8b558ef07d10580f1c8ce9d`
- `frontend/src/services/historyClient.ts` — `cb3ac069cb0992ad893129df3f3819cd087372193510082d58962e088479f9b5`
- `frontend/src/services/settingsClient.ts` — `f959847e7407131230b124625f55045436e974eb2fb4e65bd5d1f633775d792d`
- `frontend/src/services/apiKeysClient.ts` — `e066f89a2025b7990f01cbcb6fde347bc9b329184ac67bdd42543890f5cb63c2`
- `backend/app/main.py` — `79800e370b0268c8cf59c2e803098ee536687a1e0f91f20e6be32e21d2b168c6`
- `backend/app/api/routes/auth.py` — `f46359fdcd046bae43f3dc5d27c0e4e1d45c80b24778421330c30734afc6cbe7`
- `backend/app/api/routes/parts.py` — `cd7460e565eac9e70d2ff9878952d93fe5f7da01c0566aa3e5d8c0c501fe69b8`
- `backend/app/api/routes/part_types.py` — `f9482a7dc495e706e43b1bae82a56bfa53a85845ab029df1f52115ff59325ace`
- `backend/app/api/routes/manufacturers.py` — `e237bc2906b600ddf34c6ba2b2911bf8993f0dbaa16edb0802a1da0b6c412cf6`
- `backend/app/api/routes/packages.py` — `0e58c96417367f60cbfc4fe38bc75e53dc929fbb2d545dc1a1b1da47c69d7bd6`
- `backend/app/api/routes/locations.py` — `d441b270245734348757dc9f1648868e30030b57fafaec43d1ef4406bebc653e`
- `backend/app/api/routes/projects.py` — `8111f4ccbc5b3ec02bad7ff31a2b3d37f9249da3b3619662ffac7fcfcb2771bd`
- `backend/app/api/routes/reservations.py` — `8cdde76cdfee362725a51993a0325fc4763b1cb808b0571d4566a24b66469382`
- `backend/app/api/routes/history.py` — `5130ca9bacf5d777e46fc952ee645c96168f5070f0522a8518bdaeb55ebdedfb`
- `backend/app/api/routes/app_settings.py` — `fad327231511f219a5a55c28ab65df82c5a6a3e474e1103dac3a00a045e05e38`
- `backend/app/api/routes/api_keys.py` — `a71b43f2a1a6e95431d195a52381c802d31c10805ae9cc14ecba21054d5db416`
- `backend/app/api/routes/backups.py` — `5e23bb3a8d6648370b42f034c381395e4cab74abd516d55598bac076339e6a27`
- `backend/app/api/routes/restores.py` — `17feb4d17fa6f677cdafbebcf3c2026e44ba077add888162ededf9690f699f65`
- `backend/app/api/routes/mcp_oauth.py` — `09ae198f1d1df39dadf22b69cfadb794dc84ad8df88b48fa75d502d244b1cf3c`
- `backend/app/core/lifecycle.py` — `fad9f825da019a00418e7e8a39f4be90eec2f051ae89a288b3195ac0b3052550`
- `docker-compose.yml` — `90024234bae81fa67ff3997bd9ad9388532b6ef934ec5796c98e06df0fa1b8ce`
- `backend/Dockerfile` — `37841e343fcf891b0e3c6ba30d047388ed0f15861a2e33a17ed9bc426805d506`

## Recommended next patch sequence

**Patch 687:** backend live-event foundation only.

- Add broker/generation/sequence/ring/topic revisions.
- Add authenticated `/api/live/events` and `/api/live/state`.
- Integrate lifecycle-aware stream termination.
- Add isolated backend smoke for auth, event framing, replay/resync, fallback state and maintenance drain.
- Do not wire page invalidations yet and do not remove Refresh controls.

**Patch 688:** shared authenticated frontend provider plus the first narrow browser-test wiring.

- One fetch-stream provider under auth scope.
- reconnect/resync/poll fallback.
- wire `inventory`, `projects`, `reservations`, and `history` into existing reload seams first.
- preserve all stale guards, filters, pagination, selection, Retry and routine Refresh controls.
- browser-test with two signed-in tabs/windows.

Then expand Settings/API/MCP/catalogue topic coverage in the next sequential slice, apply browser feedback, and checkpoint only after explicit approval.

## Decision

Patch 686 is intentionally diagnostic-only. The source shape is now sufficiently mapped to proceed with a narrow backend foundation in Patch 687 without weakening authentication, duplicating one stream per page, or breaking restore drain semantics.
