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
    McpSettingsResponse,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)
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


# PARTPILOT:MCP_SETTINGS_SERVICE:V473
def get_mcp_settings(db: Session) -> McpSettingsResponse:
    return McpSettingsResponse(
        enabled=get_bool_setting(db, MCP_ENABLED_KEY, False),
        read_tools_enabled=get_bool_setting(
            db, MCP_READ_ENABLED_KEY, True
        ),
        write_tools_enabled=get_bool_setting(
            db, MCP_WRITE_ENABLED_KEY, False
        ),
    )


def update_mcp_settings(
    db: Session,
    payload: McpSettingsUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> McpSettingsResponse:
    before = get_mcp_settings(db)
    after = McpSettingsResponse(
        enabled=payload.enabled,
        read_tools_enabled=payload.read_tools_enabled,
        write_tools_enabled=payload.write_tools_enabled,
    )
    if before == after:
        return before

    changed_fields = [
        field_name
        for field_name in (
            "enabled",
            "read_tools_enabled",
            "write_tools_enabled",
        )
        if getattr(before, field_name) != getattr(after, field_name)
    ]

    try:
        settings = [
            set_app_setting(
                db, MCP_ENABLED_KEY, after.enabled, commit=False
            ),
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
        ]
        db.add(
            AuditLog(
                event_type="settings.mcp_updated",
                entity_type="app_setting",
                entity_id=settings[0].id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary="Updated MCP access settings",
                before_json=before.model_dump(),
                after_json=after.model_dump(),
                metadata_json={
                    "setting_keys": [
                        MCP_ENABLED_KEY,
                        MCP_READ_ENABLED_KEY,
                        MCP_WRITE_ENABLED_KEY,
                    ],
                    "changed_fields": changed_fields,
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
