from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import get_app_setting, set_app_setting
from app.models import AuditLog, McpWriteIntent, Part, PartType, PartTypeField, User
from app.services.app_settings import (
    MCP_DIRECT_CLIENTS_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_ENABLED_KEY,
)
from app.services.live_sync import live_sync_broker
from app.services.mcp_direct_auth import DIRECT_AUTH_BEARER_KEY, create_named_direct_client
from app.services.mcp_permissions import DEFAULT_MCP_TOOL_PERMISSIONS, MCP_TOOL_PERMISSIONS_KEY

# PARTPILOT:MCP_INVENTORY_PART_CREATE_SMOKE:V755
READ_TOOLS = {
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
}
CREATE_TOOL = "create_part"
EXPECTED_HEAD = "0021_mcp_inventory_part_metadata_update"


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP inventory part-create smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def request_headers(key: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": "https://partpilot.example",
        "Authorization": f"Bearer {key}",
    }


def listed_names(client: TestClient, key: str, request_id: int) -> set[str]:
    response = client.post(
        "/mcp",
        headers=request_headers(key),
        json={"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
        follow_redirects=False,
    )
    if response.status_code != 200:
        fail(f"tools/list returned {response.status_code}: {response.text[:800]}")
    tools = response.json().get("result", {}).get("tools")
    if not isinstance(tools, list):
        fail("tools/list returned no tools array")
    return {
        item.get("name")
        for item in tools
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def call_tool(
    client: TestClient,
    key: str,
    request_id: int,
    arguments: dict[str, object],
) -> dict:
    response = client.post(
        "/mcp",
        headers=request_headers(key),
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": CREATE_TOOL, "arguments": arguments},
        },
        follow_redirects=False,
    )
    if response.status_code != 200:
        fail(f"{CREATE_TOOL} returned HTTP {response.status_code}: {response.text[:800]}")
    return response.json().get("result", {})


def structured_success(result: dict, label: str) -> dict:
    if result.get("isError") is True:
        fail(f"{label} unexpectedly failed: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        fail(f"{label} returned no structured content: {result}")
    return structured


def expect_tool_error(result: dict, label: str) -> None:
    if result.get("isError") is not True:
        fail(f"{label} should have failed closed: {result}")


def part_ids(part_number: str) -> list[int]:
    db = SessionLocal()
    try:
        return list(
            db.execute(
                select(Part.id).where(Part.part_number == part_number).order_by(Part.id)
            ).scalars()
        )
    finally:
        db.close()


def created_audit_count(part_id: int) -> int:
    db = SessionLocal()
    try:
        return int(
            db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.event_type == "part.created",
                    AuditLog.entity_type == "part",
                    AuditLog.entity_id == part_id,
                )
            ).scalar_one()
        )
    finally:
        db.close()


def main() -> None:
    path = database_path()
    before_bytes = path.read_bytes()
    direct_id: int | None = None
    try:
        db = SessionLocal()
        try:
            revision = db.connection().exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
            if revision != EXPECTED_HEAD:
                fail(f"Expected {EXPECTED_HEAD}, got {revision}")
            stored_policy = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
            if (
                not isinstance(stored_policy, dict)
                or set(stored_policy) != set(DEFAULT_MCP_TOOL_PERMISSIONS)
                or any(
                    type(stored_policy[name]) is not bool
                    for name in DEFAULT_MCP_TOOL_PERMISSIONS
                )
            ):
                fail(f"Malformed copied MCP tool policy: {stored_policy}")
            if len(DEFAULT_MCP_TOOL_PERMISSIONS) != 12 or CREATE_TOOL not in DEFAULT_MCP_TOOL_PERMISSIONS:
                fail("Expected canonical six-read plus six-write tool policy")

            owner = db.execute(
                select(User)
                .where(User.is_active.is_(True), User.role == "owner")
                .order_by(User.id)
            ).scalars().first()
            if owner is None:
                fail("Part-create smoke requires one active owner")

            candidates = list(
                db.execute(
                    select(PartType)
                    .where(PartType.is_active.is_(True))
                    .order_by(PartType.id)
                ).scalars()
            )
            part_type = None
            for candidate in candidates:
                required = int(
                    db.execute(
                        select(func.count(PartTypeField.id)).where(
                            PartTypeField.part_type_id == candidate.id,
                            PartTypeField.is_required.is_(True),
                        )
                    ).scalar_one()
                )
                if required == 0:
                    part_type = candidate
                    break
            if part_type is None:
                fail("Part-create smoke requires one active type without required fields")

            issued = create_named_direct_client(
                db,
                actor_user_id=owner.id,
                name="Patch 755 inventory create smoke",
                mode=DIRECT_AUTH_BEARER_KEY,
                commit=False,
            )
            client_key = issued.plaintext_key
            direct_id = issued.record.id
            owner_id = owner.id
            part_type_id = part_type.id
            set_app_setting(db, "mcp.enabled", True, commit=False)
            set_app_setting(db, "mcp.read_tools_enabled", True, commit=False)
            set_app_setting(db, "mcp.write_tools_enabled", True, commit=False)
            set_app_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, True, commit=False)
            set_app_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False, commit=False)
            policy = dict(DEFAULT_MCP_TOOL_PERMISSIONS)
            for name in policy:
                policy[name] = name in READ_TOOLS or name == CREATE_TOOL
            set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, policy, commit=False)
            db.commit()
        finally:
            db.close()

        from app.main import app
        from app.mcp.runtime import mcp_registered_tool_names
        import asyncio

        registered = set(asyncio.run(mcp_registered_tool_names()))
        if registered != set(DEFAULT_MCP_TOOL_PERMISSIONS):
            fail(f"Unexpected FastMCP registry: {sorted(registered)}")

        with TestClient(app, base_url="https://partpilot.example") as client:
            expected_visible = READ_TOOLS | {CREATE_TOOL}
            if listed_names(client, client_key, 1) != expected_visible:
                fail("Named direct client did not see exactly six reads plus create_part")

            part_number = "P755-MCP-CREATE"
            if part_ids(part_number):
                fail("Patch 755 create fixture already exists")
            live_before = live_sync_broker.state()["revisions"].copy()
            create_args = {
                "part_type_id": part_type_id,
                "part_number": part_number,
                "name": "Patch 755 MCP created part",
                "total_quantity": 7,
                "low_stock_enabled": True,
                "low_stock_threshold": 2,
                "idempotency_key": "p755-create-part-001",
            }
            preview = structured_success(
                call_tool(client, client_key, 10, create_args),
                "create preview",
            )
            if preview.get("phase") != "preview":
                fail("Create preview phase is wrong")
            token = preview.get("confirmation_token")
            if not isinstance(token, str) or not token.startswith("pp_mcp_confirm_"):
                fail("Create preview did not return a valid confirmation token")
            exact = preview.get("preview", {})
            if exact.get("part_number_available") is not True:
                fail("Create preview did not prove part number availability")
            normalized = exact.get("normalized_payload", {})
            if normalized.get("part_number") != part_number or normalized.get("total_quantity") != 7:
                fail("Create preview normalized payload is wrong")
            if part_ids(part_number):
                fail("Create preview mutated inventory")
            if live_sync_broker.state()["revisions"] != live_before:
                fail("Create preview published live invalidation")

            confirm_args = {**create_args, "confirmation_token": token}
            completed = structured_success(
                call_tool(client, client_key, 11, confirm_args),
                "create confirmation",
            )
            if completed.get("phase") != "completed" or completed.get("replayed") is not False:
                fail("Create confirmation result shape is wrong")
            part = completed.get("part")
            if not isinstance(part, dict) or part.get("part_number") != part_number:
                fail("Create confirmation did not return the created part")
            part_id = part.get("id")
            if type(part_id) is not int or part.get("total_quantity") != 7 or part.get("reserved_quantity") != 0:
                fail("Created part stock state is wrong")
            if part_ids(part_number) != [part_id] or created_audit_count(part_id) != 1:
                fail("Create confirmation did not persist exactly one part/audit")

            verify = SessionLocal()
            try:
                audit = verify.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.event_type == "part.created",
                        AuditLog.entity_id == part_id,
                    )
                    .order_by(AuditLog.id.desc())
                ).scalars().first()
                if (
                    audit is None
                    or audit.actor_type != "mcp"
                    or audit.actor_user_id != owner_id
                    or not isinstance(audit.metadata_json, dict)
                    or audit.metadata_json.get("mcp_client_name")
                    != "Patch 755 inventory create smoke"
                ):
                    fail("Created-part business audit MCP attribution is wrong")
                from app.services.history import list_history
                history = list_history(
                    verify,
                    kind="audit",
                    event_type="part.created",
                    actor_type="mcp",
                    limit=100,
                )
                entry = next(
                    (item for item in history.entries if item.entity_id == part_id),
                    None,
                )
                if (
                    entry is None
                    or entry.actor_display_name != "Patch 755 inventory create smoke"
                    or entry.actor_user_id != owner_id
                ):
                    fail("Created-part History MCP client attribution is wrong")
            finally:
                verify.close()

            live_after = live_sync_broker.state()["revisions"].copy()
            for topic, before_value in live_before.items():
                expected = before_value + 1 if topic in {"inventory", "history"} else before_value
                if live_after[topic] != expected:
                    fail(f"Create confirmation live revision mismatch for {topic}")

            replay = structured_success(
                call_tool(client, client_key, 12, confirm_args),
                "create replay",
            )
            if replay.get("replayed") is not True:
                fail("Completed create replay was not marked replayed")
            if part_ids(part_number) != [part_id] or created_audit_count(part_id) != 1:
                fail("Create replay duplicated inventory/audit")
            if live_sync_broker.state()["revisions"] != live_after:
                fail("Create replay published duplicate live invalidation")

            changed_args = dict(create_args)
            changed_args["name"] = "Changed arguments must fail"
            expect_tool_error(
                call_tool(client, client_key, 13, changed_args),
                "changed arguments with completed idempotency key",
            )
            if part_ids(part_number) != [part_id]:
                fail("Changed-argument rejection mutated inventory")

            drift_number = "P755-MCP-DRIFT"
            if part_ids(drift_number):
                fail("Patch 755 drift fixture already exists")
            drift_args = {
                "part_type_id": part_type_id,
                "part_number": drift_number,
                "name": "Patch 755 drift candidate",
                "total_quantity": 1,
                "idempotency_key": "p755-create-drift-01",
            }
            drift_preview = structured_success(
                call_tool(client, client_key, 20, drift_args),
                "drift preview",
            )
            drift_token = drift_preview.get("confirmation_token")
            drift_db = SessionLocal()
            try:
                competing = Part(
                    part_type_id=part_type_id,
                    part_number=drift_number,
                    name="Patch 755 competing part",
                    total_quantity=0,
                    reserved_quantity=0,
                    low_stock_enabled=False,
                    is_deleted=False,
                )
                drift_db.add(competing)
                drift_db.commit()
                competing_id = competing.id
            finally:
                drift_db.close()
            expect_tool_error(
                call_tool(
                    client,
                    client_key,
                    21,
                    {**drift_args, "confirmation_token": drift_token},
                ),
                "create state drift confirmation",
            )
            if part_ids(drift_number) != [competing_id]:
                fail("State-drift rejection created a duplicate part")

            verify = SessionLocal()
            try:
                if direct_id is None:
                    fail("Create smoke direct-client id is unavailable")
                intents = verify.execute(
                    select(McpWriteIntent).where(
                        McpWriteIntent.tool_name == CREATE_TOOL,
                        McpWriteIntent.principal_key == f"direct:{direct_id}",
                    )
                ).scalars().all()
                if len(intents) != 2:
                    fail(f"Expected exactly two create write intents, got {len(intents)}")
                serialized = json.dumps(
                    [
                        {
                            "preview": item.preview_json,
                            "result": item.result_json,
                            "digest": item.confirmation_digest,
                        }
                        for item in intents
                    ],
                    sort_keys=True,
                    default=str,
                )
                for candidate in (token, drift_token):
                    if candidate in serialized:
                        fail("Plaintext create confirmation token was persisted")
            finally:
                verify.close()

        print(
            "[PASS] guarded MCP inventory part creation preserves canonical validation, "
            "preview/confirm idempotency, dependency drift rejection, MCP attribution, "
            "token secrecy and inventory/history live invalidation"
        )
    finally:
        engine.dispose()
        path.write_bytes(before_bytes)
        if path.read_bytes() != before_bytes:
            fail("MCP inventory part-create smoke did not restore copied database bytes exactly")


if __name__ == "__main__":
    main()
