from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.app_settings import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    CurrencySettingsResponse,
    CurrencySettingsUpdateRequest,
    McpDirectAuthCustomHeaderRequest,
    McpDirectAuthKeyResponse,
    McpDirectAuthStatusResponse,
    McpDirectAuthTrustedNetworkRequest,
    McpDirectClientCreateRequest,
    McpDirectClientCreateResponse,
    McpDirectClientKeyResponse,
    McpDirectClientRotateRequest,
    McpDirectClientSummaryResponse,
    McpDirectClientsResponse,
    McpDirectClientUpdateRequest,
    McpClientToolPermissionsResponse,
    McpClientToolPermissionsUpdateRequest,
    McpOAuthClientRegistrationRequest,
    McpOAuthClientRegistrationResponse,
    McpOAuthClientsResponse,
    McpOAuthManageableClientsResponse,
    McpSettingsResponse,
    McpToolPermissionsResponse,
    McpToolPermissionsUpdateRequest,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    ReversiblePreferenceResetRequest,
    ReversiblePreferenceResetResponse,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
    TimezoneSettingsResponse,
    TimezoneSettingsUpdateRequest,
)
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_BEARER_KEY,
    DIRECT_AUTH_CUSTOM_HEADER,
    DIRECT_AUTH_DISABLED,
    DIRECT_AUTH_TRUSTED_NETWORK,
    McpDirectAuthConfigurationError,
    McpDirectAuthHeaderNameError,
    McpDirectAuthNetworkError,
    McpDirectAuthNameError,
    McpDirectAuthDecryptionError,
    McpDirectAuthNotConfiguredError,
    configure_trusted_networks,
    configure_named_trusted_networks,
    create_named_direct_client,
    disable_direct_auth,
    get_direct_auth,
    get_named_direct_client,
    list_direct_clients,
    reveal_direct_key,
    reveal_named_direct_client_key,
    revoke_named_direct_client,
    rotate_bearer_key,
    rotate_custom_header_key,
    rotate_named_direct_client_key,
    trusted_networks_for_record,
    update_named_direct_client,
)

from app.services.mcp_oauth import (
    McpOAuthConnectedClientNotFoundError,
    McpOAuthValidationError,
    list_connected_oauth_clients,
    list_manageable_oauth_clients,
    register_client,
    revoke_connected_oauth_client,
)
from app.services.mcp_permissions import (
    McpToolPermissionConfigurationError,
    McpToolPermissionTargetNotFoundError,
    client_tool_permissions_response,
    global_tool_permissions_response,
    update_direct_client_tool_permissions,
    update_global_tool_permissions,
    update_oauth_client_tool_permissions,
)

from app.services.app_settings import (
    AppearanceThemeUnavailableError,
    McpSettingsValidationError,
    get_appearance_settings,
    get_currency_settings,
    get_mcp_settings,
    get_reservation_settings,
    get_search_settings,
    get_timezone_settings,
    reset_reversible_preference,
    update_appearance_settings,
    update_currency_settings,
    update_mcp_settings,
    update_reservation_settings,
    update_search_settings,
    update_timezone_settings,
)
from app.services.live_sync import publish_live_invalidation


# PARTPILOT:PREFERENCES_LIVE_SYNC_PUBLICATION:V705
def _publish_preference_mutation(user_id: int) -> None:
    publish_live_invalidation(
        ("preferences", "history"),
        resource={"type": "preferences", "id": user_id},
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
    result = update_search_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )
    _publish_preference_mutation(current_user.id)
    return result


# PARTPILOT:CURRENCY_PREFERENCE_ROUTE:V675
@router.get("/currency", response_model=CurrencySettingsResponse)
def read_currency_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrencySettingsResponse:
    del current_user
    return get_currency_settings(db)


@router.patch("/currency", response_model=CurrencySettingsResponse)
def patch_currency_settings(
    payload: CurrencySettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrencySettingsResponse:
    result = update_currency_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )
    _publish_preference_mutation(current_user.id)
    return result


# PARTPILOT:TIMEZONE_PREFERENCE_ROUTE:V676
@router.get("/timezone", response_model=TimezoneSettingsResponse)
def read_timezone_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimezoneSettingsResponse:
    del current_user
    return get_timezone_settings(db)


@router.patch("/timezone", response_model=TimezoneSettingsResponse)
def patch_timezone_settings(
    payload: TimezoneSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimezoneSettingsResponse:
    result = update_timezone_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )
    _publish_preference_mutation(current_user.id)
    return result


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
    result = update_reservation_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )
    _publish_preference_mutation(current_user.id)
    return result


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
        result = update_appearance_settings(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
        _publish_preference_mutation(current_user.id)
        return result
    except AppearanceThemeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:TARGETED_PREFERENCE_RESET_ROUTE:V673
@router.post("/preferences/reset", response_model=ReversiblePreferenceResetResponse)
def reset_preference_to_default(
    payload: ReversiblePreferenceResetRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReversiblePreferenceResetResponse:
    result = reset_reversible_preference(
        db,
        target=payload.target,
        actor_user_id=current_user.id,
        commit=True,
    )
    _publish_preference_mutation(current_user.id)
    return result


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
    try:
        return update_mcp_settings(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except McpSettingsValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# PARTPILOT:MCP_DIRECT_AUTH_API_ROUTE:V503
def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


# PARTPILOT:MCP_TOOL_PERMISSION_ADMIN_API:V650
def _mcp_permission_error(exc: Exception) -> HTTPException:
    if isinstance(exc, McpToolPermissionTargetNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.get(
    "/mcp/tool-permissions",
    response_model=McpToolPermissionsResponse,
)
def read_mcp_tool_permissions(
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpToolPermissionsResponse:
    del current_user
    _no_store(response)
    try:
        return global_tool_permissions_response(db)
    except McpToolPermissionConfigurationError as exc:
        raise _mcp_permission_error(exc) from exc


@router.patch(
    "/mcp/tool-permissions",
    response_model=McpToolPermissionsResponse,
)
def patch_mcp_tool_permissions(
    payload: McpToolPermissionsUpdateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpToolPermissionsResponse:
    _no_store(response)
    try:
        return update_global_tool_permissions(
            db,
            payload.permissions,
            actor_user_id=current_user.id,
            commit=True,
        )
    except McpToolPermissionConfigurationError as exc:
        raise _mcp_permission_error(exc) from exc


@router.patch(
    "/mcp/oauth-clients/{client_database_id}/permissions",
    response_model=McpClientToolPermissionsResponse,
)
def patch_mcp_oauth_client_permissions(
    client_database_id: int,
    payload: McpClientToolPermissionsUpdateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpClientToolPermissionsResponse:
    _no_store(response)
    try:
        return update_oauth_client_tool_permissions(
            db,
            user_id=current_user.id,
            client_database_id=client_database_id,
            denied_tools=payload.denied_tools,
            actor_user_id=current_user.id,
            commit=True,
        )
    except (
        McpToolPermissionConfigurationError,
        McpToolPermissionTargetNotFoundError,
    ) as exc:
        raise _mcp_permission_error(exc) from exc


@router.patch(
    "/mcp/direct-clients/{client_id}/permissions",
    response_model=McpClientToolPermissionsResponse,
)
def patch_mcp_direct_client_permissions(
    client_id: int,
    payload: McpClientToolPermissionsUpdateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpClientToolPermissionsResponse:
    _no_store(response)
    try:
        return update_direct_client_tool_permissions(
            db,
            client_id=client_id,
            denied_tools=payload.denied_tools,
            actor_user_id=current_user.id,
            commit=True,
        )
    except (
        McpToolPermissionConfigurationError,
        McpToolPermissionTargetNotFoundError,
    ) as exc:
        raise _mcp_permission_error(exc) from exc


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

# PARTPILOT:MCP_OAUTH_MANAGEABLE_API:V559
@router.get("/mcp/oauth-clients/manageable", response_model=McpOAuthManageableClientsResponse)
def read_manageable_mcp_oauth_clients(response: Response, current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> McpOAuthManageableClientsResponse:
    _no_store(response)
    return list_manageable_oauth_clients(db, user_id=current_user.id)


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


# PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_API:V627

def _named_direct_client_summary(
    db: Session,
    record,
) -> McpDirectClientSummaryResponse:
    permissions = client_tool_permissions_response(db, record.denied_tools_json)
    key_configured = bool(
        record.mode in {DIRECT_AUTH_BEARER_KEY, DIRECT_AUTH_CUSTOM_HEADER}
        and record.key_ciphertext
        and record.key_digest
        and record.key_prefix
    )
    return McpDirectClientSummaryResponse(
        id=record.id,
        name=record.name,
        enabled=bool(record.enabled),
        mode=record.mode,
        masked_key=(f"{record.key_prefix}••••••••" if key_configured else None),
        custom_header_name=(
            record.custom_header_name
            if record.mode == DIRECT_AUTH_CUSTOM_HEADER
            else None
        ),
        trusted_networks=(
            trusted_networks_for_record(record)
            if record.mode == DIRECT_AUTH_TRUSTED_NETWORK
            else []
        ),
        rotated_at=record.rotated_at,
        last_used_at=record.last_used_at,
        last_resolved_client_ip=record.last_resolved_client_ip,
        created_at=record.created_at,
        updated_at=record.updated_at,
        denied_tools=permissions.denied_tools,
        tool_permissions=permissions.tools,
    )


def _named_direct_clients_response(db: Session) -> McpDirectClientsResponse:
    clients = [
        _named_direct_client_summary(db, record)
        for record in list_direct_clients(db, include_revoked=False)
        if record.mode != DIRECT_AUTH_DISABLED
    ]
    return McpDirectClientsResponse(clients=clients, total=len(clients))


def _named_direct_error(exc: Exception) -> HTTPException:
    if isinstance(exc, McpDirectAuthNotConfiguredError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
    if isinstance(
        exc,
        (McpDirectAuthNameError, McpDirectAuthHeaderNameError, McpDirectAuthNetworkError),
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.get("/mcp/direct-clients", response_model=McpDirectClientsResponse)
def read_mcp_direct_clients(
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientsResponse:
    del current_user
    _no_store(response)
    return _named_direct_clients_response(db)


@router.post(
    "/mcp/direct-clients",
    response_model=McpDirectClientCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mcp_direct_client(
    payload: McpDirectClientCreateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientCreateResponse:
    _no_store(response)
    try:
        created = create_named_direct_client(
            db,
            actor_user_id=current_user.id,
            name=payload.name,
            mode=payload.mode,
            header_name=payload.header_name,
            networks=payload.networks,
            commit=True,
        )
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthHeaderNameError,
        McpDirectAuthNetworkError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    if hasattr(created, "plaintext_key"):
        record = created.record
        key = created.plaintext_key
    else:
        record = created
        key = None
    return McpDirectClientCreateResponse(
        **_named_direct_client_summary(db, record).model_dump(),
        key=key,
    )


@router.patch(
    "/mcp/direct-clients/{client_id}",
    response_model=McpDirectClientSummaryResponse,
)
def patch_mcp_direct_client(
    client_id: int,
    payload: McpDirectClientUpdateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientSummaryResponse:
    _no_store(response)
    try:
        record = update_named_direct_client(
            db,
            client_id=client_id,
            actor_user_id=current_user.id,
            name=payload.name,
            enabled=payload.enabled,
            commit=True,
        )
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthNetworkError,
        McpDirectAuthNotConfiguredError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    return _named_direct_client_summary(db, record)


@router.post(
    "/mcp/direct-clients/{client_id}/rotate",
    response_model=McpDirectClientKeyResponse,
)
def rotate_mcp_named_direct_client(
    client_id: int,
    payload: McpDirectClientRotateRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientKeyResponse:
    _no_store(response)
    try:
        issued = rotate_named_direct_client_key(
            db,
            client_id=client_id,
            actor_user_id=current_user.id,
            header_name=payload.header_name,
            commit=True,
        )
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthHeaderNameError,
        McpDirectAuthNotConfiguredError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    return McpDirectClientKeyResponse(
        **_named_direct_client_summary(db, issued.record).model_dump(),
        key=issued.plaintext_key,
    )


@router.post(
    "/mcp/direct-clients/{client_id}/reveal",
    response_model=McpDirectClientKeyResponse,
)
def reveal_mcp_named_direct_client(
    client_id: int,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientKeyResponse:
    _no_store(response)
    try:
        key = reveal_named_direct_client_key(
            db,
            client_id=client_id,
            actor_user_id=current_user.id,
            commit=True,
        )
        record = get_named_direct_client(db, client_id)
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthDecryptionError,
        McpDirectAuthNotConfiguredError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    return McpDirectClientKeyResponse(
        **_named_direct_client_summary(db, record).model_dump(),
        key=key,
    )


@router.put(
    "/mcp/direct-clients/{client_id}/trusted-networks",
    response_model=McpDirectClientSummaryResponse,
)
def put_mcp_named_direct_client_networks(
    client_id: int,
    payload: McpDirectAuthTrustedNetworkRequest,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientSummaryResponse:
    _no_store(response)
    try:
        record = configure_named_trusted_networks(
            db,
            client_id=client_id,
            actor_user_id=current_user.id,
            networks=payload.networks,
            commit=True,
        )
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthNetworkError,
        McpDirectAuthNotConfiguredError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    return _named_direct_client_summary(db, record)


@router.delete(
    "/mcp/direct-clients/{client_id}",
    response_model=McpDirectClientsResponse,
)
def delete_mcp_named_direct_client(
    client_id: int,
    response: Response,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpDirectClientsResponse:
    _no_store(response)
    try:
        revoke_named_direct_client(
            db,
            client_id=client_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except (
        McpDirectAuthConfigurationError,
        McpDirectAuthNotConfiguredError,
    ) as exc:
        raise _named_direct_error(exc) from exc
    return _named_direct_clients_response(db)


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
