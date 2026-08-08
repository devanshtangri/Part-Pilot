# Chat 21 to Chat 22 Handoff

<!-- PARTPILOT:CHAT21_TO_CHAT22_HANDOFF:V633 -->

## Next chat identity

- Title: `Chat 22: MCP Permissions and Settings Organization`
- Patch range: `634-658`
- First patch: `634`
- Planned boundary: `658`
- Start by inspecting this handoff, `docs/Checkpoint.md`, `docs/Implementation_Roadmap.md`, `docs/Part_Pilot_Project_Memory.txt`, `README.md`, and the newest relevant diagnostic.
- Patch 634 should be diagnostic-only for the individual-tool/per-client MCP permission slice before any implementation.

Do not create a `Chat_22_Starting_Prompt.md` file. The ready-to-paste next-chat prompt is provided only in chat after Patch 633 succeeds.

## Exact pre-boundary state

- Branch: `main`
- Pre-boundary HEAD/origin: `88ca83cd407d63772e027cac409357f5bc192ad0`
- Latest subject: `Checkpoint named direct MCP clients`
- Git/index: clean
- Deployment image: `sha256:8b7c61ac6bee39967ba139641d97982b60f62c4809a2e8a4ed2659321bcc73cd`
- Deployment: healthy, restart count `0`
- Alembic: `0015_mcp_direct_clients`
- Database pre-boundary snapshot SHA-256: `f3ceb38823fafad75e9c8e86eddf1420945c636b6de32259d57d86da85ae625a`
- Database pre-boundary size: `815104` bytes
- SQLite integrity: `ok`; foreign-key violations: `0`
- Users: `1`; sessions: `4`
- Parts: `14`; Part Types: `34`; Projects: `8`; Reservations: `10`; stock movements: `35`
- Audit rows: `233`; max audit ID: `235`
- App settings: `19`; REST API-key rows: `2`; OAuth client rows: `10`; direct-auth rows: `1`
- Owner: ID `1`, username `devanshtangri`, display name `Devansh Tangri`, built-in avatar `storage`
- MCP enabled/read/write: `true/true/false`
- `mcp.direct_clients_enabled=false`; `mcp.direct_no_auth_enabled=false`
- Direct-auth row `1`: `Legacy direct client`, mode `disabled`, disabled; no active secret material
- Deleted item still recoverable: `(8, 5V Relay, Part Type 17, total 0, reserved 0)`
- Restore staging directory was absent at the pre-boundary snapshot; do not recreate or infer state merely to match older handoffs.
- Instance-secret SHA-256: `19c5c9519a188a8f969bb2bd67c65da1418a73605e8747450df8ddeb44d8b47b`
- `.dockerignore` SHA-256: `2bd494395e3997ded13aa0ab44b03ee242d8d3dc45af992d595f2e46c5da27e6`

OAuth/token rows are operational and may change during normal external-client use. Treat the values above as a timestamped boundary snapshot; validate ownership/revocation/consent/token-family semantics rather than freezing volatile token counts or timestamps.

## Important source hashes

- `backend/app/mcp/runtime.py`: `07835598a918ad6e7527fcb53dd523b9be9ec485bca14dc05ecaf4ce3b97b6e0`
- `backend/app/mcp/part_tools.py`: `3630f50532f0a2a77fe5f06571d20283afd8879c4cabd661ffbb9a4a8fa581fa`
- `backend/app/services/mcp_direct_auth.py`: `971dcadfde3240a9b8c342f018146902e7b905b9acaf9cc23ffe98495e131c48`
- `backend/app/api/routes/app_settings.py`: `5dc087809244d5d053657c08719c17046ce3c3fe0982910c3041ad597cc4c93e`
- `backend/app/models/core.py`: `ff93a4ac6466562cd41db734d4c0e9977b9a6566b5cf41da4714f354c9ebd7d6`
- `backend/alembic/versions/0015_mcp_direct_clients.py`: `648cd9e302c4d0984a5b7a573ecb65ca9f2133f2e7cc741857c9fc7b5b6daa2e`
- `frontend/src/pages/Settings.tsx`: `e53c208dc3ef90486d978376cbc9b125f2af9ee79fc62c06c2411bf5017a3bd3`
- `frontend/src/pages/Settings.css`: `6977439610e6f307c7840c5f24e59ba5143105d4fbc4d356746e0484953e5804`
- `frontend/src/components/McpDirectClientsSection.tsx`: `c67b1d2677e4903516f60c579099cf2ea527b884d62cee2d3b968608b49a2251`
- `frontend/src/services/settingsClient.ts`: `7c7eb10f6634348d083b965248f153a1dc95f1c6197b4c9f75c97306e01841cb`
- `frontend/src/types/settings.ts`: `4657413f08cd178c646258b26d0f0a1bdd533ba519c0e25b49a6a37f118756ca`

## Chat 21 completed work

### Current-user account and security
- Protected profile read/update, username/display-name normalization/uniqueness and built-in avatar catalogue.
- Database-backed custom avatar upload/crop/removal with normalization and backup/restore coverage.
- Password change requires current-password verification, rejects reuse, preserves current session and revokes other active sessions by default.
- Safe session list, targeted revocation and revoke-all-other; bearer tokens/hashes are never returned.
- New sessions capture bounded User-Agent and trusted-resolver IP. Older sessions remain honestly `Unknown`.
- Account/Security Settings browser UI is approved.

### Recycle-bin dependency and purge hardening
- Normal Part deletion stays recoverable.
- Custom Part Types cannot be removed while active or recoverable Deleted items reference them.
- Dependency-first delete dialog separates active/deleted blockers and can open Deleted items with exact Part Type filtering.
- Permanent purge requires typed `DELETE`, is atomic, preserves audit history, frees reusable metadata and detaches eligible historical links.
- Browser test permanently purged ESP01, then deleted Development Board Part Type; 5V Relay remains recoverable.

### Scoped REST API keys and API Access
- Alembic `0014_api_keys`: named `pp_api_key_` credentials, one-time plaintext, digest-only storage, expiry, scopes, rotation/revocation and last-used metadata.
- API-key Bearer is accepted only on 43 explicitly registered Inventory/Catalogue/Project/Reservation/History method/path contracts. Browser sessions retain existing access. Auth/Settings/Backup/Restore stay session-only.
- Invalid/revoked/expired=401; missing scope=403.
- Browser-approved API Access UI supports create/edit/rotate/revoke, hidden revoked audit records, scope presets, one-time-secret handling and API-doc actions.
- Both REST API browser-test records remain revoked. Do not expose credential digests/secrets.

### Canonical Docker build context
- Patch 623 diagnosed 112 ignored backend `.pyc` files entering Docker because `.dockerignore` was absent.
- Patch 625 diagnosed 26 tracked backend/frontend files at filesystem mode `0600` while Git canonical mode was `100644`; Docker COPY metadata changed exact image identity despite identical bytes.
- Patch 626 added `.dockerignore` and canonical-mode normalization. Exact-image checks must preserve this invariant.

### Named direct MCP clients
- Alembic `0015_mcp_direct_clients` evolves the singleton into multi-row named direct clients while retaining the disabled legacy row for audit compatibility.
- Supported modes: Bearer key, custom HTTP header and trusted IPv4/IPv6 networks.
- Each named client has independent identity, enable/disable, rotation/revocation and safe usage metadata.
- Explicit OAuth/direct credential auth has precedence; trusted-network resolution follows; instance-wide no-auth is final fallback.
- `Allow direct MCP clients` is separate from OAuth. OAuth is never disabled merely because direct clients are off.
- `No authentication` is instance-wide because unauthenticated traffic cannot honestly carry a named identity. It is OFF by default, requires exact typed `ALLOW NO AUTH` confirmation and remains read-only/gated by MCP server + read tools.
- MCP write authorization remains OFF and no write tools are exposed.
- Browser-approved UI includes named-client security dialogs, one-time credential results, corrected typography/card hierarchy, aligned MCP section widths and one readable disabled-state opacity.

## Recovery history that matters
- Patch 616 failed before writes because a frozen tracked diff omitted a new untracked scope-smoke file. Freeze untracked payloads explicitly.
- Patch 618 produced a corrupted compressed UI payload; avoid unnecessary zlib packaging when plain payloads are safer.
- Patches 621/622/624 failed during API Access checkpoint recovery; Patches 623/625 diagnosed ignored bytecode and filesystem mode drift before Patch 626 fixed the canonical context.
- Patch 628 built correct visual CSS but failed because a CSS comment runtime marker was stripped by minification. Use DOM/value/custom-property markers.
- Patch 629 failed before writes because packaged CSS bytes differed from the rehearsal fingerprint. Freeze exact final script-produced bytes.
- Before Patch 631, an assistant rehearsal accidentally wrote the exact intended V631 CSS and deployed its image live. Patch 631 preflight detected it and performed no write; Patch 632 formally adopted/checkpointed those exact approved bytes. **Never mutate live source/deployment during rehearsal; isolated `/tmp` only.**
- User requires patch-generation turns to stay under roughly 10 minutes. Prefer bounded inspection, one isolated rehearsal, then package.

## Chat 22 first slice — individual-tool/per-client MCP permissions
Patch 634 must be diagnostic-only. Inspect exact committed source and create a `docs/diagonostic_*.md` readiness report before implementation. At minimum inspect:
1. Six current MCP read tools and tool-name/registration representation.
2. Runtime principal identity for OAuth, named Bearer/custom-header/trusted-network clients and instance-wide no-auth.
3. Existing global `mcp.read_tools_enabled`/`mcp.write_tools_enabled` gates and write-disabled contract.
4. Safe policy keys for OAuth client IDs/database IDs and named direct-client IDs without leaking credentials.
5. Backup/restore schema implications and migration/table vs app-settings design.
6. Settings UI seams for global defaults, client overrides and inherited/effective states.
7. Smoke seams for deny/allow/inherit, revoked/disabled clients, no-auth, OAuth, direct modes and session-only administration.

Design rules:
- Do not invent a named identity for no-auth traffic.
- Global permissions and per-client overrides need deterministic precedence and explainable effective state.
- Never let policy/UI implicitly enable MCP write tools; writes remain disabled until safeguarded write-tool work.
- Preserve OAuth/direct auth semantics and current credentials.
- Use copied-db unique fixtures and exact cleanup/restoration.
- Browser-test source remains uncommitted until approval; checkpoint promptly.

## Broader Settings task already approved for later
The user wants restrained section dividers/grouping throughout Settings wherever relevant, not just MCP. This is a broad Settings pass, not piecemeal decoration. Maintain flat/dense enterprise UI, subtle borders, restrained radii and functional hierarchy; no gradients, glow, glassmorphism or decorative over-segmentation.

Within MCP, keep `Enable MCP server` first as master; disabled subordinate content remains readable but non-interactive; read/write/tool authorization belongs in permissions/security grouping.

## Other remaining V1 work
- Protect `/docs`, `/redoc` and `/openapi.json` with a deliberate public-alpha policy; API keys never administer Auth/Settings/Data.
- Persisted app-wide ISO currency selector; formatting only, no FX conversion.
- Server-backed whole-inventory Stored Parts metrics independent of pagination: Total components=sum active `total_quantity`; Inventory value=sum known `total_quantity * unit_price` with explicit price coverage; Available, Reserved, Low stock, Out of stock, distinct Part count.
- Preference/default restoration; multi-user roles Owner/Admin/Operator/Viewer; safeguarded MCP writes after permissions; final accessibility/security/responsive/API-MCP regression.
- Notifications & Messaging remain post-v1.

## Boundary invariants
- Patch 633 is documentation-only; no application source, deployment, database, credentials, inventory or fixture changes.
- Stage exactly Checkpoint, Roadmap, project memory, README and this handoff.
- Push main, fetch and verify local HEAD equals origin/main.
- After Patch 633 succeeds, Chat 21 is closed. Do not consume Patch 634 in this chat.
