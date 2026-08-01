from __future__ import annotations

from app.core.config import get_settings
from app.services.backups import (
    sqlite_path_from_database_url,
)
from app.services.restore_bootstrap import (
    RestoreBootstrapFatalError,
    process_pending_restore,
)
from app.services.restores import (
    restore_staging_root_for_database,
)


# PARTPILOT:PRE_UVICORN_RESTORE_BOOTSTRAP:V439
def main() -> int:
    settings = get_settings()
    database_path = sqlite_path_from_database_url(
        settings.database_url
    )
    staging_root = (
        restore_staging_root_for_database(
            database_path
        )
    )
    try:
        result = process_pending_restore(
            live_database_path=database_path,
            staging_root=staging_root,
        )
    except RestoreBootstrapFatalError as exc:
        print(
            "Part Pilot restore bootstrap fatal: "
            f"{exc}",
            flush=True,
        )
        return 1

    if result is None:
        print(
            "Part Pilot restore bootstrap: no pending job",
            flush=True,
        )
    elif result.status == "succeeded":
        print(
            "Part Pilot restore bootstrap: restore succeeded",
            flush=True,
        )
    else:
        print(
            "Part Pilot restore bootstrap: restore failed; "
            "original database recovered",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
