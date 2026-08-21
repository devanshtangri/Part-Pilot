from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models import Part, PartType, User, UserSession
from app.services.auth import create_session
from app.services.parts import get_inventory_metrics


class InventoryMetricsSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise InventoryMetricsSmokeFailure(message)


def main() -> None:
    with SessionLocal() as db:
        part_type = db.execute(
            select(PartType).where(PartType.is_active.is_(True)).order_by(PartType.id).limit(1)
        ).scalar_one()
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id).limit(1)
        ).scalar_one()
        baseline = get_inventory_metrics(db)
        suffix = uuid4().hex[:12]
        priced = Part(
            part_type_id=part_type.id,
            part_number=f"METRIC-{suffix}-P",
            name=f"Metrics priced {suffix}",
            total_quantity=11,
            reserved_quantity=4,
            unit_price=Decimal("2.5000"),
            low_stock_enabled=True,
            low_stock_threshold=7,
            is_deleted=False,
            deleted_at=None,
        )
        unpriced = Part(
            part_type_id=part_type.id,
            part_number=f"METRIC-{suffix}-U",
            name=f"Metrics unpriced {suffix}",
            total_quantity=7,
            reserved_quantity=2,
            unit_price=None,
            low_stock_enabled=False,
            low_stock_threshold=None,
            is_deleted=False,
            deleted_at=None,
        )
        out_fixture = Part(
            part_type_id=part_type.id,
            part_number=f"METRIC-{suffix}-O",
            name=f"Metrics out {suffix}",
            total_quantity=0,
            reserved_quantity=0,
            unit_price=None,
            low_stock_enabled=False,
            low_stock_threshold=None,
            is_deleted=False,
            deleted_at=None,
        )
        deleted_fixture = Part(
            part_type_id=part_type.id,
            part_number=f"METRIC-{suffix}-D",
            name=f"Metrics deleted {suffix}",
            total_quantity=100,
            reserved_quantity=10,
            unit_price=Decimal("99.0000"),
            low_stock_enabled=False,
            low_stock_threshold=None,
            is_deleted=True,
            deleted_at=priced.created_at,
        )
        # SQLite accepts an explicit deleted timestamp after flush; keep the fixture
        # fully test-owned and outside the active metric set.
        from datetime import datetime, timezone
        deleted_fixture.deleted_at = datetime.now(timezone.utc)
        db.add_all((priced, unpriced, out_fixture, deleted_fixture))
        db.flush()
        fixture_ids = [priced.id, unpriced.id, out_fixture.id, deleted_fixture.id]
        session = create_session(
            db,
            user=user,
            user_agent="inventory-metrics-smoke",
            ip_address="127.0.0.1",
            commit=False,
        )
        session_id = session.session.id
        db.commit()
        session_token = session.token

    try:
        with SessionLocal() as db:
            measured = get_inventory_metrics(db)
        if measured.active_part_count != baseline.active_part_count + 3:
            fail(f"Active part count delta mismatch: {baseline.active_part_count} -> {measured.active_part_count}")
        if measured.physical_quantity != baseline.physical_quantity + 18:
            fail(f"Physical quantity delta mismatch: {baseline.physical_quantity} -> {measured.physical_quantity}")
        if measured.reserved_quantity != baseline.reserved_quantity + 6:
            fail(f"Reserved quantity delta mismatch: {baseline.reserved_quantity} -> {measured.reserved_quantity}")
        if measured.available_quantity != baseline.available_quantity + 12:
            fail(f"Available quantity delta mismatch: {baseline.available_quantity} -> {measured.available_quantity}")
        if measured.priced_part_count != baseline.priced_part_count + 1:
            fail(f"Priced part count delta mismatch: {baseline.priced_part_count} -> {measured.priced_part_count}")
        if measured.inventory_value != baseline.inventory_value + Decimal("27.5000"):
            fail(f"Inventory value delta mismatch: {baseline.inventory_value} -> {measured.inventory_value}")
        if measured.stock_alert_count != baseline.stock_alert_count + 2:
            fail(f"Stock alert count delta mismatch: {baseline.stock_alert_count} -> {measured.stock_alert_count}")
        if measured.low_stock_count != baseline.low_stock_count + 1:
            fail(f"Low-stock count delta mismatch: {baseline.low_stock_count} -> {measured.low_stock_count}")
        if measured.out_of_stock_count != baseline.out_of_stock_count + 1:
            fail(f"Out-of-stock count delta mismatch: {baseline.out_of_stock_count} -> {measured.out_of_stock_count}")

        client = TestClient(app)
        unauthenticated = client.get("/api/parts/metrics")
        if unauthenticated.status_code != 401:
            fail(f"Unauthenticated metrics returned {unauthenticated.status_code}")
        response = client.get(
            "/api/parts/metrics",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if response.status_code != 200:
            fail(f"Authenticated metrics returned {response.status_code}: {response.text}")
        payload = response.json()
        expected = {
            "active_part_count": measured.active_part_count,
            "physical_quantity": measured.physical_quantity,
            "reserved_quantity": measured.reserved_quantity,
            "available_quantity": measured.available_quantity,
            "priced_part_count": measured.priced_part_count,
            "inventory_value": str(measured.inventory_value),
            "stock_alert_count": measured.stock_alert_count,
            "low_stock_count": measured.low_stock_count,
            "out_of_stock_count": measured.out_of_stock_count,
        }
        actual = dict(payload)
        actual["inventory_value"] = str(actual.get("inventory_value"))
        if actual != expected:
            fail(f"Metrics API payload mismatch: expected={expected}, actual={actual}")
    finally:
        with SessionLocal() as db:
            db.execute(delete(UserSession).where(UserSession.id == session_id))
            db.execute(delete(Part).where(Part.id.in_(fixture_ids)))
            db.commit()
        with SessionLocal() as db:
            restored = get_inventory_metrics(db)
        if restored != baseline:
            fail(f"Fixture cleanup did not restore baseline metrics: {baseline} -> {restored}")

    print("[PASS] Whole-inventory Stored Parts metrics aggregate active records and physical/reserved/available quantities, reuse existing low/out-of-stock alert semantics, exclude deleted parts, value only priced physical stock, expose protected API access and restore copied-database baseline exactly")


if __name__ == "__main__":
    main()
