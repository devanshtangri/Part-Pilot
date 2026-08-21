from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.client_ip import (
    ClientAddressError,
    TrustedProxyConfigurationError,
    TrustedProxyResolver,
)
from app.core.config import get_settings
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
    AVATAR_IMAGE_MIME,
    BUILTIN_AVATAR_IDS,
    MAX_AVATAR_UPLOAD_BYTES,
    AvatarImageValidationError,
    authenticate_user,
    clear_user_avatar_image,
    create_first_user,
    create_session,
    get_user_for_session_token,
    has_any_user,
    normalize_avatar_image,
    revoke_session,
    set_user_avatar_image,
    update_user_profile,
    user_avatar_image_metadata,
)

from app.schemas.auth import (
    OtherSessionsRevokeResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    SessionListResponse,
    SessionResponse,
    SessionRevokeResponse,
    ManagedUserActionResponse,
    ManagedUserAccessUpdateRequest,
    ManagedUserCreateRequest,
    ManagedUserDeleteRequest,
    ManagedUserListResponse,
    ManagedUserPasswordResetRequest,
    ManagedUserResponse,
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
from app.services.api_keys import (
    API_KEY_PREFIX,
    ApiKeyAuthenticationError,
    ApiKeyScopeError,
    validate_api_key,
)
from app.services.live_sync import publish_live_invalidation
from app.services.authorization import (
    ROLE_ADMINISTRATOR,
    ROLE_OWNER,
    RoleAuthorizationError,
    require_minimum_role,
    require_rest_scope_role,
)
from app.services.user_admin import (
    ManagedUserNotFoundError,
    UserAdministrationError,
    UserAdministrationForbiddenError,
    create_managed_user,
    delete_managed_user,
    force_reset_managed_user_password,
    list_managed_users,
    revoke_managed_user_sessions,
    update_managed_user_access,
)


# PARTPILOT:ACCOUNT_LIVE_SYNC_PUBLICATION:V705
def _publish_account_mutation(user_id: int) -> None:
    publish_live_invalidation(
        ("account", "history"),
        resource={"type": "user", "id": user_id},
    )


router = APIRouter(prefix="/auth", tags=["auth"])


# PARTPILOT:SESSION_REQUEST_METADATA:V605
MAX_SESSION_USER_AGENT_CHARS = 1024


def _session_request_metadata(request: Request) -> tuple[str | None, str | None]:
    raw_user_agent = request.headers.get("user-agent")
    user_agent = (raw_user_agent or "").strip()[:MAX_SESSION_USER_AGENT_CHARS]
    if not user_agent:
        user_agent = None

    try:
        settings = get_settings()
        client_ip = str(
            TrustedProxyResolver.from_raw(
                settings.trusted_proxy_cidrs
            ).resolve_client_ip(request.scope)
        )
    except (ClientAddressError, TrustedProxyConfigurationError):
        client_ip = None

    return user_agent, client_ip


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


# PARTPILOT:USER_ROLE_ROUTE_DEPENDENCIES:V732
def _minimum_role_dependency(minimum_role: str):
    def dependency(current_user=Depends(get_current_user)):
        try:
            require_minimum_role(current_user, minimum_role)
        except RoleAuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return current_user

    dependency.__name__ = f"require_{minimum_role}_user"
    return dependency


require_administrator_user = _minimum_role_dependency(ROLE_ADMINISTRATOR)
require_owner_user = _minimum_role_dependency(ROLE_OWNER)


# PARTPILOT:REST_API_KEY_ROUTE_SCOPE_AUTH:V616
def _get_rest_user_for_scope(
    authorization: str | None,
    db: Session,
    required_scope: str,
):
    token = _extract_bearer_token(authorization)
    if token.startswith(API_KEY_PREFIX):
        try:
            user = validate_api_key(
                db,
                token,
                required_scopes=(required_scope,),
                touch_last_used=True,
                commit=True,
            ).user
        except ApiKeyScopeError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key does not grant the required scope",
            ) from exc
        except ApiKeyAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            ) from exc
    else:
        user = get_user_for_session_token(db, token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )

    try:
        require_rest_scope_role(user, required_scope)
    except RoleAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return user


def _rest_scope_dependency(required_scope: str):
    def dependency(
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ):
        return _get_rest_user_for_scope(authorization, db, required_scope)

    dependency.__name__ = "require_" + required_scope.replace(":", "_")
    setattr(dependency, "partpilot_api_key_scope", required_scope)
    return dependency


require_inventory_read = _rest_scope_dependency("inventory:read")
require_inventory_write = _rest_scope_dependency("inventory:write")
require_catalogues_read = _rest_scope_dependency("catalogues:read")
require_catalogues_write = _rest_scope_dependency("catalogues:write")
require_projects_read = _rest_scope_dependency("projects:read")
require_projects_write = _rest_scope_dependency("projects:write")
require_reservations_read = _rest_scope_dependency("reservations:read")
require_reservations_write = _rest_scope_dependency("reservations:write")
require_history_read = _rest_scope_dependency("history:read")


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
    request: Request,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    user_agent, ip_address = _session_request_metadata(request)
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
        session_token = create_session(
            db,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
            commit=False,
        )
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
        role=user.role,
    )


@router.post(
    "/complete-setup",
    response_model=SetupStatusResponse,
)
def complete_setup(
    payload: SetupPreferencesRequest,
    current_user=Depends(require_owner_user),
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
    current_user=Depends(require_owner_user),
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
    request: Request,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    user_agent, ip_address = _session_request_metadata(request)
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

    session_token = create_session(
        db,
        user=user,
        user_agent=user_agent,
        ip_address=ip_address,
        commit=True,
    )

    return AuthTokenResponse(
        token=session_token.token,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def _current_user_response(current_user) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        avatar_id=current_user.avatar_id,
        has_custom_avatar=current_user.avatar_image_data is not None,
        avatar_image_sha256=current_user.avatar_image_sha256,
        role=current_user.role,
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
    _publish_account_mutation(updated.id)
    return _profile_response(updated)


# PARTPILOT:CUSTOM_AVATAR_ROUTES:V598
@router.get("/profile/avatar-image")
def read_profile_avatar_image(
    current_user=Depends(get_current_user),
):
    try:
        metadata = user_avatar_image_metadata(current_user)
    except AvatarImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored avatar image is invalid",
        ) from exc
    if not metadata["has_custom_avatar"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom avatar image not found",
        )
    return Response(
        content=current_user.avatar_image_data or b"",
        media_type=AVATAR_IMAGE_MIME,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "ETag": f'"{current_user.avatar_image_sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/profile/avatar-image", response_model=ProfileResponse)
async def upload_profile_avatar_image(
    image: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    content_type = (image.content_type or "").lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar image must be PNG, JPEG, or WebP",
        )
    try:
        payload = await image.read(MAX_AVATAR_UPLOAD_BYTES + 1)
    finally:
        await image.close()
    if len(payload) > MAX_AVATAR_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar image exceeds the 5 MiB limit",
        )
    try:
        normalized = normalize_avatar_image(payload)
        set_user_avatar_image(
            db,
            user=current_user,
            image=normalized,
            actor_user_id=current_user.id,
            commit=True,
        )
        _publish_account_mutation(current_user.id)
    except AvatarImageValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _profile_response(current_user)


@router.delete("/profile/avatar-image", response_model=ProfileResponse)
def delete_profile_avatar_image(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        clear_user_avatar_image(
            db,
            user=current_user,
            actor_user_id=current_user.id,
            commit=True,
        )
        _publish_account_mutation(current_user.id)
    except AvatarImageValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored avatar image is invalid",
        ) from exc
    return _profile_response(current_user)


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

    _publish_account_mutation(current_user.id)
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

    _publish_account_mutation(current_user.id)
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

    _publish_account_mutation(current_user.id)
    return SessionRevokeResponse(ok=True, revoked=revoked)

# PARTPILOT:USER_ROLE_ADMIN_ROUTES:V732
def _managed_user_response(user) -> ManagedUserResponse:
    return ManagedUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _raise_user_admin_error(exc: Exception) -> None:
    if isinstance(exc, ManagedUserNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, UserAdministrationForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, UserAdministrationError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise exc


@router.get("/users", response_model=ManagedUserListResponse)
def read_managed_users(
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserListResponse:
    try:
        users = list_managed_users(db, actor=current_user)
    except (UserAdministrationForbiddenError, UserAdministrationError) as exc:
        _raise_user_admin_error(exc)
    return ManagedUserListResponse(
        users=[_managed_user_response(user) for user in users],
        total=len(users),
    )


@router.post("/users", response_model=ManagedUserResponse, status_code=status.HTTP_201_CREATED)
def create_managed_user_route(
    payload: ManagedUserCreateRequest,
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserResponse:
    try:
        user = create_managed_user(
            db,
            actor=current_user,
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
            commit=True,
        )
    except (UserAdministrationForbiddenError, UserAdministrationError, ValueError) as exc:
        db.rollback(); _raise_user_admin_error(exc)
    _publish_account_mutation(user.id)
    return _managed_user_response(user)


@router.patch("/users/{user_id}", response_model=ManagedUserResponse)
def update_managed_user_access_route(
    user_id: int,
    payload: ManagedUserAccessUpdateRequest,
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserResponse:
    try:
        user = update_managed_user_access(
            db,
            actor=current_user,
            user_id=user_id,
            role=payload.role,
            is_active=payload.is_active,
            commit=True,
        )
    except (ManagedUserNotFoundError, UserAdministrationForbiddenError, UserAdministrationError, ValueError) as exc:
        db.rollback(); _raise_user_admin_error(exc)
    _publish_account_mutation(user.id)
    return _managed_user_response(user)


@router.post("/users/{user_id}/force-password", response_model=ManagedUserActionResponse)
def force_managed_user_password_route(
    user_id: int,
    payload: ManagedUserPasswordResetRequest,
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserActionResponse:
    try:
        revoked = force_reset_managed_user_password(
            db,
            actor=current_user,
            user_id=user_id,
            new_password=payload.new_password,
            commit=True,
        )
    except (ManagedUserNotFoundError, UserAdministrationForbiddenError, UserAdministrationError, ValueError) as exc:
        db.rollback(); _raise_user_admin_error(exc)
    _publish_account_mutation(user_id)
    return ManagedUserActionResponse(ok=True, revoked_sessions=revoked)


@router.post("/users/{user_id}/revoke-sessions", response_model=ManagedUserActionResponse)
def revoke_managed_user_sessions_route(
    user_id: int,
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserActionResponse:
    try:
        revoked = revoke_managed_user_sessions(
            db,
            actor=current_user,
            user_id=user_id,
            commit=True,
        )
    except (ManagedUserNotFoundError, UserAdministrationForbiddenError, UserAdministrationError) as exc:
        db.rollback(); _raise_user_admin_error(exc)
    _publish_account_mutation(user_id)
    return ManagedUserActionResponse(ok=True, revoked_sessions=revoked)


@router.delete("/users/{user_id}", response_model=ManagedUserActionResponse)
def delete_managed_user_route(
    user_id: int,
    payload: ManagedUserDeleteRequest,
    current_user=Depends(require_administrator_user),
    db: Session = Depends(get_db),
) -> ManagedUserActionResponse:
    try:
        delete_managed_user(
            db,
            actor=current_user,
            user_id=user_id,
            confirmation_username=payload.confirmation_username,
            commit=True,
        )
    except (ManagedUserNotFoundError, UserAdministrationForbiddenError, UserAdministrationError) as exc:
        db.rollback(); _raise_user_admin_error(exc)
    publish_live_invalidation(("account", "history"), resource={"type": "user", "id": user_id})
    return ManagedUserActionResponse(ok=True)
