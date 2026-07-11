from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

import app.models  # Ensure every SQLAlchemy table is registered on Base.metadata.
from app.db.base import Base
from app.db.seed import (
    seed_builtin_part_types,
    seed_builtin_template_fields,
    seed_default_app_settings,
)

DEBUG_RESET_ENV = "PARTPILOT_ENABLE_DEBUG_RESET"
RESET_CONFIRMATION = "RESET PART PILOT"


@dataclass(frozen=True)
class DebugResetResult:
    recreated_part_types: int
    recreated_template_fields: int
    recreated_settings: int


def debug_database_reset_enabled() -> bool:
    value = os.getenv(DEBUG_RESET_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def reset_application_database(db: Session) -> DebugResetResult:
    if not debug_database_reset_enabled():
        raise RuntimeError("Debug database reset is disabled")

    # Delete in reverse dependency order so SQLite foreign keys remain enabled.
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())

    db.commit()

    recreated_part_types = seed_builtin_part_types(db)
    recreated_template_fields = seed_builtin_template_fields(db)
    recreated_settings = seed_default_app_settings(db)

    return DebugResetResult(
        recreated_part_types=recreated_part_types,
        recreated_template_fields=recreated_template_fields,
        recreated_settings=recreated_settings,
    )
