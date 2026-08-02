from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import AppSetting, AuditLog, User
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_SCOPE_READ,
    MCP_WRITE_ENABLED_KEY,
    exchange_authorization_code,
    grant_consent,
    issue_authorization_code,
    pkce_s256_challenge,
    register_client,
)
from app.services.projects import get_project, list_projects
from app.services.reservations import get_reservation, list_reservations


# PARTPILOT:MCP_WORKSPACE_TOOLS_SMOKE:V471
RESOURCE = "https://partpilot.example/mcp"
REDIRECT = "https://client.example/callback"
VERIFIER = "w" * 64
EXPECTED_TOOL_NAMES = (
    "get_part_details",
    "get_project_details",
    "get_reservation_details",
    "list_projects",
    "list_reservations",
    "search_parts",
)


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP workspace smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def database_snapshot() -> dict[str, object]:
    path = sqlite_path()
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        tables = [
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        rows = {
            table: [
                {key: row[key] for key in row.keys()}
                for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
            ]
            for table in tables
        }
        has_sequences = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        sequences = (
            [
                tuple(row)
                for row in db.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
            if has_sequences
            else []
        )
        return {"rows": rows, "sequences": sequences}
    finally:
        db.close()


def restore_sequences(snapshot: dict[str, object]) -> None:
    db = sqlite3.connect(sqlite_path())
    try:
        has_sequences = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if has_sequences:
            db.execute("DELETE FROM sqlite_sequence")
            for name, sequence in snapshot["sequences"]:
                db.execute(
                    "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)",
                    (name, sequence),
                )
            db.commit()
    finally:
        db.close()


def request_headers(token: str) -> dict[str, str]:
    return {
        "Host": "partpilot.example",
        "X-Forwarded-Proto": "https",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def call_tool_payload(
    request_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def structured_tool_call(
    client: TestClient,
    token: str,
    *,
    request_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/mcp",
        headers=request_headers(token),
        json=call_tool_payload(request_id, name, arguments),
        follow_redirects=False,
    )
    if response.status_code != 200:
        fail(f"{name} returned HTTP {response.status_code}: {response.text[:500]}")
    result = response.json().get("result", {})
    if result.get("isError") is True:
        fail(f"{name} returned a tool error: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        fail(f"{name} returned no structured content: {result}")
    return structured


def check_only() -> None:
    from app.mcp.runtime import mcp_registered_tool_names

    names = asyncio.run(mcp_registered_tool_names())
    if names != EXPECTED_TOOL_NAMES:
        fail(f"Unexpected registered MCP tools: {names!r}")
    print(
        "[PASS] MCP workspace registry exposes Project and Reservation "
        "list/detail tools alongside inventory tools"
    )


def full_flow() -> None:
    before = database_snapshot()
    db = SessionLocal()
    client_identifier: str | None = None
    audit_ids: list[int] = []
    original_settings: dict[str, tuple[object, object, object]] = {}
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None:
            fail("MCP workspace smoke requires one existing user")

        for key in (MCP_ENABLED_KEY, MCP_READ_ENABLED_KEY, MCP_WRITE_ENABLED_KEY):
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one_or_none()
            if setting is None:
                fail(f"Required MCP setting is missing: {key}")
            original_settings[key] = (
                copy.deepcopy(setting.value_json),
                setting.value_text,
                setting.updated_at,
            )

        set_app_setting(db, MCP_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_READ_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_WRITE_ENABLED_KEY, False, commit=False)

        registered = register_client(
            db,
            client_name="Patch 471 Workspace Tool Smoke",
            redirect_uris=[REDIRECT],
            token_endpoint_auth_method="none",
            metadata={"fixture": "patch-471-workspace"},
            actor_user_id=user.id,
            commit=False,
        )
        client_identifier = registered.client_id
        grant_consent(
            db,
            user_id=user.id,
            client_id=client_identifier,
            scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        code = issue_authorization_code(
            db,
            client_id=client_identifier,
            user_id=user.id,
            redirect_uri=REDIRECT,
            scopes=[MCP_SCOPE_READ],
            code_challenge=pkce_s256_challenge(VERIFIER),
            code_challenge_method="S256",
            resource_uri=RESOURCE,
            commit=False,
        )
        issued = exchange_authorization_code(
            db,
            code=code.code,
            client_id=client_identifier,
            client_secret=None,
            redirect_uri=REDIRECT,
            code_verifier=VERIFIER,
            resource_uri=RESOURCE,
            commit=False,
        )
        db.commit()

        expected_projects = list_projects(db, limit=3, offset=0)
        expected_reservations = list_reservations(db, limit=3, offset=0)
        if not expected_projects.projects:
            fail("MCP workspace smoke requires one Project")
        if not expected_reservations.reservations:
            fail("MCP workspace smoke requires one Reservation")
        project_id = expected_projects.projects[0].id
        reservation_id = expected_reservations.reservations[0].id
        expected_project = get_project(db, project_id)
        expected_reservation = get_reservation(db, reservation_id)

        from app.main import app

        with TestClient(app, base_url="https://partpilot.example") as client:
            project_list = structured_tool_call(
                client,
                issued.access_token,
                request_id=10,
                name="list_projects",
                arguments={"limit": 3},
            )
            actual_project_ids = [
                row.get("id")
                for row in project_list.get("projects", [])
                if isinstance(row, dict)
            ]
            expected_project_ids = [
                project.id for project in expected_projects.projects
            ]
            if actual_project_ids != expected_project_ids:
                fail(
                    f"list_projects IDs differ: "
                    f"{actual_project_ids} != {expected_project_ids}"
                )
            if project_list.get("total") != expected_projects.total:
                fail("list_projects total differs from the canonical service")

            project_detail = structured_tool_call(
                client,
                issued.access_token,
                request_id=11,
                name="get_project_details",
                arguments={"project_id": project_id},
            )
            if (
                project_detail.get("project")
                != expected_project.model_dump(mode="json")
            ):
                fail("get_project_details differs from the canonical service")

            reservation_list = structured_tool_call(
                client,
                issued.access_token,
                request_id=12,
                name="list_reservations",
                arguments={"limit": 3},
            )
            actual_reservation_ids = [
                row.get("id")
                for row in reservation_list.get("reservations", [])
                if isinstance(row, dict)
            ]
            expected_reservation_ids = [
                reservation.id
                for reservation in expected_reservations.reservations
            ]
            if actual_reservation_ids != expected_reservation_ids:
                fail(
                    f"list_reservations IDs differ: "
                    f"{actual_reservation_ids} != {expected_reservation_ids}"
                )
            if reservation_list.get("total") != expected_reservations.total:
                fail("list_reservations total differs from the canonical service")

            reservation_detail = structured_tool_call(
                client,
                issued.access_token,
                request_id=13,
                name="get_reservation_details",
                arguments={"reservation_id": reservation_id},
            )
            if (
                reservation_detail.get("reservation")
                != expected_reservation.model_dump(mode="json")
            ):
                fail(
                    "get_reservation_details differs from the canonical service"
                )

        audit_check = SessionLocal()
        try:
            tool_audits = [
                row
                for row in audit_check.execute(
                    select(AuditLog)
                    .where(AuditLog.event_type == "mcp.tool_called")
                    .order_by(AuditLog.id.asc())
                ).scalars()
                if isinstance(row.metadata_json, dict)
                and row.metadata_json.get("client_id") == client_identifier
            ]
            expected_names = {
                "list_projects",
                "get_project_details",
                "list_reservations",
                "get_reservation_details",
            }
            if len(tool_audits) != 4:
                fail(
                    f"Expected four MCP workspace tool audits, "
                    f"got {len(tool_audits)}"
                )
            if {
                row.metadata_json.get("tool") for row in tool_audits
            } != expected_names:
                fail("MCP workspace audit tool names are incorrect")
            for row in tool_audits:
                if row.actor_type != "mcp" or row.actor_user_id != user.id:
                    fail("MCP workspace audit actor attribution is incorrect")
                if row.metadata_json.get("success") is not True:
                    fail("Successful MCP workspace call was audited as failed")
                serialized = json.dumps(row.metadata_json, sort_keys=True)
                for secret in (
                    issued.access_token,
                    issued.refresh_token,
                    code.code,
                ):
                    if secret and secret in serialized:
                        fail("MCP workspace audit leaked an OAuth secret")
        finally:
            audit_check.close()

        cleanup = SessionLocal()
        try:
            for key, (value_json, value_text, updated_at) in original_settings.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == key)
                ).scalar_one()
                setting.value_json = copy.deepcopy(value_json)
                setting.value_text = value_text
                setting.updated_at = updated_at

            if client_identifier is not None:
                audit_ids = [
                    row.id
                    for row in cleanup.execute(
                        select(AuditLog).where(
                            AuditLog.event_type.like("mcp.%")
                        )
                    ).scalars()
                    if isinstance(row.metadata_json, dict)
                    and row.metadata_json.get("client_id") == client_identifier
                ]
                from app.models import McpOAuthClient

                client_row = cleanup.execute(
                    select(McpOAuthClient).where(
                        McpOAuthClient.client_id == client_identifier
                    )
                ).scalar_one_or_none()
                if client_row is not None:
                    cleanup.delete(client_row)
            if audit_ids:
                cleanup.query(AuditLog).filter(
                    AuditLog.id.in_(audit_ids)
                ).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()

        restore_sequences(before)
        if database_snapshot() != before:
            fail(
                "MCP workspace tool smoke did not restore the exact database snapshot"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "[PASS] MCP Project and Reservation list/detail tools match canonical "
        "services, remain read-only, write secret-free audits, and clean up exactly"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        check_only()
    else:
        full_flow()


if __name__ == "__main__":
    main()
