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
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)


SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY = (
    "search.show_out_of_stock_section"
)
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
