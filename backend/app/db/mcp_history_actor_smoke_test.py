from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import AuditLog, McpOAuthClient, Part, StockMovement, User
from app.services.history import list_history, list_history_filter_options


# PARTPILOT:MCP_HISTORY_ACTOR_SMOKE:V758
EXPECTED_HEAD = "0021_mcp_inventory_part_metadata_update"
CLIENT_NAME = "Claude History Smoke"


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP History actor smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def main() -> None:
    path = database_path()
    before_bytes = path.read_bytes()
    try:
        db = SessionLocal()
        try:
            revision = db.connection().exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
            if revision != EXPECTED_HEAD:
                fail(f"Expected {EXPECTED_HEAD}, got {revision}")

            owner = db.execute(
                select(User)
                .where(User.is_active.is_(True), User.role == "owner")
                .order_by(User.id.asc())
            ).scalars().first()
            part = db.execute(
                select(Part)
                .where(Part.is_deleted.is_(False))
                .order_by(Part.id.asc())
            ).scalars().first()
            if owner is None or part is None:
                fail("MCP History actor smoke requires an active owner and part")

            suffix = uuid4().hex[:12]
            client = McpOAuthClient(
                registered_by_user_id=owner.id,
                client_id=f"p758_history_{suffix}",
                client_secret_hash=None,
                client_name=CLIENT_NAME,
                client_uri=None,
                redirect_uris_json=["https://client.example/callback"],
                grant_types_json=["authorization_code", "refresh_token"],
                response_types_json=["code"],
                token_endpoint_auth_method="none",
                metadata_json={"fixture": "patch-758-history"},
                denied_tools_json=[],
                revoked_at=None,
            )
            db.add(client)
            db.flush()

            base_time = datetime.now(timezone.utc) - timedelta(seconds=2)
            legacy_business = AuditLog(
                created_at=base_time,
                event_type="part.created",
                entity_type="part",
                entity_id=part.id,
                actor_type="mcp",
                actor_user_id=owner.id,
                summary=f"Patch 758 legacy OAuth attribution {suffix}",
                before_json=None,
                after_json={"id": part.id, "name": part.name},
                metadata_json={"part_type_id": part.part_type_id},
            )
            legacy_tool = AuditLog(
                created_at=base_time + timedelta(milliseconds=5),
                event_type="mcp.tool_called",
                entity_type="mcp_tool",
                entity_id=None,
                actor_type="mcp",
                actor_user_id=owner.id,
                summary=f"Patch 758 completed create_part {suffix}",
                before_json=None,
                after_json=None,
                metadata_json={
                    "tool": "create_part",
                    "auth_method": "oauth",
                    "request_id": "p758-history",
                    "success": True,
                    "arguments": {
                        "part_type_id": part.part_type_id,
                        "idempotency_key": f"p758-history-{suffix}",
                        "phase": "confirm",
                    },
                    "client_id": client.client_id,
                    "token_id": 758000,
                    "result": {
                        "phase": "completed",
                        "intent_id": 758000,
                        "part_id": part.id,
                        "replayed": False,
                    },
                },
            )
            db.add_all([legacy_business, legacy_tool])
            db.flush()

            movement = StockMovement(
                part_id=part.id,
                reservation_id=None,
                movement_type="restock",
                quantity_delta=1,
                quantity_before=int(part.total_quantity),
                quantity_after=int(part.total_quantity) + 1,
                reserved_quantity_before=int(part.reserved_quantity),
                reserved_quantity_after=int(part.reserved_quantity),
                available_quantity_before=(
                    int(part.total_quantity) - int(part.reserved_quantity)
                ),
                available_quantity_after=(
                    int(part.total_quantity) + 1 - int(part.reserved_quantity)
                ),
                unit_price_snapshot=part.unit_price,
                currency_snapshot=None,
                reason=f"Patch 758 MCP movement {suffix}",
                note=None,
                source="mcp",
                actor_user_id=owner.id,
                created_at=base_time + timedelta(seconds=1),
            )
            db.add(movement)
            db.flush()
            stamped_business = AuditLog(
                created_at=base_time + timedelta(seconds=1, milliseconds=5),
                event_type="part.quantity_adjusted",
                entity_type="part",
                entity_id=part.id,
                actor_type="mcp",
                actor_user_id=owner.id,
                summary=f"Patch 758 stamped MCP attribution {suffix}",
                before_json={"total_quantity": int(part.total_quantity)},
                after_json={"total_quantity": int(part.total_quantity) + 1},
                metadata_json={
                    "source": "mcp",
                    "movement_type": "restock",
                    "stock_movement_id": movement.id,
                    "mcp_client_name": CLIENT_NAME,
                    "mcp_auth_method": "oauth",
                },
            )
            db.add(stamped_business)
            db.commit()
            for row in (legacy_business, legacy_tool, movement, stamped_business):
                db.refresh(row)

            audits = list_history(
                db,
                kind="audit",
                event_type="part.created",
                actor_type="mcp",
                limit=100,
            )
            legacy_entry = next(
                (entry for entry in audits.entries if entry.key == f"audit:{legacy_business.id}"),
                None,
            )
            if (
                legacy_entry is None
                or legacy_entry.actor_display_name != CLIENT_NAME
                or legacy_entry.actor_type != "mcp"
                or legacy_entry.actor_user_id != owner.id
            ):
                fail(f"Legacy OAuth History actor hydration is wrong: {legacy_entry}")

            movements = list_history(
                db,
                kind="stock_movement",
                actor_type="mcp",
                limit=100,
            )
            movement_entry = next(
                (entry for entry in movements.entries if entry.key == f"movement:{movement.id}"),
                None,
            )
            if (
                movement_entry is None
                or movement_entry.actor_display_name != CLIENT_NAME
                or movement_entry.actor_type != "mcp"
                or movement_entry.actor_user_id != owner.id
            ):
                fail(f"MCP movement History actor hydration is wrong: {movement_entry}")

            user_movements = list_history(
                db,
                kind="stock_movement",
                actor_type="user",
                limit=100,
            )
            if any(entry.key == f"movement:{movement.id}" for entry in user_movements.entries):
                fail("MCP movement leaked into the user actor-type filter")

            options = list_history_filter_options(db)
            actor_types = {item.value: item.count for item in options.actor_types}
            if actor_types.get("mcp", 0) < 3:
                fail(f"MCP History actor facet did not include MCP movement: {actor_types}")
        finally:
            db.close()

        print(
            "[PASS] MCP History shows OAuth/direct client identity instead of the backing "
            "human for MCP audits and stock movements while preserving actor_user_id authority"
        )
    finally:
        engine.dispose()
        path.write_bytes(before_bytes)
        if path.read_bytes() != before_bytes:
            fail("MCP History actor smoke did not restore copied database bytes exactly")


if __name__ == "__main__":
    main()
