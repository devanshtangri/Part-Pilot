# Chat 11 Fixture Cleanup Diagnostic

<!-- PARTPILOT:CHAT11_FIXTURE_CLEANUP_DIAGNOSTIC:V287 -->

## Status

- Patch: 287
- Mode: diagnostic-only
- Application source modified: no
- Live database modified: no
- Deployment modified: no
- Boundary documents modified: no
- Diagnostic report only: committed and pushed
- Current documentation HEAD before this report: `465af5a9d4261577a63a52d8acb66227ef6c34fb`
- Patch 284 diagnostic HEAD: `bc4833a1e0cc978dfd93af72e87a1df5e2de25a4`
- Patch 280 policy HEAD: `5aa80c6c86e6e571baa5102ee7552fd98a749976`
- Approved application source HEAD: `ba721e59f5c815951ae0422090d7cd646df9e886`
- Patch 278 backup: `/projects/Part Pilot/fixes/backups/patch_278_20260727-230434`
- Alembic head: `0005_packages`

Patch 278 failed after manifest-owned fixture cleanup because post-cleanup
verification reported a change in `app_settings`. Patch 278 restored the
database from backup and left the repository clean.

## Repository and deployment

- Branch: `main`
- Local source HEAD matched `origin/main`.
- Current documentation message: `Remove unintended Part Pilot memory file`
- Patch 284 diagnostic message: `Recover Chat 11 boundary diagnostic`
- Patch 280 policy message: `Normalize Part Pilot boundary prompt policy`
- Approved source message: `Finalize Stored Parts search and sorting`
- Container ID: `5f84a320d363a8471ff0589cd1ddb75693d6415df0d0df017ee153fe48dcaa46`
- Container image: `sha256:ebc8e959373c7ecd51df93b433148156567ed07d312446371385dc9d98825416`
- Live database: `/projects/Part Pilot/data/partpilot.db`
- Live database SHA-256: `6badfb2b6595354a6b798915cfee1bb9155c85f76e43efcae956d983286d310a`
- Patch 278 backup database: `/projects/Part Pilot/fixes/backups/patch_278_20260727-230434/partpilot_before_patch_278.sqlite3`
- Backup database SHA-256: `6badfb2b6595354a6b798915cfee1bb9155c85f76e43efcae956d983286d310a`
- Manifest-owned fixture IDs: 70

## Source hashes

- `backend/app/api/routes/parts.py`: `2501759a082a12e74dfab3ec9cc48be8e19bb426a96f0ef0ed3035fd2e3460b4`
- `backend/app/db/smoke_test.py`: `511b9f757f4129ef84846ead97c113760fb4a473ced62c34e78a736a0c4c6ad4`
- `backend/app/services/parts.py`: `34e448f514ed2f115cfc24b27a35667fbd7fdbec8472fd2d4101dcb0ed470998`
- `frontend/src/pages/PartManager.css`: `b3c64207fa1c171e8770f46790cd693df41413f5fe5d242d52d4e5727bff10de`
- `frontend/src/pages/PartManager.tsx`: `1122bb8b9525775cc794b404875a49b5dc28a2ff9f89fb5df85607176ec793b9`
- `frontend/src/services/partsClient.ts`: `8dc0f4a07610807427e9bc56050ea84b76d504b5466ba377cdc4470f715fa43f`
- `frontend/src/types/parts.ts`: `755bb9817dd6e4363ddab11ae34896b68a22b32543832f09b5fbd64c67bca930`

## Evidence summary

- The cleanup dependency graph does **not** target `app_settings`.
- The disposable cleanup simulation leaves `app_settings` unchanged before any application restart.
- The restored live database currently matches the Patch 278 backup in `app_settings`; the failed drift may have occurred only during the cleanup/restart verification sequence.
- No foreign-key dependency path exists from `parts` to `app_settings`.

## Restored live database versus Patch 278 backup

The comparison below was performed read-only after Patch 278 rollback.

No table rows differ.

## Disposable cleanup simulation

The Patch 278 cleanup algorithm was repeated on a temporary copy of the backup
database. The live database was not used.

- Simulation integrity check: `ok`
- Foreign-key violations: `0`
- PP241 fixtures remaining after simulation:
  `0`
- `app_settings` targeted by dependency graph:
  `False`
- `app_settings` changed by cleanup before restart:
  `False`
- Dependency path from `parts` to `app_settings`:
  `none`

### Planned target rows

| Table | Target rows |
|---|---:|
| `parts` | 70 |

### Rows deleted by simulation

| Table | Deleted rows |
|---|---:|
| `parts` | 70 |

### Rows added by simulation

| Table | Added rows |
|---|---:|
| None | 0 |

### Simulated `app_settings` changes

Removed: 0
Added: 0

No simulated `app_settings` row changes.

## Live `app_settings` drift after rollback/startup

Removed: 0
Added: 0

No current live-versus-backup `app_settings` row changes.

## Relevant triggers

No trigger SQL references `app_settings` or `parts`.

## Relevant source excerpts

### `backend/app/db/smoke_test.py`

Total matching excerpts: 29

Line 107:

```text
0105:
0106:
0107: def check_seed_data() -> None:
0108:     with db_session() as db:
0109:         part_type_count = db.execute(text("select count(*) from part_types where is_builtin = 1")).scalar()
```

Line 111:

```text
0109:         part_type_count = db.execute(text("select count(*) from part_types where is_builtin = 1")).scalar()
0110:         field_count = db.execute(text("select count(*) from part_type_fields")).scalar()
0111:         settings_count = db.execute(text("select count(*) from app_settings")).scalar()
0112:
0113:         missing_settings = []
```

Line 116:

```text
0114:         for key in EXPECTED_SETTINGS:
0115:             exists = db.execute(
0116:                 text("select 1 from app_settings where key = :key"),
0117:                 {"key": key},
0118:             ).scalar()
```

Line 129:

```text
0127:
0128:     if missing_settings:
0129:         fail(f"Missing default app settings: {', '.join(sorted(missing_settings))}")
0130:
0131:     ok(f"Built-in part types exist: {part_type_count}")
```

Line 133:

```text
0131:     ok(f"Built-in part types exist: {part_type_count}")
0132:     ok(f"Template fields exist: {field_count}")
0133:     ok(f"Default app settings exist: {settings_count}")
0134:
0135:
```

Line 249:

```text
0247:             db.flush()
0248:
0249:             db.execute(text("delete from app_settings where key = 'smoke.test.setting'"))
0250:             db.flush()
0251:             db.rollback()
```
### `backend/app/services/app_settings.py`

Total matching excerpts: 1

Line 7:

```text
0005: from app.db.settings import get_bool_setting, set_app_setting
0006: from app.models import AuditLog
0007: from app.schemas.app_settings import (
0008:     SearchSettingsResponse,
0009:     SearchSettingsUpdateRequest,
```
### `backend/app/db/seed.py`

Total matching excerpts: 14

Line 9:

```text
0007:
0008: from app.db.session import SessionLocal
0009: from app.models import AppSetting, PartType, PartTypeField
0010:
0011:
```

Line 50:

```text
0048:
0049:
0050: DEFAULT_APP_SETTINGS: dict[str, dict[str, object]] = {
0051:     "setup.completed": {"value_json": False, "value_text": None},
0052:     "app.display_name": {"value_json": "Part Pilot", "value_text": "Part Pilot"},
```

Line 321:

```text
0319:
0320:
0321: def seed_builtin_part_types(db: Session) -> int:
0322:     created = 0
0323:     existing_slugs = {
```

Line 348:

```text
0346:
0347:
0348: def seed_builtin_template_fields(db: Session) -> int:
0349:     created = 0
0350:
```

Line 391:

```text
0389:
0390:
0391: def seed_default_app_settings(db: Session) -> int:
0392:     created = 0
0393:
```

Line 394:

```text
0392:     created = 0
0393:
0394:     existing_keys = {row.key for row in db.query(AppSetting.key).all()}
0395:
0396:     for key, values in DEFAULT_APP_SETTINGS.items():
```
### `backend/app/main.py`

Total matching excerpts: 2

Line 48:

```text
0046: from app.api.routes.locations import router as locations_router
0047: # PATCH 182: protected application search settings routes
0048: from app.api.routes.app_settings import router as app_settings_router
0049: from app.core.config import get_settings
0050:
```

Line 83:

```text
0081: app.include_router(locations_router, prefix="/api")
0082: # PATCH 182: protected application search settings API
0083: app.include_router(app_settings_router, prefix="/api")
0084:
0085: frontend_dist = Path("/app/frontend_dist")
```
### `backend/app/models/__init__.py`

Total matching excerpts: 2

Line 2:

```text
0001: from app.models.core import (
0002:     AppSetting,
0003:     AuditLog,
0004:     Backup,
```

Line 25:

```text
0023:
0024: __all__ = [
0025:     "AppSetting",
0026:     "AuditLog",
0027:     "Backup",
```
### `backend/app/models/core.py`

Total matching excerpts: 2

Line 52:

```text
0050:
0051:
0052: class AppSetting(Base, TimestampMixin):
0053:     __tablename__ = "app_settings"
0054:
```

Line 53:

```text
0051:
0052: class AppSetting(Base, TimestampMixin):
0053:     __tablename__ = "app_settings"
0054:
0055:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
```
### `backend/app/api/routes/app_settings.py`

Total matching excerpts: 2

Line 8:

```text
0006: from app.api.routes.auth import get_current_user
0007: from app.db.session import get_db
0008: from app.schemas.app_settings import (
0009:     SearchSettingsResponse,
0010:     SearchSettingsUpdateRequest,
```

Line 12:

```text
0010:     SearchSettingsUpdateRequest,
0011: )
0012: from app.services.app_settings import (
0013:     get_search_settings,
0014:     update_search_settings,
```
### `backend/app/services/debug_reset.py`

Total matching excerpts: 7

Line 10:

```text
0008: import app.models  # Ensure every SQLAlchemy table is registered on Base.metadata.
0009: from app.db.base import Base
0010: from app.db.seed import (
0011:     seed_builtin_part_types,
0012:     seed_builtin_template_fields,
```

Line 11:

```text
0009: from app.db.base import Base
0010: from app.db.seed import (
0011:     seed_builtin_part_types,
0012:     seed_builtin_template_fields,
0013:     seed_default_app_settings,
```

Line 12:

```text
0010: from app.db.seed import (
0011:     seed_builtin_part_types,
0012:     seed_builtin_template_fields,
0013:     seed_default_app_settings,
0014: )
```

Line 13:

```text
0011:     seed_builtin_part_types,
0012:     seed_builtin_template_fields,
0013:     seed_default_app_settings,
0014: )
0015:
```

Line 42:

```text
0040:     db.commit()
0041:
0042:     recreated_part_types = seed_builtin_part_types(db)
0043:     recreated_template_fields = seed_builtin_template_fields(db)
0044:     recreated_settings = seed_default_app_settings(db)
```

Line 43:

```text
0041:
0042:     recreated_part_types = seed_builtin_part_types(db)
0043:     recreated_template_fields = seed_builtin_template_fields(db)
0044:     recreated_settings = seed_default_app_settings(db)
0045:
```
### `backend/app/services/app_setup.py`

Total matching excerpts: 6

Line 8:

```text
0006: from sqlalchemy.orm import Session
0007:
0008: from app.models import AppSetting
0009:
0010: SETUP_COMPLETED_KEY = "setup.completed"
```

Line 22:

```text
0020:
0021:
0022: def _get_setting(db: Session, key: str) -> AppSetting | None:
0023:     return db.execute(
0024:         select(AppSetting).where(AppSetting.key == key)
```

Line 24:

```text
0022: def _get_setting(db: Session, key: str) -> AppSetting | None:
0023:     return db.execute(
0024:         select(AppSetting).where(AppSetting.key == key)
0025:     ).scalar_one_or_none()
0026:
```

Line 28:

```text
0026:
0027:
0028: def _get_or_create_setting(db: Session, key: str) -> AppSetting:
0029:     setting = _get_setting(db, key)
0030:     if setting is not None:
```

Line 33:

```text
0031:         return setting
0032:
0033:     setting = AppSetting(key=key, value_json=None, value_text=None)
0034:     db.add(setting)
0035:     db.flush()
```

Line 39:

```text
0037:
0038:
0039: def _string_value(setting: AppSetting | None) -> str | None:
0040:     if setting is None:
0041:         return None
```
### `backend/app/db/settings.py`

Total matching excerpts: 5

Line 8:

```text
0006:
0007: from app.db.utils import parse_setting_value
0008: from app.models import AppSetting
0009:
0010:
```

Line 12:

```text
0010:
0011: def get_app_setting(db: Session, key: str, default: Any = None) -> Any:
0012:     setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
0013:     if setting is None:
0014:         return default
```

Line 25:

```text
0023:     text_value: str | None = None,
0024:     commit: bool = True,
0025: ) -> AppSetting:
0026:     setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
0027:     if setting is None:
```

Line 26:

```text
0024:     commit: bool = True,
0025: ) -> AppSetting:
0026:     setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
0027:     if setting is None:
0028:         setting = AppSetting(key=key)
```

Line 28:

```text
0026:     setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
0027:     if setting is None:
0028:         setting = AppSetting(key=key)
0029:         db.add(setting)
0030:
```

## Safe boundary-recovery plan

1. Keep the current live database and committed application source unchanged.
2. In the recovery script, take a fresh SQLite backup while the service is
   running, stop the service, and apply the manifest-owned deletion.
3. Before restarting the application, require exact equality with the
   precomputed cleanup result for **all** tables and require zero foreign-key
   violations.
4. Restart the existing deployment and run the complete smoke suite.
5. After restart, continue requiring exact equality for every inventory-bearing
   table and zero PP241 fixtures.
6. Handle `app_settings` according to this report's measured evidence:
   - when cleanup simulation leaves it unchanged but restart mutates it, compare
     the post-restart table against an explicitly captured no-op restart
     baseline or an exact allowlist of observed setting keys/columns;
   - never weaken verification for parts, quantities, locations,
     manufacturers, packages, tags, history or other inventory tables.
7. Do not create `docs/Chat_12_Starting_Prompt.md`.
8. Update durable docs and the handoff only after cleanup verification passes.
9. Commit/push the boundary documentation with an explicit allowlist.
10. Provide the next-chat prompt only in the chat response after the recovery
    terminal output ends with exactly `Everything PASS`.
11. The next sequential patch after this diagnostic is Patch 288. It must read
    this committed report before attempting fixture cleanup or the boundary.
12. Chat 12 begins only after successful boundary recovery and owns 30 patches;
    its boundary is start patch plus 29.

## Updated boundary rules requested by the user

- Do not create or commit a next-chat prompt file.
- Keep the ready-to-paste next-chat prompt only in the current chat.
- Provide that prompt only after the boundary-recovery script has been run and
  its terminal output ends with exactly `Everything PASS`.
- Future chats own 30 sequential patch numbers instead of 25.
- Failed boundary scripts consume their patch number.
- Keep the current chat active for narrow, high-safety boundary recovery until
  success.
