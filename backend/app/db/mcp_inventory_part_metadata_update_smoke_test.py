from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import get_app_setting, set_app_setting
from app.models import AuditLog, McpWriteIntent, Part, PartType, PartTypeField, StockMovement, User
from app.schemas.parts import PartUpdateRequest
from app.services.app_settings import MCP_DIRECT_CLIENTS_ENABLED_KEY, MCP_DIRECT_NO_AUTH_ENABLED_KEY
from app.services.live_sync import live_sync_broker
from app.services.mcp_direct_auth import DIRECT_AUTH_BEARER_KEY, create_named_direct_client
from app.services.mcp_permissions import DEFAULT_MCP_TOOL_PERMISSIONS, MCP_TOOL_PERMISSIONS_KEY
from app.services.parts import update_part_metadata as update_part_metadata_service

# PARTPILOT:MCP_INVENTORY_PART_METADATA_UPDATE_SMOKE:V760
READ_TOOLS = {
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
}
EDIT_TOOL = "update_part_metadata"
EXPECTED_HEAD = "0022_mcp_inventory_part_lifecycle"
CLIENT_NAME = "Patch 760 metadata edit smoke"


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP metadata-edit smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def request_headers(key: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": "https://partpilot.example",
        "Authorization": f"Bearer {key}",
    }


def listed_tools(client: TestClient, key: str, request_id: int) -> list[dict]:
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
    return [item for item in tools if isinstance(item, dict)]


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
            "params": {"name": EDIT_TOOL, "arguments": arguments},
        },
        follow_redirects=False,
    )
    if response.status_code != 200:
        fail(f"{EDIT_TOOL} returned HTTP {response.status_code}: {response.text[:800]}")
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
            policy = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
            if (
                not isinstance(policy, dict)
                or set(policy) != set(DEFAULT_MCP_TOOL_PERMISSIONS)
                or len(policy) != 14
                or any(type(value) is not bool for value in policy.values())
            ):
                fail(f"Malformed fourteen-tool copied MCP policy: {policy}")

            owner = db.execute(
                select(User)
                .where(User.is_active.is_(True), User.role == "owner")
                .order_by(User.id)
            ).scalars().first()
            if owner is None:
                fail("Metadata-edit smoke requires one active owner")

            types = list(
                db.execute(
                    select(PartType)
                    .where(PartType.is_active.is_(True))
                    .order_by(PartType.id)
                ).scalars()
            )
            part_type = None
            for candidate in types:
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
                fail("Metadata-edit smoke requires an active type without required fields")

            target = Part(
                part_type_id=part_type.id,
                part_number="P760-MCP-EDIT-TARGET",
                name="Patch 760 original metadata",
                description="Original metadata state",
                package="Original package",
                notes="Original notes",
                total_quantity=9,
                reserved_quantity=2,
                unit_price="1.2500",
                low_stock_enabled=True,
                low_stock_threshold=2,
                is_deleted=False,
            )
            duplicate = Part(
                part_type_id=part_type.id,
                part_number="P760-MCP-EDIT-DUPLICATE",
                name="Patch 760 duplicate-number fixture",
                total_quantity=1,
                reserved_quantity=0,
                low_stock_enabled=False,
                is_deleted=False,
            )
            db.add_all([target, duplicate])
            db.flush()
            target_id = target.id
            duplicate_number = duplicate.part_number
            owner_id = owner.id
            part_type_id = part_type.id

            issued = create_named_direct_client(
                db,
                actor_user_id=owner.id,
                name=CLIENT_NAME,
                mode=DIRECT_AUTH_BEARER_KEY,
                commit=False,
            )
            client_key = issued.plaintext_key
            direct_id = issued.record.id
            set_app_setting(db, "mcp.enabled", True, commit=False)
            set_app_setting(db, "mcp.read_tools_enabled", True, commit=False)
            set_app_setting(db, "mcp.write_tools_enabled", True, commit=False)
            set_app_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, True, commit=False)
            set_app_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False, commit=False)
            fixture_policy = dict(DEFAULT_MCP_TOOL_PERMISSIONS)
            for name in fixture_policy:
                fixture_policy[name] = name in READ_TOOLS or name == EDIT_TOOL
            set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, fixture_policy, commit=False)
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
            tools = listed_tools(client, client_key, 1)
            names = {item.get("name") for item in tools}
            if names != READ_TOOLS | {EDIT_TOOL}:
                fail(f"Named direct client did not see six reads plus metadata edit: {names}")
            edit_schema = next(item for item in tools if item.get("name") == EDIT_TOOL).get("inputSchema")
            required = set(edit_schema.get("required", [])) if isinstance(edit_schema, dict) else set()
            must_be_explicit = {
                "part_id",
                "part_type_id",
                "manufacturer_id",
                "location_id",
                "part_number",
                "name",
                "description",
                "package",
                "notes",
                "unit_price",
                "purchase_link",
                "low_stock_enabled",
                "low_stock_threshold",
                "field_values",
                "idempotency_key",
            }
            if not must_be_explicit.issubset(required) or "confirmation_token" in required:
                fail(f"Metadata edit schema does not require the complete replacement payload: {required}")

            update_args: dict[str, object] = {
                "part_id": target_id,
                "part_type_id": part_type_id,
                "manufacturer_id": None,
                "location_id": None,
                "part_number": "P760-MCP-EDIT-UPDATED",
                "name": "Patch 760 updated metadata",
                "description": "Updated through guarded MCP metadata edit",
                "package": "Updated package",
                "notes": "Updated notes",
                "unit_price": "2.5000",
                "purchase_link": "https://example.com/p760",
                "low_stock_enabled": False,
                "low_stock_threshold": None,
                "field_values": [],
                "idempotency_key": "p760-metadata-update-001",
            }
            movement_before = 0
            audit_before = 0
            verify = SessionLocal()
            try:
                movement_before = int(
                    verify.execute(
                        select(func.count(StockMovement.id)).where(StockMovement.part_id == target_id)
                    ).scalar_one()
                )
                audit_before = int(
                    verify.execute(
                        select(func.count(AuditLog.id)).where(
                            AuditLog.event_type == "part.metadata_updated",
                            AuditLog.entity_id == target_id,
                        )
                    ).scalar_one()
                )
            finally:
                verify.close()
            live_before = live_sync_broker.state()["revisions"].copy()

            preview = structured_success(call_tool(client, client_key, 10, update_args), "metadata preview")
            token = preview.get("confirmation_token")
            exact = preview.get("preview", {})
            if (
                preview.get("phase") != "preview"
                or not isinstance(token, str)
                or not token.startswith("pp_mcp_confirm_")
                or exact.get("before_metadata", {}).get("name") != "Patch 760 original metadata"
                or exact.get("proposed_metadata", {}).get("name") != "Patch 760 updated metadata"
                or exact.get("part_number_available") is not True
                or "name" not in exact.get("changed_fields", [])
            ):
                fail(f"Metadata preview is incomplete or wrong: {preview}")

            verify = SessionLocal()
            try:
                row = verify.get(Part, target_id)
                if row is None or row.name != "Patch 760 original metadata" or row.total_quantity != 9 or row.reserved_quantity != 2:
                    fail("Metadata preview mutated the target part")
            finally:
                verify.close()
            if live_sync_broker.state()["revisions"] != live_before:
                fail("Metadata preview published live invalidation")

            completed = structured_success(
                call_tool(client, client_key, 11, {**update_args, "confirmation_token": token}),
                "metadata confirmation",
            )
            part = completed.get("part", {})
            if (
                completed.get("phase") != "completed"
                or completed.get("replayed") is not False
                or part.get("name") != "Patch 760 updated metadata"
                or part.get("total_quantity") != 9
                or part.get("reserved_quantity") != 2
            ):
                fail(f"Metadata confirmation result is wrong: {completed}")

            verify = SessionLocal()
            try:
                movement_after = int(
                    verify.execute(
                        select(func.count(StockMovement.id)).where(StockMovement.part_id == target_id)
                    ).scalar_one()
                )
                audits = list(
                    verify.execute(
                        select(AuditLog).where(
                            AuditLog.event_type == "part.metadata_updated",
                            AuditLog.entity_id == target_id,
                        ).order_by(AuditLog.id)
                    ).scalars()
                )
                if movement_after != movement_before:
                    fail("Metadata edit created a stock movement")
                if len(audits) != audit_before + 1:
                    fail("Metadata confirmation did not create exactly one business audit")
                audit = audits[-1]
                if (
                    audit.actor_type != "mcp"
                    or audit.actor_user_id != owner_id
                    or not isinstance(audit.metadata_json, dict)
                    or audit.metadata_json.get("mcp_client_name") != CLIENT_NAME
                    or audit.before_json.get("name") != "Patch 760 original metadata"
                    or audit.after_json.get("name") != "Patch 760 updated metadata"
                    or "total_quantity" in audit.before_json
                    or "reserved_quantity" in audit.after_json
                ):
                    fail(f"Metadata business audit attribution/snapshot is wrong: {audit.metadata_json}")
            finally:
                verify.close()

            live_after = live_sync_broker.state()["revisions"].copy()
            for topic, before_value in live_before.items():
                expected = before_value + 1 if topic in {"inventory", "history"} else before_value
                if live_after[topic] != expected:
                    fail(f"Metadata confirmation live revision mismatch for {topic}")

            replay = structured_success(
                call_tool(client, client_key, 12, {**update_args, "confirmation_token": token}),
                "metadata replay",
            )
            if replay.get("replayed") is not True:
                fail("Completed metadata replay was not marked replayed")
            if live_sync_broker.state()["revisions"] != live_after:
                fail("Metadata replay published duplicate live invalidation")

            changed_args = dict(update_args)
            changed_args["description"] = "Changed argument must fail"
            expect_tool_error(call_tool(client, client_key, 13, changed_args), "changed metadata arguments")

            duplicate_args = {**update_args, "part_number": duplicate_number, "idempotency_key": "p760-duplicate-001"}
            expect_tool_error(call_tool(client, client_key, 14, duplicate_args), "duplicate part number")

            type_args = {**update_args, "part_type_id": part_type_id + 999999, "idempotency_key": "p760-type-change-01"}
            expect_tool_error(call_tool(client, client_key, 15, type_args), "part type change")

            drift_args = {
                **update_args,
                "name": "Patch 760 post-drift desired metadata",
                "idempotency_key": "p760-metadata-drift-01",
            }
            drift_preview = structured_success(call_tool(client, client_key, 20, drift_args), "metadata drift preview")
            drift_token = drift_preview.get("confirmation_token")
            drift_db = SessionLocal()
            try:
                drift_payload = PartUpdateRequest(
                    part_type_id=part_type_id,
                    manufacturer_id=None,
                    location_id=None,
                    part_number="P760-MCP-EDIT-UPDATED",
                    name="Patch 760 concurrent metadata change",
                    description="Concurrent change after MCP preview",
                    package="Updated package",
                    notes="Updated notes",
                    unit_price="2.5000",
                    purchase_link="https://example.com/p760",
                    low_stock_enabled=False,
                    low_stock_threshold=None,
                    field_values=[],
                )
                update_part_metadata_service(
                    drift_db,
                    target_id,
                    drift_payload,
                    actor_user_id=owner_id,
                    commit=True,
                )
            finally:
                drift_db.close()
            expect_tool_error(
                call_tool(client, client_key, 21, {**drift_args, "confirmation_token": drift_token}),
                "metadata state drift",
            )
            verify = SessionLocal()
            try:
                target_row = verify.get(Part, target_id)
                if target_row is None or target_row.name != "Patch 760 concurrent metadata change":
                    fail("State-drift rejection overwrote the concurrent metadata change")
                if target_row.total_quantity != 9 or target_row.reserved_quantity != 2:
                    fail("Metadata drift flow changed stock quantities")
                if direct_id is None:
                    fail("Metadata-edit direct-client id is unavailable")
                intents = list(
                    verify.execute(
                        select(McpWriteIntent).where(
                            McpWriteIntent.tool_name == EDIT_TOOL,
                            McpWriteIntent.principal_key == f"direct:{direct_id}",
                        )
                    ).scalars()
                )
                fixture_keys = {"p760-metadata-update-001", "p760-metadata-drift-01"}
                owned = [item for item in intents if item.idempotency_key in fixture_keys]
                if len(owned) != 2:
                    fail(f"Expected exactly two fixture metadata intents, got {len(owned)}")
                serialized = json.dumps(
                    [
                        {
                            "preview": item.preview_json,
                            "result": item.result_json,
                            "digest": item.confirmation_digest,
                        }
                        for item in owned
                    ],
                    sort_keys=True,
                    default=str,
                )
                for candidate in (token, drift_token):
                    if candidate and candidate in serialized:
                        fail("Plaintext metadata confirmation token was persisted")
            finally:
                verify.close()

        print(
            "[PASS] guarded MCP inventory metadata editing requires an explicit full replacement, "
            "preserves stock, previews exact before/after state, rejects duplicate/type/drift changes, "
            "replays idempotently, records MCP client attribution and keeps confirmation tokens secret"
        )
    finally:
        engine.dispose()
        path.write_bytes(before_bytes)
        if path.read_bytes() != before_bytes:
            fail("Metadata-edit smoke did not restore the copied database bytes exactly")


if __name__ == "__main__":
    main()
