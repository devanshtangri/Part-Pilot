from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import parse_setting_value
from app.models import AppSetting


def get_app_setting(db: Session, key: str, default: Any = None) -> Any:
    setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if setting is None:
        return default
    return parse_setting_value(setting.value_json, setting.value_text, default)


def set_app_setting(
    db: Session,
    key: str,
    value: Any,
    *,
    text_value: str | None = None,
    commit: bool = True,
) -> AppSetting:
    setting = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if setting is None:
        setting = AppSetting(key=key)
        db.add(setting)

    setting.value_json = value
    setting.value_text = text_value if text_value is not None else (value if isinstance(value, str) else None)

    if commit:
        db.commit()
        db.refresh(setting)
    else:
        db.flush()

    return setting


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    value = get_app_setting(db, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def get_str_setting(db: Session, key: str, default: str = "") -> str:
    value = get_app_setting(db, key, default)
    if value is None:
        return default
    return str(value)
