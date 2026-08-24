from __future__ import annotations

from datetime import timezone
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.db.constants import SOURCE_MCP
from app.db.session import SessionLocal
from app.mcp.part_tools import _append_tool_audit, _bounded_request_id, _principal_from_context
from app.models import Part, Project, Reservation
from app.schemas.parts import PartQuantityAdjustmentRequest, PartQuantityAdjustmentResponse
from app.schemas.projects import ProjectResponse
from app.schemas.reservations import ReservationResponse
from app.services.live_sync import publish_live_invalidation
from app.services.mcp_permissions import authorize_mcp_tool
from app.services.mcp_write_safeguards import (
    McpWriteSafeguardError,
    complete_write_intent,
    completed_write_replay,
    fail_write_intent,
    prepare_write_intent,
    validate_confirmation,
)
from app.services.parts import (
    adjust_part_quantity as adjust_part_quantity_service,
    preview_part_quantity_adjustment,
)
from app.services.projects import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectValidationError,
    get_project,
    reserve_project as reserve_project_service,
)
from app.services.reservations import (
    ReservationConflictError,
    ReservationNotFoundError,
    ReservationValidationError,
    cancel_reservation as cancel_reservation_service,
    consume_reservation as consume_reservation_service,
    get_reservation,
)

# PARTPILOT:SAFEGUARDED_MCP_WRITE_TOOLS:V734
WRITE_TOOL_NAMES = ("reserve_project", "consume_reservation", "cancel_reservation", "adjust_part_quantity")

class WriteStockDelta(BaseModel):
    part_id: int
    part_number: str | None = None
    part_name: str | None = None
    units: int
    physical_before: int
    physical_after: int
    reserved_before: int
    reserved_after: int
    available_before: int
    available_after: int

class WriteImpactPreview(BaseModel):
    action: Literal["reserve_project", "consume_reservation", "cancel_reservation"]
    target_type: Literal["project", "reservation"]
    target_id: int
    target_label: str
    status_before: str
    status_after: str
    linked_project_id: int | None = None
    linked_project_status_before: str | None = None
    linked_project_status_after: str | None = None
    total_units: int
    items: list[WriteStockDelta]

class SafeguardedWriteResult(BaseModel):
    summary: str
    phase: Literal["preview", "completed"]
    idempotency_key: str
    confirmation_required: bool
    confirmation_token: str | None = None
    expires_at: str | None = None
    preview: WriteImpactPreview
    project: ProjectResponse | None = None
    reservation: ReservationResponse | None = None
    replayed: bool = False


class PartQuantityAdjustmentPreview(BaseModel):
    action: Literal["adjust_part_quantity"]
    target_type: Literal["part"]
    target_id: int
    target_label: str
    part_number: str | None = None
    part_name: str | None = None
    operation: Literal["add", "remove", "consume", "correction"]
    movement_type: str
    quantity_delta: int
    physical_before: int
    physical_after: int
    reserved_before: int
    reserved_after: int
    available_before: int
    available_after: int
    reason: str
    note: str | None = None


class SafeguardedPartQuantityWriteResult(BaseModel):
    summary: str
    phase: Literal["preview", "completed"]
    idempotency_key: str
    confirmation_required: bool
    confirmation_token: str | None = None
    expires_at: str | None = None
    preview: PartQuantityAdjustmentPreview
    adjustment: PartQuantityAdjustmentResponse | None = None
    replayed: bool = False


def _serialize_result(result: SafeguardedWriteResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


def _preview_project_reservation(db, project_id: int) -> tuple[WriteImpactPreview, ProjectResponse]:
    project = get_project(db, project_id)
    if project.status != "draft":
        raise ProjectConflictError(
            f"Only Draft Projects can be reserved. Current status: {project.status}."
        )
    if not project.items:
        raise ProjectValidationError("A Project must contain at least one part before reservation.")
    deltas: list[WriteStockDelta] = []
    total_units = 0
    for item in project.items:
        if item.part_id is None or item.part_is_deleted:
            raise ProjectValidationError("Project contains an item whose part is unavailable.")
        if item.total_quantity is None or item.reserved_quantity is None or item.available_quantity is None:
            raise ProjectValidationError("Project stock state is unavailable for preview.")
        if item.quantity > item.available_quantity:
            raise ProjectConflictError(
                f"Part {item.part_id} has only {item.available_quantity} available units."
            )
        total_units += item.quantity
        deltas.append(WriteStockDelta(
            part_id=item.part_id,
            part_number=item.part_number,
            part_name=item.part_name,
            units=item.quantity,
            physical_before=item.total_quantity,
            physical_after=item.total_quantity,
            reserved_before=item.reserved_quantity,
            reserved_after=item.reserved_quantity + item.quantity,
            available_before=item.available_quantity,
            available_after=item.available_quantity - item.quantity,
        ))
    existing = db.execute(
        select(func.count(Reservation.id)).where(Reservation.project_id == project_id)
    ).scalar_one()
    if existing:
        raise ProjectConflictError("Draft Project already has a linked Reservation.")
    return WriteImpactPreview(
        action="reserve_project", target_type="project", target_id=project.id,
        target_label=project.name, status_before="draft", status_after="reserved",
        linked_project_id=project.id, linked_project_status_before="draft",
        linked_project_status_after="reserved", total_units=total_units, items=deltas,
    ), project


def _preview_reservation_action(db, reservation_id: int, action: Literal["consume_reservation", "cancel_reservation"]) -> tuple[WriteImpactPreview, ReservationResponse]:
    reservation = get_reservation(db, reservation_id)
    if reservation.status != "active":
        raise ReservationConflictError(
            f"Only active reservations can be {'consumed' if action == 'consume_reservation' else 'cancelled'}. Current status: {reservation.status}."
        )
    if not reservation.items:
        raise ReservationConflictError("Active reservation has no items.")
    linked_before = linked_after = None
    if reservation.project_id is not None:
        linked = db.get(Project, reservation.project_id)
        if linked is None or linked.status != "reserved":
            raise ReservationConflictError("Linked Project must exist and be Reserved before this action.")
        linked_ids = list(db.execute(
            select(Reservation.id).where(Reservation.project_id == linked.id).order_by(Reservation.id)
        ).scalars())
        if linked_ids != [reservation.id]:
            raise ReservationConflictError("Linked Project must have exactly one Reservation before this action.")
        linked_before = "reserved"
        linked_after = "consumed" if action == "consume_reservation" else "cancelled"
    deltas: list[WriteStockDelta] = []
    total_units = 0
    for item in reservation.items:
        if item.part_id is None or item.total_quantity is None or item.reserved_quantity is None or item.available_quantity is None:
            raise ReservationConflictError("Reservation stock state is unavailable for preview.")
        if item.reserved_quantity < item.quantity:
            raise ReservationConflictError(
                f"Part {item.part_id} has only {item.reserved_quantity} reserved units."
            )
        if action == "consume_reservation" and item.total_quantity < item.quantity:
            raise ReservationConflictError(
                f"Part {item.part_id} has only {item.total_quantity} physical units."
            )
        total_units += item.quantity
        physical_after = item.total_quantity - item.quantity if action == "consume_reservation" else item.total_quantity
        reserved_after = item.reserved_quantity - item.quantity
        available_after = physical_after - reserved_after
        deltas.append(WriteStockDelta(
            part_id=item.part_id, part_number=item.part_number, part_name=item.part_name,
            units=item.quantity, physical_before=item.total_quantity, physical_after=physical_after,
            reserved_before=item.reserved_quantity, reserved_after=reserved_after,
            available_before=item.available_quantity, available_after=available_after,
        ))
    status_after = "consumed" if action == "consume_reservation" else "cancelled"
    return WriteImpactPreview(
        action=action, target_type="reservation", target_id=reservation.id,
        target_label=reservation.label, status_before="active", status_after=status_after,
        linked_project_id=reservation.project_id,
        linked_project_status_before=linked_before, linked_project_status_after=linked_after,
        total_units=total_units, items=deltas,
    ), reservation


def _publish_completed(action: str, target_id: int, project_id: int | None) -> None:
    if action == "reserve_project":
        publish_live_invalidation(
            ("inventory", "projects", "reservations", "history"),
            resource={"type": "project", "id": target_id},
        )
        return
    topics = ["inventory"]
    if project_id is not None:
        topics.append("projects")
    topics.extend(("reservations", "history"))
    publish_live_invalidation(
        tuple(topics), resource={"type": "reservation", "id": target_id}
    )


def _run_guarded_write(
    *, ctx: Context, tool_name: str, target_id: int, idempotency_key: str,
    confirmation_token: str | None,
) -> SafeguardedWriteResult:
    if target_id < 1:
        raise ValueError("Target id must be greater than zero.")
    principal = _principal_from_context(ctx)
    request_id = _bounded_request_id(ctx)
    arguments = {"target_id": target_id}
    db = SessionLocal()
    try:
        authorization_user_id = authorize_mcp_tool(db, principal, tool_name)
        if type(authorization_user_id) is not int:
            raise RuntimeError("MCP write authorization did not resolve a user authority.")
        replay_json = completed_write_replay(
            db, principal=principal, tool_name=tool_name,
            idempotency_key=idempotency_key, arguments=arguments,
        )
        if replay_json is not None:
            replay = SafeguardedWriteResult.model_validate(replay_json)
            return replay.model_copy(update={"replayed": True})
        if tool_name == "reserve_project":
            preview, _ = _preview_project_reservation(db, target_id)
        else:
            preview, _ = _preview_reservation_action(db, target_id, tool_name)
        preview_json = preview.model_dump(mode="json")

        if confirmation_token is None:
            prepared = prepare_write_intent(
                db, principal=principal, authorization_user_id=authorization_user_id,
                tool_name=tool_name, idempotency_key=idempotency_key,
                arguments=arguments, preview=preview_json,
            )
            if prepared.replay_result is not None:
                replay = SafeguardedWriteResult.model_validate(prepared.replay_result)
                return replay.model_copy(update={"replayed": True})
            assert prepared.confirmation_token is not None
            result = SafeguardedWriteResult(
                summary=(
                    f"Preview ready for {tool_name}. Review the exact stock/status delta, then call the same tool with this idempotency_key and confirmation_token within five minutes."
                ),
                phase="preview", idempotency_key=idempotency_key,
                confirmation_required=True, confirmation_token=prepared.confirmation_token,
                expires_at=prepared.intent.expires_at.replace(tzinfo=timezone.utc).isoformat(),
                preview=preview,
            )
            _append_tool_audit(
                db, principal=principal, request_id=request_id, tool_name=tool_name,
                success=True, arguments={"target_id": target_id, "idempotency_key": idempotency_key, "phase": "preview"},
                result={"phase": "preview", "intent_id": prepared.intent.id, "confirmation_required": True},
            )
            db.commit()
            return result

        validated = validate_confirmation(
            db, principal=principal, tool_name=tool_name,
            idempotency_key=idempotency_key, confirmation_token=confirmation_token,
            arguments=arguments, current_preview=preview_json,
        )
        if validated.replay_result is not None:
            replay = SafeguardedWriteResult.model_validate(validated.replay_result)
            return replay.model_copy(update={"replayed": True})

        if tool_name == "reserve_project":
            project = reserve_project_service(
                db, target_id, actor_user_id=authorization_user_id,
                actor_type="mcp", source=SOURCE_MCP, commit=False,
            )
            final = SafeguardedWriteResult(
                summary=f"Confirmed MCP write reserved Project {target_id} exactly once.",
                phase="completed", idempotency_key=idempotency_key,
                confirmation_required=False, preview=preview, project=project,
            )
            project_id = target_id
        elif tool_name == "consume_reservation":
            reservation = consume_reservation_service(
                db, target_id, actor_user_id=authorization_user_id,
                actor_type="mcp", source=SOURCE_MCP, commit=False,
            )
            final = SafeguardedWriteResult(
                summary=f"Confirmed MCP write consumed Reservation {target_id} exactly once.",
                phase="completed", idempotency_key=idempotency_key,
                confirmation_required=False, preview=preview, reservation=reservation,
            )
            project_id = reservation.project_id
        else:
            reservation = cancel_reservation_service(
                db, target_id, actor_user_id=authorization_user_id,
                actor_type="mcp", source=SOURCE_MCP, commit=False,
            )
            final = SafeguardedWriteResult(
                summary=f"Confirmed MCP write cancelled Reservation {target_id} exactly once.",
                phase="completed", idempotency_key=idempotency_key,
                confirmation_required=False, preview=preview, reservation=reservation,
            )
            project_id = reservation.project_id

        complete_write_intent(db, validated.intent, _serialize_result(final))
        _append_tool_audit(
            db, principal=principal, request_id=request_id, tool_name=tool_name,
            success=True, arguments={"target_id": target_id, "idempotency_key": idempotency_key, "phase": "confirm"},
            result={"phase": "completed", "intent_id": validated.intent.id, "replayed": False},
        )
        db.commit()
        _publish_completed(tool_name, target_id, project_id)
        return final
    except Exception as exc:
        db.rollback()
        if confirmation_token is not None:
            try:
                fail_write_intent(
                    db, principal=principal if 'principal' in locals() else {},
                    tool_name=tool_name, idempotency_key=idempotency_key,
                    error_type=type(exc).__name__,
                )
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def _part_quantity_preview(db, part_id: int, payload: PartQuantityAdjustmentRequest) -> PartQuantityAdjustmentPreview:
    plan = preview_part_quantity_adjustment(db, part_id, payload, source=SOURCE_MCP)
    return PartQuantityAdjustmentPreview(
        action="adjust_part_quantity",
        target_type="part",
        target_id=plan.part_id,
        target_label=plan.part_label,
        part_number=plan.part_number,
        part_name=plan.part_name,
        operation=payload.operation,
        movement_type=plan.movement_type,
        quantity_delta=plan.quantity_delta,
        physical_before=plan.quantity_before,
        physical_after=plan.quantity_after,
        reserved_before=plan.reserved_quantity,
        reserved_after=plan.reserved_quantity,
        available_before=plan.available_before,
        available_after=plan.available_after,
        reason=plan.reason,
        note=plan.note,
    )


def _run_guarded_part_quantity_write(
    *,
    ctx: Context,
    part_id: int,
    operation: Literal["add", "remove", "consume", "correction"],
    quantity: int,
    idempotency_key: str,
    reason: str | None,
    note: str | None,
    confirmation_token: str | None,
) -> SafeguardedPartQuantityWriteResult:
    if part_id < 1:
        raise ValueError("Part id must be greater than zero.")
    payload = PartQuantityAdjustmentRequest(
        operation=operation, quantity=quantity, reason=reason, note=note
    )
    principal = _principal_from_context(ctx)
    request_id = _bounded_request_id(ctx)
    arguments = {"part_id": part_id, **payload.model_dump(mode="json")}
    tool_name = "adjust_part_quantity"
    db = SessionLocal()
    try:
        authorization_user_id = authorize_mcp_tool(db, principal, tool_name)
        if type(authorization_user_id) is not int:
            raise RuntimeError("MCP write authorization did not resolve a user authority.")

        replay_json = completed_write_replay(
            db,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            arguments=arguments,
        )
        if replay_json is not None:
            replay = SafeguardedPartQuantityWriteResult.model_validate(replay_json)
            return replay.model_copy(update={"replayed": True})

        preview = _part_quantity_preview(db, part_id, payload)
        preview_json = preview.model_dump(mode="json")
        if confirmation_token is None:
            prepared = prepare_write_intent(
                db,
                principal=principal,
                authorization_user_id=authorization_user_id,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
                arguments=arguments,
                preview=preview_json,
            )
            if prepared.replay_result is not None:
                replay = SafeguardedPartQuantityWriteResult.model_validate(
                    prepared.replay_result
                )
                return replay.model_copy(update={"replayed": True})
            assert prepared.confirmation_token is not None
            result = SafeguardedPartQuantityWriteResult(
                summary=(
                    "Preview ready for adjust_part_quantity. Review the exact physical/"
                    "reserved/available stock delta, then call the same tool with this "
                    "idempotency_key and confirmation_token within five minutes."
                ),
                phase="preview",
                idempotency_key=idempotency_key,
                confirmation_required=True,
                confirmation_token=prepared.confirmation_token,
                expires_at=prepared.intent.expires_at.replace(
                    tzinfo=timezone.utc
                ).isoformat(),
                preview=preview,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name=tool_name,
                success=True,
                arguments={
                    **arguments,
                    "idempotency_key": idempotency_key,
                    "phase": "preview",
                },
                result={
                    "phase": "preview",
                    "intent_id": prepared.intent.id,
                    "confirmation_required": True,
                },
            )
            db.commit()
            return result

        validated = validate_confirmation(
            db,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            confirmation_token=confirmation_token,
            arguments=arguments,
            current_preview=preview_json,
        )
        if validated.replay_result is not None:
            replay = SafeguardedPartQuantityWriteResult.model_validate(
                validated.replay_result
            )
            return replay.model_copy(update={"replayed": True})

        adjustment = adjust_part_quantity_service(
            db,
            part_id,
            payload,
            actor_user_id=authorization_user_id,
            actor_type="mcp",
            source=SOURCE_MCP,
            commit=False,
        )
        final = SafeguardedPartQuantityWriteResult(
            summary=f"Confirmed MCP stock adjustment for Part {part_id} exactly once.",
            phase="completed",
            idempotency_key=idempotency_key,
            confirmation_required=False,
            preview=preview,
            adjustment=adjustment,
        )
        complete_write_intent(
            db, validated.intent, final.model_dump(mode="json")
        )
        _append_tool_audit(
            db,
            principal=principal,
            request_id=request_id,
            tool_name=tool_name,
            success=True,
            arguments={
                **arguments,
                "idempotency_key": idempotency_key,
                "phase": "confirm",
            },
            result={
                "phase": "completed",
                "intent_id": validated.intent.id,
                "replayed": False,
            },
        )
        db.commit()
        publish_live_invalidation(
            ("inventory", "history"),
            resource={"type": "part", "id": part_id},
        )
        return final
    except Exception as exc:
        db.rollback()
        if confirmation_token is not None:
            try:
                fail_write_intent(
                    db,
                    principal=principal if "principal" in locals() else {},
                    tool_name=tool_name,
                    idempotency_key=idempotency_key,
                    error_type=type(exc).__name__,
                )
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def register_write_tools(server: FastMCP) -> None:
    consequential = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
    destructive = ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
    )

    @server.tool(
        name="reserve_project", title="Reserve a Part Pilot Project",
        description=(
            "Safeguarded Project reservation. First call with project_id and a stable idempotency_key to receive an exact stock/status preview and five-minute confirmation token. No mutation occurs until the same call is repeated with that token."
        ), annotations=consequential, structured_output=True,
    )
    def reserve_project(
        ctx: Context,
        project_id: Annotated[int, Field(gt=0)],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
        confirmation_token: Annotated[str | None, Field(max_length=160)] = None,
    ) -> SafeguardedWriteResult:
        return _run_guarded_write(
            ctx=ctx, tool_name="reserve_project", target_id=project_id,
            idempotency_key=idempotency_key, confirmation_token=confirmation_token,
        )

    @server.tool(
        name="consume_reservation", title="Consume a Part Pilot Reservation",
        description=(
            "Safeguarded irreversible reserved-stock consumption. First call previews the exact physical/reserved delta; the second call must repeat the same idempotency_key with the short-lived confirmation token."
        ), annotations=destructive, structured_output=True,
    )
    def consume_reservation(
        ctx: Context,
        reservation_id: Annotated[int, Field(gt=0)],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
        confirmation_token: Annotated[str | None, Field(max_length=160)] = None,
    ) -> SafeguardedWriteResult:
        return _run_guarded_write(
            ctx=ctx, tool_name="consume_reservation", target_id=reservation_id,
            idempotency_key=idempotency_key, confirmation_token=confirmation_token,
        )

    @server.tool(
        name="cancel_reservation", title="Cancel a Part Pilot Reservation",
        description=(
            "Safeguarded reservation cancellation and stock release. First call previews the exact release/status delta; the second call must repeat the same idempotency_key with the short-lived confirmation token."
        ), annotations=consequential, structured_output=True,
    )
    def cancel_reservation(
        ctx: Context,
        reservation_id: Annotated[int, Field(gt=0)],
        idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
        confirmation_token: Annotated[str | None, Field(max_length=160)] = None,
    ) -> SafeguardedWriteResult:
        return _run_guarded_write(
            ctx=ctx, tool_name="cancel_reservation", target_id=reservation_id,
            idempotency_key=idempotency_key, confirmation_token=confirmation_token,
        )

    @server.tool(
        name="adjust_part_quantity",
        title="Adjust Part Pilot Part Quantity",
        description=(
            "Safeguarded inventory quantity adjustment using Part Pilot's canonical add, "
            "remove, consume, or correction semantics. The first call returns the exact "
            "physical/reserved/available delta and a five-minute confirmation token; no "
            "inventory mutation occurs until the same arguments and idempotency_key are "
            "repeated with that token."
        ),
        annotations=destructive,
        structured_output=True,
    )
    def adjust_part_quantity(
        ctx: Context,
        part_id: Annotated[int, Field(gt=0)],
        operation: Literal["add", "remove", "consume", "correction"],
        quantity: int,
        idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
        reason: Annotated[str | None, Field(max_length=180)] = None,
        note: Annotated[str | None, Field(max_length=5000)] = None,
        confirmation_token: Annotated[str | None, Field(max_length=160)] = None,
    ) -> SafeguardedPartQuantityWriteResult:
        return _run_guarded_part_quantity_write(
            ctx=ctx,
            part_id=part_id,
            operation=operation,
            quantity=quantity,
            idempotency_key=idempotency_key,
            reason=reason,
            note=note,
            confirmation_token=confirmation_token,
        )
