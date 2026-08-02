from __future__ import annotations

from pathlib import Path
import tempfile
import threading

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.backups import ManualBackupStatusResponse
from app.services.backups import (
    BACKUP_MEDIA_TYPE,
    BackupArtifact,
    BackupArtifactError,
    create_backup_artifact,
    get_manual_backup_status,
    record_backup_generated_audit,
    remove_backup_operation_directory,
    sqlite_path_from_database_url,
)


router = APIRouter(prefix="/backups", tags=["backups"])
BACKUP_GENERATION_LOCK = threading.Lock()
BACKUP_OPERATION_PARENT = Path(tempfile.gettempdir())


def _cleanup_artifact(
    artifact: BackupArtifact | None,
) -> None:
    if artifact is None:
        return
    try:
        remove_backup_operation_directory(
            artifact.operation_directory,
            expected_parent=BACKUP_OPERATION_PARENT,
        )
    except BackupArtifactError:
        pass



# PARTPILOT:MANUAL_BACKUP_STATUS_ROUTE:V452
@router.get(
    "/status",
    response_model=ManualBackupStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "description": (
                "Recorded manual backup-download status. "
                "No scheduled or retained server-side copy is implied."
            ),
        },
    },
)
def read_manual_backup_status(
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManualBackupStatusResponse:
    del current_user
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return get_manual_backup_status(db)


# PARTPILOT:BACKUP_DOWNLOAD_ROUTE:V434
@router.post(
    "/download",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "content": {
                BACKUP_MEDIA_TYPE: {},
            },
            "description": "Versioned Part Pilot backup artifact.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Another backup generation is in progress.",
        },
    },
)
def download_backup(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    if not BACKUP_GENERATION_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another backup generation is already in progress.",
        )

    artifact: BackupArtifact | None = None
    try:
        settings = get_settings()
        source_database = sqlite_path_from_database_url(
            settings.database_url
        )
        artifact = create_backup_artifact(
            source_database,
            BACKUP_OPERATION_PARENT,
        )
        record_backup_generated_audit(
            db,
            artifact,
            actor_user_id=current_user.id,
            commit=True,
        )

        return FileResponse(
            path=artifact.archive_path,
            media_type=BACKUP_MEDIA_TYPE,
            filename=artifact.filename,
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
            },
            background=BackgroundTask(
                remove_backup_operation_directory,
                artifact.operation_directory,
                expected_parent=BACKUP_OPERATION_PARENT,
            ),
        )
    except BackupArtifactError as exc:
        db.rollback()
        _cleanup_artifact(artifact)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backup generation failed.",
        ) from exc
    except Exception as exc:
        db.rollback()
        _cleanup_artifact(artifact)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backup generation failed.",
        ) from exc
    finally:
        BACKUP_GENERATION_LOCK.release()
