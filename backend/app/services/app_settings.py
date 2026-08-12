from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.settings import (
    get_app_setting,
    get_bool_setting,
    get_str_setting,
    set_app_setting,
)
from app.models import AuditLog
from app.schemas.app_settings import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    CurrencySettingsResponse,
    CurrencySettingsUpdateRequest,
    McpSettingsResponse,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    ReversiblePreferenceResetResponse,
    ReversiblePreferenceResetTarget,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
    TimezoneSettingsResponse,
    TimezoneSettingsUpdateRequest,
)
from app.services.app_setup import DEFAULT_CURRENCY_KEY, DEFAULT_TIMEZONE_KEY
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_WRITE_ENABLED_KEY,
)


SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY = (
    "search.show_out_of_stock_section"
)
APPEARANCE_THEME_KEY = "appearance.theme"
APPEARANCE_LIGHT_THEME_AVAILABLE_KEY = (
    "appearance.light_theme_available"
)
VALID_APPEARANCE_THEMES = {"dark", "light", "system"}
RESERVATION_EXPIRY_MODE_KEY = "reservations.expiry.mode"
RESERVATION_EXPIRY_DEFAULT_DAYS_KEY = (
    "reservations.expiry.default_days"
)
MCP_DIRECT_CLIENTS_ENABLED_KEY = "mcp.direct_clients_enabled"
MCP_DIRECT_NO_AUTH_ENABLED_KEY = "mcp.direct_no_auth_enabled"
MCP_DIRECT_NO_AUTH_LAST_CLIENT_IP_KEY = "mcp.direct_no_auth_last_client_ip"
MCP_DIRECT_NO_AUTH_CONFIRMATION = "ALLOW NO AUTH"
DEFAULT_APPEARANCE_THEME = "dark"
DEFAULT_SHOW_OUT_OF_STOCK_SECTION = True
DEFAULT_RESERVATION_EXPIRY_MODE = "none"
DEFAULT_RESERVATION_EXPIRY_DEFAULT_DAYS = None
REVERSIBLE_PREFERENCE_SETTING_KEYS = (
    APPEARANCE_THEME_KEY,
    SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,
    RESERVATION_EXPIRY_MODE_KEY,
    RESERVATION_EXPIRY_DEFAULT_DAYS_KEY,
)


class McpSettingsValidationError(RuntimeError):
    pass


def get_search_settings(db: Session) -> SearchSettingsResponse:
    return SearchSettingsResponse(
        show_out_of_stock_section=get_bool_setting(
            db,
            SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,
            True,
        )
    )


def update_search_settings(
    db: Session,
    payload: SearchSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> SearchSettingsResponse:
    before_value = get_bool_setting(
        db,
        SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,
        True,
    )
    after_value = payload.show_out_of_stock_section

    try:
        setting = set_app_setting(
            db,
            SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,
            after_value,
            commit=False,
        )

        if before_value != after_value:
            db.add(
                AuditLog(
                    event_type="settings.search_updated",
                    entity_type="app_setting",
                    entity_id=setting.id,
                    actor_type=(
                        "user"
                        if actor_user_id is not None
                        else "system"
                    ),
                    actor_user_id=actor_user_id,
                    summary="Updated inventory search settings",
                    before_json={
                        "show_out_of_stock_section": before_value,
                    },
                    after_json={
                        "show_out_of_stock_section": after_value,
                    },
                    metadata_json={
                        "setting_key": (
                            SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY
                        ),
                        "changed_fields": [
                            "show_out_of_stock_section",
                        ],
                    },
                )
            )

        db.flush()
        if commit:
            db.commit()
            db.refresh(setting)

    except Exception:
        if commit:
            db.rollback()
        raise

    return SearchSettingsResponse(
        show_out_of_stock_section=after_value
    )


# PARTPILOT:CURRENCY_PREFERENCE_SERVICE:V675
def get_currency_settings(db: Session) -> CurrencySettingsResponse:
    currency = get_str_setting(db, DEFAULT_CURRENCY_KEY, "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise RuntimeError("Default currency is not configured correctly")
    return CurrencySettingsResponse(currency=currency)


def update_currency_settings(
    db: Session,
    payload: CurrencySettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> CurrencySettingsResponse:
    before = get_currency_settings(db)
    after = CurrencySettingsResponse(currency=payload.currency)
    if before == after:
        return before

    try:
        setting = set_app_setting(
            db,
            DEFAULT_CURRENCY_KEY,
            after.currency,
            text_value=after.currency,
            commit=False,
        )
        db.add(
            AuditLog(
                event_type="settings.currency_updated",
                entity_type="app_setting",
                entity_id=setting.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Updated default currency",
                before_json={"currency": before.currency},
                after_json={"currency": after.currency},
                metadata_json={
                    "setting_key": DEFAULT_CURRENCY_KEY,
                    "changed_fields": ["currency"],
                    "formatting_only": True,
                    "historical_snapshots_preserved": True,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(setting)
    except Exception:
        if commit:
            db.rollback()
        raise
    return after


# PARTPILOT:TIMEZONE_PREFERENCE_SERVICE:V676
def get_timezone_settings(db: Session) -> TimezoneSettingsResponse:
    timezone = get_str_setting(db, DEFAULT_TIMEZONE_KEY, "").strip()
    if not timezone:
        raise RuntimeError("Default timezone is not configured correctly")
    return TimezoneSettingsResponse(timezone=timezone)


def update_timezone_settings(
    db: Session,
    payload: TimezoneSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> TimezoneSettingsResponse:
    before = get_timezone_settings(db)
    after = TimezoneSettingsResponse(timezone=payload.timezone)
    if before == after:
        return before

    try:
        setting = set_app_setting(
            db,
            DEFAULT_TIMEZONE_KEY,
            after.timezone,
            text_value=after.timezone,
            commit=False,
        )
        db.add(
            AuditLog(
                event_type="settings.timezone_updated",
                entity_type="app_setting",
                entity_id=setting.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Updated display timezone",
                before_json={"timezone": before.timezone},
                after_json={"timezone": after.timezone},
                metadata_json={
                    "setting_key": DEFAULT_TIMEZONE_KEY,
                    "changed_fields": ["timezone"],
                    "display_only": True,
                    "stored_timestamps_preserved": True,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(setting)
    except Exception:
        if commit:
            db.rollback()
        raise
    return after


# PARTPILOT:RESERVATION_SETTINGS_SERVICE:V361
def get_reservation_settings(db: Session) -> ReservationSettingsResponse:
    raw_mode = get_str_setting(
        db,
        RESERVATION_EXPIRY_MODE_KEY,
        "none",
    ).strip()
    raw_days = get_app_setting(
        db,
        RESERVATION_EXPIRY_DEFAULT_DAYS_KEY,
        None,
    )

    if (
        raw_mode != "default"
        or isinstance(raw_days, bool)
        or not isinstance(raw_days, int)
        or not 1 <= raw_days <= 3650
    ):
        return ReservationSettingsResponse(
            expiry_mode="none",
            default_days=None,
        )

    return ReservationSettingsResponse(
        expiry_mode="default",
        default_days=raw_days,
    )


def update_reservation_settings(
    db: Session,
    payload: ReservationSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationSettingsResponse:
    before = get_reservation_settings(db)
    after = ReservationSettingsResponse(
        expiry_mode=payload.expiry_mode,
        default_days=(
            payload.default_days
            if payload.expiry_mode == "default"
            else None
        ),
    )

    if before == after:
        return before

    changed_fields = [
        field_name
        for field_name in ("expiry_mode", "default_days")
        if getattr(before, field_name) != getattr(after, field_name)
    ]

    try:
        mode_setting = set_app_setting(
            db,
            RESERVATION_EXPIRY_MODE_KEY,
            after.expiry_mode,
            text_value=after.expiry_mode,
            commit=False,
        )
        days_setting = set_app_setting(
            db,
            RESERVATION_EXPIRY_DEFAULT_DAYS_KEY,
            after.default_days,
            text_value=None,
            commit=False,
        )

        db.add(
            AuditLog(
                event_type="settings.reservations_updated",
                entity_type="app_setting",
                entity_id=mode_setting.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary="Updated reservation defaults",
                before_json=before.model_dump(),
                after_json=after.model_dump(),
                metadata_json={
                    "setting_keys": [
                        RESERVATION_EXPIRY_MODE_KEY,
                        RESERVATION_EXPIRY_DEFAULT_DAYS_KEY,
                    ],
                    "changed_fields": changed_fields,
                },
            )
        )

        db.flush()
        if commit:
            db.commit()
            db.refresh(mode_setting)
            db.refresh(days_setting)

    except Exception:
        if commit:
            db.rollback()
        raise

    return after


# PARTPILOT:APPEARANCE_SETTINGS_SERVICE:V411
class AppearanceThemeUnavailableError(ValueError):
    pass


def get_appearance_settings(
    db: Session,
) -> AppearanceSettingsResponse:
    raw_theme = get_str_setting(
        db,
        APPEARANCE_THEME_KEY,
        "dark",
    ).strip().casefold()
    light_theme_available = get_bool_setting(
        db,
        APPEARANCE_LIGHT_THEME_AVAILABLE_KEY,
        True,
    )

    theme = (
        raw_theme
        if raw_theme in VALID_APPEARANCE_THEMES
        else "dark"
    )
    if not light_theme_available and theme != "dark":
        theme = "dark"

    return AppearanceSettingsResponse(
        theme=theme,
        light_theme_available=light_theme_available,
    )


def update_appearance_settings(
    db: Session,
    payload: AppearanceSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> AppearanceSettingsResponse:
    before = get_appearance_settings(db)

    if (
        payload.theme != "dark"
        and not before.light_theme_available
    ):
        raise AppearanceThemeUnavailableError(
            "The light appearance theme is not available for this "
            "installation."
        )

    after = AppearanceSettingsResponse(
        theme=payload.theme,
        light_theme_available=before.light_theme_available,
    )
    if before == after:
        return before

    try:
        setting = set_app_setting(
            db,
            APPEARANCE_THEME_KEY,
            after.theme,
            text_value=after.theme,
            commit=False,
        )
        db.add(
            AuditLog(
                event_type="settings.appearance_updated",
                entity_type="app_setting",
                entity_id=setting.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary="Updated application appearance",
                before_json={"theme": before.theme},
                after_json={"theme": after.theme},
                metadata_json={
                    "setting_key": APPEARANCE_THEME_KEY,
                    "changed_fields": ["theme"],
                    "light_theme_available": (
                        before.light_theme_available
                    ),
                },
            )
        )

        db.flush()
        if commit:
            db.commit()
            db.refresh(setting)

    except Exception:
        if commit:
            db.rollback()
        raise

    return after


# PARTPILOT:TARGETED_PREFERENCE_RESET_SERVICE:V673
PREFERENCE_TARGET_SETTING_KEYS: dict[ReversiblePreferenceResetTarget, tuple[str, ...]] = {
    "appearance": (APPEARANCE_THEME_KEY,),
    "inventory": (SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,),
    "reservations": (RESERVATION_EXPIRY_MODE_KEY, RESERVATION_EXPIRY_DEFAULT_DAYS_KEY),
}


def reset_reversible_preference(
    db: Session,
    *,
    target: ReversiblePreferenceResetTarget,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReversiblePreferenceResetResponse:
    keys = PREFERENCE_TARGET_SETTING_KEYS[target]
    defaults = {
        APPEARANCE_THEME_KEY: DEFAULT_APPEARANCE_THEME,
        SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY: DEFAULT_SHOW_OUT_OF_STOCK_SECTION,
        RESERVATION_EXPIRY_MODE_KEY: DEFAULT_RESERVATION_EXPIRY_MODE,
        RESERVATION_EXPIRY_DEFAULT_DAYS_KEY: DEFAULT_RESERVATION_EXPIRY_DEFAULT_DAYS,
    }
    raw_values = {
        APPEARANCE_THEME_KEY: get_app_setting(db, APPEARANCE_THEME_KEY, DEFAULT_APPEARANCE_THEME),
        SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY: get_app_setting(db, SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY, DEFAULT_SHOW_OUT_OF_STOCK_SECTION),
        RESERVATION_EXPIRY_MODE_KEY: get_app_setting(db, RESERVATION_EXPIRY_MODE_KEY, DEFAULT_RESERVATION_EXPIRY_MODE),
        RESERVATION_EXPIRY_DEFAULT_DAYS_KEY: get_app_setting(db, RESERVATION_EXPIRY_DEFAULT_DAYS_KEY, DEFAULT_RESERVATION_EXPIRY_DEFAULT_DAYS),
    }
    changed_setting_keys = [key for key in keys if type(raw_values[key]) is not type(defaults[key]) or raw_values[key] != defaults[key]]

    if target == "appearance":
        current = get_appearance_settings(db)
        before = current.model_dump()
        after = ReversiblePreferenceResetResponse(target=target, appearance=AppearanceSettingsResponse(theme=DEFAULT_APPEARANCE_THEME, light_theme_available=current.light_theme_available))
    elif target == "inventory":
        before = get_search_settings(db).model_dump()
        after = ReversiblePreferenceResetResponse(target=target, inventory=SearchSettingsResponse(show_out_of_stock_section=DEFAULT_SHOW_OUT_OF_STOCK_SECTION))
    else:
        before = get_reservation_settings(db).model_dump()
        after = ReversiblePreferenceResetResponse(target=target, reservations=ReservationSettingsResponse(expiry_mode=DEFAULT_RESERVATION_EXPIRY_MODE, default_days=DEFAULT_RESERVATION_EXPIRY_DEFAULT_DAYS))

    if not changed_setting_keys:
        return after

    try:
        changed_settings = []
        for key in changed_setting_keys:
            text_value = defaults[key] if key in {APPEARANCE_THEME_KEY, RESERVATION_EXPIRY_MODE_KEY} else None
            changed_settings.append(set_app_setting(db, key, defaults[key], text_value=text_value, commit=False))
        db.add(AuditLog(
            event_type="settings.preference_reset",
            entity_type="app_setting",
            entity_id=changed_settings[0].id,
            actor_type="user" if actor_user_id is not None else "system",
            actor_user_id=actor_user_id,
            summary=f"Reset {target} preference to default",
            before_json=before,
            after_json=after.model_dump(exclude_none=True),
            metadata_json={
                "target": target,
                "setting_keys": list(keys),
                "changed_setting_keys": changed_setting_keys,
                "preserves_other_preferences": True,
                "preserves_security_and_business_data": True,
            },
        ))
        db.flush()
        if commit: db.commit()
    except Exception:
        if commit: db.rollback()
        raise
    return after


# PARTPILOT:MCP_SETTINGS_SERVICE:V627
def get_mcp_settings(db: Session) -> McpSettingsResponse:
    last_ip = get_str_setting(db, MCP_DIRECT_NO_AUTH_LAST_CLIENT_IP_KEY, "").strip()
    return McpSettingsResponse(
        enabled=get_bool_setting(db, MCP_ENABLED_KEY, False),
        read_tools_enabled=get_bool_setting(db, MCP_READ_ENABLED_KEY, True),
        write_tools_enabled=get_bool_setting(db, MCP_WRITE_ENABLED_KEY, False),
        direct_clients_enabled=get_bool_setting(
            db, MCP_DIRECT_CLIENTS_ENABLED_KEY, False
        ),
        direct_no_auth_enabled=get_bool_setting(
            db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False
        ),
        direct_no_auth_last_client_ip=last_ip or None,
    )


def update_mcp_settings(
    db: Session,
    payload: McpSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> McpSettingsResponse:
    before = get_mcp_settings(db)
    if payload.direct_no_auth_enabled and not payload.direct_clients_enabled:
        raise McpSettingsValidationError(
            "No-auth direct access requires Allow direct MCP clients."
        )
    if (
        payload.direct_no_auth_enabled
        and not before.direct_no_auth_enabled
        and payload.direct_no_auth_confirmation != MCP_DIRECT_NO_AUTH_CONFIRMATION
    ):
        raise McpSettingsValidationError(
            f"Type {MCP_DIRECT_NO_AUTH_CONFIRMATION!r} to enable unauthenticated MCP access."
        )

    after = McpSettingsResponse(
        enabled=payload.enabled,
        read_tools_enabled=payload.read_tools_enabled,
        write_tools_enabled=payload.write_tools_enabled,
        direct_clients_enabled=payload.direct_clients_enabled,
        direct_no_auth_enabled=payload.direct_no_auth_enabled,
        direct_no_auth_last_client_ip=before.direct_no_auth_last_client_ip,
    )
    comparable_fields = (
        "enabled",
        "read_tools_enabled",
        "write_tools_enabled",
        "direct_clients_enabled",
        "direct_no_auth_enabled",
    )
    changed_fields = [
        field_name
        for field_name in comparable_fields
        if getattr(before, field_name) != getattr(after, field_name)
    ]
    if not changed_fields:
        return before

    try:
        settings = [
            set_app_setting(db, MCP_ENABLED_KEY, after.enabled, commit=False),
            set_app_setting(
                db,
                MCP_READ_ENABLED_KEY,
                after.read_tools_enabled,
                commit=False,
            ),
            set_app_setting(
                db,
                MCP_WRITE_ENABLED_KEY,
                after.write_tools_enabled,
                commit=False,
            ),
            set_app_setting(
                db,
                MCP_DIRECT_CLIENTS_ENABLED_KEY,
                after.direct_clients_enabled,
                commit=False,
            ),
            set_app_setting(
                db,
                MCP_DIRECT_NO_AUTH_ENABLED_KEY,
                after.direct_no_auth_enabled,
                commit=False,
            ),
        ]
        db.add(
            AuditLog(
                event_type="settings.mcp_updated",
                entity_type="app_setting",
                entity_id=settings[0].id,
                actor_type=("user" if actor_user_id is not None else "system"),
                actor_user_id=actor_user_id,
                summary="Updated MCP access settings",
                before_json=before.model_dump(),
                after_json=after.model_dump(),
                metadata_json={
                    "setting_keys": [
                        MCP_ENABLED_KEY,
                        MCP_READ_ENABLED_KEY,
                        MCP_WRITE_ENABLED_KEY,
                        MCP_DIRECT_CLIENTS_ENABLED_KEY,
                        MCP_DIRECT_NO_AUTH_ENABLED_KEY,
                    ],
                    "changed_fields": changed_fields,
                    "no_auth_confirmation": "redacted",
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            for setting in settings:
                db.refresh(setting)
    except Exception:
        if commit:
            db.rollback()
        raise
    return after
