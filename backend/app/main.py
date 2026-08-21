from contextlib import asynccontextmanager
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

# PATCH 073: exception-aware SPA frontend fallback
class SPAStaticFiles(StaticFiles):
    # Serve index.html for browser routes while preserving backend and
    # missing-file 404 responses.
    async def get_response(self, path: str, scope: dict):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise

            normalized_path = path.lstrip("/")

            if (
                normalized_path == "api"
                or normalized_path.startswith("api/")
            ):
                raise

            if Path(normalized_path).suffix:
                raise

            if scope.get("method") not in {"GET", "HEAD"}:
                raise

            return await super().get_response("index.html", scope)

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.part_types import router as part_types_router
# PATCH 093: inventory part routes
from app.api.routes.parts import router as parts_router
# PATCH 095: manufacturer catalogue routes
from app.api.routes.manufacturers import router as manufacturers_router
# PATCH 128: package catalogue routes
from app.api.routes.packages import router as packages_router
# PATCH 156: reusable location catalogue routes
from app.api.routes.locations import router as locations_router
# PATCH 182: protected application search settings routes
from app.api.routes.app_settings import router as app_settings_router
# PARTPILOT:REST_API_KEY_ROUTER_REGISTRATION:V615
from app.api.routes.api_keys import router as api_keys_router
# PATCH 303: protected reservation read/create routes
from app.api.routes.reservations import router as reservations_router
# PATCH 374: protected Project read/create routes
from app.api.routes.projects import router as projects_router
# PARTPILOT:SYSTEM_HISTORY_ROUTER_REGISTRATION:V406
from app.api.routes.history import router as history_router
# PARTPILOT:AUTHENTICATED_LIVE_SYNC_ROUTER:V687
from app.api.routes.live_sync import router as live_sync_router
# PARTPILOT:BACKUP_DOWNLOAD_ROUTER:V434
from app.api.routes.backups import router as backups_router
# PARTPILOT:RESTORE_VALIDATION_ROUTER:V438
from app.api.routes.restores import router as restores_router
# PARTPILOT:MCP_OAUTH_HTTP_ROUTER:V467
from app.api.routes.mcp_oauth import router as mcp_oauth_router
from app.core.config import get_settings
# PARTPILOT:RESTORE_UPLOAD_LIMIT:V438
from app.core.upload_limits import RestoreUploadLimitMiddleware
# PARTPILOT:APPLICATION_LIFECYCLE:V436
from app.core.lifecycle import (
    LifecycleRequestMiddleware,
    application_lifecycle,
)
from app.db.session import dispose_database_engine
# PARTPILOT:MCP_STREAMABLE_HTTP_IMPORT:V469
from app.mcp.runtime import mcp_http_endpoint, mcp_runtime_lifespan

settings = get_settings()


# PARTPILOT:PUBLIC_OPENAPI_METADATA:V720
PARTPILOT_API_VERSION = "0.1.0"
PARTPILOT_BEARER_SCHEME = "PartPilotBearer"
PARTPILOT_API_DESCRIPTION = """
Part Pilot exposes an authenticated REST API for inventory and workflow automation.

### REST API keys
Create keys from **Settings → API Access**. Send the key as:

`Authorization: Bearer pp_api_key_...`

Only operations marked **API key or session** accept REST API keys. Each such
operation declares the exact required scope. API keys cannot administer Part
Pilot accounts, Settings, API keys, backups/restores, or the browser live-sync
transport.

### Browser/session administration
Session-only operations use the same Bearer header with a Part Pilot session
token. Swagger's **Authorize** control can be used for either credential type;
the individual operation documentation states which type is accepted.

### MCP
The MCP Streamable HTTP endpoint is `/mcp` and is intentionally outside this
OpenAPI document. MCP OAuth protocol endpoints remain documented separately
under the **mcp-oauth** tag and do not accept Part Pilot REST API keys.
""".strip()
PARTPILOT_OPENAPI_TAGS = [
    {"name": "parts", "description": "Inventory records and stock operations. REST API keys require `inventory:read` or `inventory:write` as shown per operation."},
    {"name": "part-types", "description": "Part-type and template-field catalogue. REST API keys use `catalogues:read` / `catalogues:write`."},
    {"name": "manufacturers", "description": "Manufacturer catalogue. REST API keys use `catalogues:read` / `catalogues:write`."},
    {"name": "packages", "description": "Package catalogue. REST API keys use `catalogues:read` / `catalogues:write`."},
    {"name": "locations", "description": "Location catalogue. REST API keys use `catalogues:read` / `catalogues:write`."},
    {"name": "projects", "description": "Project planning and lifecycle. REST API keys use `projects:read` / `projects:write`."},
    {"name": "reservations", "description": "Reservation records, lifecycle, and activity. REST API keys use `reservations:read` / `reservations:write`."},
    {"name": "history", "description": "Unified operational history. REST API keys require `history:read`."},
    {"name": "health", "description": "Unauthenticated health and readiness probes."},
    {"name": "auth", "description": "Account bootstrap, login, profile, password, and session administration. Except for bootstrap/login routes, these are session-only."},
    {"name": "settings", "description": "Session-only workspace and integration administration, including REST API-key management. REST API keys cannot administer these endpoints."},
    {"name": "live-sync", "description": "Session-only authenticated browser invalidation transport. This is not part of the REST API-key surface."},
    {"name": "backups", "description": "Session-only backup generation and status."},
    {"name": "restores", "description": "Session-only restore validation and commit operations."},
    {"name": "mcp-oauth", "description": "MCP OAuth discovery, authorization, token, and revocation protocol endpoints. These are separate from REST API-key authentication."},
]
PARTPILOT_API_KEY_SCOPE_DESCRIPTIONS = {
    "inventory:read": "Read inventory parts, low-stock state, deleted-part records, details, and stock movement history.",
    "inventory:write": "Create/edit inventory parts and perform restore, purge, delete, or quantity mutations.",
    "catalogues:read": "Read part types, manufacturers, packages, locations, and catalogue dependency information.",
    "catalogues:write": "Create/edit/delete supported catalogue records.",
    "projects:read": "Read Project collections and details.",
    "projects:write": "Create/edit Projects and perform reserve, consume, or cancel lifecycle actions.",
    "reservations:read": "Read Reservations, details, and activity.",
    "reservations:write": "Create/edit/delete Reservations and perform lifecycle actions.",
    "history:read": "Read unified History and filter options.",
}
PARTPILOT_ANONYMOUS_OPENAPI_PATHS = {
    "/health",
    "/ready",
    "/api/health",
    "/api/ready",
    "/api/auth/setup-status",
    "/api/auth/setup",
    "/api/auth/login",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    application_lifecycle.mark_started()
    try:
        async with mcp_runtime_lifespan():
            yield
    finally:
        application_lifecycle.begin_shutdown()
        await asyncio.to_thread(
            application_lifecycle.wait_for_drain,
            timeout=30.0,
            max_active_requests=0,
        )
        dispose_database_engine()
        application_lifecycle.mark_stopped()


app = FastAPI(
    title=settings.app_name,
    version=PARTPILOT_API_VERSION,
    description=PARTPILOT_API_DESCRIPTION,
    openapi_tags=PARTPILOT_OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    LifecycleRequestMiddleware,
    state=application_lifecycle,
)
app.add_middleware(
    RestoreUploadLimitMiddleware,
)

# Root health check required by Phase 1 completion criteria.
app.include_router(health_router)

# API-prefixed health check for the frontend API client.
app.include_router(health_router, prefix="/api")

# Phase 3 authentication routes.
app.include_router(auth_router, prefix="/api")

# Phase 4 part type and template field routes.
app.include_router(part_types_router, prefix="/api")
# PATCH 093: inventory part API
app.include_router(parts_router, prefix="/api")
# PATCH 095: manufacturer catalogue API
app.include_router(manufacturers_router, prefix="/api")
# PATCH 128: package catalogue API
app.include_router(packages_router, prefix="/api")
# PATCH 156: reusable location catalogue API
app.include_router(locations_router, prefix="/api")
# PATCH 182: protected application search settings API
app.include_router(app_settings_router, prefix="/api")
# PARTPILOT:REST_API_KEY_ROUTER_REGISTRATION:V615
app.include_router(api_keys_router, prefix="/api")
# PATCH 303: protected reservation read/create API
app.include_router(reservations_router, prefix="/api")
# PATCH 374: protected Project read/create API
app.include_router(projects_router, prefix="/api")
# PARTPILOT:SYSTEM_HISTORY_ROUTER_REGISTRATION:V406
app.include_router(history_router, prefix="/api")
# PARTPILOT:AUTHENTICATED_LIVE_SYNC_REGISTRATION:V687
app.include_router(live_sync_router, prefix="/api")
# PARTPILOT:BACKUP_DOWNLOAD_ROUTER:V434
app.include_router(backups_router, prefix="/api")
# PARTPILOT:RESTORE_VALIDATION_ROUTER:V438
app.include_router(restores_router, prefix="/api")
# PARTPILOT:MCP_OAUTH_HTTP_REGISTRATION:V467
app.include_router(mcp_oauth_router)

# PARTPILOT:MCP_STREAMABLE_HTTP_ROUTE:V469
app.router.routes.append(
    Route(
        "/mcp",
        endpoint=mcp_http_endpoint,
        methods=["GET", "POST", "DELETE"],
        name="mcp-streamable-http",
        include_in_schema=False,
    )
)


# PARTPILOT:PUBLIC_OPENAPI_AUTH_SCOPE_CONTRACT:V720
def _route_api_key_scope(route: APIRoute) -> str | None:
    scopes = {
        getattr(dependency.call, "partpilot_api_key_scope", None)
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "partpilot_api_key_scope", None) is not None
    }
    if len(scopes) > 1:
        raise RuntimeError(
            f"OpenAPI route has multiple Part Pilot API-key scopes: {route.path}"
        )
    return next(iter(scopes), None)


def _prepend_openapi_note(operation: dict, note: str) -> None:
    existing = operation.get("description")
    operation["description"] = (
        f"{note}\n\n{existing}" if existing else note
    )


def _iter_partpilot_openapi_routes(router, prefix: str = ""):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path_format, route
            continue
        if type(route).__name__ == "_IncludedRouter":
            nested_prefix = prefix + route.include_context.prefix
            yield from _iter_partpilot_openapi_routes(
                route.original_router,
                nested_prefix,
            )


def _partpilot_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes[PARTPILOT_BEARER_SCHEME] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "Part Pilot session token or pp_api_key_...",
        "description": (
            "Enter only the token value. Swagger sends `Authorization: Bearer <token>`. "
            "REST API keys (`pp_api_key_...`) work only on operations marked "
            "`API key or session`; session tokens are required for session-only operations."
        ),
    }
    schema["x-partpilot-api-key-scopes"] = [
        {"name": scope, "description": description}
        for scope, description in PARTPILOT_API_KEY_SCOPE_DESCRIPTIONS.items()
    ]

    paths = schema.get("paths", {})
    for effective_path, route in _iter_partpilot_openapi_routes(app):
        if not route.include_in_schema:
            continue
        api_key_scope = _route_api_key_scope(route)
        for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
            operation = paths.get(effective_path, {}).get(method.lower())
            if operation is None:
                continue

            if api_key_scope is not None:
                operation["security"] = [{PARTPILOT_BEARER_SCHEME: []}]
                operation["x-partpilot-access"] = "api-key-or-session"
                operation["x-partpilot-api-key-scope"] = api_key_scope
                _prepend_openapi_note(
                    operation,
                    f"**Authentication:** Bearer session token or REST API key with `{api_key_scope}`.",
                )
                responses = operation.setdefault("responses", {})
                responses.setdefault(
                    "401",
                    {"description": "Missing, invalid, expired, or revoked Bearer credential."},
                )
                responses.setdefault(
                    "403",
                    {"description": f"Bearer credential is valid but does not grant `{api_key_scope}`."},
                )
                continue

            if effective_path in PARTPILOT_ANONYMOUS_OPENAPI_PATHS:
                operation.pop("security", None)
                operation["x-partpilot-access"] = "public"
                _prepend_openapi_note(operation, "**Authentication:** None.")
                continue

            if (
                effective_path.startswith("/.well-known/")
                or effective_path.startswith("/oauth/")
            ):
                operation.pop("security", None)
                operation["x-partpilot-access"] = "oauth-protocol"
                _prepend_openapi_note(
                    operation,
                    "**Access:** MCP OAuth protocol endpoint. Part Pilot REST API keys are not accepted here.",
                )
                continue

            if effective_path.startswith("/api/"):
                operation["security"] = [{PARTPILOT_BEARER_SCHEME: []}]
                operation["x-partpilot-access"] = "session-only"
                _prepend_openapi_note(
                    operation,
                    "**Authentication:** Part Pilot session Bearer token only. REST API keys are not accepted for this operation.",
                )
                operation.setdefault("responses", {}).setdefault(
                    "401",
                    {"description": "Missing, invalid, or expired Part Pilot session token."},
                )

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _partpilot_openapi

frontend_dist = Path("/app/frontend_dist")
if frontend_dist.exists():
    app.mount(
        "/",
        SPAStaticFiles(directory=frontend_dist, html=True),
        name="frontend",
    )
