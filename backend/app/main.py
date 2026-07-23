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

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.part_types import router as part_types_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health check required by Phase 1 completion criteria.
app.include_router(health_router)

# API-prefixed health check for the frontend API client.
app.include_router(health_router, prefix="/api")

# Phase 3 authentication routes.
app.include_router(auth_router, prefix="/api")

# Phase 4 part type and template field routes.
app.include_router(part_types_router, prefix="/api")

frontend_dist = Path("/app/frontend_dist")
if frontend_dist.exists():
    app.mount(
        "/",
        SPAStaticFiles(directory=frontend_dist, html=True),
        name="frontend",
    )
