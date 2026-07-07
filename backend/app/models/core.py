from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)


class PartType(Base, TimestampMixin):
    __tablename__ = "part_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PartTypeField(Base, TimestampMixin):
    __tablename__ = "part_type_fields"
    __table_args__ = (
        UniqueConstraint("part_type_id", "field_key", name="uq_part_type_fields_type_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_type_id: Mapped[int] = mapped_column(ForeignKey("part_types.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    field_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    options_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    default_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    normalized_name: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Part(Base, TimestampMixin):
    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint(
            "(name IS NOT NULL AND length(trim(name)) > 0) OR "
            "(part_number IS NOT NULL AND length(trim(part_number)) > 0)",
            name="ck_parts_name_or_part_number",
        ),
        CheckConstraint("total_quantity >= 0", name="ck_parts_total_quantity_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_parts_reserved_quantity_nonnegative"),
        CheckConstraint("reserved_quantity <= total_quantity", name="ck_parts_reserved_lte_total"),
        UniqueConstraint("part_number", name="uq_parts_part_number"),
        Index("ix_parts_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_type_id: Mapped[int] = mapped_column(ForeignKey("part_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    part_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    package: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    quantity_purchased: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    low_stock_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PartFieldValue(Base, TimestampMixin):
    __tablename__ = "part_field_values"
    __table_args__ = (
        UniqueConstraint("part_id", "field_id", name="uq_part_field_values_part_field"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("part_type_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_bool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)


class PartTag(Base):
    __tablename__ = "part_tags"
    __table_args__ = (
        UniqueConstraint("part_id", "tag_id", name="uq_part_tags_part_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PartAlias(Base, TimestampMixin):
    __tablename__ = "aliases"
    __table_args__ = (
        UniqueConstraint("part_id", "alias", name="uq_aliases_part_alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(180), nullable=False, index=True)


class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(180), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    estimated_total_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)


class ProjectItem(Base, TimestampMixin):
    __tablename__ = "project_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_reserved_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)


class ReservationItem(Base, TimestampMixin):
    __tablename__ = "reservation_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_reservation_items_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(40), default="system", nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="created", nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
