<!-- PARTPILOT:DIAGONOSTIC_BACKUP_SCHEMA_COMPATIBILITY:V596 -->
# Patch 596 backup/restore schema compatibility diagnostic

## Verdict

**BLOCKED — repair backup/restore schema compatibility before adding custom
avatar storage or any further database migration.**

The Account browser-test source remains valid and untouched. The blocker is the
portable backup format, not the Account UI.

## Exact current baseline

- HEAD/origin: `d6f5f04fb3ab473de12011ace26e692dbf82d49e`
- Deployment image: `sha256:e677e5e2d3e86441e056d1108a5b2295dccef73e158c21cf4248e9cf802b9d94`
- Alembic head: `0012_user_avatar_id`
- SQLite integrity: `ok`
- Foreign-key violations: none
- Sessions: `4` stored / `4` active
- Audit rows at diagnostic start: `203`
- Live critical-schema SHA-256: `b424bcf63d7de8ccb3d9742a1f2f25a58054d4a41fba274710296112d6b17abc`

## Current live tables

- `alembic_version`
- `aliases`
- `app_settings`
- `audit_log`
- `backups`
- `locations`
- `manufacturers`
- `mcp_direct_auth`
- `mcp_oauth_authorization_codes`
- `mcp_oauth_clients`
- `mcp_oauth_consents`
- `mcp_oauth_tokens`
- `packages`
- `part_field_values`
- `part_tags`
- `part_type_fields`
- `part_types`
- `parts`
- `project_items`
- `projects`
- `reservation_items`
- `reservations`
- `sessions`
- `stock_movements`
- `tags`
- `users`

## Verified regression

`backend/app/services/backups.py` is still locked to:

- Alembic revision `0007_projects_contract`;
- critical schema `c80247b636ff8476605926a15e14892aec8c3630b6f3873d29c2525e02f1f24d`;
- an exact table list that predates MCP persistence.

The current copied-database backup smoke fails with:

```text
Snapshot table contract changed. missing=[], extra=['mcp_direct_auth', 'mcp_oauth_authorization_codes', 'mcp_oauth_clients', 'mcp_oauth_consents', 'mcp_oauth_tokens']
```

This was reproduced against a SQLite online copy of the live database using the
currently deployed image. The live database was not mutated.

## Why this blocks custom uploaded avatars

Patch 595 chose SQLite-backed normalized image storage so profile images inherit
portable backup/restore semantics. Adding Alembic `0013` before repairing the
backup schema contract would deepen an already-existing compatibility gap and
would make the claim of portable custom avatars false.

## Required repair contract

The next implementation must modernize backup/restore compatibility for the
current schema **before** the custom-avatar migration.

Requirements:

1. Preserve the `.ppbackup` safety properties: canonical manifest, integrity,
   foreign-key checks, hashes, size limits, staging, rollback and session
   invalidation.
2. Include all currently required MCP tables in the database table contract.
3. Define an explicit forward schema-version strategy instead of silently
   overwriting the old `0007` constants.
4. Do not claim old backups are compatible unless an actual migration-on-restore
   path is implemented and tested.
5. Keep historical format/version semantics explicit; reject unsupported
   revisions before replacement.
6. Update backup generation, validation, restore staging/bootstrap and all
   associated smoke tests together.
7. Prove current-schema backup generation and restore validation on copied
   databases.
8. Preserve real inventory, users, sessions, OAuth/direct credentials and
   existing restore staging.
9. Keep the five pending Account browser-test files uncommitted and byte-identical.

## Safe next order

1. Implement the backup/restore current-schema compatibility repair.
2. Run complete backup generation, validation and restore copied-DB smoke.
3. Re-run full application smoke and live preservation checks.
4. Then add Pillow + Alembic `0013` custom-avatar BLOB metadata.
5. Extend the repaired backup/restore contract to `0013` in the same avatar
   backend slice or via an immediately adjacent compatibility update.
6. Continue session metadata capture and frontend custom-avatar integration.
