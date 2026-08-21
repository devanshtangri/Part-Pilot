from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.api_keys import (
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeySecretResponse,
    ApiKeySummaryResponse,
    ApiKeyUpdateRequest,
)
from app.services.api_keys import (
    AVAILABLE_API_KEY_SCOPES,
    ApiKeyNotFoundError,
    ApiKeyStateError,
    ApiKeyValidationError,
    api_key_status,
    create_api_key,
    list_api_keys,
    masked_api_key,
    revoke_api_key,
    rotate_api_key,
    scopes_for_api_key,
    update_api_key,
)
from app.services.live_sync import publish_live_invalidation
from app.services.authorization import allowed_rest_scopes_for_role


# PARTPILOT:API_KEY_LIVE_SYNC_PUBLICATION:V708
def _publish_api_key_mutation(key_id: int) -> None:
    publish_live_invalidation(
        ("integrations.api_keys", "history"),
        resource={"type": "api_key", "id": key_id},
    )


# PARTPILOT:REST_API_KEY_ADMIN_ROUTE:V615
router = APIRouter(prefix="/settings/api-keys", tags=["settings"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _summary(record) -> ApiKeySummaryResponse:
    return ApiKeySummaryResponse(
        id=record.id,
        name=record.name,
        masked_key=masked_api_key(record),
        scopes=scopes_for_api_key(record),
        status=api_key_status(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
        expires_at=record.expires_at,
        rotated_at=record.rotated_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )


def _secret_response(issued) -> ApiKeySecretResponse:
    return ApiKeySecretResponse(
        **_summary(issued.record).model_dump(),
        key=issued.plaintext_key,
    )


def _allowed_scopes(current_user) -> list[str]:
    return allowed_rest_scopes_for_role(current_user.role, AVAILABLE_API_KEY_SCOPES)


def _require_allowed_scopes(current_user, scopes: list[str]) -> None:
    allowed = set(_allowed_scopes(current_user))
    denied = [scope for scope in scopes if scope not in allowed]
    if denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"The {current_user.role} role cannot grant API key scope(s): "
                + ", ".join(denied)
            ),
        )


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, ApiKeyNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ApiKeyStateError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ApiKeyValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    raise exc


@router.get("", response_model=ApiKeyListResponse)
def read_api_keys(
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyListResponse:
    _no_store(response)
    records = list_api_keys(db, user_id=current_user.id)
    return ApiKeyListResponse(
        keys=[_summary(record) for record in records],
        total=len(records),
        available_scopes=_allowed_scopes(current_user),
    )


@router.post(
    "",
    response_model=ApiKeySecretResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key_route(
    payload: ApiKeyCreateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeySecretResponse:
    _no_store(response)
    _require_allowed_scopes(current_user, payload.scopes)
    try:
        issued = create_api_key(
            db,
            actor_user_id=current_user.id,
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            commit=True,
        )
    except (ApiKeyValidationError, ApiKeyStateError) as exc:
        _raise_service_error(exc)
    _publish_api_key_mutation(issued.record.id)
    return _secret_response(issued)


@router.put("/{key_id}", response_model=ApiKeySummaryResponse)
def update_api_key_route(
    key_id: int,
    payload: ApiKeyUpdateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeySummaryResponse:
    _no_store(response)
    _require_allowed_scopes(current_user, payload.scopes)
    try:
        record = update_api_key(
            db,
            actor_user_id=current_user.id,
            key_id=key_id,
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            commit=True,
        )
    except (
        ApiKeyNotFoundError,
        ApiKeyStateError,
        ApiKeyValidationError,
    ) as exc:
        _raise_service_error(exc)
    _publish_api_key_mutation(record.id)
    return _summary(record)


@router.post("/{key_id}/rotate", response_model=ApiKeySecretResponse)
def rotate_api_key_route(
    key_id: int,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeySecretResponse:
    _no_store(response)
    try:
        issued = rotate_api_key(
            db,
            actor_user_id=current_user.id,
            key_id=key_id,
            commit=True,
        )
    except (
        ApiKeyNotFoundError,
        ApiKeyStateError,
        ApiKeyValidationError,
    ) as exc:
        _raise_service_error(exc)
    _publish_api_key_mutation(issued.record.id)
    return _secret_response(issued)


@router.delete("/{key_id}", response_model=ApiKeySummaryResponse)
def revoke_api_key_route(
    key_id: int,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeySummaryResponse:
    _no_store(response)
    try:
        record = revoke_api_key(
            db,
            actor_user_id=current_user.id,
            key_id=key_id,
            commit=True,
        )
    except (
        ApiKeyNotFoundError,
        ApiKeyStateError,
        ApiKeyValidationError,
    ) as exc:
        _raise_service_error(exc)
    _publish_api_key_mutation(record.id)
    return _summary(record)
