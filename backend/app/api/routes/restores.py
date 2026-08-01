from __future__ import annotations

from pathlib import Path
import threading

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.schemas.restores import (
    RestoreValidationResponse,
)
from app.services.backups import (
    BACKUP_MEDIA_TYPE,
    sqlite_path_from_database_url,
)
from app.services.restores import (
    RestoreStagingStateError,
    RestoreUploadTooLargeError,
    RestoreValidationError,
    restore_staging_root_for_database,
    stage_restore_archive,
    sweep_expired_restore_staging,
)


router = APIRouter(
    prefix="/restores",
    tags=["restores"],
)
RESTORE_VALIDATION_LOCK = threading.Lock()
RESTORE_STAGING_ROOT = (
    restore_staging_root_for_database(
        sqlite_path_from_database_url(
            get_settings().database_url
        )
    )
)
ALLOWED_RESTORE_CONTENT_TYPES = {
    BACKUP_MEDIA_TYPE,
    "application/zip",
    "application/octet-stream",
}


# PARTPILOT:RESTORE_VALIDATION_ROUTE:V438
@router.post(
    "/validate",
    response_model=RestoreValidationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "description": (
                "Compressed restore upload exceeds 256 MiB."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Backup artifact or restore metadata is invalid."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "description": (
                "Another restore validation is in progress."
            ),
        },
    },
)
def validate_restore_upload(
    backup: UploadFile = File(...),
    current_user=Depends(get_current_user),
) -> RestoreValidationResponse:
    filename = backup.filename or ""
    content_type = (
        backup.content_type
        or "application/octet-stream"
    ).lower()
    if content_type not in (
        ALLOWED_RESTORE_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Restore file must use a supported "
                "backup media type."
            ),
        )

    if not RESTORE_VALIDATION_LOCK.acquire(
        blocking=False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another restore validation is already "
                "in progress."
            ),
        )

    try:
        sweep_expired_restore_staging(
            RESTORE_STAGING_ROOT
        )
        backup.file.seek(0)
        staged = stage_restore_archive(
            backup.file,
            original_filename=filename,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            staging_root=RESTORE_STAGING_ROOT,
        )
        return staged.response()
    except RestoreUploadTooLargeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Restore upload exceeds the supported size limit."
            ),
        ) from exc
    except (
        RestoreValidationError,
        RestoreStagingStateError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Backup file is not a valid Part Pilot "
                "restore artifact."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Restore validation failed.",
        ) from exc
    finally:
        RESTORE_VALIDATION_LOCK.release()
