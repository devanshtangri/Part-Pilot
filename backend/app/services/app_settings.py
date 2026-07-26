from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.settings import get_bool_setting, set_app_setting
from app.models import AuditLog
from app.schemas.app_settings import (
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)


SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY = (
    "search.show_out_of_stock_section"
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
