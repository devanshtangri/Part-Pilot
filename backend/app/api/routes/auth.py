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
    ProfileResponse,
    ProfileUpdateRequest,
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
    BUILTIN_AVATAR_IDS,
    authenticate_user,
    create_first_user,
    create_session,
    get_user_for_session_token,
    has_any_user,
    revoke_session,
    update_user_profile,
)

from app.schemas.auth import (
    OtherSessionsRevokeResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    SessionListResponse,
    SessionResponse,
    SessionRevokeResponse,
)
from app.services.auth import (
    CurrentPasswordInvalidError,
    CurrentSessionRevocationError,
    CurrentSessionUnavailableError,
    PasswordReuseError,
    SessionNotFoundError,
    change_password as change_user_password,
    is_session_active,
    list_user_sessions,
    require_current_session,
    revoke_all_other_sessions,
    revoke_user_session,
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


def _current_user_response(current_user) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        avatar_id=current_user.avatar_id,
        is_active=current_user.is_active,
    )


def _profile_response(current_user) -> ProfileResponse:
    return ProfileResponse(
        **_current_user_response(current_user).model_dump(),
        available_avatar_ids=list(BUILTIN_AVATAR_IDS),
    )


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user=Depends(get_current_user)) -> CurrentUserResponse:
    return _current_user_response(current_user)


@router.get("/profile", response_model=ProfileResponse)
def read_profile(current_user=Depends(get_current_user)) -> ProfileResponse:
    return _profile_response(current_user)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        updated = update_user_profile(
            db,
            user=current_user,
            username=payload.username,
            display_name=payload.display_name,
            avatar_id=payload.avatar_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _profile_response(updated)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    token = _extract_bearer_token(authorization)
    revoked = revoke_session(db, token, commit=True)
    return LogoutResponse(ok=revoked)

# PARTPILOT:PASSWORD_SESSION_ADMIN_ROUTES:V584
def _current_session_for_request(
    *,
    authorization: str | None,
    db: Session,
    current_user,
):
    token = _extract_bearer_token(authorization)
    try:
        return require_current_session(db, user=current_user, token=token)
    except CurrentSessionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc


def _session_response(session, current_session) -> SessionResponse:
    user_agent = session.user_agent
    if user_agent is not None and len(user_agent) > 512:
        user_agent = user_agent[:512]
    return SessionResponse(
        id=session.id,
        is_current=session.id == current_session.id,
        is_active=is_session_active(session),
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
        user_agent=user_agent,
        ip_address=session.ip_address,
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password_route(
    payload: PasswordChangeRequest,
    authorization: str | None = Header(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PasswordChangeResponse:
    current_session = _current_session_for_request(
        authorization=authorization,
        db=db,
        current_user=current_user,
    )
    try:
        revoked = change_user_password(
            db,
            user=current_user,
            current_session=current_session,
            current_password=payload.current_password,
            new_password=payload.new_password,
            actor_user_id=current_user.id,
            commit=True,
        )
    except CurrentPasswordInvalidError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PasswordReuseError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except CurrentSessionUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PasswordChangeResponse(ok=True, revoked_other_sessions=revoked)


@router.get("/sessions", response_model=SessionListResponse)
def read_sessions(
    authorization: str | None = Header(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    current_session = _current_session_for_request(
        authorization=authorization,
        db=db,
        current_user=current_user,
    )
    try:
        sessions = list_user_sessions(
            db,
            user=current_user,
            current_session=current_session,
        )
    except CurrentSessionUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc

    return SessionListResponse(
        sessions=[_session_response(item, current_session) for item in sessions]
    )


@router.post(
    "/sessions/revoke-all-other",
    response_model=OtherSessionsRevokeResponse,
)
def revoke_other_sessions_route(
    authorization: str | None = Header(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OtherSessionsRevokeResponse:
    current_session = _current_session_for_request(
        authorization=authorization,
        db=db,
        current_user=current_user,
    )
    try:
        revoked = revoke_all_other_sessions(
            db,
            user=current_user,
            current_session=current_session,
            actor_user_id=current_user.id,
            commit=True,
        )
    except CurrentSessionUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc

    return OtherSessionsRevokeResponse(ok=True, revoked_sessions=revoked)


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionRevokeResponse,
)
def revoke_session_route(
    session_id: int,
    authorization: str | None = Header(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionRevokeResponse:
    current_session = _current_session_for_request(
        authorization=authorization,
        db=db,
        current_user=current_user,
    )
    try:
        _, revoked = revoke_user_session(
            db,
            user=current_user,
            current_session=current_session,
            session_id=session_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except SessionNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from exc
    except CurrentSessionRevocationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CurrentSessionUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc

    return SessionRevokeResponse(ok=True, revoked=revoked)
