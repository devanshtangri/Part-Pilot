# PartPilot Phase 3 Auth Handoff

**Project:** PartPilot / Part Pilot  
**Repo:** `https://github.com/devanshtangri/Part-Pilot.git`  
**Local project path used by user:** `/projects/Part Pilot`  
**Container/service name:** `partpilot`  
**Current phase:** Phase 3 — First-run setup and authentication  
**Created after:** Patch 029 failed to apply due to a syntax error.

---

## Important Working Preferences

- Continue using numbered downloadable fix scripts in `fixes/NNN_*.py`.
- Do **not** spam `git status --short` after every patch/test cycle. Use it only:
  - before a commit/checkpoint,
  - when diagnosing unexpected file changes,
  - or when verifying final repo state.
- It is acceptable to add/update `.md` files in `docs/` as a secondary project memory/handoff mechanism when useful.
- Do not assume GitHub is fully up to date with local state unless the user confirms `git status` or has pushed.
- Avoid rewriting large files blindly unless restoring from a known-good commit first.
- If a file has become corrupted by a patch, restore it from `HEAD` first, then reapply the intended changes cleanly.

---

## Clean Commit Baseline

The last known committed and pushed clean checkpoint before the current uncommitted Phase 3 route/service work was:

```text
236f6c0 (HEAD -> main, origin/main) Add Phase 3 auth foundation
```

At that point:
- Phase 3 auth foundation was committed.
- `backend/app/core/security.py` existed.
- `backend/requirements.txt` included auth hashing dependencies.
- `backend/app/db/smoke_test.py` included auth foundation checks.
- Smoke test passed through:

```text
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth foundation smoke test completed
```

Do not assume later patches are committed unless user confirms.

---

## Current Uncommitted Work After Patch 028 / Failed Patch 029

The user has been applying fixes after commit `236f6c0`. Current working tree is expected to contain uncommitted changes from patches 021–028 and a failed 029 script. Important touched files likely include:

```text
backend/app/db/smoke_test.py
backend/app/main.py
backend/app/services/__init__.py
backend/app/services/auth.py
backend/app/schemas/__init__.py
backend/app/schemas/auth.py
backend/app/api/routes/__init__.py
backend/app/api/routes/auth.py
backend/requirements.txt
fixes/018_phase3_auth_service.py
fixes/019_phase3_auth_service_schema_fix.py
fixes/020_phase3_auth_service_import_fix.py
fixes/021_phase3_auth_service_clean_reapply.py
fixes/022_phase3_auth_api_routes.py
fixes/023_phase3_auth_service_api_compat.py
fixes/024_phase3_register_auth_routes.py
fixes/025_phase3_restore_auth_smoke_and_routes.py
fixes/026_phase3_auth_api_route_smoke_fix.py
fixes/027_phase3_auth_api_flow_smoke.py
fixes/028_phase3_add_testclient_dependency.py
fixes/029_phase3_auth_datetime_fix.py  # broken script
```

Ask the user for `git status --short` only if needed before creating the next patch or committing.

---

## What Already Went Wrong and Was Fixed

### 1. Wrong directory patch

An early auth foundation patch wrote files to:

```text
app/...
alembic/...
```

instead of:

```text
backend/app/...
backend/alembic/...
```

This was fixed by removing the wrong root-level `app/` and `alembic/`.

### 2. Redundant users migration/model

A patch incorrectly added:

```text
backend/app/models/user.py
backend/alembic/versions/0003_users.py
```

That was wrong because the existing repo already had `User` and `UserSession` in:

```text
backend/app/models/core.py
```

and the Phase 2 database foundation already had the `users` and `sessions` tables. No new migration is required for the current V1 auth work.

The redundant files were removed by recovery patches.

### 3. `backend/app/models/__init__.py` corruption

Some patches overwrote `models/__init__.py` with guessed imports like:

```python
from app.models.part import Part
```

but the actual project model layout is mostly in:

```text
backend/app/models/core.py
```

This was fixed by restoring `backend/app/models/__init__.py` from `HEAD`.

### 4. `passlib`/`bcrypt` warning

`passlib==1.7.4` with newer `bcrypt` produced:

```text
(trapped) error reading bcrypt version
```

This was fixed by pinning:

```text
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

### 5. Auth service import/name mismatch

Patch 022 used `get_user_for_session_token`, while the smoke test expected `get_user_by_session_token`.

Patch 023 added compatibility aliases so both names should exist:

- `get_user_by_session_token(...)`
- `get_user_for_session_token(...)`
- `logout_session(...)`
- `revoke_session(...)`

### 6. Route registration missing

The smoke test found all auth API routes missing:

```text
Missing auth API routes: ['/api/auth/login', '/api/auth/logout', '/api/auth/me', '/api/auth/setup', '/api/auth/setup-status']
```

Patch 024/025 registered auth routes in `backend/app/main.py`.

### 7. Smoke route listing broke on FastAPI internals

Smoke test originally did:

```python
routes = {route.path for route in fastapi_app.routes}
```

That failed with:

```text
AttributeError: '_IncludedRouter' object has no attribute 'path'
```

Patch 026 changed route checking to use OpenAPI paths:

```python
paths = set(fastapi_app.openapi().get("paths", {}).keys())
```

This worked.

### 8. Missing TestClient dependency

Patch 027 introduced FastAPI `TestClient`, but Starlette required `httpx2`:

```text
RuntimeError: The starlette.testclient module requires the httpx2 package to be installed.
```

Patch 028 added `httpx2` to `backend/requirements.txt`.

---

## Last Successful Smoke Test Before Patch 027 API Flow Failure

After Patch 026, smoke test passed:

```text
[PASS] Database connection works
[PASS] SQLite foreign keys are enabled
[PASS] Alembic is at head: 0002_schema_hardening
[PASS] Built-in part types exist: 34
[PASS] Template fields exist: 153
[PASS] Default app settings exist: 17
[PASS] Invalid part without name/part number is rejected
[PASS] Valid sample part can be inserted and rolled back
[PASS] Backend DB utilities work
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth service works
[PASS] Phase 3 auth API routes are registered
[PASS] Phase 3 auth service smoke test completed
```

---

## Current Failing State

Patch 028 installed `httpx2`, so the API flow smoke test now runs further.

The current failure is:

```text
TypeError: can't compare offset-naive and offset-aware datetimes
```

Trace location:

```text
/app/backend/app/api/routes/auth.py", line 41, in get_current_user
  user = get_user_for_session_token(db, token)

/app/backend/app/services/auth.py", line 141, in get_user_for_session_token
  return get_user_by_session_token(db, token)

/app/backend/app/services/auth.py", line 132, in get_user_by_session_token
  if session is None or not is_session_active(session):

/app/backend/app/services/auth.py", line 127, in is_session_active
  return session.revoked_at is None and session.expires_at > utc_now()

TypeError: can't compare offset-naive and offset-aware datetimes
```

This means:
- Login succeeded.
- A token was issued.
- `/api/auth/me` was called with `Authorization: Bearer <token>`.
- The API dependency reached `get_user_for_session_token`.
- The session lookup worked far enough to compare `session.expires_at`.
- SQLite returned `session.expires_at` as a timezone-naive datetime.
- The auth service compares it against a timezone-aware `utc_now()`.

Patch 029 was supposed to fix this, but **Patch 029 did not run** because the generated script itself had a syntax error:

```text
File "/projects/Part Pilot/fixes/029_phase3_auth_datetime_fix.py", line 15
    """Normalize DB datetimes for SQLite-safe comparisons.
       ^^^^^^^^^
SyntaxError: invalid syntax
```

Therefore the container remained on the previous auth service code, and the same datetime failure repeated.

---

## Next Best Step

Create a new fix script:

```text
fixes/030_phase3_auth_datetime_fix_clean.py
```

It should **not** use a nested triple-quote string incorrectly. Use safe quoting or build the file from a raw triple-single-quoted string.

Patch 030 should update only:

```text
backend/app/services/auth.py
```

unless inspection shows another file truly needs a change.

### Required behavior

Normalize all auth service datetimes to one consistent style. Since SQLite returns naive datetimes, the simplest local-compatible approach is:

- Use naive UTC timestamps internally for auth/session comparisons.
- Generate naive UTC with:

```python
datetime.utcnow()
```

or:

```python
datetime.now(timezone.utc).replace(tzinfo=None)
```

- When comparing values from DB, normalize them:

```python
def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value
```

Then:

```python
def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def is_session_active(session: UserSession) -> bool:
    if session.revoked_at is not None:
        return False
    return normalize_datetime(session.expires_at) > utc_now()
```

Also ensure `create_session()` stores:

```python
expires_at=utc_now() + timedelta(days=SESSION_DAYS)
```

not a timezone-aware datetime.

If `revoke_session()` sets `revoked_at`, use `utc_now()`.

---

## Auth Service Design Notes

The existing schema is single-user V1 oriented. Do not add role/admin fields unless the user explicitly changes scope.

Expected service functions:

```python
normalize_username(username: str) -> str
create_user(db: Session, username: str, password: str) -> User
get_user_by_username(db: Session, username: str) -> User | None
authenticate_user(db: Session, username: str, password: str) -> User | None
create_session(db: Session, user: User) -> tuple[UserSession, str]
hash_session_token(token: str) -> str
get_session_by_token(db: Session, token: str) -> UserSession | None
is_session_active(session: UserSession) -> bool
get_user_by_session_token(db: Session, token: str) -> User | None
get_user_for_session_token(db: Session, token: str) -> User | None
logout_session(db: Session, token: str) -> bool
revoke_session(db: Session, token: str) -> bool
has_any_user(db: Session) -> bool
```

Compatibility aliases are okay and useful because earlier route/smoke code used both naming styles.

---

## Expected API Routes

The auth API route file should expose:

```text
GET  /api/auth/setup-status
POST /api/auth/setup
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout
```

Current smoke test expects these paths to exist in OpenAPI.

### General behavior

- `setup-status`: returns whether first-run setup is needed.
- `setup`: creates the first user if none exists.
- `login`: verifies credentials and returns bearer token.
- `me`: requires bearer token and returns current user.
- `logout`: revokes session token.

---

## Expected Smoke Test Ending After Fix 030

After Patch 030, run:

```bash
python3 fixes/030_phase3_auth_datetime_fix_clean.py
docker compose up -d --build
docker compose exec -T partpilot python -m app.db.smoke_test
```

Expected final passes:

```text
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth service works
[PASS] Phase 3 auth API routes are registered
[PASS] Phase 3 auth API flow works
[PASS] Phase 3 auth service smoke test completed
```

If it fails again, inspect exact current files before generating another patch:

```bash
sed -n '1,240p' backend/app/services/auth.py
sed -n '1,180p' backend/app/api/routes/auth.py
sed -n '340,470p' backend/app/db/smoke_test.py
```

Do not guess file structure.

---

## Commit Guidance

Do not give commit/push commands automatically after every patch.

When the smoke test passes after Patch 030, then it is reasonable to verify file state once and checkpoint:

```bash
git status --short
```

Only then decide whether to commit the Phase 3 auth service/API work. A likely commit message would be:

```text
Add Phase 3 auth service and API routes
```

But do not ask the user to commit until the API flow smoke test passes.

---

## Important Caveat for Next Chat

The current conversation had several incorrect patches. Be extra strict in the next chat:

1. Prefer inspecting actual files before generating patches.
2. Do not invent model fields such as `is_admin`.
3. Do not add migrations unless the existing schema is confirmed missing something.
4. Use the actual repo structure: backend code is under `backend/`.
5. Use numbered fix scripts and keep patches narrow.
6. When a patch corrupts a file, restore from `HEAD` before reapplying.
7. Avoid touching `main.py` or `smoke_test.py` without understanding their current content.
8. If a build fails but the next command still runs, remember the smoke test may be using the old running container.
