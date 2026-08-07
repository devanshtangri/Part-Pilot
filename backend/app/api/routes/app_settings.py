from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.app_settings import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    McpDirectAuthCustomHeaderRequest,
    McpDirectAuthKeyResponse,
    McpDirectAuthStatusResponse,
    McpDirectAuthTrustedNetworkRequest,
    McpOAuthClientRegistrationRequest,
    McpOAuthClientRegistrationResponse,
    McpOAuthClientsResponse,
    McpSettingsResponse,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_BEARER_KEY,
    DIRECT_AUTH_CUSTOM_HEADER,
    DIRECT_AUTH_DISABLED,
    DIRECT_AUTH_TRUSTED_NETWORK,
    McpDirectAuthConfigurationError,
    McpDirectAuthHeaderNameError,
    McpDirectAuthNetworkError,
    McpDirectAuthDecryptionError,
    McpDirectAuthNotConfiguredError,
    configure_trusted_networks,
    disable_direct_auth,
    get_direct_auth,
    reveal_direct_key,
    rotate_bearer_key,
    rotate_custom_header_key,
    trusted_networks_for_record,
)

from app.services.mcp_oauth import (
    McpOAuthConnectedClientNotFoundError,
    McpOAuthValidationError,
    list_connected_oauth_clients,
    register_client,
    revoke_connected_oauth_client,
)

from app.services.app_settings import (
    AppearanceThemeUnavailableError,
    get_appearance_settings,
    get_mcp_settings,
    get_reservation_settings,
    get_search_settings,
    update_appearance_settings,
    update_mcp_settings,
    update_reservation_settings,
    update_search_settings,
)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/search", response_model=SearchSettingsResponse)
def read_search_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchSettingsResponse:
    del current_user
    return get_search_settings(db)


@router.patch("/search", response_model=SearchSettingsResponse)
def patch_search_settings(
    payload: SearchSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchSettingsResponse:
    return update_search_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:RESERVATION_SETTINGS_ROUTE:V361
@router.get("/reservations", response_model=ReservationSettingsResponse)
def read_reservation_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationSettingsResponse:
    del current_user
    return get_reservation_settings(db)


@router.patch("/reservations", response_model=ReservationSettingsResponse)
def patch_reservation_settings(
    payload: ReservationSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationSettingsResponse:
    return update_reservation_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:APPEARANCE_SETTINGS_ROUTE:V411
@router.get(
    "/appearance",
    response_model=AppearanceSettingsResponse,
)
def read_appearance_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppearanceSettingsResponse:
    del current_user
    return get_appearance_settings(db)


@router.patch(
    "/appearance",
    response_model=AppearanceSettingsResponse,
)
def patch_appearance_settings(
    payload: AppearanceSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppearanceSettingsResponse:
    try:
        return update_appearance_settings(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except AppearanceThemeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:MCP_SETTINGS_ROUTE:V473
@router.get("/mcp", response_model=McpSettingsResponse)
def read_mcp_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpSettingsResponse:
    del current_user
    return get_mcp_settings(db)


@router.patch("/mcp", response_model=McpSettingsResponse)
def patch_mcp_settings(
    payload: McpSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpSettingsResponse:
    return update_mcp_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:MCP_DIRECT_AUTH_API_ROUTE:V503
def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


# PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_API:V555
@router.post("/mcp/oauth-clients", response_model=McpOAuthClientRegistrationResponse, status_code=status.HTTP_201_CREATED)
def create_mcp_oauth_client(payload: McpOAuthClientRegistrationRequest, response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpOAuthClientRegistrationResponse:
    _no_store(response)
    if payload.client_type == "public" and payload.token_endpoint_auth_method != "none":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Public OAuth clients must use authentication method none.",
            headers={"Cache-Control":"no-store","Pragma":"no-cache"},
        )
    if payload.client_type == "confidential" and payload.token_endpoint_auth_method not in {"client_secret_post", "client_secret_basic"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confidential OAuth clients must use client_secret_post or client_secret_basic.",
            headers={"Cache-Control":"no-store","Pragma":"no-cache"},
        )
    try:
        registered=register_client(db,client_name=payload.client_name,redirect_uris=payload.redirect_uris,grant_types=("authorization_code","refresh_token"),response_types=("code",),token_endpoint_auth_method=payload.token_endpoint_auth_method,metadata={"registration_source":"settings","client_type":payload.client_type},actor_user_id=current_user.id,registered_by_user_id=current_user.id,commit=True)
    except McpOAuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,detail=str(exc),headers={"Cache-Control":"no-store","Pragma":"no-cache"}) from exc
    client=registered.client
    return McpOAuthClientRegistrationResponse(database_id=client.id,client_id=registered.client_id,client_name=client.client_name,redirect_uris=list(client.redirect_uris_json or []),client_type=payload.client_type,token_endpoint_auth_method=client.token_endpoint_auth_method,created_at=client.created_at,client_secret=registered.client_secret)


# PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_API:V540
@router.get(
    "/mcp/oauth-clients",
    response_model=McpOAuthClientsResponse,
)
def read_mcp_oauth_clients(
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpOAuthClientsResponse:
    _no_store(response)
    return list_connected_oauth_clients(
        db,
        user_id=current_user.id,
    )

# PARTPILOT:MCP_OAUTH_CLIENT_REVOCATION_API:V541
@router.delete(
    "/mcp/oauth-clients/{client_database_id}",
    response_model=McpOAuthClientsResponse,
)
def delete_mcp_oauth_client(
    client_database_id: int,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpOAuthClientsResponse:
    _no_store(response)
    try:
        return revoke_connected_oauth_client(
            db,
            user_id=current_user.id,
            client_database_id=client_database_id,
            commit=True,
        )
    except McpOAuthConnectedClientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc


def _direct_auth_status(db: Session) -> McpDirectAuthStatusResponse:
    record = get_direct_auth(db)
    trusted_networks = trusted_networks_for_record(record)
    key_configured = bool(
        record is not None
        and record.mode in {DIRECT_AUTH_BEARER_KEY, DIRECT_AUTH_CUSTOM_HEADER}
        and record.key_ciphertext
        and record.key_digest
        and record.key_prefix
        and (
            record.mode != DIRECT_AUTH_CUSTOM_HEADER
            or record.custom_header_name is not None
        )
    )
    configured = key_configured or bool(
        record is not None
        and record.mode == DIRECT_AUTH_TRUSTED_NETWORK
        and trusted_networks
    )
    return McpDirectAuthStatusResponse(
        mode=record.mode if record is not None else DIRECT_AUTH_DISABLED,
        configured=configured,
        masked_key=(f"{record.key_prefix}••••••••" if key_configured and record is not None else None),
        custom_header_name=(
            record.custom_header_name
            if record is not None and record.mode == DIRECT_AUTH_CUSTOM_HEADER
            else None
        ),
        trusted_networks=trusted_networks,
        rotated_at=record.rotated_at if record is not None else None,
        last_used_at=record.last_used_at if record is not None else None,
    )

@router.get("/mcp/direct-auth", response_model=McpDirectAuthStatusResponse)
def read_mcp_direct_auth(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthStatusResponse:
    del current_user
    _no_store(response)
    return _direct_auth_status(db)

@router.post("/mcp/direct-auth/bearer-key", response_model=McpDirectAuthKeyResponse)
def rotate_mcp_direct_key(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthKeyResponse:
    _no_store(response)
    try:
        issued=rotate_bearer_key(db,actor_user_id=current_user.id,commit=True)
    except McpDirectAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    current=_direct_auth_status(db)
    return McpDirectAuthKeyResponse(**current.model_dump(),key=issued.plaintext_key)



@router.post(
    "/mcp/direct-auth/custom-header",
    response_model=McpDirectAuthKeyResponse,
)
def rotate_mcp_custom_header_key(
    payload: McpDirectAuthCustomHeaderRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectAuthKeyResponse:
    _no_store(response)
    try:
        issued = rotate_custom_header_key(
            db,
            actor_user_id=current_user.id,
            header_name=payload.header_name,
            commit=True,
        )
    except McpDirectAuthHeaderNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    except McpDirectAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    current = _direct_auth_status(db)
    return McpDirectAuthKeyResponse(
        **current.model_dump(),
        key=issued.plaintext_key,
    )


@router.post(
    "/mcp/direct-auth/trusted-network",
    response_model=McpDirectAuthStatusResponse,
)
def configure_mcp_trusted_networks(
    payload: McpDirectAuthTrustedNetworkRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectAuthStatusResponse:
    _no_store(response)
    try:
        configure_trusted_networks(
            db,
            actor_user_id=current_user.id,
            networks=payload.networks,
            commit=True,
        )
    except McpDirectAuthNetworkError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        ) from exc
    except McpDirectAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        ) from exc
    return _direct_auth_status(db)

@router.post("/mcp/direct-auth/reveal", response_model=McpDirectAuthKeyResponse)
def reveal_mcp_direct_key(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthKeyResponse:
    _no_store(response)
    try:
        key=reveal_direct_key(db,actor_user_id=current_user.id,commit=True)
    except (McpDirectAuthConfigurationError,McpDirectAuthDecryptionError,McpDirectAuthNotConfiguredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    current=_direct_auth_status(db)
    return McpDirectAuthKeyResponse(**current.model_dump(),key=key)

@router.delete("/mcp/direct-auth", response_model=McpDirectAuthStatusResponse)
def delete_mcp_direct_auth(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthStatusResponse:
    _no_store(response)
    disable_direct_auth(db,actor_user_id=current_user.id,commit=True)
    return _direct_auth_status(db)
