from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.lifecycle import application_lifecycle
from app.db.session import SessionLocal
from app.models import User, UserSession
from app.services.auth import create_session
from app.services.live_sync import (
    LIVE_SYNC_TOPICS,
    LiveSyncBroker,
    live_sync_broker,
)


# PARTPILOT:AUTHENTICATED_LIVE_SYNC_SMOKE:V687
class LiveSyncSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise LiveSyncSmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"Live-sync smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def table_counts() -> dict[str, int]:
    connection = sqlite3.connect(sqlite_path())
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        return {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
            for table in tables
        }
    finally:
        connection.close()


def session_rows() -> list[tuple[object, ...]]:
    connection = sqlite3.connect(sqlite_path())
    try:
        columns = [
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(sessions)"
            )
        ]
        if not columns:
            fail("sessions table is missing")
        selected = ", ".join(f'"{column}"' for column in columns)
        return [
            tuple(row)
            for row in connection.execute(
                f"SELECT {selected} FROM sessions ORDER BY id"
            )
        ]
    finally:
        connection.close()


def session_sequence() -> int | None:
    connection = sqlite3.connect(sqlite_path())
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if not exists:
            return None
        row = connection.execute(
            "SELECT seq FROM sqlite_sequence "
            "WHERE name='sessions'"
        ).fetchone()
        return int(row[0]) if row is not None else None
    finally:
        connection.close()


def restore_session_sequence(value: int | None) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if not exists:
            return
        connection.execute(
            "DELETE FROM sqlite_sequence "
            "WHERE name='sessions'"
        )
        if value is not None:
            connection.execute(
                "INSERT INTO sqlite_sequence(name, seq) "
                "VALUES ('sessions', ?)",
                (value,),
            )
        connection.commit()
    finally:
        connection.close()


def check_broker_contract() -> None:
    broker = LiveSyncBroker(
        generation="patch687",
        replay_limit=2,
        subscriber_queue_limit=1,
    )

    initial_state = broker.state()
    if (
        initial_state["generation"] != "patch687"
        or initial_state["sequence"] != 0
        or set(initial_state["revisions"]) != set(LIVE_SYNC_TOPICS)
        or any(initial_state["revisions"].values())
    ):
        fail(f"Initial broker state is invalid: {initial_state!r}")

    subscriber, initial = broker.subscribe()
    if (
        len(initial) != 1
        or initial[0].event_type != "ready"
        or initial[0].event_id != "patch687:0"
    ):
        fail(f"Fresh subscription handshake is invalid: {initial!r}")

    first = broker.publish(
        ["history", "inventory", "history"],
        resource={"type": "part", "id": 7},
    )
    if (
        first.event_id != "patch687:1"
        or first.topics != ("inventory", "history")
        or first.resource != {"type": "part", "id": 7}
    ):
        fail(f"First invalidation is invalid: {first!r}")

    delivered = broker.poll(subscriber)
    if (
        delivered is None
        or delivered.event_type != "invalidate"
        or delivered.event_id != first.event_id
        or delivered.data.get("topics") != ["inventory", "history"]
    ):
        fail(f"Subscriber delivery is invalid: {delivered!r}")

    broker.publish(["projects"])
    broker.publish(["reservations"])
    overflow = broker.poll(subscriber)
    if (
        overflow is None
        or overflow.event_type != "resync"
        or overflow.data.get("reason") != "subscriber_overflow"
    ):
        fail(f"Subscriber overflow did not force resync: {overflow!r}")

    broker.unsubscribe(subscriber)
    if broker.subscriber_count() != 0:
        fail("Broker subscriber cleanup failed")

    replay_subscriber, replay = broker.subscribe("patch687:2")
    if (
        [item.event_type for item in replay]
        != ["invalidate", "ready"]
        or replay[0].event_id != "patch687:3"
    ):
        fail(f"Replay contract is invalid: {replay!r}")
    broker.unsubscribe(replay_subscriber)

    stale_subscriber, stale = broker.subscribe("patch687:0")
    if (
        len(stale) != 1
        or stale[0].event_type != "resync"
        or stale[0].data.get("reason") != "replay_window_exceeded"
    ):
        fail(f"Stale replay did not resync: {stale!r}")
    broker.unsubscribe(stale_subscriber)

    generation_subscriber, generation = broker.subscribe(
        "older-process:3"
    )
    if (
        len(generation) != 1
        or generation[0].event_type != "resync"
        or generation[0].data.get("reason")
        != "generation_changed"
    ):
        fail(f"Generation mismatch did not resync: {generation!r}")
    broker.unsubscribe(generation_subscriber)

    for invalid_resource in (
        {"type": "part", "id": 1, "secret": "no"},
        {"type": "", "id": 1},
        {"type": "part", "id": True},
    ):
        try:
            broker.publish(
                ["inventory"],
                resource=invalid_resource,
            )
        except ValueError:
            pass
        else:
            fail(
                "Sensitive/invalid resource hint shape was accepted: "
                f"{invalid_resource!r}"
            )

    try:
        broker.publish(["not-a-topic"])
    except ValueError:
        pass
    else:
        fail("Unknown live-sync topic was accepted")


def check_http_contract() -> None:
    before_counts = table_counts()
    before_sessions = session_rows()
    before_sequence = session_sequence()
    session_id: int | None = None

    db = SessionLocal()
    try:
        user = db.execute(
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.id.asc())
        ).scalars().first()
        if user is None:
            fail("Live-sync smoke requires one active user")
        issued = create_session(
            db,
            user=user,
            user_agent="Patch 687 live-sync smoke",
            ip_address="127.0.0.1",
            commit=True,
        )
        session_id = int(issued.session.id)
        token = issued.token
    finally:
        db.close()

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        from app.main import app

        with TestClient(app) as client:
            unauth_state = client.get("/api/live/state")
            if unauth_state.status_code != 401:
                fail(
                    "Unauthenticated live state did not return 401: "
                    f"{unauth_state.status_code}"
                )

            unauth_events = client.get("/api/live/events")
            if unauth_events.status_code != 401:
                fail(
                    "Unauthenticated live stream did not return 401: "
                    f"{unauth_events.status_code}"
                )

            state = client.get(
                "/api/live/state",
                headers=headers,
            )
            if (
                state.status_code != 200
                or state.headers.get("cache-control")
                != "no-store, max-age=0"
            ):
                fail(
                    "Authenticated live state response is invalid: "
                    f"{state.status_code} {state.text[:300]}"
                )
            state_payload = state.json()
            if (
                not isinstance(state_payload.get("generation"), str)
                or not state_payload["generation"]
                or not isinstance(state_payload.get("sequence"), int)
                or set(state_payload.get("revisions", {}))
                != set(LIVE_SYNC_TOPICS)
            ):
                fail(
                    "Authenticated live state payload is invalid: "
                    f"{state_payload!r}"
                )

            openapi = client.get("/openapi.json")
            paths = openapi.json().get("paths", {})
            if set(paths.get("/api/live/state", {})) != {"get"}:
                fail("Live state route is missing from OpenAPI")
            if set(paths.get("/api/live/events", {})) != {"get"}:
                fail("Live event route is missing from OpenAPI")

            base_state = live_sync_broker.state()
            base_id = (
                f"{base_state['generation']}:"
                f"{base_state['sequence']}"
            )
            published = live_sync_broker.publish(
                ["inventory", "history"],
                resource={"type": "part", "id": 687},
            )

            maintenance_errors: list[str] = []

            def enter_maintenance() -> None:
                time.sleep(0.5)
                try:
                    application_lifecycle.begin_maintenance(
                        "Patch 687 live stream drain smoke"
                    )
                except Exception as exc:
                    maintenance_errors.append(
                        f"{type(exc).__name__}: {exc}"
                    )

            thread = threading.Thread(
                target=enter_maintenance,
                daemon=True,
            )
            thread.start()
            streamed = client.get(
                "/api/live/events",
                headers={
                    **headers,
                    "Accept": "text/event-stream",
                    "Last-Event-ID": base_id,
                },
            )
            thread.join(timeout=3.0)

            if thread.is_alive():
                fail("Maintenance trigger thread did not finish")
            if maintenance_errors:
                fail(
                    "Maintenance trigger failed: "
                    + "; ".join(maintenance_errors)
                )
            if streamed.status_code != 200:
                fail(
                    "Authenticated live stream failed: "
                    f"{streamed.status_code} {streamed.text[:300]}"
                )
            content_type = streamed.headers.get(
                "content-type",
                "",
            )
            if not content_type.startswith("text/event-stream"):
                fail(
                    "Live stream content type is invalid: "
                    f"{content_type!r}"
                )

            body = streamed.text
            expected_id = f"id: {published.event_id}\n"
            if (
                expected_id not in body
                or "event: invalidate\n" not in body
                or '"topics":["inventory","history"]' not in body
                or '"type":"part"' not in body
                or '"id":687' not in body
            ):
                fail(
                    "Authenticated stream did not replay the "
                    f"published invalidation: {body[:700]!r}"
                )
            if token in body:
                fail("Live stream leaked the session token")

            lifecycle = application_lifecycle.snapshot()
            if (
                lifecycle.phase != "maintenance"
                or lifecycle.active_requests != 0
                or lifecycle.accepting_requests
                or lifecycle.ready
            ):
                fail(
                    "Live stream did not drain cleanly for maintenance: "
                    f"{lifecycle!r}"
                )
            if not application_lifecycle.wait_for_drain(
                timeout=1.0,
                max_active_requests=0,
            ):
                fail("Lifecycle drain remained blocked by live stream")
            if live_sync_broker.subscriber_count() != 0:
                fail(
                    "Live stream subscription remained registered "
                    "after maintenance close"
                )

            application_lifecycle.leave_maintenance()
            recovered = client.get(
                "/api/live/state",
                headers=headers,
            )
            if recovered.status_code != 200:
                fail(
                    "Live state did not recover after maintenance: "
                    f"{recovered.status_code}"
                )

            revisions = recovered.json().get("revisions", {})
            if (
                revisions.get("inventory", 0) < 1
                or revisions.get("history", 0) < 1
            ):
                fail(
                    "Live state revisions did not reflect "
                    f"published invalidation: {revisions!r}"
                )
    finally:
        cleanup = SessionLocal()
        try:
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None:
                    cleanup.delete(session)
            cleanup.commit()
        finally:
            cleanup.close()
        restore_session_sequence(before_sequence)

    after_counts = table_counts()
    after_sessions = session_rows()
    if after_counts != before_counts:
        fail(
            "Live-sync smoke changed copied database table counts: "
            f"before={before_counts!r} after={after_counts!r}"
        )
    if after_sessions != before_sessions:
        fail(
            "Live-sync smoke did not restore the exact "
            "sessions rows"
        )


def main() -> None:
    check_broker_contract()
    check_http_contract()
    print(
        "[PASS] Authenticated live-sync broker, replay/resync, "
        "protected state/stream routes and maintenance drain are valid"
    )


if __name__ == "__main__":
    main()
