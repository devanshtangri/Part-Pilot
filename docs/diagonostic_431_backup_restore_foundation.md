# Diagnostic 431 — Backup and Restore Foundation

<!-- PARTPILOT:DIAGONOSTIC_BACKUP_RESTORE_FOUNDATION:V431 -->

## Purpose and guardrails

Patch 431 is diagnostic-only. It records the exact recovered starting state for
Chat 16 and defines a safety-first backup/restore architecture before
any application implementation. It does not modify application source,
build or redeploy the service, create a backup artifact, replace a
database file, invalidate a session, or alter live data.

The report is the only staged and committed file. The six realistic
Patch 401 Parts and all existing History remain untouched.

## Recovery history before this report

- Patch 427 was consumed after a safe pre-write diagnostic failure:
  one generic authentication dependency marker occurred three times.
  No report, source, deployment, commit or live-data change remained.
- Patch 428 removed the page-header runtime appearance badge and passed
  build, deployment, copied-database smoke and browser testing.
- Patch 429 committed and pushed only the approved Settings.tsx and
  Settings.css changes. The working tree and index are clean.
- Patch 430 was consumed after another safe pre-write failure:
  a raw PRAGMA text count included both the executable call and its
  explanatory docstring. No report, source, deployment, commit or
  live-data change remained.
- Patch 431 replaces both listener text counts with AST-based semantic
  validation of the exact decorator, function and cursor operations.
- Current checkpoint commit: `8477f1b047120da82964c3845f353cf46f9bf524`.

## Exact repository and boundary state

- Generated at: `2026-08-01T18:36:59Z`
- Repository: `/projects/Part Pilot`
- Branch: `main`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Baseline HEAD/origin: `8477f1b047120da82964c3845f353cf46f9bf524`
- Working tree before report: clean
- Git index before report: empty
- Patch 426 boundary log: `fixes/logs/426_chat15_settings_boundary_20260801-232204.log`
- Boundary log SHA-256: `097fa24f6d49f75e4f644c66a8ec24854b117ee3384b442d606c56443776d830`
- Patch 426 evidence ends with `Everything PASS`.

## Deployment and storage state

- Compose service/container: `partpilot`
- Deployment image ID: `sha256:7113e04244629f7508ecee3bd3c45dfec0bf63d25317192ce2a447997305623c`
- Image reference: `partpilot-partpilot`
- Container status: `running`
- Runtime command: `sh -c uvicorn app.main:app --host 0.0.0.0 --port ${PARTPILOT_CONTAINER_PORT:-8000}`
- Restart policy: `unless-stopped`
- Docker healthcheck: absent
- `/data` source: `/projects/Part Pilot/data`
- `/data` mount type/access: `bind` / `rw`
- Host data directory: mode `0o755`, UID:GID `0:0`
- Live database: `/projects/Part Pilot/data/partpilot.db`
- Live database mode: `0o644`, UID:GID `0:0`
- Live database size: `565248` bytes
- Container temporary directory: `/tmp`
- `/tmp` is not mounted and is therefore suitable only for ephemeral
  download staging, not a restore job that must survive restart.

Current process table:

```text
PID                 PPID                USER                GROUP               COMMAND
12516               12492               root                root                sh -c uvicorn app.main:app --host 0.0.0.0 --port ${PARTPILOT_CONTAINER_PORT:-8000}
12576               12516               root                root                /usr/local/bin/python3.12 /usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Runtime engine

- `PARTPILOT_DATABASE_URL`: `sqlite:////data/partpilot.db`
- SQLAlchemy driver/database: `sqlite` / `/data/partpilot.db`
- Pool implementation: `sqlalchemy.pool.impl.QueuePool`
- Pool status from isolated runtime probe: `Pool size: 5  Connections in pool: 1 Current Overflow: -4 Current Checked out connections: 0`
- App connection `PRAGMA foreign_keys`: `1`
- Container UID:GID: `0:0`
- Application runtime uses `QueuePool`; Alembic independently uses
  `NullPool`. These are not interchangeable restore semantics.

## Live SQLite state

- File SHA-256: `5f9bf25f4c1fa41f229d1b69208e7f22b49716ce85d536a3b1420b9540d9e52d`
- Logical SHA-256: `371e79bce6d793abce86c5c7f2ed390b2414773c67309fd81724084fb45794a4`
- Alembic revision: `0007_projects_contract`
- Integrity check: `ok`
- Foreign-key violations: `0`
- Journal mode: `delete`
- Locking mode: `normal`
- Synchronous: `2`
- Busy timeout: `5000` ms
- Page size/count: `4096` / `138`
- Freelist pages: `6`
- Standalone SQLite connection foreign keys before explicit enable: `0`
- Same diagnostic connection after explicit enable: `1`
- The application enables foreign keys on each SQLAlchemy connection.
- No WAL or shared-memory sidecar is present; the current journal mode
  is `delete`. Backup logic must not assume that future deployments
  will always remain in this mode.

### Counts to preserve

| Table | Rows |
|---|---:|
| `users` | 1 |
| `sessions` | 7 |
| `part_types` | 36 |
| `part_type_fields` | 157 |
| `manufacturers` | 9 |
| `packages` | 23 |
| `locations` | 1 |
| `parts` | 15 |
| `part_field_values` | 31 |
| `projects` | 7 |
| `project_items` | 10 |
| `reservations` | 9 |
| `reservation_items` | 14 |
| `stock_movements` | 32 |
| `audit_log` | 96 |
| `app_settings` | 17 |
| `backups` | 0 |

### Session state

- Active sessions: `7`
- Revoked sessions: `0`
- Expired, unrevoked sessions: `0`
- Tokens are stored in the browser, while only SHA-256 token hashes and
  expiry/revocation metadata are stored in SQLite.
- A raw restore of an older snapshot could reactivate session rows that
  were valid when that backup was created. Successful restore must
  therefore invalidate every restored session and require fresh login.

### Dormant backup scaffolding

- `backups.enabled`: `true`
- `backups.frequency`: `daily`
- `backups.path`: `/data/backups`
- `backups.retention_count`: `14`
- `backups` table rows: `0`
- These settings and the `backups` table were seeded in the database
  foundation, but no scheduler, service, API, retention worker or UI
  consumes them. Patch 431 does not activate or reinterpret them.
- The existing `Backup.path` column assumes a retained filesystem path.
  An ephemeral manual download should use append-only `AuditLog` evidence
  rather than inserting a row whose temporary path is immediately removed.

## Alembic revision discovery

- `0001_database_foundation` ← `<base>` (`0001_database_foundation.py`)
- `0002_schema_hardening` ← `0001_database_foundation` (`0002_schema_hardening.py`)
- `0003_user_display_name` ← `0002_schema_hardening` (`0003_user_display_name.py`)
- `0004_manufacturers` ← `0003_user_display_name` (`0004_manufacturers.py`)
- `0005_packages` ← `0004_manufacturers` (`0005_packages.py`)
- `0006_reservation_contract` ← `0005_packages` (`0006_reservation_contract.py`)
- `0007_projects_contract` ← `0006_reservation_contract` (`0007_projects_contract.py`)

The deployed head and database revision are both `0007_projects_contract`.
Initial restore compatibility must be exact-revision only. Automatic
upgrade, downgrade or cross-branch restore is deferred until a separately
tested migration policy exists.

## HTTP, upload and download baseline

- Health status: `200`
- OpenAPI path count: `38`
- Unauthenticated protected Settings status: `401`
- Backup/restore API paths: none
- `UploadFile`, `FileResponse`, `StreamingResponse`, request-stream and
  request-size middleware usage: none
- `python-multipart` installed: `False`
- Health and OpenAPI responses currently have no explicit cache-control
  header. Backup responses must set their own no-store headers.
- Starlette/FastAPI currently has no Part Pilot-specific upload ceiling.
  A future restore endpoint must enforce a body limit at the ASGI receive
  layer; checking `Content-Length` alone is insufficient.

Deployed package versions:

```text
alembic=1.18.5
fastapi=0.141.1
python-multipart=NOT_INSTALLED
sqlalchemy=2.0.51
starlette=1.3.1
uvicorn=0.52.0
```

## Exact source hashes

| File | SHA-256 |
|---|---|
| `.gitignore` | `48f16bb3f8be5b25b363be3523c8b257228f9b88553bbceb85dc727b7998aed9` |
| `backend/Dockerfile` | `0c1f56ed850f41aea0d77081afe514d8ef36cb3e9da232a953740cb99e439807` |
| `backend/alembic/env.py` | `9ea9c09e689ad418bcebca5be5048b0757d6407803639cfa79bcb513c975092d` |
| `backend/alembic/versions/0001_database_foundation.py` | `82107d03f8ca60e3865a494bebb3071213857d49a0fcbe010b5aecebdb2f0807` |
| `backend/app/api/routes/app_settings.py` | `afa370046b06e54ebc8a211e504b63a0b6ddec2d5339617a669e584d5546c3c4` |
| `backend/app/api/routes/auth.py` | `1518e3ce313f0c9d066b7f4d276ac78aa6f2e84c2a6252623ada04a12bb89ec6` |
| `backend/app/core/config.py` | `cb1821d712451f0f3d93bc76f5ce4907bd3a58dac57e8189eb8700c28fcd59fb` |
| `backend/app/db/base.py` | `987edfd9dfe38b2c49492c7d1a4e774015d16b72e2281b018e4160be6b47d560` |
| `backend/app/db/seed.py` | `6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de` |
| `backend/app/db/session.py` | `66d2fd6ad0df1ecf08418d34b9a2634d72bf146d8a919e01a1d8d40f3bcb0fe4` |
| `backend/app/db/settings.py` | `f0c3037f153f856a97a4424ce87ddf30470b0b4fdd2ac150b728ea1f9cdca12b` |
| `backend/app/db/smoke_test.py` | `7e9ad959374b80be5069fd4ed71841cc7d6af62d1ebb1fbf34290e66bab9fbab` |
| `backend/app/main.py` | `d180ade11804b57951f97bb5a3956925e508b94b2da6dcc34db1af632a24a5a6` |
| `backend/app/models/core.py` | `8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679` |
| `backend/app/schemas/auth.py` | `4e12fa84bf0ed86901ff1251c44d745289f5d98cae090cbcfe6f32390e95b8b0` |
| `backend/app/services/app_settings.py` | `8676698c61df0e8ac50f53a54a33caeb183c4e2ffecab5c18e708dbd909b18d1` |
| `backend/app/services/auth.py` | `389c44ac1f8ba48eef071c85e0c0b3cd6376988c730be39e0b3895d0ab501f90` |
| `backend/app/services/debug_reset.py` | `7161e663b2f91f9220589aa8b3fdfb8af15a45f9306c2c7d63fa14fd2a0c24de` |
| `backend/requirements.txt` | `a611bf7cf03a599b4b23a040a1dabd3f6594d5128a1479a49dcba0ea70896289` |
| `docker-compose.yml` | `d0f5e706c0058792934dae8476a2144a5c72b633b6f9d9d6f062ff2ffb98d1ba` |
| `frontend/src/auth/AuthContext.tsx` | `7c046d1c3aac2230ae072e0ea13f6bc22763c5f2deba32fb1a97cec9dd7f5fef` |
| `frontend/src/pages/Settings.css` | `b2913f727fb2df05f287e7bda98768daef17cd9761094035d353535ab4acadd4` |
| `frontend/src/pages/Settings.tsx` | `ff43ef22ddb786a20a70f01b4dc0c93cc13152b6c46273daa4191c15a3ea20d8` |
| `frontend/src/services/authClient.ts` | `2363949c0ee423facbdb070f1b41f37c9fcc06a592e843464becee68465fe640` |
| `frontend/src/services/settingsClient.ts` | `59bb9892fdcc02b9662dce3151c4314b591c835e3fe3822ba25ea6f7e95c0ccf` |
| `frontend/src/types/settings.ts` | `4f57da8db2a6643944c663f87a39dac06ee1cd8c6542eb0eef687ad80ea9641d` |
| `frontend/vite.config.ts` | `b8376116c4a91306a1c522afe67930275dd2d5861e48d980742b36f27406d838` |

## Exact implementation shapes

### Database URL and cached settings

```python
0008: class Settings(BaseSettings):
0009:     app_name: str = Field(default="Part Pilot", alias="PARTPILOT_APP_NAME")
0010:     env: str = Field(default="development", alias="PARTPILOT_ENV")
0011:
0012:     host_port: int = Field(default=7890, alias="PARTPILOT_HOST_PORT")
0013:     container_port: int = Field(default=8000, alias="PARTPILOT_CONTAINER_PORT")
0014:
0015:     database_url: str = Field(
0016:         default="sqlite:///../data/partpilot.db",
0017:         alias="PARTPILOT_DATABASE_URL",
0018:     )
```

```python
0054: @lru_cache
0055: def get_settings() -> Settings:
0056:     return Settings()
```

The database URL is environment-backed and cached for the process lifetime.
A restart is therefore the clean boundary for changing database location
or applying a staged restore bootstrap.

### SQLAlchemy engine, pool and request sessions

```python
0001: from sqlalchemy import create_engine, event
0002: from sqlalchemy.orm import sessionmaker
0003:
0004: from app.core.config import get_settings
0005:
0006: settings = get_settings()
0007:
0008: connect_args = {}
0009: if settings.database_url.startswith("sqlite"):
0010:     connect_args = {"check_same_thread": False}
0011:
0012: engine = create_engine(
0013:     settings.database_url,
0014:     connect_args=connect_args,
0015:     pool_pre_ping=True,
0016: )
0017:
0018:
0019: @event.listens_for(engine, "connect")
0020: def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
0021:     if settings.database_url.startswith("sqlite"):
0022:         cursor = dbapi_connection.cursor()
0023:         cursor.execute("PRAGMA foreign_keys=ON")
0024:         cursor.close()
0025:
0026: SessionLocal = sessionmaker(
0027:     autocommit=False,
0028:     autoflush=False,
0029:     bind=engine,
0030: )
0031:
0032:
0033: def get_db():
0034:     db = SessionLocal()
0035:     try:
0036:         yield db
0037:     finally:
0038:         db.close()
```

The engine does not specify `poolclass`, so SQLAlchemy 2.0 selects
`QueuePool`. Request dependencies close ORM sessions but do not dispose
the engine or guarantee that all concurrent requests have drained.

### Duplicate SQLite foreign-key listeners

```python
0020: from sqlalchemy.orm import Mapped, mapped_column
0021: from sqlalchemy.engine import Engine
0022:
0023: from app.db.base import Base
0024:
0025:
0026: def utc_now() -> datetime:
0027:     return datetime.now(timezone.utc)
0028:
0029:
0030: @event.listens_for(Engine, "connect")
0031: def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
0032:     """Ensure SQLite enforces foreign-key constraints.
0033:
0034:     SQLite accepts foreign-key definitions but does not enforce them unless
0035:     PRAGMA foreign_keys=ON is set per connection.
0036:     """
0037:     cursor = dbapi_connection.cursor()
0038:     cursor.execute("PRAGMA foreign_keys=ON")
0039:     cursor.close()
```

A global `Engine` listener in the model and an engine-specific listener
in `db/session.py` both issue the same pragma. This is harmless but
duplicated. Future lifecycle work should consolidate it without changing
foreign-key enforcement.

### Authentication sessions

```python
0061: class User(Base, TimestampMixin):
0062:     __tablename__ = "users"
0063:
0064:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0065:     username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
0066:     display_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
0067:     password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
0068:     is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
0069:     last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
0070:
0071:
0072: class UserSession(Base, TimestampMixin):
0073:     __tablename__ = "sessions"
0074:
0075:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0076:     user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
0077:     token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
0078:     expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
0079:     revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
0080:     user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
0081:     ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
```

```python
0150: def create_session(
0151:     db: Session,
0152:     *,
0153:     user: User,
0154:     user_agent: str | None = None,
0155:     ip_address: str | None = None,
0156:     days: int = DEFAULT_SESSION_DAYS,
0157:     commit: bool = True,
0158: ) -> SessionToken:
0159:     if days <= 0:
0160:         raise ValueError("Session duration must be positive")
0161:
0162:     token = generate_session_token()
0163:     session = UserSession(
0164:         user_id=user.id,
0165:         token_hash=hash_session_token(token),
0166:         expires_at=_naive_utc_now() + timedelta(days=days),
0167:         revoked_at=None,
0168:         user_agent=user_agent,
0169:         ip_address=ip_address,
0170:     )
0171:     db.add(session)
0172:     db.flush()
0173:     if commit:
0174:         db.commit()
0175:         db.refresh(session)
0176:     return SessionToken(token=token, session=session)
0177:
0178:
0179: def get_session_by_token(db: Session, token: str) -> UserSession | None:
0180:     token_hash = hash_session_token(token)
0181:     return db.execute(select(UserSession).where(UserSession.token_hash == token_hash)).scalar_one_or_none()
0182:
0183:
0184: def is_session_active(session: UserSession) -> bool:
0185:     expires_at = _to_naive_utc(session.expires_at)
0186:     revoked_at = _to_naive_utc(session.revoked_at)
0187:     return revoked_at is None and expires_at is not None and expires_at > _naive_utc_now()
0188:
0189:
0190: def get_user_by_session_token(db: Session, token: str) -> User | None:
0191:     session = get_session_by_token(db, token)
0192:     if session is None or not is_session_active(session):
0193:         return None
0194:     user = db.get(User, session.user_id)
0195:     if user is None or not user.is_active:
0196:         return None
0197:     return user
0198:
0199:
0200: def get_user_for_session_token(db: Session, token: str) -> User | None:
0201:     return get_user_by_session_token(db, token)
0202:
0203:
0204: def logout_session(db: Session, token: str, *, commit: bool = True) -> bool:
0205:     session = get_session_by_token(db, token)
0206:     if session is None:
0207:         return False
0208:     if session.revoked_at is None:
0209:         session.revoked_at = _naive_utc_now()
0210:         db.flush()
0211:         if commit:
0212:             db.commit()
0213:     return True
0214:
0215:
0216: def revoke_session(db: Session, token: str, *, commit: bool = True) -> bool:
0217:     return logout_session(db, token, commit=commit)
```

### Audit and backup models

```python
0483: class AuditLog(Base):
0484:     __tablename__ = "audit_log"
0485:     __table_args__ = (
0486:         CheckConstraint("actor_type IN ('system', 'manual', 'user', 'mcp', 'ai')", name="ck_audit_log_actor_type"),
0487:         Index("ix_audit_log_entity", "entity_type", "entity_id"),
0488:         Index("ix_audit_log_event_created", "event_type", "created_at"),
0489:     )
0490:
0491:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0492:     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
0493:     event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
0494:     entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
0495:     entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
0496:     actor_type: Mapped[str] = mapped_column(String(40), default="system", nullable=False)
0497:     actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
0498:     summary: Mapped[str | None] = mapped_column(Text, nullable=True)
0499:     before_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
0500:     after_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
0501:     metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
0502:
0503:
0504: class Backup(Base):
0505:     __tablename__ = "backups"
0506:     __table_args__ = (
0507:         CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_backups_size_bytes_nonnegative"),
0508:         CheckConstraint("status IN ('created', 'failed', 'restored')", name="ck_backups_status"),
0509:     )
0510:
0511:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
0512:     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
0513:     filename: Mapped[str] = mapped_column(String(255), nullable=False)
0514:     path: Mapped[str] = mapped_column(Text, nullable=False)
0515:     size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
0516:     status: Mapped[str] = mapped_column(String(40), default="created", nullable=False, index=True)
0517:     note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Reset route and reset service

```python
0162: @router.post(
0163:     "/debug/reset-database",
0164:     response_model=DebugResetResponse,
0165: )
0166: def debug_reset_database(
0167:     payload: DebugResetRequest,
0168:     current_user=Depends(get_current_user),
0169:     db: Session = Depends(get_db),
0170: ) -> DebugResetResponse:
0171:     del current_user
0172:
0173:     if not debug_database_reset_enabled():
0174:         raise HTTPException(
0175:             status_code=status.HTTP_404_NOT_FOUND,
0176:             detail="Debug database reset is disabled",
0177:         )
0178:
0179:     if payload.confirmation != RESET_CONFIRMATION:
0180:         raise HTTPException(
0181:             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
0182:             detail=f"Confirmation must be exactly: {RESET_CONFIRMATION}",
0183:         )
0184:
0185:     try:
0186:         result = reset_application_database(db)
0187:     except Exception:
0188:         db.rollback()
0189:         raise
0190:
0191:     return DebugResetResponse(
0192:         ok=True,
0193:         recreated_part_types=result.recreated_part_types,
0194:         recreated_template_fields=result.recreated_template_fields,
0195:         recreated_settings=result.recreated_settings,
0196:     )
```

```python
0016: DEBUG_RESET_ENV = "PARTPILOT_ENABLE_DEBUG_RESET"
0017: RESET_CONFIRMATION = "RESET PART PILOT"
0018:
0019:
0020: @dataclass(frozen=True)
0021: class DebugResetResult:
0022:     recreated_part_types: int
0023:     recreated_template_fields: int
0024:     recreated_settings: int
0025:
0026:
0027: def debug_database_reset_enabled() -> bool:
0028:     value = os.getenv(DEBUG_RESET_ENV, "").strip().lower()
0029:     return value in {"1", "true", "yes", "on"}
0030:
0031:
0032: def reset_application_database(db: Session) -> DebugResetResult:
0033:     if not debug_database_reset_enabled():
0034:         raise RuntimeError("Debug database reset is disabled")
0035:
0036:     # Delete in reverse dependency order so SQLite foreign keys remain enabled.
0037:     for table in reversed(Base.metadata.sorted_tables):
0038:         db.execute(table.delete())
0039:
0040:     db.commit()
0041:
0042:     recreated_part_types = seed_builtin_part_types(db)
0043:     recreated_template_fields = seed_builtin_template_fields(db)
0044:     recreated_settings = seed_default_app_settings(db)
0045:
0046:     return DebugResetResult(
0047:         recreated_part_types=recreated_part_types,
0048:         recreated_template_fields=recreated_template_fields,
0049:         recreated_settings=recreated_settings,
0050:     )
```

Database reset is an authenticated, environment-gated row deletion and
reseed transaction. It does not replace the SQLite file. It deletes the
`sessions` table contents, so the current browser token becomes invalid.
Restore must remain a separate product operation and must not reuse reset
implementation semantics.

### Application startup and shutdown

```python
0055: from app.core.config import get_settings
0056:
0057: settings = get_settings()
0058:
0059: app = FastAPI(title=settings.app_name)
0060:
0061: app.add_middleware(
0062:     CORSMiddleware,
0063:     allow_origins=settings.cors_origin_list,
0064:     allow_credentials=True,
0065:     allow_methods=["*"],
0066:     allow_headers=["*"],
0067: )
0068:
0069: # Root health check required by Phase 1 completion criteria.
0070: app.include_router(health_router)
0071:
0072: # API-prefixed health check for the frontend API client.
0073: app.include_router(health_router, prefix="/api")
0074:
0075: # Phase 3 authentication routes.
0076: app.include_router(auth_router, prefix="/api")
0077:
0078: # Phase 4 part type and template field routes.
0079: app.include_router(part_types_router, prefix="/api")
0080: # PATCH 093: inventory part API
0081: app.include_router(parts_router, prefix="/api")
0082: # PATCH 095: manufacturer catalogue API
0083: app.include_router(manufacturers_router, prefix="/api")
0084: # PATCH 128: package catalogue API
0085: app.include_router(packages_router, prefix="/api")
0086: # PATCH 156: reusable location catalogue API
0087: app.include_router(locations_router, prefix="/api")
0088: # PATCH 182: protected application search settings API
0089: app.include_router(app_settings_router, prefix="/api")
0090: # PATCH 303: protected reservation read/create API
0091: app.include_router(reservations_router, prefix="/api")
0092: # PATCH 374: protected Project read/create API
0093: app.include_router(projects_router, prefix="/api")
0094: # PARTPILOT:SYSTEM_HISTORY_ROUTER_REGISTRATION:V406
0095: app.include_router(history_router, prefix="/api")
0096:
0097: frontend_dist = Path("/app/frontend_dist")
0098: if frontend_dist.exists():
0099:     app.mount(
0100:         "/",
0101:         SPAStaticFiles(directory=frontend_dist, html=True),
0102:         name="frontend",
0103:     )
```

There is no FastAPI lifespan handler, startup restore bootstrap, shutdown
drain, engine disposal or application maintenance gate.

### Alembic runtime

```python
0015: settings = get_settings()
0016: config.set_main_option("sqlalchemy.url", settings.database_url)
0017:
0018: target_metadata = Base.metadata
0019:
0020:
0021: def run_migrations_offline() -> None:
0022:     url = config.get_main_option("sqlalchemy.url")
0023:     context.configure(
0024:         url=url,
0025:         target_metadata=target_metadata,
0026:         literal_binds=True,
0027:         dialect_opts={"paramstyle": "named"},
0028:     )
0029:
0030:     with context.begin_transaction():
0031:         context.run_migrations()
0032:
0033:
0034: def run_migrations_online() -> None:
0035:     connectable = engine_from_config(
0036:         config.get_section(config.config_ini_section, {}),
0037:         prefix="sqlalchemy.",
0038:         poolclass=pool.NullPool,
0039:     )
0040:
0041:     with connectable.connect() as connection:
0042:         context.configure(
0043:             connection=connection,
0044:             target_metadata=target_metadata,
0045:         )
0046:
0047:         with context.begin_transaction():
0048:             context.run_migrations()
```

### Docker process and persistent volume

```dockerfile
0010: FROM python:3.12-slim
0011:
0012: ENV PYTHONUNBUFFERED=1
0013: ENV PYTHONDONTWRITEBYTECODE=1
0014:
0015: WORKDIR /app
0016:
0017: COPY backend/requirements.txt /app/backend/requirements.txt
0018: RUN pip install --no-cache-dir -r /app/backend/requirements.txt
0019:
0020: COPY backend /app/backend
0021: COPY --from=frontend-builder /frontend/dist /app/frontend_dist
0022:
0023: WORKDIR /app/backend
0024:
0025: # EXPOSE is documentation only. Runtime port is controlled by PARTPILOT_CONTAINER_PORT.
0026: EXPOSE 8000
0027:
0028: CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PARTPILOT_CONTAINER_PORT:-8000}"]
```

```yaml
0001: services:
0002:   partpilot:
0003:     build:
0004:       context: .
0005:       dockerfile: backend/Dockerfile
0006:     container_name: partpilot
0007:     env_file:
0008:       - .env
0009:     environment:
0010:       PARTPILOT_DATABASE_URL: sqlite:////data/partpilot.db
0011:       PARTPILOT_ENABLE_DEBUG_RESET: "${PARTPILOT_ENABLE_DEBUG_RESET:-true}"
0012:     ports:
0013:       - "${PARTPILOT_HOST_PORT:-7890}:${PARTPILOT_CONTAINER_PORT:-8000}"
0014:     volumes:
0015:       - ./data:/data
0016:     restart: unless-stopped
```

The container has one Uvicorn process, no reload worker and no healthcheck.
Docker's `unless-stopped` restart policy can support a controlled restore
restart after a pre-Uvicorn bootstrap is introduced.

### Seeded backup settings

```python
0053:     "appearance.theme": {"value_json": "dark", "value_text": "dark"},
0054:     "appearance.light_theme_available": {"value_json": True, "value_text": None},
0055:     "currency.default": {"value_json": None, "value_text": None},
0056:     "timezone.default": {"value_json": None, "value_text": None},
0057:     "search.show_out_of_stock_section": {"value_json": True, "value_text": None},
0058:     "price.warn_when_missing": {"value_json": True, "value_text": None},
0059:     "reservations.expiry.mode": {"value_json": "none", "value_text": "none"},
0060:     "reservations.expiry.default_days": {"value_json": None, "value_text": None},
0061:     "backups.enabled": {"value_json": True, "value_text": None},
0062:     "backups.frequency": {"value_json": "daily", "value_text": "daily"},
0063:     "backups.path": {"value_json": "/data/backups", "value_text": "/data/backups"},
0064:     "backups.retention_count": {"value_json": 14, "value_text": None},
0065:     "mcp.enabled": {"value_json": False, "value_text": None},
0066:     "mcp.read_tools_enabled": {"value_json": True, "value_text": None},
0067:     "mcp.write_tools_enabled": {"value_json": False, "value_text": None},
0068: }
```

### Settings Data section and reset flow

```tsx
0325:     }
0326:     setResetDialogOpen(false);
0327:     setConfirmation("");
0328:     setResetError(null);
0329:   }
0330:
0331:   async function confirmDatabaseReset(): Promise<void> {
0332:     const activeToken =
0333:       token ?? localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
0334:
0335:     if (!activeToken) {
0336:       setResetError(
0337:         "Your session is missing. Sign in again before resetting."
0338:       );
0339:       return;
0340:     }
0341:
0342:     setIsResetting(true);
0343:     setResetError(null);
0344:
0345:     try {
0346:       await resetApplicationDatabase(
0347:         activeToken,
0348:         confirmation
0349:       );
0350:       localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
0351:       localStorage.removeItem(APPEARANCE_STORAGE_KEY);
0352:       document.documentElement.dataset.theme = "dark";
0353:       document.documentElement.dataset.themePreference = "dark";
0354:       document.documentElement.style.colorScheme = "dark";
0355:       window.location.replace("/");
0356:     } catch (caught) {
0357:       setResetError(
0358:         caught instanceof Error
0359:           ? caught.message
0360:           : "Unable to reset the database"
0361:       );
0362:       setIsResetting(false);
0363:     }
0364:   }
0365:
0366:   return (
0367:     <div
0368:       className="page-stack settings-page"
0369:       data-search-settings-version="search-settings-toggle-v194"
0370:       data-reservation-settings-version="reservation-expiry-settings-v362"
0371:       data-partpilot-appearance="PARTPILOT:SETTINGS_APPEARANCE_WORKSPACE:V412"
0372:       data-partpilot-runtime-badge="PARTPILOT:SETTINGS_RUNTIME_BADGE_REMOVED:V428"
0373:     >
0374:       <header className="page-header settings-page-header">
0375:         <div>
0376:           <p className="eyebrow">Application configuration</p>
0377:           <h1>Settings</h1>
0378:           <p>
0379:             Manage appearance, inventory behavior, reservation defaults,
0380:             and local data controls for this installation.
0381:           </p>
0382:         </div>
0383:       </header>
0384:
0385:       <nav
```

```tsx
0770:               className="settings-preference-state is-success"
0771:               role="status"
0772:             >
0773:               Reservation defaults saved.
0774:             </p>
0775:           ) : null}
0776:         </section>
0777:
0778:         <section
0779:           id="settings-data"
0780:           className="card settings-section settings-danger-section settings-grid-data"
0781:           aria-labelledby="settings-data-title"
0782:         >
0783:           <div className="settings-section-heading">
0784:             <div>
0785:               <span className="card-label">Local data</span>
0786:               <h2 id="settings-data-title">Database reset</h2>
0787:               <p>
0788:                 Return this installation to first-run setup. Built-in
0789:                 part types, templates, and default settings are recreated.
0790:               </p>
0791:             </div>
0792:             <span className="settings-danger-badge">
0793:               Permanent action
0794:             </span>
0795:           </div>
0796:
0797:           <div className="settings-danger-summary">
0798:             <p>
0799:               This deletes the owner account, sessions, inventory,
0800:               Projects, Reservations, History, and application settings.
0801:               Files outside the database are not removed.
0802:             </p>
0803:             <button
0804:               className="danger-button settings-danger-launch"
0805:               type="button"
0806:               onClick={openDatabaseResetDialog}
0807:             >
0808:               Review database reset
0809:             </button>
0810:           </div>
0811:         </section>
0812:       </div>
0813:
0814:       {resetDialogOpen ? (
0815:         <div
0816:           className="settings-reset-backdrop"
0817:           data-partpilot-reset-dialog="PARTPILOT:SETTINGS_RESET_DIALOG:V412"
0818:           data-partpilot-reset-refinement="PARTPILOT:SETTINGS_RESET_DIALOG_REFINEMENT:V415"
0819:         >
0820:           <section
0821:             className="settings-reset-dialog"
0822:             role="dialog"
0823:             aria-modal="true"
0824:             aria-labelledby="settings-reset-dialog-title"
0825:             aria-describedby="settings-reset-dialog-description"
0826:           >
0827:             <header>
0828:               <p className="eyebrow">Final confirmation</p>
0829:               <h2 id="settings-reset-dialog-title">
0830:                 Erase the Part Pilot database?
0831:               </h2>
0832:             </header>
0833:             <div className="settings-reset-dialog-content">
0834:               <p id="settings-reset-dialog-description">
0835:                 This immediately removes every local database record
0836:                 and signs you out. This action cannot be undone.
0837:               </p>
0838:               <dl>
0839:                 <div>
0840:                   <dt>Scope</dt>
0841:                   <dd>Accounts, inventory, workflows, history, settings</dd>
0842:                 </div>
0843:               </dl>
0844:               <label className="settings-reset-confirmation">
0845:                 <span>
0846:                   Type <code>{RESET_CONFIRMATION}</code> to continue
0847:                 </span>
0848:                 <input
0849:                   type="text"
0850:                   value={confirmation}
0851:                   onChange={(event) => {
0852:                     setConfirmation(event.target.value);
0853:                     setResetError(null);
0854:                   }}
0855:                   placeholder={RESET_CONFIRMATION}
0856:                   autoComplete="off"
0857:                   spellCheck={false}
0858:                   autoFocus
0859:                   aria-invalid={Boolean(resetError)}
0860:                 />
0861:               </label>
0862:               {resetError ? (
0863:                 <p className="form-error" role="alert">
0864:                   {resetError}
0865:                 </p>
0866:               ) : null}
0867:             </div>
0868:             <footer>
0869:               <button
0870:                 className="settings-action settings-action-secondary"
0871:                 type="button"
0872:                 disabled={isResetting}
0873:                 onClick={closeDatabaseResetDialog}
0874:               >
0875:                 Keep existing data
0876:               </button>
0877:               <button
0878:                 className="danger-button"
0879:                 type="button"
0880:                 disabled={!canReset}
0881:                 onClick={() =>
0882:                   void confirmDatabaseReset()
0883:                 }
0884:               >
0885:                 {isResetting
0886:                   ? "Erasing database..."
0887:                   : "Erase database permanently"}
0888:               </button>
0889:             </footer>
0890:           </section>
0891:         </div>
0892:       ) : null}
0893:     </div>
0894:   );
0895: }
```

The Data card is currently a dedicated Database reset danger card. Backup
and restore should turn Data into a broader product area with three
visually separate operations: Download backup, Restore backup, and the
existing permanent Database reset subsection. Existing reset phrase
confirmation and sign-out behavior must remain intact.

## Risk register

### R1 — Live file replacement with pooled connections

**Severity: critical.** Replacing `/data/partpilot.db` while Uvicorn is
running can leave checked-out or pooled SQLite connections attached to the
old inode. Different requests could then observe different database files.
`engine.dispose()` alone does not close connections currently checked out
by concurrent requests. A direct in-request file swap is rejected.

### R2 — No maintenance/drain lifecycle

**Severity: critical.** The application has no gate that rejects new writes,
tracks active requests, drains sessions or closes the engine. Restore must
not be enabled until restart/bootstrap coordination exists.

### R3 — Session resurrection

**Severity: high.** A snapshot includes session rows. Restoring them unchanged
can revive old tokens and remove newer revocations. Successful restore must
delete all restored sessions before service availability and communicate
that every browser will be signed out.

### R4 — Upload and archive abuse

**Severity: high.** There is no body-size middleware or multipart dependency.
A restore endpoint needs streaming limits, archive-entry limits, extracted
size limits, compression-ratio checks, path validation and strict file
allowlisting before parsing SQLite.

### R5 — Ownership and atomicity

**Severity: high.** The current process and database are root-owned. Atomic
replacement requires candidate, rollback and live files on the same ext4
filesystem, explicit mode/UID/GID preservation, `fsync` of files and parent
directory, and `os.replace` rather than cross-filesystem copy.

### R6 — Incomplete backup scaffolding

**Severity: medium.** Existing settings imply scheduled retained backups but
no worker exists. The first implementation should be explicit manual
download only; scheduling/retention must not appear active until built.

### R7 — No Docker healthcheck

**Severity: medium.** Restore restart progress cannot rely on container health
today. Add a real healthcheck or poll `/api/health` with bounded retry and
verify Alembic plus database integrity before declaring restore complete.

### R8 — Audit placement

**Severity: medium.** A successful restore replaces the database that recorded
the request. Success evidence must be appended to the restored database
after validation. On rollback, verify the exact original snapshot first,
then append a single failure audit as the only intentional post-verification
delta.

## Backup artifact proposal — format version 1

### Archive contract

- Extension: `.ppbackup`
- Media type: `application/vnd.partpilot.backup+zip`
- Exact archive entries: `manifest.json` and `partpilot.db`
- No directories, duplicate names, extra files, symlinks, encrypted
  entries, absolute paths or path traversal.
- Human-readable filename:
  `part-pilot-backup-YYYYMMDDTHHMMSSZ-0007-projects-contract.ppbackup`.
- The timestamp is UTC and the revision slug is normalized.
- `manifest.json` is UTF-8 canonical JSON with sorted keys and a trailing
  newline. Format version 1 requires an exact known key set.

### Required manifest shape

```json
{
  "application": {
    "backup_writer_version": 1,
    "name": "Part Pilot"
  },
  "created_at_utc": "2026-08-01T17:55:00Z",
  "database": {
    "filename": "partpilot.db",
    "foreign_key_violations": 0,
    "sha256": "5f9bf25f4c1fa41f229d1b69208e7f22b49716ce85d536a3b1420b9540d9e52d",
    "size_bytes": 565248,
    "sqlite_integrity_check": "ok"
  },
  "format": "part-pilot-backup",
  "format_version": 1,
  "restore_policy": {
    "invalidate_all_sessions_after_restore": true,
    "sessions_present_in_snapshot": true
  },
  "schema": {
    "alembic_revision": "0007_projects_contract",
    "compatibility_policy": "exact_revision",
    "critical_schema_sha256": "7e8b9dcc58dbe0d17095a7637dd4d29d9ec0d31ce18e9e6283800822fcc2129e",
    "database_dialect": "sqlite"
  },
  "scope": {
    "excluded": [
      "container_image",
      "logs",
      "temporary_files"
    ],
    "included": [
      "users",
      "catalogues",
      "parts",
      "projects",
      "reservations",
      "stock_movements",
      "audit_log",
      "app_settings",
      "sessions"
    ]
  }
}
```

### Snapshot creation

1. Authenticate the requesting user.
2. Create a mode-0700 operation directory under `/tmp`.
3. Open the live SQLite database read-only and create `partpilot.db` with
   Python's `sqlite3.Connection.backup()` online backup API.
4. Open the snapshot independently, enable foreign keys, run
   `PRAGMA integrity_check` and `PRAGMA foreign_key_check`, discover the
   Alembic revision, required tables and critical settings.
5. Hash the completed snapshot, write the canonical manifest, package exactly
   the two allowlisted entries and hash the final archive for audit metadata.
6. Append `backup.generated` to the live `audit_log` with requester, format
   version, revision, filename, database hash and archive size. This audit
   is evidence of generation and is not required to be inside that snapshot.
7. Return a file response with:
   - `Content-Type: application/vnd.partpilot.backup+zip`;
   - quoted `Content-Disposition` filename;
   - `Cache-Control: no-store, max-age=0`;
   - `Pragma: no-cache`;
   - `X-Content-Type-Options: nosniff`.
8. Remove the operation directory with a response background cleanup task.
   Also sweep only stale, marker-owned backup temp directories on startup.

The online backup API is the consistency mechanism. Directly copying a
live database file is explicitly rejected.

## Protected backup API proposal

### `POST /api/backups/download`

- Requires the existing Bearer authentication dependency.
- Accepts no database path and no arbitrary filename.
- Creates one snapshot on demand and returns the versioned artifact.
- Uses a per-process backup lock to limit concurrent snapshot work.
- Does not modify inventory, reservations, projects or stock movements.
- Writes one actor-attributed audit event after artifact validation.
- Manual download is independent of the dormant scheduling settings.

A later `GET /api/backups/capabilities` may expose format/version and limits
to the Settings UI. It must not expose host filesystem paths.

## Restore validation contract

### Limits

- Default compressed upload limit: 256 MiB.
- Default extracted database limit: 1 GiB.
- Manifest limit: 64 KiB.
- Archive entry count: exactly 2.
- Enforce `Content-Length` when present and independently count bytes at
  the ASGI receive layer so chunked requests cannot bypass the ceiling.
- Reject suspicious compression ratios and unsupported compression methods.
- Add `python-multipart` only when the bounded upload contract is implemented.

### Validation before any live change

1. Stream the upload to a marker-owned staging file with mode 0600.
2. Verify ZIP structure without extracting paths blindly.
3. Normalize every entry using POSIX rules and reject absolute paths, drive
   prefixes, `..`, empty names, duplicate names, symlinks, devices,
   encrypted entries and all unexpected files.
4. Parse the manifest with an exact schema; reject unknown format versions,
   missing fields, wrong types, invalid UTC timestamps and duplicate JSON
   keys.
5. Verify declared filename, compressed/extracted sizes and database SHA-256.
6. Require `format=part-pilot-backup`, `format_version=1`, SQLite dialect and
   exact Alembic revision `0007_projects_contract` for the initial release.
7. Open the candidate in immutable/read-only mode. Run integrity and
   foreign-key checks.
8. Verify the full required-table allowlist, critical columns/schema hash,
   one Alembic row, at least one active user, setup completion and valid
   currency/timezone/appearance values.
9. Produce a sanitized metadata summary and opaque high-entropy validation
   token. Do not expose archive paths.
10. Any rejection removes only operation-owned staging files and leaves the
    live database byte-for-byte unchanged.

### Proposed two-phase API

- `POST /api/restores/validate`: bounded multipart upload; returns sanitized
  metadata, warnings, expiry and an opaque validation token.
- `POST /api/restores/{validation_token}/commit`: requires authentication,
  an exact typed confirmation phrase and the still-valid staged hash.
- Validation tokens are single-use, short-lived, mode-0600 state owned by
  the installation and bound to the requesting user.

## Restore replacement and restart decision

### Decision

**Do not replace the live database inside the running Uvicorn request
process. Use a controlled container restart and a pre-Uvicorn restore
bootstrap.**

The current process has QueuePool connections, no request drain and no
lifespan disposal. A bootstrap that runs before Uvicorn starts is the only
current design that can prove no application connection is open during
replacement.

### Required lifecycle additions before restore is enabled

1. Add a FastAPI lifespan handler that closes request-owned resources and
   calls `engine.dispose(close=True)` on shutdown.
2. Add an application maintenance gate so restore confirmation blocks new
   mutating requests and waits for bounded active-request drain.
3. Add a small container entrypoint/restore-bootstrap runner before Uvicorn.
4. The confirmed API writes an fsynced restore job under a fixed internal
   `/data/.partpilot-restore/` directory, returns `202 Accepted`, then a
   post-response action terminates the container cleanly.
5. Docker `restart: unless-stopped` starts the bootstrap. The commit endpoint
   must remain disabled unless that supervisor contract is detected.

### Bootstrap sequence

1. Revalidate the job token, archive hash, manifest and candidate database.
2. Open the current live database and create an online rollback snapshot
   with `sqlite3.Connection.backup()` on the same `/data` filesystem.
3. Validate and fsync the rollback snapshot; record its file and logical
   hashes in operation state.
4. Preserve live file mode, UID and GID on the candidate.
5. Atomically move the live file to an operation-owned previous path and
   `os.replace()` the candidate into `/data/partpilot.db`; fsync the file
   and parent directory.
6. Open the replacement independently, rerun all checks, delete all rows
   from `sessions`, append one `backup.restored` audit, commit and verify
   again.
7. Start Uvicorn only after the final database is healthy and the Alembic
   revision is compatible.
8. Keep a bounded restore result record for the frontend, then remove all
   candidate/rollback files after acknowledgement or retention timeout.

### Failure and rollback

On any bootstrap failure:

1. Close every SQLite handle.
2. Atomically restore the validated rollback snapshot.
3. Reopen it and verify the exact pre-restore file/logical hashes, integrity,
   foreign keys, revision, counts and critical settings.
4. Only after exact verification, append one `backup.restore_failed` audit as
   the sole intentional delta.
5. Start the service on the recovered original database and verify health.
6. Preserve a sanitized operation result; remove only manifest-owned staging
   files.
7. If rollback verification itself fails, do not start normal application
   traffic. Leave the original and rollback artifacts intact and report the
   exact paths, hashes and failure phase.

## Authentication consequences

- Backup download does not invalidate the caller's session.
- Restore validation does not invalidate sessions.
- Restore commit signs out every browser. The frontend should clear
  `partpilot.auth.token` and appearance cache after the commit is accepted.
- Successful bootstrap deletes all restored session rows before Uvicorn
  becomes available. The owner signs in again against the restored user
  database.
- If restore rolls back, original session rows are recovered, but the
  initiating browser may still require a fresh login because its local token
  was deliberately cleared.
- A restore audit uses `actor_user_id` only when the requested user ID and
  username still identify the same restored user; otherwise it records a
  system actor with sanitized requester metadata.

## Settings Data UI proposal

After backend contracts pass independently:

1. Rename the Data card heading from `Database reset` to `Backup and restore`.
2. Add a non-destructive Download backup row with format/revision guidance.
3. Add a separate destructive Restore backup row with file picker and
   `Review restore` action.
4. Keep Database reset as its own permanent-action subsection with the
   existing phrase-confirmed dialog.
5. Restore review shows filename, creation UTC, format version, revision,
   database size/hash status, included scope and sign-out/restart warning.
6. Progress states are explicit: Uploading, Validating, Ready for review,
   Scheduling restart, Restoring, Verifying, Restarting, Complete/Rolled
   back.
7. Use an accessible in-app dialog, focus management, Escape restrictions
   during commit and useful validation/rollback errors. Do not use native
   browser confirmation.
8. Preserve the current mobile order and readable one-column controls.

## Testing design

All automated restore tests use copied databases and injectable paths.
The real `/projects/Part Pilot/data/partpilot.db` is never a restore target.

Required coverage:

- online backup consistency while a copied source receives writes;
- deterministic manifest and human-readable filename;
- exact preservation of every existing user, catalogue, Part, Project,
  Reservation, movement, audit and setting row;
- successful restore adds only the expected restore audit and session
  invalidation delta;
- corrupt ZIP, truncated ZIP, extra/duplicate entries, encrypted entry,
  absolute path, Windows drive path, `..` traversal and symlink rejection;
- manifest parse/type/required-field/unknown-version failures;
- database hash mismatch, oversized upload, oversized extracted database
  and compression-bomb behavior;
- incompatible Alembic revision, missing/extra critical tables, schema
  fingerprint mismatch, integrity failure and foreign-key failure;
- interrupted replacement at every fsync/rename boundary;
- rollback restores exact copied source bytes/logical state before the
  append-only failure audit;
- restart/bootstrap success and startup refusal after unrecoverable failure;
- OpenAPI contracts, unauthenticated rejection, no-cache download headers,
  cleanup of operation-owned temp files and no inventory mutations;
- complete copied-database smoke suite and live database preservation.

## Safe sequential implementation plan

1. **Artifact core:** add typed manifest models, online SQLite snapshot helper,
   canonical packaging, validation primitives and copied-database tests.
2. **Protected download:** add authenticated backup route, headers, cleanup,
   audit evidence, OpenAPI and smoke coverage. Browser-test download only.
3. **Lifecycle foundation:** add lifespan engine disposal, maintenance gate,
   bounded request accounting and health/readiness distinction.
4. **Restore validator:** add ASGI upload limit, multipart dependency, strict
   archive/manifest/schema validation and staged metadata contract.
5. **Bootstrap/rollback:** add pre-Uvicorn restore runner, operation state,
   online rollback snapshot, atomic replacement, session invalidation,
   verification and fault-injection tests against copies.
6. **Restore APIs:** connect validate/commit contracts only after restart
   behavior is proven in Docker and rollback tests pass.
7. **Settings UI:** add Download, Restore review/progress and preserve reset.
8. **Browser approval:** test dark/light, desktop/mobile, invalid artifacts,
   successful isolated restore, sign-out, restart and rollback messaging.
9. **Checkpoint:** stage only approved files, rerun full copied-database smoke,
   verify live bytes/logical state, commit and push.

MCP remains deferred and must not enter any backup/restore patch.

## Diagnostic conclusion

- Backup is feasible without service restart when generated through the
  SQLite online backup API and served from an operation-owned temp artifact.
- Restore is not safe in the current request process because QueuePool,
  concurrent sessions and missing lifecycle controls prevent proof that all
  connections have released the old inode.
- The approved direction is strict validate-first staging plus a controlled
  restart/pre-Uvicorn bootstrap with an online rollback snapshot and atomic
  same-filesystem replacement.
- Successful restore invalidates all sessions and requires sign-in.
- No implementation should begin until this report is inspected.

## Diagnostic invariants

- Critical schema SHA-256: `7e8b9dcc58dbe0d17095a7637dd4d29d9ec0d31ce18e9e6283800822fcc2129e`
- Source marker groups validated: `9`
- Upload/download source token counts: `{"BaseHTTPMiddleware": 0, "Content-Disposition": 0, "FileResponse": 0, "StreamingResponse": 0, "UploadFile": 0, "request.stream(": 0}`
- Duplicate foreign-key listeners observed: `2`
- FastAPI lifespan hooks observed: `0`
- Engine disposal calls observed: `0`
