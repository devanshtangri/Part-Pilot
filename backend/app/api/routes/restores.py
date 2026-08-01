from __future__ import annotations

from pathlib import Path
import threading

from fastapi import (
    APIRouter,
    Depends,
    BackgroundTasks,
    File,
    HTTPException,
    Path as FastAPIPath,
    UploadFile,
    status,
)
from starlette.responses import JSONResponse

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.core.lifecycle import (
    LifecycleStateError,
    application_lifecycle,
)
from app.schemas.restores import (
    RESTORE_TOKEN_PATTERN,
    RestoreCommitRequest,
    RestoreCommitResponse,
    RestoreValidationResponse,
)
from app.services.backups import (
    BACKUP_MEDIA_TYPE,
    sqlite_path_from_database_url,
)
from app.services.restore_bootstrap import (
    RestoreBootstrapError,
    cancel_restore_commit_job,
    prepare_restore_commit_job,
)
from app.services.restore_restart import (
    restore_supervisor_available,
    terminate_process_for_restore,
)
from app.services.restores import (
    RestoreStagingStateError,
    RestoreUploadTooLargeError,
    RestoreValidationError,
    load_staged_restore,
    restore_staging_root_for_database,
    stage_restore_archive,
    sweep_expired_restore_staging,
)


router = APIRouter(
    prefix="/restores",
    tags=["restores"],
)
RESTORE_VALIDATION_LOCK = threading.Lock()
RESTORE_COMMIT_LOCK = threading.Lock()
RESTORE_DRAIN_TIMEOUT_SECONDS = 30.0
RESTORE_LIVE_DATABASE_PATH = (
    sqlite_path_from_database_url(
        get_settings().database_url
    )
)
RESTORE_STAGING_ROOT = (
    restore_staging_root_for_database(
        RESTORE_LIVE_DATABASE_PATH
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


# PARTPILOT:RESTORE_COMMIT_ROUTE:V440
@router.post(
    "/{validation_token}/commit",
    response_model=RestoreCommitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": (
                "Restore could not enter a drained maintenance state."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "Validation token, ownership, expiry, or confirmation "
                "is invalid."
            ),
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": (
                "The configured container supervisor cannot restart "
                "Part Pilot safely."
            ),
        },
    },
)
def commit_validated_restore(
    payload: RestoreCommitRequest,
    background_tasks: BackgroundTasks,
    validation_token: str = FastAPIPath(
        pattern=RESTORE_TOKEN_PATTERN,
    ),
    current_user=Depends(get_current_user),
):
    if not restore_supervisor_available():
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Restore restart supervision is unavailable."
            ),
        )

    if not RESTORE_COMMIT_LOCK.acquire(
        blocking=False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another restore commit is already in progress."
            ),
        )

    maintenance_started = False
    commit_prepared = False
    try:
        load_staged_restore(
            validation_token,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            staging_root=RESTORE_STAGING_ROOT,
        )
        application_lifecycle.begin_maintenance(
            "database restore restart scheduled"
        )
        maintenance_started = True
        drained = application_lifecycle.wait_for_drain(
            timeout=RESTORE_DRAIN_TIMEOUT_SECONDS,
            max_active_requests=1,
        )
        if not drained:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Part Pilot could not drain active requests "
                    "for restore."
                ),
            )

        prepare_restore_commit_job(
            validation_token,
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            live_database_path=(
                RESTORE_LIVE_DATABASE_PATH
            ),
            staging_root=RESTORE_STAGING_ROOT,
        )
        commit_prepared = True

        response = RestoreCommitResponse(
            status="restart_scheduled",
            validation_token=validation_token,
            message=(
                "Part Pilot is restarting to apply the validated "
                "backup. Sign in again after it becomes ready."
            ),
            sessions_will_be_invalidated=True,
            reauthentication_required=True,
        )
        background_tasks.add_task(
            terminate_process_for_restore,
            validation_token,
            current_user.id,
            current_user.username,
            RESTORE_STAGING_ROOT,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=response.model_dump(
                mode="json"
            ),
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Retry-After": "5",
            },
            background=background_tasks,
        )

    except HTTPException:
        if commit_prepared:
            try:
                cancel_restore_commit_job(
                    validation_token,
                    actor_user_id=current_user.id,
                    actor_username=current_user.username,
                    staging_root=RESTORE_STAGING_ROOT,
                )
            except Exception:
                pass
        if maintenance_started:
            try:
                application_lifecycle.leave_maintenance()
            except LifecycleStateError:
                pass
        raise
    except (
        RestoreBootstrapError,
        RestoreStagingStateError,
    ) as exc:
        if commit_prepared:
            try:
                cancel_restore_commit_job(
                    validation_token,
                    actor_user_id=current_user.id,
                    actor_username=current_user.username,
                    staging_root=RESTORE_STAGING_ROOT,
                )
            except Exception:
                pass
        if maintenance_started:
            try:
                application_lifecycle.leave_maintenance()
            except LifecycleStateError:
                pass
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Restore validation token cannot be committed."
            ),
        ) from exc
    except LifecycleStateError as exc:
        if maintenance_started:
            try:
                application_lifecycle.leave_maintenance()
            except LifecycleStateError:
                pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Part Pilot cannot enter restore maintenance mode."
            ),
        ) from exc
    except Exception as exc:
        if commit_prepared:
            try:
                cancel_restore_commit_job(
                    validation_token,
                    actor_user_id=current_user.id,
                    actor_username=current_user.username,
                    staging_root=RESTORE_STAGING_ROOT,
                )
            except Exception:
                pass
        if maintenance_started:
            try:
                application_lifecycle.leave_maintenance()
            except LifecycleStateError:
                pass
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Restore commit scheduling failed.",
        ) from exc
    finally:
        RESTORE_COMMIT_LOCK.release()
