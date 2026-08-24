from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.constants import SOURCE_MCP
from app.db.session import SessionLocal, engine
from app.db.settings import get_app_setting, set_app_setting
from app.models import (
    AuditLog,
    McpDirectAuth,
    McpWriteIntent,
    Part,
    PartType,
    Project,
    ProjectItem,
    Reservation,
    StockMovement,
    User,
)
from app.services.app_settings import (
    MCP_DIRECT_CLIENTS_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_ENABLED_KEY,
)
from app.services.live_sync import live_sync_broker
from app.services.mcp_direct_auth import DIRECT_AUTH_BEARER_KEY, create_named_direct_client
from app.services.mcp_permissions import (
    DEFAULT_MCP_TOOL_PERMISSIONS,
    MCP_TOOL_PERMISSIONS_KEY,
    McpToolPermissionDeniedError,
    authorize_mcp_tool,
)
from app.services.projects import reserve_project as reserve_project_service

# PARTPILOT:MCP_WRITE_TOOLS_SMOKE:V734
READ_TOOLS = {
    "search_parts", "get_part_details", "list_projects", "get_project_details",
    "list_reservations", "get_reservation_details",
}
WRITE_TOOLS = {"reserve_project", "consume_reservation", "cancel_reservation"}
ALL_TOOLS = READ_TOOLS | WRITE_TOOLS


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP write smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def request_headers(key: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": "https://partpilot.example",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def tools_payload(request_id: int) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}


def call_payload(request_id: int, name: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def listed_names(client: TestClient, key: str | None, request_id: int) -> set[str]:
    response = client.post(
        "/mcp", headers=request_headers(key), json=tools_payload(request_id), follow_redirects=False
    )
    if response.status_code != 200:
        fail(f"tools/list returned {response.status_code}: {response.text[:800]}")
    tools = response.json().get("result", {}).get("tools")
    if not isinstance(tools, list):
        fail("tools/list returned no tools array")
    return {item.get("name") for item in tools if isinstance(item, dict) and isinstance(item.get("name"), str)}


def call_tool(client: TestClient, key: str, request_id: int, name: str, arguments: dict[str, object]) -> dict:
    response = client.post(
        "/mcp", headers=request_headers(key), json=call_payload(request_id, name, arguments), follow_redirects=False
    )
    if response.status_code != 200:
        fail(f"{name} returned HTTP {response.status_code}: {response.text[:800]}")
    return response.json().get("result", {})


def structured_success(result: dict, label: str) -> dict:
    if result.get("isError") is True:
        fail(f"{label} unexpectedly failed: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        fail(f"{label} returned no structured content")
    return structured


def expect_tool_error(result: dict, label: str) -> None:
    if result.get("isError") is not True:
        fail(f"{label} should have failed closed: {result}")


def create_draft_project(db, part_type_id: int, suffix: str) -> tuple[Project, Part]:
    part = Part(
        part_type_id=part_type_id,
        part_number=f"P734-{suffix}",
        name=f"Patch 734 {suffix}",
        total_quantity=40,
        reserved_quantity=0,
        low_stock_enabled=False,
        is_deleted=False,
    )
    db.add(part); db.flush()
    project = Project(
        name=f"Patch 734 {suffix} Project",
        status="draft",
        created_by="system",
    )
    db.add(project); db.flush()
    db.add(ProjectItem(project_id=project.id, part_id=part.id, quantity=7))
    db.flush()
    return project, part


def current_stock(part_id: int) -> tuple[int, int]:
    db = SessionLocal()
    try:
        part = db.get(Part, part_id)
        if part is None:
            fail("Fixture part disappeared")
        return int(part.total_quantity), int(part.reserved_quantity)
    finally:
        db.close()


def reservation_for_project(project_id: int) -> int:
    db = SessionLocal()
    try:
        row = db.execute(select(Reservation.id).where(Reservation.project_id == project_id)).scalar_one_or_none()
        if row is None:
            fail("Expected linked Reservation was not created")
        return int(row)
    finally:
        db.close()


def main() -> None:
    path = database_path()
    before_bytes = path.read_bytes()
    client_key: str | None = None
    owner_id: int | None = None
    try:
        db = SessionLocal()
        try:
            revision = db.connection().exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            if revision != "0018_mcp_write_intents":
                fail(f"Expected 0018_mcp_write_intents, got {revision}")
            stored_policy = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
            if (
                not isinstance(stored_policy, dict)
                or set(stored_policy) != set(DEFAULT_MCP_TOOL_PERMISSIONS)
                or any(type(stored_policy[name]) is not bool for name in DEFAULT_MCP_TOOL_PERMISSIONS)
            ):
                fail(f"Malformed copied MCP tool policy: {stored_policy}")
            if db.query(McpWriteIntent).count() != 0:
                fail("Copied production DB unexpectedly contains MCP write intents")

            owner = db.execute(
                select(User).where(User.is_active.is_(True), User.role == "owner").order_by(User.id)
            ).scalars().first()
            if owner is None:
                fail("Write smoke requires one active owner")
            owner_id = owner.id
            part_type = db.execute(select(PartType).order_by(PartType.id)).scalars().first()
            if part_type is None:
                fail("Write smoke requires an existing part type")

            reserve_project, reserve_part = create_draft_project(db, part_type.id, "RESERVE")
            wrong_project, wrong_part = create_draft_project(db, part_type.id, "WRONG")
            drift_project, drift_part = create_draft_project(db, part_type.id, "DRIFT")
            consume_project, consume_part = create_draft_project(db, part_type.id, "CONSUME")
            cancel_project, cancel_part = create_draft_project(db, part_type.id, "CANCEL")

            # Pre-reserve consume/cancel fixtures through canonical service; these are setup only.
            consume_reserved = reserve_project_service(db, consume_project.id, actor_user_id=owner.id, commit=False)
            cancel_reserved = reserve_project_service(db, cancel_project.id, actor_user_id=owner.id, commit=False)
            db.flush()
            consume_reservation_id = db.execute(select(Reservation.id).where(Reservation.project_id == consume_project.id)).scalar_one()
            cancel_reservation_id = db.execute(select(Reservation.id).where(Reservation.project_id == cancel_project.id)).scalar_one()

            issued = create_named_direct_client(
                db,
                actor_user_id=owner.id,
                name="Patch 734 write smoke",
                mode=DIRECT_AUTH_BEARER_KEY,
                commit=False,
            )
            client_key = issued.plaintext_key
            direct = issued.record
            set_app_setting(db, "mcp.enabled", True, commit=False)
            set_app_setting(db, "mcp.read_tools_enabled", True, commit=False)
            set_app_setting(db, "mcp.write_tools_enabled", True, commit=False)
            set_app_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, True, commit=False)
            set_app_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False, commit=False)
            # Live MCP policy is mutable. Force only this copied smoke fixture to the
            # canonical write-off baseline before the first transport assertion.
            set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, dict(DEFAULT_MCP_TOOL_PERMISSIONS), commit=False)
            db.commit()
            fixture_ids = {
                "reserve_project": reserve_project.id, "reserve_part": reserve_part.id,
                "wrong_project": wrong_project.id, "wrong_part": wrong_part.id,
                "drift_project": drift_project.id, "drift_part": drift_part.id,
                "consume_project": consume_project.id, "consume_part": consume_part.id,
                "consume_reservation": int(consume_reservation_id),
                "cancel_project": cancel_project.id, "cancel_part": cancel_part.id,
                "cancel_reservation": int(cancel_reservation_id), "direct": direct.id,
            }
        finally:
            db.close()

        from app.main import app
        from app.mcp.runtime import mcp_registered_tool_names
        import asyncio
        if set(asyncio.run(mcp_registered_tool_names())) != ALL_TOOLS:
            fail("FastMCP registry does not contain six read plus three write tools")

        with TestClient(app, base_url="https://partpilot.example") as client:
            if listed_names(client, client_key, 1) != READ_TOOLS:
                fail("Globally-off write tools were visible to a named direct client")

            setup = SessionLocal()
            try:
                policy = dict(DEFAULT_MCP_TOOL_PERMISSIONS)
                for name in WRITE_TOOLS:
                    policy[name] = True
                set_app_setting(setup, MCP_TOOL_PERMISSIONS_KEY, policy, commit=False)
                setup.commit()
            finally:
                setup.close()
            if listed_names(client, client_key, 2) != ALL_TOOLS:
                fail("Eligible named direct client did not receive all enabled write tools")

            # Per-client deny takes immediate effect.
            setup = SessionLocal()
            try:
                direct = setup.get(McpDirectAuth, fixture_ids["direct"])
                direct.denied_tools_json = ["cancel_reservation"]
                setup.commit()
            finally:
                setup.close()
            names = listed_names(client, client_key, 3)
            if "cancel_reservation" in names or not {"reserve_project", "consume_reservation"}.issubset(names):
                fail("Named-client write deny did not affect tools/list immediately")
            setup = SessionLocal()
            try:
                direct = setup.get(McpDirectAuth, fixture_ids["direct"])
                direct.denied_tools_json = []
                setup.commit()
            finally:
                setup.close()

            # Backing viewer authority cannot receive any write tool.
            setup = SessionLocal()
            try:
                user = setup.get(User, owner_id); user.role = "viewer"; setup.commit()
            finally:
                setup.close()
            if listed_names(client, client_key, 4) != READ_TOOLS:
                fail("Viewer-backed direct client received write access")
            setup = SessionLocal()
            try:
                user = setup.get(User, owner_id); user.role = "owner"; setup.commit()
            finally:
                setup.close()

            # No-auth is permanently read-only even if a malformed principal falsely carries mcp:write.
            setup = SessionLocal()
            try:
                noauth_principal = {
                    "auth_method": "direct_no_auth", "actor_type": "mcp",
                    "actor_user_id": None, "scopes": ["mcp:read", "mcp:write"],
                    "resource_uri": "https://partpilot.example/mcp",
                    "direct_auth_id": None, "direct_client_name": "No authentication",
                    "client_ip": "203.0.113.250",
                }
                try:
                    authorize_mcp_tool(setup, noauth_principal, "reserve_project")
                except McpToolPermissionDeniedError:
                    pass
                else:
                    fail("No-auth MCP received write authorization")
            finally:
                setup.close()

            # Wrong confirmation token fails without mutation.
            before_wrong = current_stock(fixture_ids["wrong_part"])
            preview = structured_success(call_tool(client, client_key, 10, "reserve_project", {
                "project_id": fixture_ids["wrong_project"], "idempotency_key": "p734-wrong-token-01"
            }), "wrong-token preview")
            token = preview.get("confirmation_token")
            if not isinstance(token, str) or not token.startswith("pp_mcp_confirm_"):
                fail("Preview did not return a bounded confirmation token")
            if current_stock(fixture_ids["wrong_part"]) != before_wrong:
                fail("Preview mutated stock")
            expect_tool_error(call_tool(client, client_key, 11, "reserve_project", {
                "project_id": fixture_ids["wrong_project"], "idempotency_key": "p734-wrong-token-01",
                "confirmation_token": "pp_mcp_confirm_wrong"
            }), "wrong confirmation token")
            if current_stock(fixture_ids["wrong_part"]) != before_wrong:
                fail("Wrong confirmation token mutated stock")

            # State drift after preview fails closed.
            drift_before = current_stock(fixture_ids["drift_part"])
            drift_preview = structured_success(call_tool(client, client_key, 12, "reserve_project", {
                "project_id": fixture_ids["drift_project"], "idempotency_key": "p734-state-drift-01"
            }), "drift preview")
            drift_token = drift_preview["confirmation_token"]
            drift_db = SessionLocal()
            try:
                part = drift_db.get(Part, fixture_ids["drift_part"]); part.total_quantity += 1; drift_db.commit()
            finally:
                drift_db.close()
            expect_tool_error(call_tool(client, client_key, 13, "reserve_project", {
                "project_id": fixture_ids["drift_project"], "idempotency_key": "p734-state-drift-01",
                "confirmation_token": drift_token
            }), "state drift confirmation")
            if current_stock(fixture_ids["drift_part"])[1] != drift_before[1]:
                fail("State-drift rejection changed reserved quantity")

            # Changed arguments with the same idempotency key are rejected.
            arg_preview = structured_success(call_tool(client, client_key, 14, "reserve_project", {
                "project_id": fixture_ids["reserve_project"], "idempotency_key": "p734-arg-lock-001"
            }), "argument-lock preview")
            expect_tool_error(call_tool(client, client_key, 15, "reserve_project", {
                "project_id": fixture_ids["wrong_project"], "idempotency_key": "p734-arg-lock-001"
            }), "changed arguments")

            # Valid reserve: preview no event/no mutation, confirm exact once, replay no second mutation.
            reserve_before = current_stock(fixture_ids["reserve_part"])
            live_before = live_sync_broker.state()["revisions"].copy()
            reserve_preview = structured_success(call_tool(client, client_key, 20, "reserve_project", {
                "project_id": fixture_ids["reserve_project"], "idempotency_key": "p734-reserve-valid-01"
            }), "reserve preview")
            if live_sync_broker.state()["revisions"] != live_before:
                fail("Reserve preview published live-sync invalidation")
            if current_stock(fixture_ids["reserve_part"]) != reserve_before:
                fail("Reserve preview mutated inventory")
            reserve_token = reserve_preview["confirmation_token"]
            reserve_done = structured_success(call_tool(client, client_key, 21, "reserve_project", {
                "project_id": fixture_ids["reserve_project"], "idempotency_key": "p734-reserve-valid-01",
                "confirmation_token": reserve_token
            }), "reserve confirmation")
            if reserve_done.get("phase") != "completed" or reserve_done.get("replayed") is not False:
                fail("Reserve confirmation result shape is wrong")
            reserve_after = current_stock(fixture_ids["reserve_part"])
            if reserve_after != (reserve_before[0], reserve_before[1] + 7):
                fail(f"Reserve confirmation delta is wrong: {reserve_before} -> {reserve_after}")
            rev = live_sync_broker.state()["revisions"]
            for topic in ("inventory", "projects", "reservations", "history"):
                if rev[topic] != live_before[topic] + 1:
                    fail(f"Reserve confirmation live-sync revision wrong for {topic}")
            replay = structured_success(call_tool(client, client_key, 22, "reserve_project", {
                "project_id": fixture_ids["reserve_project"], "idempotency_key": "p734-reserve-valid-01",
                "confirmation_token": reserve_token
            }), "reserve replay")
            if replay.get("replayed") is not True or current_stock(fixture_ids["reserve_part"]) != reserve_after:
                fail("Reserve idempotent replay mutated stock twice")
            if live_sync_broker.state()["revisions"] != rev:
                fail("Idempotent replay published a second live invalidation")

            # Consume exact once.
            consume_before = current_stock(fixture_ids["consume_part"])
            consume_preview = structured_success(call_tool(client, client_key, 30, "consume_reservation", {
                "reservation_id": fixture_ids["consume_reservation"], "idempotency_key": "p734-consume-valid1"
            }), "consume preview")
            consume_done = structured_success(call_tool(client, client_key, 31, "consume_reservation", {
                "reservation_id": fixture_ids["consume_reservation"], "idempotency_key": "p734-consume-valid1",
                "confirmation_token": consume_preview["confirmation_token"]
            }), "consume confirmation")
            if consume_done.get("phase") != "completed": fail("Consume did not complete")
            if current_stock(fixture_ids["consume_part"]) != (consume_before[0]-7, consume_before[1]-7):
                fail("Consume delta is wrong")

            # Cancel exact once.
            cancel_before = current_stock(fixture_ids["cancel_part"])
            cancel_preview = structured_success(call_tool(client, client_key, 40, "cancel_reservation", {
                "reservation_id": fixture_ids["cancel_reservation"], "idempotency_key": "p734-cancel-valid-01"
            }), "cancel preview")
            cancel_done = structured_success(call_tool(client, client_key, 41, "cancel_reservation", {
                "reservation_id": fixture_ids["cancel_reservation"], "idempotency_key": "p734-cancel-valid-01",
                "confirmation_token": cancel_preview["confirmation_token"]
            }), "cancel confirmation")
            if cancel_done.get("phase") != "completed": fail("Cancel did not complete")
            if current_stock(fixture_ids["cancel_part"]) != (cancel_before[0], cancel_before[1]-7):
                fail("Cancel release delta is wrong")

            verify = SessionLocal()
            try:
                # Confirmation material is digest-only; business movements and audits identify MCP + backing user.
                intents = verify.execute(select(McpWriteIntent)).scalars().all()
                if len(intents) < 6:
                    fail("Expected safeguarded write intent evidence was not persisted")
                serialized = json.dumps([
                    {"preview": i.preview_json, "result": i.result_json, "digest": i.confirmation_digest}
                    for i in intents
                ], sort_keys=True, default=str)
                for candidate in (token, drift_token, reserve_token, consume_preview["confirmation_token"], cancel_preview["confirmation_token"]):
                    if candidate and candidate in serialized:
                        fail("Plaintext confirmation token was persisted")
                mcp_movements = verify.execute(
                    select(StockMovement).where(
                        StockMovement.source == SOURCE_MCP,
                        StockMovement.actor_user_id == owner_id,
                    )
                ).scalars().all()
                if not any(m.reservation_id == reservation_for_project(fixture_ids["reserve_project"]) and m.movement_type == "reserve" for m in mcp_movements):
                    fail("MCP reserve movement attribution is missing")
                if not any(m.reservation_id == fixture_ids["consume_reservation"] and m.movement_type == "consume" for m in mcp_movements):
                    fail("MCP consume movement attribution is missing")
                if not any(m.reservation_id == fixture_ids["cancel_reservation"] and m.movement_type == "release" for m in mcp_movements):
                    fail("MCP cancel movement attribution is missing")
                business_audits = verify.execute(
                    select(AuditLog).where(AuditLog.actor_type == "mcp", AuditLog.actor_user_id == owner_id)
                ).scalars().all()
                if not any(a.event_type == "project.reserved" for a in business_audits):
                    fail("MCP Project business audit attribution is missing")
                if not any(a.event_type == "reservation.consumed" for a in business_audits):
                    fail("MCP consume business audit attribution is missing")
                if not any(a.event_type == "reservation.cancelled" for a in business_audits):
                    fail("MCP cancel business audit attribution is missing")
                audit_json = json.dumps([a.metadata_json for a in business_audits], sort_keys=True, default=str)
                for candidate in (token, drift_token, reserve_token):
                    if candidate and candidate in audit_json:
                        fail("MCP audit leaked confirmation material")
            finally:
                verify.close()

        print("[PASS] MCP safeguarded write tools preserve mutable copied policy while enforcing global/client/role/no-auth ceilings, preview-confirm idempotency, drift/token rejection, exact reserve/consume/cancel stock deltas, MCP attribution and live-sync publication")
    finally:
        engine.dispose()
        path.write_bytes(before_bytes)
        if path.read_bytes() != before_bytes:
            fail("MCP write smoke did not restore the copied database bytes exactly")


if __name__ == "__main__":
    main()
