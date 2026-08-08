from __future__ import annotations

from decimal import Decimal
from ipaddress import ip_address
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AuditLog
from app.schemas.parts import PartResponse
from app.services.mcp_oauth import MCP_SCOPE_READ, available_scopes
from app.services.parts import PartNotFoundError, get_part, list_parts


# PARTPILOT:MCP_PART_READ_TOOLS:V509
PART_TOOL_NAMES = ("get_part_details", "search_parts")
_SORT_FIELDS = {
    "default",
    "part",
    "type",
    "manufacturer",
    "location",
    "available",
    "total",
    "status",
}
_STOCK_STATUSES = {"all", "in", "low", "out"}
_SORT_DIRECTIONS = {"asc", "desc"}


class PartSearchItem(BaseModel):
    id: int
    display_name: str
    part_number: str | None = None
    name: str | None = None
    part_type: str
    manufacturer: str | None = None
    location: str | None = None
    package: str | None = None
    total_quantity: int
    reserved_quantity: int
    available_quantity: int
    stock_status: str
    unit_price: str | None = None


class SearchPartsResult(BaseModel):
    summary: str
    total: int
    limit: int
    offset: int
    returned: int
    has_more: bool
    next_offset: int | None = None
    parts: list[PartSearchItem]


class PartDetailsResult(BaseModel):
    summary: str
    stock_status: str
    part: PartResponse


def _principal_from_context(ctx: Context) -> dict[str, Any]:
    request = ctx.request_context.request
    scope = getattr(request, "scope", None)
    state = scope.get("state", {}) if isinstance(scope, dict) else {}
    principal = state.get("partpilot_mcp_principal") if isinstance(state, dict) else None
    if not isinstance(principal, dict):
        raise RuntimeError("Authenticated MCP principal is unavailable.")

    auth_method = principal.get("auth_method")
    if auth_method not in {
        "oauth",
        "direct_bearer",
        "direct_custom_header",
        "direct_trusted_network",
        "direct_no_auth",
    }:
        raise RuntimeError("Authenticated MCP principal is invalid.")
    if principal.get("actor_type") != "mcp":
        raise RuntimeError("Authenticated MCP principal is invalid.")
    scopes = principal.get("scopes")
    if (
        not isinstance(scopes, list)
        or any(not isinstance(scope_name, str) for scope_name in scopes)
        or MCP_SCOPE_READ not in scopes
    ):
        raise RuntimeError("Authenticated MCP principal lacks read access.")
    if not isinstance(principal.get("resource_uri"), str):
        raise RuntimeError("Authenticated MCP principal is invalid.")

    if auth_method == "oauth":
        actor_user_id = principal.get("actor_user_id")
        oauth = principal.get("oauth")
        if type(actor_user_id) is not int or not isinstance(oauth, dict):
            raise RuntimeError("Authenticated MCP OAuth principal is invalid.")
        expected = {
            "token_id": int,
            "client_database_id": int,
            "client_id": str,
        }
        for key, expected_type in expected.items():
            value = oauth.get(key)
            if expected_type is int:
                valid = type(value) is int
            else:
                valid = isinstance(value, expected_type)
            if not valid:
                raise RuntimeError("Authenticated MCP OAuth principal is invalid.")
    else:
        if principal.get("actor_user_id") is not None:
            raise RuntimeError("Authenticated MCP direct principal is invalid.")
        if "oauth" in principal:
            raise RuntimeError("Authenticated MCP direct principal is invalid.")
        client_ip = principal.get("client_ip")
        if client_ip is not None:
            if not isinstance(client_ip, str):
                raise RuntimeError("Authenticated MCP direct principal is invalid.")
            try:
                ip_address(client_ip)
            except ValueError as exc:
                raise RuntimeError("Authenticated MCP direct principal is invalid.") from exc
        if auth_method in {"direct_trusted_network", "direct_no_auth"} and client_ip is None:
            raise RuntimeError("Authenticated MCP source-based principal is invalid.")
        direct_client_name = principal.get("direct_client_name")
        if not isinstance(direct_client_name, str) or not direct_client_name.strip():
            raise RuntimeError("Authenticated MCP direct principal is invalid.")
        direct_auth_id = principal.get("direct_auth_id")
        if auth_method == "direct_no_auth":
            if direct_auth_id is not None:
                raise RuntimeError("Authenticated MCP no-auth principal is invalid.")
        elif type(direct_auth_id) is not int or direct_auth_id < 1:
            raise RuntimeError("Authenticated MCP named-client principal is invalid.")
    return principal


def _bounded_request_id(ctx: Context) -> str:
    return ctx.request_id[:128]


def _stock_status(part: PartResponse) -> str:
    if part.available_quantity <= 0:
        return "out_of_stock"
    if part.is_low_stock:
        return "low_stock"
    return "available"


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _compact_part(part: PartResponse) -> PartSearchItem:
    return PartSearchItem(
        id=part.id,
        display_name=part.name or part.part_number or f"Part {part.id}",
        part_number=part.part_number,
        name=part.name,
        part_type=part.part_type_name,
        manufacturer=part.manufacturer_name,
        location=part.location_name,
        package=part.package,
        total_quantity=part.total_quantity,
        reserved_quantity=part.reserved_quantity,
        available_quantity=part.available_quantity,
        stock_status=_stock_status(part),
        unit_price=_decimal_text(part.unit_price),
    )


def _append_tool_audit(
    db: Session,
    *,
    principal: dict[str, Any],
    request_id: str,
    tool_name: str,
    success: bool,
    arguments: dict[str, Any],
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> None:
    auth_method = principal["auth_method"]
    metadata: dict[str, Any] = {
        "tool": tool_name,
        "auth_method": auth_method,
        "request_id": request_id,
        "success": success,
        "arguments": arguments,
    }
    if auth_method == "oauth":
        oauth = principal["oauth"]
        metadata["client_id"] = oauth["client_id"]
        metadata["token_id"] = oauth["token_id"]
    elif auth_method in {
        "direct_bearer",
        "direct_custom_header",
        "direct_trusted_network",
        "direct_no_auth",
    }:
        metadata["direct_client_id"] = principal["direct_auth_id"]
        metadata["direct_client_name"] = principal["direct_client_name"]
        if principal.get("client_ip") is not None:
            metadata["client_ip"] = principal["client_ip"]
        # Preserve the legacy metadata key for existing History/tooling consumers.
        metadata["direct_auth_id"] = principal["direct_auth_id"]
    else:
        raise RuntimeError("Authenticated MCP principal is invalid.")
    if result is not None:
        metadata["result"] = result
    if error_type is not None:
        metadata["error_type"] = error_type[:80]

    db.add(
        AuditLog(
            event_type="mcp.tool_called",
            entity_type="mcp_tool",
            entity_id=None,
            actor_type=principal["actor_type"],
            actor_user_id=principal["actor_user_id"],
            summary=(
                f"MCP client called {tool_name} successfully."
                if success
                else f"MCP client call to {tool_name} failed."
            ),
            metadata_json=metadata,
        )
    )


def _ensure_read_tools_enabled(db: Session) -> None:
    scopes = available_scopes(db, require_enabled=True)
    if MCP_SCOPE_READ not in scopes:
        raise RuntimeError("MCP read tools are disabled in Part Pilot settings.")


def _validate_search_arguments(
    *,
    query: str | None,
    stock_status: str,
    part_type_id: int | None,
    location_id: int | None,
    sort_by: str,
    sort_direction: str,
    limit: int,
    offset: int,
) -> str | None:
    normalised_query = None if query is None else " ".join(query.split())
    if normalised_query is not None and len(normalised_query) > 180:
        raise ValueError("query must be 180 characters or fewer.")
    if part_type_id is not None and part_type_id <= 0:
        raise ValueError("part_type_id must be greater than zero.")
    if location_id is not None and location_id <= 0:
        raise ValueError("location_id must be greater than zero.")
    if stock_status not in _STOCK_STATUSES:
        raise ValueError("stock_status must be one of: all, in, low, out.")
    if sort_by not in _SORT_FIELDS:
        raise ValueError("sort_by is unsupported.")
    if sort_direction not in _SORT_DIRECTIONS:
        raise ValueError("sort_direction must be asc or desc.")
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50.")
    if offset < 0:
        raise ValueError("offset cannot be negative.")
    return normalised_query or None


def register_part_tools(server: FastMCP) -> None:
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        name="search_parts",
        title="Search Part Pilot inventory",
        description=(
            "Search active Part Pilot inventory by part number, name, description, "
            "type, manufacturer, location, aliases, tags, package, notes, and typed "
            "custom fields. Returns compact stock-aware rows with bounded pagination."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def search_parts(
        ctx: Context,
        query: Annotated[
            str | None,
            Field(description="Optional universal search text, up to 180 characters."),
        ] = None,
        stock_status: Literal["all", "in", "low", "out"] = "all",
        part_type_id: int | None = None,
        location_id: int | None = None,
        sort_by: Literal[
            "default",
            "part",
            "type",
            "manufacturer",
            "location",
            "available",
            "total",
            "status",
        ] = "default",
        sort_direction: Literal["asc", "desc"] = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> SearchPartsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        db = SessionLocal()
        audit_completed = False
        arguments: dict[str, Any] = {
            "query": None if query is None else query[:180],
            "stock_status": stock_status,
            "part_type_id": part_type_id,
            "location_id": location_id,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
            "limit": limit,
            "offset": offset,
        }
        try:
            _ensure_read_tools_enabled(db)
            normalised_query = _validate_search_arguments(
                query=query,
                stock_status=stock_status,
                part_type_id=part_type_id,
                location_id=location_id,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
                offset=offset,
            )
            collection = list_parts(
                db,
                part_type_id=part_type_id,
                location_id=location_id,
                search=normalised_query,
                stock_status=stock_status,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
                offset=offset,
            )
            items = [_compact_part(part) for part in collection.parts]
            returned = len(items)
            has_more = offset + returned < collection.total
            result = SearchPartsResult(
                summary=(
                    f"Found {collection.total} matching active parts; "
                    f"returning {returned} from offset {offset}."
                ),
                total=collection.total,
                limit=limit,
                offset=offset,
                returned=returned,
                has_more=has_more,
                next_offset=(offset + returned if has_more else None),
                parts=items,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="search_parts",
                success=True,
                arguments={**arguments, "query": normalised_query},
                result={"total": collection.total, "returned": returned},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                try:
                    _append_tool_audit(
                        db,
                        principal=principal,
                        request_id=request_id,
                        tool_name="search_parts",
                        success=False,
                        arguments=arguments,
                        error_type=type(exc).__name__,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
            raise
        finally:
            db.close()

    @server.tool(
        name="get_part_details",
        title="Get exact Part Pilot part details",
        description=(
            "Retrieve one active inventory part by numeric ID, including stock, "
            "pricing, location, manufacturer, package, notes, timestamps, and all "
            "typed custom-field values."
        ),
        annotations=annotations,
        structured_output=True,
    )
    def get_part_details(
        part_id: Annotated[int, Field(description="Positive Part Pilot part ID.")],
        ctx: Context,
    ) -> PartDetailsResult:
        principal = _principal_from_context(ctx)
        request_id = _bounded_request_id(ctx)
        db = SessionLocal()
        audit_completed = False
        arguments = {"part_id": part_id}
        try:
            _ensure_read_tools_enabled(db)
            if part_id <= 0:
                raise ValueError("part_id must be greater than zero.")
            try:
                part = get_part(db, part_id)
            except PartNotFoundError as exc:
                raise ValueError("Active inventory part not found.") from exc
            result = PartDetailsResult(
                summary=(
                    "Retrieved "
                    + (part.name or part.part_number or f"Part {part.id}")
                    + f" (ID {part.id})."
                ),
                stock_status=_stock_status(part),
                part=part,
            )
            _append_tool_audit(
                db,
                principal=principal,
                request_id=request_id,
                tool_name="get_part_details",
                success=True,
                arguments=arguments,
                result={"part_id": part.id},
            )
            db.commit()
            audit_completed = True
            return result
        except Exception as exc:
            db.rollback()
            if not audit_completed:
                try:
                    _append_tool_audit(
                        db,
                        principal=principal,
                        request_id=request_id,
                        tool_name="get_part_details",
                        success=False,
                        arguments=arguments,
                        error_type=type(exc).__name__,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
            raise
        finally:
            db.close()
