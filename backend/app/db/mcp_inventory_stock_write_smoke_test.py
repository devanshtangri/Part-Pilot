from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.constants import SOURCE_MANUAL, SOURCE_MCP
from app.db.session import SessionLocal, engine
from app.db.settings import get_app_setting, set_app_setting
from app.models import AuditLog, McpWriteIntent, Part, PartType, StockMovement, User
from app.services.app_settings import (
    MCP_DIRECT_CLIENTS_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_ENABLED_KEY,
)
from app.services.live_sync import live_sync_broker
from app.services.mcp_direct_auth import DIRECT_AUTH_BEARER_KEY, create_named_direct_client
from app.services.mcp_permissions import DEFAULT_MCP_TOOL_PERMISSIONS, MCP_TOOL_PERMISSIONS_KEY
from app.services.parts import adjust_part_quantity as adjust_part_quantity_service
from app.schemas.parts import PartQuantityAdjustmentRequest

# PARTPILOT:MCP_INVENTORY_STOCK_WRITE_SMOKE:V747
READ_TOOLS = {
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
}
STOCK_TOOL = "adjust_part_quantity"


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP inventory stock-write smoke requires SQLite, got {url!r}")
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
            "params": {"name": STOCK_TOOL, "arguments": arguments},
        },
        follow_redirects=False,
    )
    if response.status_code != 200:
        fail(f"{STOCK_TOOL} returned HTTP {response.status_code}: {response.text[:800]}")
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


def current_stock(part_id: int) -> tuple[int, int]:
    db = SessionLocal()
    try:
        part = db.get(Part, part_id)
        if part is None:
            fail(f"Fixture Part {part_id} disappeared")
        return int(part.total_quantity), int(part.reserved_quantity)
    finally:
        db.close()


def movement_count(part_id: int) -> int:
    db = SessionLocal()
    try:
        return int(
            db.execute(
                select(func.count(StockMovement.id)).where(StockMovement.part_id == part_id)
            ).scalar_one()
        )
    finally:
        db.close()


def business_audit_count(part_id: int) -> int:
    db = SessionLocal()
    try:
        return int(
            db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.event_type == "part.quantity_adjusted",
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
    try:
        db = SessionLocal()
        try:
            revision = db.connection().exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
            if revision != "0019_mcp_inventory_stock_write":
                fail(f"Expected 0019_mcp_inventory_stock_write, got {revision}")
            stored_policy = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
            if (
                not isinstance(stored_policy, dict)
                or set(stored_policy) != set(DEFAULT_MCP_TOOL_PERMISSIONS)
                or any(type(stored_policy[name]) is not bool for name in DEFAULT_MCP_TOOL_PERMISSIONS)
            ):
                fail(f"Malformed copied MCP tool policy: {stored_policy}")

            owner = db.execute(
                select(User)
                .where(User.is_active.is_(True), User.role == "owner")
                .order_by(User.id)
            ).scalars().first()
            if owner is None:
                fail("Stock-write smoke requires one active owner")
            part_type = db.execute(select(PartType).order_by(PartType.id)).scalars().first()
            if part_type is None:
                fail("Stock-write smoke requires an existing part type")

            add_part = Part(
                part_type_id=part_type.id,
                part_number="P747-STOCK-ADD",
                name="Patch 747 stock add",
                total_quantity=20,
                reserved_quantity=0,
                low_stock_enabled=False,
                is_deleted=False,
            )
            floor_part = Part(
                part_type_id=part_type.id,
                part_number="P747-STOCK-FLOOR",
                name="Patch 747 reserved floor",
                total_quantity=10,
                reserved_quantity=6,
                low_stock_enabled=False,
                is_deleted=False,
            )
            drift_part = Part(
                part_type_id=part_type.id,
                part_number="P747-STOCK-DRIFT",
                name="Patch 747 stock drift",
                total_quantity=30,
                reserved_quantity=0,
                low_stock_enabled=False,
                is_deleted=False,
            )
            db.add_all((add_part, floor_part, drift_part))
            db.flush()
            issued = create_named_direct_client(
                db,
                actor_user_id=owner.id,
                name="Patch 747 inventory stock smoke",
                mode=DIRECT_AUTH_BEARER_KEY,
                commit=False,
            )
            client_key = issued.plaintext_key
            owner_id = owner.id
            ids = {
                "add": add_part.id,
                "floor": floor_part.id,
                "drift": drift_part.id,
            }
            set_app_setting(db, "mcp.enabled", True, commit=False)
            set_app_setting(db, "mcp.read_tools_enabled", True, commit=False)
            set_app_setting(db, "mcp.write_tools_enabled", True, commit=False)
            set_app_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, True, commit=False)
            set_app_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False, commit=False)
            policy = dict(DEFAULT_MCP_TOOL_PERMISSIONS)
            policy[STOCK_TOOL] = True
            set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, policy, commit=False)
            db.commit()
        finally:
            db.close()

        from app.main import app
        from app.mcp.runtime import mcp_registered_tool_names
        import asyncio

        registered = set(asyncio.run(mcp_registered_tool_names()))
        if registered != READ_TOOLS | {
            "reserve_project", "consume_reservation", "cancel_reservation", STOCK_TOOL
        }:
            fail(f"Unexpected FastMCP registry: {sorted(registered)}")

        with TestClient(app, base_url="https://partpilot.example") as client:
            expected_visible = READ_TOOLS | {STOCK_TOOL}
            if listed_names(client, client_key, 1) != expected_visible:
                fail("Named direct client did not see exactly six reads plus stock adjustment")

            add_before = current_stock(ids["add"])
            movement_before = movement_count(ids["add"])
            audit_before = business_audit_count(ids["add"])
            live_before = live_sync_broker.state()["revisions"].copy()
            add_preview = structured_success(
                call_tool(
                    client,
                    client_key,
                    10,
                    {
                        "part_id": ids["add"],
                        "operation": "add",
                        "quantity": 5,
                        "idempotency_key": "p747-stock-add-001",
                        "note": "fixture add",
                    },
                ),
                "add preview",
            )
            preview = add_preview.get("preview", {})
            expected_preview = {
                "physical_before": 20,
                "physical_after": 25,
                "reserved_before": 0,
                "reserved_after": 0,
                "available_before": 20,
                "available_after": 25,
                "quantity_delta": 5,
                "operation": "add",
                "movement_type": "restock",
                "reason": "MCP stock addition",
            }
            for key, value in expected_preview.items():
                if preview.get(key) != value:
                    fail(f"Add preview {key} mismatch: {preview.get(key)!r} != {value!r}")
            token = add_preview.get("confirmation_token")
            if not isinstance(token, str) or not token.startswith("pp_mcp_confirm_"):
                fail("Add preview did not return a valid confirmation token")
            if current_stock(ids["add"]) != add_before:
                fail("Add preview mutated inventory")
            if movement_count(ids["add"]) != movement_before:
                fail("Add preview created a stock movement")
            if business_audit_count(ids["add"]) != audit_before:
                fail("Add preview created a business quantity audit")
            if live_sync_broker.state()["revisions"] != live_before:
                fail("Add preview published live invalidation")

            add_done = structured_success(
                call_tool(
                    client,
                    client_key,
                    11,
                    {
                        "part_id": ids["add"],
                        "operation": "add",
                        "quantity": 5,
                        "idempotency_key": "p747-stock-add-001",
                        "note": "fixture add",
                        "confirmation_token": token,
                    },
                ),
                "add confirmation",
            )
            if add_done.get("phase") != "completed" or add_done.get("replayed") is not False:
                fail("Add confirmation result shape is wrong")
            if current_stock(ids["add"]) != (25, 0):
                fail("Add confirmation did not apply exact stock delta")
            if movement_count(ids["add"]) != movement_before + 1:
                fail("Add confirmation did not create exactly one movement")
            if business_audit_count(ids["add"]) != audit_before + 1:
                fail("Add confirmation did not create exactly one business audit")
            live_after_add = live_sync_broker.state()["revisions"].copy()
            for topic, before_value in live_before.items():
                expected = before_value + 1 if topic in {"inventory", "history"} else before_value
                if live_after_add[topic] != expected:
                    fail(f"Add confirmation live revision mismatch for {topic}")

            verify = SessionLocal()
            try:
                movement = verify.execute(
                    select(StockMovement)
                    .where(StockMovement.part_id == ids["add"])
                    .order_by(StockMovement.id.desc())
                ).scalars().first()
                if (
                    movement is None
                    or movement.source != SOURCE_MCP
                    or movement.actor_user_id != owner_id
                    or movement.quantity_delta != 5
                    or movement.reason != "MCP stock addition"
                ):
                    fail("Confirmed add movement MCP attribution is wrong")
                audit = verify.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.event_type == "part.quantity_adjusted",
                        AuditLog.entity_id == ids["add"],
                    )
                    .order_by(AuditLog.id.desc())
                ).scalars().first()
                if (
                    audit is None
                    or audit.actor_type != "mcp"
                    or audit.actor_user_id != owner_id
                    or not isinstance(audit.metadata_json, dict)
                    or audit.metadata_json.get("source") != SOURCE_MCP
                ):
                    fail("Confirmed add business audit MCP attribution is wrong")
            finally:
                verify.close()

            replay = structured_success(
                call_tool(
                    client,
                    client_key,
                    12,
                    {
                        "part_id": ids["add"],
                        "operation": "add",
                        "quantity": 5,
                        "idempotency_key": "p747-stock-add-001",
                        "note": "fixture add",
                        "confirmation_token": token,
                    },
                ),
                "add replay",
            )
            if replay.get("replayed") is not True:
                fail("Confirmed add replay was not marked replayed")
            if current_stock(ids["add"]) != (25, 0):
                fail("Add replay mutated stock twice")
            if movement_count(ids["add"]) != movement_before + 1:
                fail("Add replay created a second movement")
            if business_audit_count(ids["add"]) != audit_before + 1:
                fail("Add replay created a second business audit")
            if live_sync_broker.state()["revisions"] != live_after_add:
                fail("Add replay published a second live invalidation")

            remove_preview = structured_success(
                call_tool(
                    client,
                    client_key,
                    20,
                    {
                        "part_id": ids["add"],
                        "operation": "remove",
                        "quantity": 3,
                        "idempotency_key": "p747-stock-remove1",
                    },
                ),
                "remove preview",
            )
            remove_done = structured_success(
                call_tool(
                    client,
                    client_key,
                    21,
                    {
                        "part_id": ids["add"],
                        "operation": "remove",
                        "quantity": 3,
                        "idempotency_key": "p747-stock-remove1",
                        "confirmation_token": remove_preview["confirmation_token"],
                    },
                ),
                "remove confirmation",
            )
            if remove_done.get("phase") != "completed" or current_stock(ids["add"]) != (22, 0):
                fail("Remove confirmation delta is wrong")

            floor_before = current_stock(ids["floor"])
            floor_movements = movement_count(ids["floor"])
            expect_tool_error(
                call_tool(
                    client,
                    client_key,
                    30,
                    {
                        "part_id": ids["floor"],
                        "operation": "remove",
                        "quantity": 5,
                        "idempotency_key": "p747-stock-floor01",
                    },
                ),
                "reserved floor preview",
            )
            if current_stock(ids["floor"]) != floor_before or movement_count(ids["floor"]) != floor_movements:
                fail("Reserved-floor rejection mutated inventory")

            correction_before = current_stock(ids["add"])
            expect_tool_error(
                call_tool(
                    client,
                    client_key,
                    31,
                    {
                        "part_id": ids["add"],
                        "operation": "correction",
                        "quantity": 2,
                        "idempotency_key": "p747-correct-no-reason",
                    },
                ),
                "correction without reason",
            )
            if current_stock(ids["add"]) != correction_before:
                fail("Invalid correction mutated inventory")

            drift_before = current_stock(ids["drift"])
            drift_preview = structured_success(
                call_tool(
                    client,
                    client_key,
                    40,
                    {
                        "part_id": ids["drift"],
                        "operation": "remove",
                        "quantity": 4,
                        "idempotency_key": "p747-stock-drift01",
                    },
                ),
                "drift preview",
            )
            drift_token = drift_preview["confirmation_token"]
            drift_db = SessionLocal()
            try:
                adjust_part_quantity_service(
                    drift_db,
                    ids["drift"],
                    PartQuantityAdjustmentRequest(operation="add", quantity=1),
                    actor_user_id=owner_id,
                    source=SOURCE_MANUAL,
                    commit=True,
                )
            finally:
                drift_db.close()
            expect_tool_error(
                call_tool(
                    client,
                    client_key,
                    41,
                    {
                        "part_id": ids["drift"],
                        "operation": "remove",
                        "quantity": 4,
                        "idempotency_key": "p747-stock-drift01",
                        "confirmation_token": drift_token,
                    },
                ),
                "state drift confirmation",
            )
            if current_stock(ids["drift"]) != (drift_before[0] + 1, drift_before[1]):
                fail("State-drift rejection performed an MCP stock mutation")

            verify = SessionLocal()
            try:
                intents = verify.execute(
                    select(McpWriteIntent).where(McpWriteIntent.tool_name == STOCK_TOOL)
                ).scalars().all()
                if len(intents) != 3:
                    fail(f"Expected exactly three stock-write intents, got {len(intents)}")
                audits = verify.execute(
                    select(AuditLog).where(AuditLog.actor_type == "mcp")
                ).scalars().all()
                serialized = json.dumps(
                    {
                        "intents": [
                            {
                                "preview": item.preview_json,
                                "result": item.result_json,
                                "digest": item.confirmation_digest,
                            }
                            for item in intents
                        ],
                        "audits": [
                            {
                                "before": row.before_json,
                                "after": row.after_json,
                                "metadata": row.metadata_json,
                            }
                            for row in audits
                        ],
                    },
                    sort_keys=True,
                    default=str,
                )
                for candidate in (
                    token,
                    remove_preview["confirmation_token"],
                    drift_token,
                ):
                    if candidate in serialized:
                        fail("Plaintext confirmation token was persisted or audited")
            finally:
                verify.close()

        print(
            "[PASS] guarded MCP inventory stock adjustment preserves preview/confirm "
            "idempotency, canonical stock floors, drift rejection, MCP attribution, "
            "token secrecy and inventory/history live invalidation"
        )
    finally:
        engine.dispose()
        path.write_bytes(before_bytes)
        if path.read_bytes() != before_bytes:
            fail("MCP inventory stock-write smoke did not restore copied database bytes exactly")


if __name__ == "__main__":
    main()
