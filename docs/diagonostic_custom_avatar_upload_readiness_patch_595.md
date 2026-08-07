<!-- PARTPILOT:DIAGONOSTIC_CUSTOM_AVATAR_READINESS:V595 -->
# Patch 595 custom avatar upload readiness diagnostic

## Verdict

**PASS — safe to implement a database-backed custom avatar slice next.**

Patch 595 is documentation-only. It does not modify application source,
deployment, credentials, or live application data.

## Exact baseline

- HEAD/origin: `8b76652730139eefdb22278db8d1497319160739`
- Deployment image: `sha256:e677e5e2d3e86441e056d1108a5b2295dccef73e158c21cf4248e9cf802b9d94`
- Alembic head: `0012_user_avatar_id`
- Current user: `devanshtangri` / `Devansh Tangri`
- Current built-in avatar at diagnostic time: `storage`
- Sessions: `4` stored / `4` active
- Audit rows at diagnostic time: `203`
- SQLite integrity: `ok`
- Foreign-key violations: none

Pending browser-test source that must remain uncommitted:

- `frontend/src/app/AppLayout.tsx` — `70060d60b64ad1f506dff8b5f117ffb3dbea5a4830425338695f5b634d329422`
- `frontend/src/pages/Settings.tsx` — `52c60658d3db75d6b176ca68fb05e4d63284721024c87c91eda28b8246e328aa`
- `frontend/src/pages/Settings.css` — `57d51e6f5c790bdbd476f8df01536610283d47f2ba73c41705b23f7ad36d781c`
- `frontend/src/styles/global.css` — `7a5c950dfc16c52c9b87d8034d9ee0fcfa32e54d2d0f7ecca6d1447cbeb29333`
- `frontend/src/components/UserAvatar.tsx` — `70a48f60cbd0c84a1f243c0810e4514562b32eac1d81c76c6b206df0294d1f3d`

## Storage findings

- `users.avatar_id` stores only a built-in avatar identifier today.
- Part Pilot persists `./data` at `/data`.
- Version-1 `.ppbackup` artifacts archive the SQLite database plus manifest;
  arbitrary profile-image filesystem paths are not part of the backup payload.
- `python-multipart` is already installed and FastAPI already uses `UploadFile`
  for restore uploads.
- No Pillow/image-decoding dependency is currently installed.
- There is no custom-avatar BLOB or metadata column today.

## Locked custom-avatar contract

Use SQLite-backed image storage for the first implementation so backup/restore
inherits the existing database snapshot contract.

Recommended Alembic `0013` additions on `users`:

- nullable `avatar_image_data` BLOB;
- nullable `avatar_image_mime` string;
- nullable `avatar_image_sha256` string;
- nullable `avatar_image_size_bytes` integer.

Keep `avatar_id` as the built-in fallback. Presence of a validated custom image
overrides that fallback; deleting the custom image immediately reveals the
stored built-in avatar again.

Backend upload contract:

- protected current-user-only PUT and DELETE endpoints;
- accept PNG, JPEG, or WebP input;
- maximum compressed upload size: 5 MiB;
- decode independently on the server with Pillow;
- reject malformed, oversized, or decompression-bomb images;
- normalize orientation;
- crop/resize to a square 256x256 representation;
- re-encode server-side to WebP and strip supplied metadata;
- store only normalized bytes plus MIME/hash/size metadata;
- never put image bytes or data URLs in audit/history;
- audit upload/replacement/removal with safe metadata only.

Frontend contract:

- custom-image chooser with local preview;
- center-crop/resize before upload for predictable UX, while backend validation
  remains authoritative;
- selected built-in avatars render as icon-only choices with accessible labels;
- Profile and Password cards use equal desktop height;
- the sidebar identity block, including avatar/name/username, links directly to
  `/settings#settings-account`;
- authenticated image fetch creates/revokes an object URL in client memory;
- no image bytes in localStorage/sessionStorage.

## Backup/restore consequence

Database-backed normalized avatar bytes are automatically included in the
existing SQLite snapshot. The implementation must extend backup/restore smoke
coverage to prove the custom avatar survives a backup snapshot and restore
validation path without adding a second storage tree.

## Session metadata follow-up

Existing four sessions have no User-Agent or IP metadata and cannot be
reconstructed. A later narrow account-security patch should populate those
fields for newly created sessions without modifying old rows.

## Deferred post-v1 Notifications & Messaging

Notifications are explicitly **not part of the first release**.

Future scope:

- optional per-user email address;
- administrator-supplied SMTP host/port/security/authentication settings;
- encrypted SMTP credentials at rest;
- test-delivery workflow;
- additional notification transports designed as pluggable channels;
- per-user event subscriptions;
- enable/disable by event category and individual event;
- delivery history, failure state, retry/backoff, and secret-free audit;
- initial event families may include stock alerts, Project/Reservation lifecycle,
  account/security events, backup/restore status, and integration activity.

## Next safe implementation order

1. Add Pillow and Alembic `0013` database-backed avatar metadata/BLOB columns.
2. Add protected custom-avatar upload/read/delete backend and copied-DB smoke.
3. Capture User-Agent/IP for newly created browser sessions.
4. Add frontend avatar-image contracts and AuthContext object-URL lifecycle.
5. Refine the pending Account UI: equal-height cards, icon-only built-ins,
   upload control, and clickable sidebar identity.
6. Browser test; do not checkpoint the pending UI before approval.
7. Checkpoint approved Account/Security source.
8. Resume scoped REST API keys.
