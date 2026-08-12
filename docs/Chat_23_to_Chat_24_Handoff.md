# Chat 23 to Chat 24 Handoff

<!-- PARTPILOT:CHAT23_TO_CHAT24_HANDOFF:V685 -->

## Chat 24 identity

- Title: `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
- Patch range: `686-710`
- First patch: `686`
- Planned boundary: `710`
- Start by reading this handoff, `docs/Checkpoint.md`, `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`, `README.md`, and the newest relevant `diagonostic_` report if recovery evidence is needed.
- Do not create a separate starting-prompt file.

## Exact boundary state

- Patch 684 checkpoint pre-boundary HEAD/origin: `0d231871a46f490e4437711b6b9ab658334cd98d`.
- Patch 684 subject: `Add regional currency and timezone preferences`.
- Patch 685 is documentation/handoff only; after it succeeds, current local `HEAD` and `origin/main` are the authoritative Chat 24 starting commit.
- Branch: `main`.
- Application working tree/index at boundary: clean; there is no pending browser-test source.
- Deployment image: `sha256:7a285a3ebb7eccf9eddb7c375a2b5616773e5aa40283ce270e41aff445ad23b9`.
- Deployment: healthy, restart count `0`.
- Alembic: `0016_mcp_tool_permissions`.
- Instance-secret SHA-256: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`.
- Live SQLite, Settings values and MCP policy are legitimate mutable state. Do not freeze an old DB/settings/policy hash into future prerequisites; validate integrity and snapshot run-start values instead.

## What Chat 23 completed

1. **MCP permission finalization** — global exact-tool hard ceiling, OAuth/named-direct inherit-or-deny overrides, no-auth global-only behavior, principal-aware authenticated `tools/list`, call-time defense in depth, honest 0-write-tool catalogue state and consistent permission UI.
2. **Direct MCP Settings hierarchy** — Allow direct clients + No authentication grouped with Named direct clients; global Server/Read/Write controls remain separate; dependency-disabled controls use `not-allowed`, `wait` only while saving.
3. **Reversible preference autosave** — Theme and Inventory selection autosave; Reservation mode saves immediately and days debounce 550 ms; failures rollback confirmed state and stale responses cannot overwrite newer edits.
4. **Preferences consolidation and targeted resets** — Theme, Inventory display and Reservation defaults live under one Preferences workspace; each has an independent target-specific Reset-to-default action; unrelated security/business state is preserved.
5. **Regional display** — persisted uppercase three-letter ISO currency formatting with no FX conversion; persisted IANA Display timezone for passive timestamps only; historical Project/Reservation currency snapshots and stored timestamps are never rewritten. Both controls are themed and responsive.

Patch 684 committed/pushed the final 20-file Regional display/currency/timezone application batch plus milestone docs. There is no uncommitted application source at this boundary.

## Recovery lessons carried forward

- Durable logs contain only bytes explicitly written to them. Never require terminal-only `Everything PASS` or exception-summary text to appear in a durable log.
- Rehearsals stay isolated from live source/deployment. Freeze and validate the exact packaged bytes that actually passed.
- Do not use source-only comments as compiled Vite runtime markers; minification may strip them. Verify rendered/runtime semantics or intentionally preserved data markers.
- Docker restart count is top-level `.RestartCount`, not `.State.RestartCount`.
- Failed scripts consume their patch number; never reuse.

## Chat 24 first objective — authenticated live invalidation

The next V1 task is near-immediate cross-client invalidation with targeted refetch.

Required behavior:

- Use one authenticated SSE-compatible stream for the signed-in frontend. Do not weaken the existing auth model merely to use native `EventSource`; inspect current session/token mechanics and choose a secure streaming client compatible with them.
- Publish compact topic/resource invalidation events after successful mutations. Events should identify what changed without shipping sensitive full records through the stream.
- Target Dashboard, Stored Parts, Projects, Reservations, History, Settings and API/MCP administration.
- Preserve each page's existing search/filter/sort/pagination/selection and stale-request guards. Invalidation triggers the narrowest safe refetch rather than resetting page state.
- Include event IDs or equivalent resync semantics so reconnect can safely recover missed changes. Reconnect with backoff; use polling only as fallback.
- Keep explicit Retry for errors. Remove routine Refresh controls only after the relevant live-sync path is browser-proven.
- Avoid duplicate streams per page; the authenticated stream should be shared at application/auth scope.
- Preserve data safety and do not create broad cleanup/deletion behavior in live-sync tests.

The first Chat 24 patch should inspect the current auth/frontend data-fetch architecture and mutation surfaces before choosing exact stream plumbing. It may implement the foundation in the same patch only if the verified source shape is unambiguous; otherwise keep the first slice narrow and evidence-driven.

## Remaining V1 after live sync

1. Public-alpha `/docs`, `/redoc` and `/openapi.json` exposure/schema hardening.
2. Server-backed whole-inventory Stored Parts metrics: Total components, Inventory value with price coverage, Available, Reserved, Low stock, Out of stock and distinct Part count.
3. Dashboard Stock alert card opens a dialog listing every alert-producing part; remove the inline Low stock table.
4. Owner/Admin/Operator/Viewer roles.
5. Safeguarded MCP write tools through the canonical catalogue/permission model.
6. Final alpha accessibility, security, responsive and API/MCP regression.

Notifications & Messaging remain post-v1.
