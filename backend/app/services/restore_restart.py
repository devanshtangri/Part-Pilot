from __future__ import annotations

import os
from pathlib import Path
import signal

from app.core.lifecycle import (
    application_lifecycle,
)
from app.db.session import (
    dispose_database_engine,
)
from app.services.restore_bootstrap import (
    cancel_restore_commit_job,
)


RESTORE_SUPERVISOR_CONTRACT_ENV = (
    "PARTPILOT_RESTORE_SUPERVISOR_CONTRACT"
)
RESTORE_SUPERVISOR_CONTRACT_VALUE = (
    "compose-restart-v1"
)


class RestoreRestartError(RuntimeError):
    pass


def restore_supervisor_available() -> bool:
    return (
        os.getenv(
            RESTORE_SUPERVISOR_CONTRACT_ENV,
            "",
        )
        == RESTORE_SUPERVISOR_CONTRACT_VALUE
    )


# PARTPILOT:RESTORE_PROCESS_RESTART:V440
def terminate_process_for_restore(
    validation_token: str,
    actor_user_id: int,
    actor_username: str,
    staging_root: Path,
) -> None:
    try:
        dispose_database_engine()
        os.kill(
            os.getpid(),
            signal.SIGTERM,
        )
    except Exception as exc:
        cancellation_error: Exception | None = None
        try:
            cancel_restore_commit_job(
                validation_token,
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                staging_root=staging_root,
            )
        except Exception as cancel_exc:
            cancellation_error = cancel_exc
        try:
            application_lifecycle.leave_maintenance()
        except Exception:
            pass
        if cancellation_error is not None:
            raise RestoreRestartError(
                "Restore process termination failed and "
                "the pending job could not be cancelled."
            ) from cancellation_error
        raise RestoreRestartError(
            "Restore process termination failed; "
            "the pending job was cancelled."
        ) from exc
