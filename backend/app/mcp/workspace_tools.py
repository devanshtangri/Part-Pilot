from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.mcp.part_tools import (
    _append_tool_audit,
    _bounded_request_id,
    _ensure_read_tools_enabled,
    _principal_from_context,
)
from app.schemas.projects import ProjectResponse
from app.schemas.reservations import ReservationResponse
from app.services.projects import (
    ProjectNotFoundError,
    get_project,
    list_projects as list_project_records,
)
from app.services.reservations import (
    ReservationNotFoundError,
    get_reservation,
    list_reservations as list_reservation_records,
)


# PARTPILOT:MCP_WORKSPACE_READ_TOOLS:V471
WORKSPACE_TOOL_NAMES = (
    "get_project_details",
    "get_reservation_details",
    "list_projects",
    "list_reservations",
)
PROJECT_STATUSES = {"draft", "reserved", "consumed", "cancelled"}
RESERVATION_STATUSES = {"active", "consumed", "cancelled", "expired"}


class ProjectListItem(BaseModel):
    id: int
    name: str
    status: str
    description: str | None = None
    item_count: int
    total_units: int
    estimated_total_value: str | None = None
    currency: str | None = None
    created_at: datetime
    updated_at: datetime


class ListProjectsResult(BaseModel):
    summary: str
    total: int
    limit: int
    offset: int
    returned: int
    has_more: bool
    next_offset: int | None = None
    projects: list[ProjectListItem]


class ProjectDetailsResult(BaseModel):
    summary: str
    project: ProjectResponse


class ReservationListItem(BaseModel):
    id: int
    label: str
    status: str
    project_id: int | None = None
    item_count: int
    total_reserved_units: int
    estimated_reserved_value: str | None = None
    currency: str | None = None
    expiry_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ListReservationsResult(BaseModel):
    summary: str
    total: int
    limit: int
    offset: int
    returned: int
    has_more: bool
    next_offset: int | None = None
    reservations: list[ReservationListItem]


class ReservationDetailsResult(BaseModel):
    summary: str
    reservation: ReservationResponse


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _validate_page(limit: int, offset: int) -> None:
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50.")
    if offset < 0:
        raise ValueError("offset cannot be negative.")


def _project_item(project: ProjectResponse) -> ProjectListItem:
    return ProjectListItem(
        id=project.id,
        name=project.name,
        status=project.status,
        description=project.description,
        item_count=project.item_count,
        total_units=project.total_units,
        estimated_total_value=_decimal_text(project.estimated_total_value),
        currency=project.currency_snapshot,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _reservation_item(reservation: ReservationResponse) -> ReservationListItem:
    return ReservationListItem(
        id=reservation.id,
        label=reservation.label,
        status=reservation.status,
        project_id=reservation.project_id,
        item_count=len(reservation.items),
        total_reserved_units=sum(item.quantity for item in reservation.items),
        estimated_reserved_value=_decimal_text(
            reservation.estimated_reserved_value
        ),
        currency=reservation.currency_snapshot,
        expiry_at=reservation.expiry_at,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
    )


def _audit_failure(
    db,
    *,
    principal: dict[str, Any],
    request_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    exc: Exception,
) -> None:
    try:
        _append_tool_audit(
            db,
            principal=principal,
            request_id=request_id,
            tool_name=tool_name,
            success=False,
            arguments=arguments,
            error_type=type(exc).__name__,
        )
        db.commit()
    except Exception:
        db.rollback()


def register_workspace_tools(server: FastMCP) -> None:
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        name="list_projects",
        title="List Part Pilot Projects",
        description=(
            "List Projects in newest-first order, optionally filtered by lifecycle "
            "status. Returns compact item counts, total planned units, value snapshots, "
            "and bounded pagination."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def list_projects(
        ctx: Context,
        status: Literal["draft", "reserved", "consumed", "cancelled"] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListProjectsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        arguments: dict[str, Any] = {
            "status": status,
            "limit": limit,
            "offset": offset,
        }
        db = SessionLocal()
        audit_completed = False
        try:
            _ensure_read_tools_enabled(db)
            _validate_page(limit, offset)
            if status is not None and status not in PROJECT_STATUSES:
                raise ValueError("Unsupported Project status.")
            collection = list_project_records(
                db,
                status_filter=status,
                limit=limit,
                offset=offset,
            )
            rows = [_project_item(project) for project in collection.projects]
            returned = len(rows)
            has_more = offset + returned < collection.total
            result = ListProjectsResult(
                summary=(
                    f"Found {collection.total} Projects"
                    + (f" with status {status}" if status else "")
                    + f"; returning {returned} from offset {offset}."
                ),
                total=collection.total,
                limit=limit,
                offset=offset,
                returned=returned,
                has_more=has_more,
                next_offset=(offset + returned if has_more else None),
                projects=rows,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="list_projects",
                success=True,
                arguments=arguments,
                result={"total": collection.total, "returned": returned},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                _audit_failure(
                    db,
                    principal=principal,
                    request_id=request_id,
                    tool_name="list_projects",
                    arguments=arguments,
                    exc=exc,
                )
            raise
        finally:
            db.close()

    @server.tool(
        name="get_project_details",
        title="Get exact Part Pilot Project details",
        description=(
            "Retrieve one Project by numeric ID, including lifecycle status, notes, "
            "value snapshots, timestamps, and the complete part plan with current stock "
            "context."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def get_project_details(
        project_id: Annotated[int, Field(description="Positive Part Pilot Project ID.")],
        ctx: Context,
    ) -> ProjectDetailsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        arguments = {"project_id": project_id}
        db = SessionLocal()
        audit_completed = False
        try:
            _ensure_read_tools_enabled(db)
            if project_id <= 0:
                raise ValueError("project_id must be greater than zero.")
            try:
                project = get_project(db, project_id)
            except ProjectNotFoundError as exc:
                raise ValueError("Project not found.") from exc
            result = ProjectDetailsResult(
                summary=f"Retrieved Project {project.name} (ID {project.id}).",
                project=project,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="get_project_details",
                success=True,
                arguments=arguments,
                result={"project_id": project.id},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                _audit_failure(
                    db,
                    principal=principal,
                    request_id=request_id,
                    tool_name="get_project_details",
                    arguments=arguments,
                    exc=exc,
                )
            raise
        finally:
            db.close()

    @server.tool(
        name="list_reservations",
        title="List Part Pilot Reservations",
        description=(
            "List Reservations in newest-first order, optionally filtered by lifecycle "
            "status. Returns compact item counts, reserved units, value snapshots, "
            "expiry information, Project links, and bounded pagination."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def list_reservations(
        ctx: Context,
        status: Literal["active", "consumed", "cancelled", "expired"] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListReservationsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        arguments: dict[str, Any] = {
            "status": status,
            "limit": limit,
            "offset": offset,
        }
        db = SessionLocal()
        audit_completed = False
        try:
            _ensure_read_tools_enabled(db)
            _validate_page(limit, offset)
            if status is not None and status not in RESERVATION_STATUSES:
                raise ValueError("Unsupported Reservation status.")
            collection = list_reservation_records(
                db,
                status_filter=status,
                limit=limit,
                offset=offset,
            )
            rows = [
                _reservation_item(reservation)
                for reservation in collection.reservations
            ]
            returned = len(rows)
            has_more = offset + returned < collection.total
            result = ListReservationsResult(
                summary=(
                    f"Found {collection.total} Reservations"
                    + (f" with status {status}" if status else "")
                    + f"; returning {returned} from offset {offset}."
                ),
                total=collection.total,
                limit=limit,
                offset=offset,
                returned=returned,
                has_more=has_more,
                next_offset=(offset + returned if has_more else None),
                reservations=rows,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="list_reservations",
                success=True,
                arguments=arguments,
                result={"total": collection.total, "returned": returned},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                _audit_failure(
                    db,
                    principal=principal,
                    request_id=request_id,
                    tool_name="list_reservations",
                    arguments=arguments,
                    exc=exc,
                )
            raise
        finally:
            db.close()

    @server.tool(
        name="get_reservation_details",
        title="Get exact Part Pilot Reservation details",
        description=(
            "Retrieve one Reservation by numeric ID, including lifecycle status, "
            "Project link, notes, expiry, value snapshots, timestamps, and the complete "
            "reserved part plan with current stock context."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def get_reservation_details(
        reservation_id: Annotated[
            int,
            Field(description="Positive Part Pilot Reservation ID."),
        ],
        ctx: Context,
    ) -> ReservationDetailsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        arguments = {"reservation_id": reservation_id}
        db = SessionLocal()
        audit_completed = False
        try:
            _ensure_read_tools_enabled(db)
            if reservation_id <= 0:
                raise ValueError("reservation_id must be greater than zero.")
            try:
                reservation = get_reservation(db, reservation_id)
            except ReservationNotFoundError as exc:
                raise ValueError("Reservation not found.") from exc
            result = ReservationDetailsResult(
                summary=(
                    f"Retrieved Reservation {reservation.label} "
                    f"(ID {reservation.id})."
                ),
                reservation=reservation,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="get_reservation_details",
                success=True,
                arguments=arguments,
                result={"reservation_id": reservation.id},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                _audit_failure(
                    db,
                    principal=principal,
                    request_id=request_id,
                    tool_name="get_reservation_details",
                    arguments=arguments,
                    exc=exc,
                )
            raise
        finally:
            db.close()
