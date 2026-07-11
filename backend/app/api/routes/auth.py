from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    AuthTokenResponse,
    CurrentUserResponse,
    DebugResetRequest,
    DebugResetResponse,
    LoginRequest,
    LogoutResponse,
    SetupPreferencesRequest,
    SetupRequest,
    SetupStatusResponse,
)
from app.services.app_setup import (
    get_application_setup_configuration,
    save_application_setup_configuration,
)
from app.services.debug_reset import (
    RESET_CONFIRMATION,
    debug_database_reset_enabled,
    reset_application_database,
)
from app.services.auth import (
    authenticate_user,
    create_first_user,
    create_session,
    get_user_for_session_token,
    has_any_user,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    token = _extract_bearer_token(authorization)
    user = get_user_for_session_token(db, token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user


def _build_setup_status(db: Session) -> SetupStatusResponse:
    account_exists = has_any_user(db)
    configuration = get_application_setup_configuration(db)

    return SetupStatusResponse(
        setup_complete=account_exists and configuration.complete,
        account_exists=account_exists,
        default_currency=configuration.default_currency,
        timezone=configuration.timezone,
    )


@router.get("/setup-status", response_model=SetupStatusResponse)
def setup_status(db: Session = Depends(get_db)) -> SetupStatusResponse:
    return _build_setup_status(db)


@router.post(
    "/setup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup(
    payload: SetupRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    try:
        user = create_first_user(
            db,
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            commit=False,
        )
        save_application_setup_configuration(
            db,
            default_currency=payload.default_currency,
            timezone=payload.timezone,
            commit=False,
        )
        session_token = create_session(db, user=user, commit=False)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return AuthTokenResponse(
        token=session_token.token,
        username=user.username,
        display_name=user.display_name,
    )


@router.post(
    "/complete-setup",
    response_model=SetupStatusResponse,
)
def complete_setup(
    payload: SetupPreferencesRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SetupStatusResponse:
    del current_user

    try:
        save_application_setup_configuration(
            db,
            default_currency=payload.default_currency,
            timezone=payload.timezone,
            commit=True,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _build_setup_status(db)




@router.post(
    "/debug/reset-database",
    response_model=DebugResetResponse,
)
def debug_reset_database(
    payload: DebugResetRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DebugResetResponse:
    del current_user

    if not debug_database_reset_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug database reset is disabled",
        )

    if payload.confirmation != RESET_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Confirmation must be exactly: {RESET_CONFIRMATION}",
        )

    try:
        result = reset_application_database(db)
    except Exception:
        db.rollback()
        raise

    return DebugResetResponse(
        ok=True,
        recreated_part_types=result.recreated_part_types,
        recreated_template_fields=result.recreated_template_fields,
        recreated_settings=result.recreated_settings,
    )

@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    user = authenticate_user(
        db,
        username=payload.username,
        password=payload.password,
    )

    if user is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_token = create_session(db, user=user, commit=True)

    return AuthTokenResponse(
        token=session_token.token,
        username=user.username,
        display_name=user.display_name,
    )


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user=Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    token = _extract_bearer_token(authorization)
    revoked = revoke_session(db, token, commit=True)
    return LogoutResponse(ok=revoked)
