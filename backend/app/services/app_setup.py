from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting

SETUP_COMPLETED_KEY = "setup.completed"
DEFAULT_CURRENCY_KEY = "currency.default"
DEFAULT_TIMEZONE_KEY = "timezone.default"


@dataclass(frozen=True)
class ApplicationSetupConfiguration:
    complete: bool
    default_currency: str | None
    timezone: str | None


def _get_setting(db: Session, key: str) -> AppSetting | None:
    return db.execute(
        select(AppSetting).where(AppSetting.key == key)
    ).scalar_one_or_none()


def _get_or_create_setting(db: Session, key: str) -> AppSetting:
    setting = _get_setting(db, key)
    if setting is not None:
        return setting

    setting = AppSetting(key=key, value_json=None, value_text=None)
    db.add(setting)
    db.flush()
    return setting


def _string_value(setting: AppSetting | None) -> str | None:
    if setting is None:
        return None

    value = setting.value_json
    if isinstance(value, str) and value.strip():
        return value.strip()

    if setting.value_text and setting.value_text.strip():
        return setting.value_text.strip()

    return None


def get_application_setup_configuration(
    db: Session,
) -> ApplicationSetupConfiguration:
    completed_setting = _get_setting(db, SETUP_COMPLETED_KEY)
    currency = _string_value(_get_setting(db, DEFAULT_CURRENCY_KEY))
    timezone = _string_value(_get_setting(db, DEFAULT_TIMEZONE_KEY))

    marked_complete = bool(
        completed_setting is not None
        and completed_setting.value_json is True
    )

    return ApplicationSetupConfiguration(
        complete=marked_complete and currency is not None and timezone is not None,
        default_currency=currency,
        timezone=timezone,
    )


def save_application_setup_configuration(
    db: Session,
    *,
    default_currency: str,
    timezone: str,
    commit: bool = True,
) -> ApplicationSetupConfiguration:
    normalized_currency = default_currency.strip().upper()
    normalized_timezone = timezone.strip()

    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise ValueError("Default currency must be a three-letter code")

    if not normalized_timezone:
        raise ValueError("Timezone cannot be empty")

    completed_setting = _get_or_create_setting(db, SETUP_COMPLETED_KEY)
    currency_setting = _get_or_create_setting(db, DEFAULT_CURRENCY_KEY)
    timezone_setting = _get_or_create_setting(db, DEFAULT_TIMEZONE_KEY)

    currency_setting.value_json = normalized_currency
    currency_setting.value_text = normalized_currency

    timezone_setting.value_json = normalized_timezone
    timezone_setting.value_text = normalized_timezone

    completed_setting.value_json = True
    completed_setting.value_text = None

    db.flush()

    if commit:
        db.commit()

    return get_application_setup_configuration(db)
