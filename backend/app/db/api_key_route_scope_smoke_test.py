from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.main import app
from app.models import ApiKey, AuditLog, User, UserSession
from app.services.api_keys import AVAILABLE_API_KEY_SCOPES, create_api_key, revoke_api_key
from app.services.auth import create_session


# PARTPILOT:REST_API_KEY_ROUTE_SCOPE_SMOKE:V616
EXPECTED_SCOPES = {
    ("GET", "/api/parts"): "inventory:read",
    ("GET", "/api/parts/low-stock"): "inventory:read",
    ("POST", "/api/parts"): "inventory:write",
    ("GET", "/api/parts/deleted"): "inventory:read",
    ("POST", "/api/parts/deleted/purge"): "inventory:write",
    ("POST", "/api/parts/{part_id}/restore"): "inventory:write",
    ("DELETE", "/api/parts/{part_id}"): "inventory:write",
    ("POST", "/api/parts/{part_id}/quantity-adjustments"): "inventory:write",
    ("GET", "/api/parts/{part_id}/movements"): "inventory:read",
    ("PUT", "/api/parts/{part_id}"): "inventory:write",
    ("GET", "/api/parts/{part_id}"): "inventory:read",
    ("GET", "/api/part-types"): "catalogues:read",
    ("POST", "/api/part-types"): "catalogues:write",
    ("GET", "/api/part-types/{part_type_id}"): "catalogues:read",
    ("PUT", "/api/part-types/{part_type_id}"): "catalogues:write",
    ("GET", "/api/part-types/{part_type_id}/delete-dependencies"): "catalogues:read",
    ("DELETE", "/api/part-types/{part_type_id}"): "catalogues:write",
    ("GET", "/api/manufacturers"): "catalogues:read",
    ("POST", "/api/manufacturers"): "catalogues:write",
    ("GET", "/api/packages"): "catalogues:read",
    ("POST", "/api/packages"): "catalogues:write",
    ("GET", "/api/locations"): "catalogues:read",
    ("POST", "/api/locations"): "catalogues:write",
    ("PUT", "/api/locations/{location_id}"): "catalogues:write",
    ("DELETE", "/api/locations/{location_id}"): "catalogues:write",
    ("GET", "/api/projects"): "projects:read",
    ("GET", "/api/projects/{project_id}"): "projects:read",
    ("POST", "/api/projects"): "projects:write",
    ("PUT", "/api/projects/{project_id}"): "projects:write",
    ("POST", "/api/projects/{project_id}/reserve"): "projects:write",
    ("POST", "/api/projects/{project_id}/consume"): "projects:write",
    ("POST", "/api/projects/{project_id}/cancel"): "projects:write",
    ("GET", "/api/reservations"): "reservations:read",
    ("GET", "/api/reservations/{reservation_id}"): "reservations:read",
    ("POST", "/api/reservations"): "reservations:write",
    ("PUT", "/api/reservations/{reservation_id}"): "reservations:write",
    ("DELETE", "/api/reservations/{reservation_id}"): "reservations:write",
    ("POST", "/api/reservations/{reservation_id}/cancel"): "reservations:write",
    ("POST", "/api/reservations/{reservation_id}/consume"): "reservations:write",
    ("POST", "/api/reservations/{reservation_id}/expire"): "reservations:write",
    ("GET", "/api/reservations/{reservation_id}/activity"): "reservations:read",
    ("GET", "/api/history/filter-options"): "history:read",
    ("GET", "/api/history"): "history:read",
}
SESSION_ONLY_PREFIXES = (
    "/api/auth",
    "/api/settings",
    "/api/backups",
    "/api/restores",
)
OPENAPI_SECURITY_SCHEME = "PartPilotBearer"
OPENAPI_SESSION_ONLY_SAMPLES = (
    ("GET", "/api/settings/api-keys"),
    ("GET", "/api/backups/status"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/live/state"),
)
OPENAPI_PUBLIC_SAMPLES = (
    ("GET", "/health"),
    ("GET", "/api/health"),
    ("GET", "/api/auth/setup-status"),
    ("POST", "/api/auth/login"),
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def scope_for_route(route: APIRoute) -> str | None:
    scopes = {
        getattr(dependency.call, "partpilot_api_key_scope", None)
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "partpilot_api_key_scope", None) is not None
    }
    if len(scopes) > 1:
        fail(f"Route has multiple API-key scopes: {route.path} {sorted(scopes)}")
    return next(iter(scopes), None)


def iter_api_routes(router, prefix: str = ""):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        if type(route).__name__ == "_IncludedRouter":
            nested_prefix = prefix + route.include_context.prefix
            yield from iter_api_routes(route.original_router, nested_prefix)


def route_contract() -> None:
    actual: dict[tuple[str, str], str] = {}
    for effective_path, route in iter_api_routes(app):
        scope = scope_for_route(route)
        methods = sorted((route.methods or set()) - {"HEAD", "OPTIONS"})
        for method in methods:
            key = (method, effective_path)
            if scope is not None:
                actual[key] = scope
            if effective_path.startswith(SESSION_ONLY_PREFIXES) and scope is not None:
                fail(f"Session-only route accidentally accepts API keys: {key} -> {scope}")
    if actual != EXPECTED_SCOPES:
        missing = sorted(set(EXPECTED_SCOPES.items()) - set(actual.items()))
        extra = sorted(set(actual.items()) - set(EXPECTED_SCOPES.items()))
        fail(f"API-key route scope map mismatch: missing={missing}, extra={extra}")


def openapi_documentation_contract(client: TestClient) -> None:
    response = client.get("/openapi.json")
    if response.status_code != 200:
        fail(f"OpenAPI document unavailable: {response.status_code}")
    document = response.json()
    info = document.get("info", {})
    if info.get("title") != "Part Pilot" or info.get("version") != "0.1.0":
        fail(f"OpenAPI info metadata mismatch: {info}")
    description = info.get("description") or ""
    for marker in ("REST API keys", "Authorization: Bearer", "MCP"):
        if marker not in description:
            fail(f"OpenAPI description is missing {marker!r}")

    scheme = (
        document.get("components", {})
        .get("securitySchemes", {})
        .get(OPENAPI_SECURITY_SCHEME)
    )
    if not isinstance(scheme, dict) or scheme.get("type") != "http" or scheme.get("scheme") != "bearer":
        fail(f"OpenAPI Bearer security scheme mismatch: {scheme}")
    if "pp_api_key_" not in str(scheme.get("description", "")):
        fail("OpenAPI Bearer scheme does not explain REST API-key usage")

    scope_catalog = document.get("x-partpilot-api-key-scopes")
    if not isinstance(scope_catalog, list):
        fail("OpenAPI API-key scope catalogue is missing")
    if [item.get("name") for item in scope_catalog] != list(AVAILABLE_API_KEY_SCOPES):
        fail(f"OpenAPI API-key scope catalogue mismatch: {scope_catalog}")
    if any(not item.get("description") for item in scope_catalog):
        fail("OpenAPI API-key scope catalogue contains an undocumented scope")

    tag_names = [tag.get("name") for tag in document.get("tags", [])]
    required_tags = {
        "parts", "part-types", "manufacturers", "packages", "locations",
        "projects", "reservations", "history", "auth", "settings",
        "health", "live-sync", "backups", "restores", "mcp-oauth",
    }
    if not required_tags.issubset(tag_names):
        fail(f"OpenAPI tag metadata incomplete: {tag_names}")

    paths = document.get("paths", {})
    for (method, path), required_scope in EXPECTED_SCOPES.items():
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            fail(f"OpenAPI missing API-key operation {method} {path}")
        if operation.get("security") != [{OPENAPI_SECURITY_SCHEME: []}]:
            fail(f"OpenAPI security mismatch for {method} {path}: {operation.get('security')}")
        if operation.get("x-partpilot-access") != "api-key-or-session":
            fail(f"OpenAPI access class mismatch for {method} {path}")
        if operation.get("x-partpilot-api-key-scope") != required_scope:
            fail(f"OpenAPI scope mismatch for {method} {path}")
        if required_scope not in str(operation.get("description", "")):
            fail(f"OpenAPI description omits required scope for {method} {path}")
        responses = operation.get("responses", {})
        if "401" not in responses or "403" not in responses:
            fail(f"OpenAPI auth responses incomplete for {method} {path}")

    for method, path in OPENAPI_SESSION_ONLY_SAMPLES:
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            fail(f"OpenAPI missing session-only sample {method} {path}")
        if operation.get("security") != [{OPENAPI_SECURITY_SCHEME: []}]:
            fail(f"Session-only OpenAPI security mismatch for {method} {path}")
        if operation.get("x-partpilot-access") != "session-only":
            fail(f"Session-only OpenAPI access mismatch for {method} {path}")
        if "x-partpilot-api-key-scope" in operation:
            fail(f"Session-only OpenAPI operation exposes API-key scope: {method} {path}")
        if "REST API keys are not accepted" not in str(operation.get("description", "")):
            fail(f"Session-only OpenAPI description is ambiguous for {method} {path}")

    for method, path in OPENAPI_PUBLIC_SAMPLES:
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict) or operation.get("x-partpilot-access") != "public":
            fail(f"Public OpenAPI access mismatch for {method} {path}")
        if operation.get("security"):
            fail(f"Public OpenAPI route unexpectedly requires Bearer auth: {method} {path}")

    oauth = paths.get("/oauth/token", {}).get("post")
    if not isinstance(oauth, dict) or oauth.get("x-partpilot-access") != "oauth-protocol":
        fail("OAuth token endpoint is not documented as OAuth protocol access")
    if oauth.get("security"):
        fail("OAuth token endpoint incorrectly advertises Part Pilot Bearer auth")
    if "/mcp" in paths:
        fail("MCP Streamable HTTP endpoint must remain excluded from OpenAPI")

    docs = client.get("/docs")
    if docs.status_code != 200 or "swagger-ui" not in docs.text.lower():
        fail(f"Swagger UI unavailable: {docs.status_code}")


def main() -> None:
    route_contract()
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id).limit(1)
        ).scalar_one()
        user_id = user.id
        audit_floor = int(db.execute(select(func.coalesce(func.max(AuditLog.id), 0))).scalar_one())
        session_floor = int(db.execute(select(func.coalesce(func.max(UserSession.id), 0))).scalar_one())
        key_floor = int(db.execute(select(func.coalesce(func.max(ApiKey.id), 0))).scalar_one())
        issued = create_api_key(
            db,
            actor_user_id=user.id,
            name="Patch 616 all scopes",
            scopes=AVAILABLE_API_KEY_SCOPES,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            commit=True,
        )
        all_key_id = issued.record.id
        all_key = issued.plaintext_key
        limited = create_api_key(
            db,
            actor_user_id=user.id,
            name="Patch 616 inventory read",
            scopes=("inventory:read",),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            commit=True,
        )
        limited_id = limited.record.id
        limited_key = limited.plaintext_key
        session = create_session(db, user=user, commit=True)
        session_token = session.token

    try:
        client = TestClient(app)
        openapi_documentation_contract(client)
        all_headers = {"Authorization": f"Bearer {all_key}"}
        limited_headers = {"Authorization": f"Bearer {limited_key}"}
        session_headers = {"Authorization": f"Bearer {session_token}"}

        for path in (
            "/api/parts?limit=1",
            "/api/part-types",
            "/api/projects?limit=1",
            "/api/reservations?limit=1",
            "/api/history?limit=1",
        ):
            response = client.get(path, headers=all_headers)
            if response.status_code != 200:
                fail(f"Full-scope API key failed {path}: {response.status_code} {response.text}")

        if client.get("/api/parts?limit=1", headers=limited_headers).status_code != 200:
            fail("inventory:read key could not read inventory")
        with SessionLocal() as db:
            limited_row = db.get(ApiKey, limited_id)
            if limited_row is None or limited_row.last_used_at is None:
                fail("Successful limited API-key request did not update last_used_at")
            limited_before_forbidden = limited_row.last_used_at
        forbidden = client.get("/api/projects?limit=1", headers=limited_headers)
        if forbidden.status_code != 403 or "required scope" not in forbidden.text:
            fail(f"Insufficient scope did not return sanitized 403: {forbidden.status_code} {forbidden.text}")
        with SessionLocal() as db:
            limited_row = db.get(ApiKey, limited_id)
            if limited_row is None or limited_row.last_used_at != limited_before_forbidden:
                fail("Forbidden API-key request unexpectedly changed last_used_at")

        for method, path in (
            ("delete", "/api/parts/2147483647"),
            ("delete", "/api/part-types/2147483647"),
            ("post", "/api/projects/2147483647/cancel"),
            ("post", "/api/reservations/2147483647/cancel"),
        ):
            response = getattr(client, method)(path, headers=all_headers)
            if response.status_code != 404:
                fail(f"Write scope did not reach protected handler {method.upper()} {path}: {response.status_code} {response.text}")

        for path in (
            "/api/settings/api-keys",
            "/api/backups/status",
            "/api/auth/me",
        ):
            response = client.get(path, headers=all_headers)
            if response.status_code != 401:
                fail(f"Session-only route accepted API key {path}: {response.status_code}")

        if client.post("/api/restores/not-a-token/commit", headers=all_headers, json={"confirmation":"RESTORE"}).status_code != 401:
            fail("Restore administration accepted an API key")

        invalid = client.get(
            "/api/parts?limit=1",
            headers={"Authorization": "Bearer pp_api_key_invalid"},
        )
        if invalid.status_code != 401 or "Invalid API key" not in invalid.text:
            fail(f"Invalid API key response mismatch: {invalid.status_code} {invalid.text}")

        with SessionLocal() as db:
            all_row = db.get(ApiKey, all_key_id)
            if all_row is None or all_row.last_used_at is None:
                fail("Successful API-key requests did not update last_used_at")
            revoke_api_key(db, actor_user_id=user_id, key_id=all_key_id, commit=True)

        revoked = client.get("/api/parts?limit=1", headers=all_headers)
        if revoked.status_code != 401 or "Invalid API key" not in revoked.text:
            fail(f"Revoked API key response mismatch: {revoked.status_code} {revoked.text}")

        session_ok = client.get("/api/parts?limit=1", headers=session_headers)
        if session_ok.status_code != 200:
            fail(f"Session fallback regressed: {session_ok.status_code} {session_ok.text}")

    finally:
        with SessionLocal() as db:
            db.execute(delete(AuditLog).where(AuditLog.id > audit_floor))
            db.execute(delete(ApiKey).where(ApiKey.id > key_floor))
            db.execute(delete(UserSession).where(UserSession.id > session_floor))
            db.commit()

    print("[PASS] REST API keys authenticate only explicitly scoped application routes, enforce all 43 registered method/path scopes, expose exact Bearer/scope/access OpenAPI metadata and Swagger UI, preserve session fallback, reject insufficient/invalid/revoked keys, track successful last use, and remain excluded from Auth/Settings/Backup/Restore/live-sync administration")


if __name__ == "__main__":
    main()
