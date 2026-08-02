from contextlib import asynccontextmanager
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
# PATCH 303: protected reservation read/create routes
from app.api.routes.reservations import router as reservations_router
# PATCH 374: protected Project read/create routes
from app.api.routes.projects import router as projects_router
# PARTPILOT:SYSTEM_HISTORY_ROUTER_REGISTRATION:V406
from app.api.routes.history import router as history_router
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
# PATCH 303: protected reservation read/create API
app.include_router(reservations_router, prefix="/api")
# PATCH 374: protected Project read/create API
app.include_router(projects_router, prefix="/api")
# PARTPILOT:SYSTEM_HISTORY_ROUTER_REGISTRATION:V406
app.include_router(history_router, prefix="/api")
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

frontend_dist = Path("/app/frontend_dist")
if frontend_dist.exists():
    app.mount(
        "/",
        SPAStaticFiles(directory=frontend_dist, html=True),
        name="frontend",
    )
