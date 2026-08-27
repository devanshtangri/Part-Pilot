from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import AuditLog, User, UserSession
from app.services.auth import create_user
from app.services.authorization import (
    ROLE_ADMINISTRATOR,
    ROLE_OWNER,
    can_manage_user_role,
    normalize_user_role,
    require_minimum_role,
)

# PARTPILOT:USER_ROLE_ADMIN_SERVICE:V732
class UserAdministrationError(ValueError):
    pass


class UserAdministrationForbiddenError(PermissionError):
    pass


class ManagedUserNotFoundError(LookupError):
    pass


def _target(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ManagedUserNotFoundError("User not found.")
    return user


def _require_admin(actor: User) -> None:
    try:
        require_minimum_role(actor, ROLE_ADMINISTRATOR)
    except PermissionError as exc:
        raise UserAdministrationForbiddenError(str(exc)) from exc


def _require_manageable(actor: User, target: User, requested_role: str | None = None) -> None:
    _require_admin(actor)
    if not can_manage_user_role(actor.role, target.role):
        raise UserAdministrationForbiddenError(
            "Your role cannot administer this user."
        )
    if requested_role is not None and not can_manage_user_role(actor.role, requested_role):
        raise UserAdministrationForbiddenError(
            "Your role cannot assign the requested role."
        )


def _bootstrap_owner_id(db: Session) -> int:
    owner_id = db.execute(select(User.id).order_by(User.id.asc()).limit(1)).scalar_one_or_none()
    if owner_id is None:
        raise UserAdministrationError("The bootstrap Owner account is missing.")
    return int(owner_id)


def _is_bootstrap_owner(db: Session, user: User) -> bool:
    return user.id == _bootstrap_owner_id(db)


def _active_owner_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(User.id)).where(
                User.role == ROLE_OWNER,
                User.is_active.is_(True),
            )
        ).scalar_one()
    )


def _protect_last_owner(db: Session, target: User, *, next_role: str | None = None, next_active: bool | None = None, deleting: bool = False) -> None:
    if target.role != ROLE_OWNER or not target.is_active:
        return
    removes_owner = deleting
    if next_role is not None and normalize_user_role(next_role) != ROLE_OWNER:
        removes_owner = True
    if next_active is False:
        removes_owner = True
    if removes_owner and _active_owner_count(db) <= 1:
        raise UserAdministrationError(
            "The last active Owner cannot be disabled, deleted, or demoted."
        )


def list_managed_users(db: Session, *, actor: User) -> list[User]:
    _require_admin(actor)
    return list(db.execute(select(User).order_by(User.created_at.asc(), User.id.asc())).scalars())


def create_managed_user(db: Session, *, actor: User, username: str, display_name: str, password: str, role: str, commit: bool = True) -> User:
    _require_admin(actor)
    normalized_role = normalize_user_role(role)
    if normalized_role == ROLE_OWNER:
        raise UserAdministrationForbiddenError(
            "Owner is reserved for the account created during initial setup."
        )
    if not can_manage_user_role(actor.role, normalized_role):
        raise UserAdministrationForbiddenError(
            "Your role cannot create a user with the requested role."
        )
    try:
        user = create_user(
            db,
            username=username,
            display_name=display_name,
            password=password,
            role=normalized_role,
            commit=False,
        )
        db.add(AuditLog(
            event_type="auth.user_created",
            entity_type="user",
            entity_id=user.id,
            actor_type="user",
            actor_user_id=actor.id,
            summary=f"Created user {user.username} with role {user.role}.",
            before_json=None,
            after_json={"username": user.username, "display_name": user.display_name, "role": user.role, "is_active": True},
            metadata_json=None,
        ))
        db.flush()
        if commit:
            db.commit(); db.refresh(user)
        return user
    except Exception:
        if commit: db.rollback()
        raise


def update_managed_user_access(db: Session, *, actor: User, user_id: int, role: str | None, is_active: bool | None, commit: bool = True) -> User:
    target = _target(db, user_id)
    normalized_role = normalize_user_role(role) if role is not None else target.role
    if role is None and is_active is None:
        raise UserAdministrationError("At least one access change is required.")
    _require_manageable(actor, target, normalized_role)
    bootstrap_owner = _is_bootstrap_owner(db, target)
    if normalized_role == ROLE_OWNER and not bootstrap_owner:
        raise UserAdministrationForbiddenError(
            "Owner is reserved for the account created during initial setup."
        )
    if bootstrap_owner and normalized_role != ROLE_OWNER:
        raise UserAdministrationError(
            "The primary Owner account cannot be demoted."
        )
    if bootstrap_owner and is_active is False:
        raise UserAdministrationError(
            "The primary Owner account cannot be disabled."
        )
    if target.id == actor.id and is_active is False:
        raise UserAdministrationError("You cannot disable your current account.")
    _protect_last_owner(db, target, next_role=normalized_role, next_active=is_active)
    before = {"role": target.role, "is_active": target.is_active}
    after = {
        "role": normalized_role,
        "is_active": target.is_active if is_active is None else is_active,
    }
    if before == after:
        return target
    try:
        target.role = normalized_role
        target.is_active = bool(after["is_active"])
        if not target.is_active:
            db.execute(
                update(UserSession)
                .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
                .values(revoked_at=func.current_timestamp())
            )
        db.add(AuditLog(
            event_type="auth.user_access_updated",
            entity_type="user",
            entity_id=target.id,
            actor_type="user",
            actor_user_id=actor.id,
            summary=f"Updated access for {target.username}.",
            before_json=before,
            after_json=after,
            metadata_json=None,
        ))
        db.flush()
        if commit:
            db.commit(); db.refresh(target)
        return target
    except Exception:
        if commit: db.rollback()
        raise


def force_reset_managed_user_password(db: Session, *, actor: User, user_id: int, new_password: str, commit: bool = True) -> int:
    target = _target(db, user_id)
    _require_manageable(actor, target)
    if len(new_password) < 8 or len(new_password) > 256:
        raise UserAdministrationError("New password must be 8-256 characters.")
    try:
        target.password_hash = hash_password(new_password)
        result = db.execute(
            update(UserSession)
            .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=func.current_timestamp())
        )
        revoked = int(result.rowcount or 0)
        db.add(AuditLog(
            event_type="auth.user_password_force_reset",
            entity_type="user",
            entity_id=target.id,
            actor_type="user",
            actor_user_id=actor.id,
            summary=f"Force-reset password for {target.username}.",
            before_json=None,
            after_json=None,
            metadata_json={"revoked_sessions": revoked},
        ))
        db.flush()
        if commit: db.commit()
        return revoked
    except Exception:
        if commit: db.rollback()
        raise


def revoke_managed_user_sessions(db: Session, *, actor: User, user_id: int, commit: bool = True) -> int:
    target = _target(db, user_id)
    _require_manageable(actor, target)
    try:
        result = db.execute(
            update(UserSession)
            .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=func.current_timestamp())
        )
        revoked = int(result.rowcount or 0)
        db.add(AuditLog(
            event_type="auth.user_sessions_revoked",
            entity_type="user",
            entity_id=target.id,
            actor_type="user",
            actor_user_id=actor.id,
            summary=f"Revoked sessions for {target.username}.",
            before_json=None,
            after_json=None,
            metadata_json={"revoked_sessions": revoked},
        ))
        db.flush()
        if commit: db.commit()
        return revoked
    except Exception:
        if commit: db.rollback()
        raise


def delete_managed_user(db: Session, *, actor: User, user_id: int, confirmation_username: str, commit: bool = True) -> None:
    target = _target(db, user_id)
    _require_manageable(actor, target)
    if _is_bootstrap_owner(db, target):
        raise UserAdministrationError(
            "The primary Owner account cannot be deleted."
        )
    if target.id == actor.id:
        raise UserAdministrationError("You cannot delete your current account.")
    if confirmation_username.strip().lower() != target.username:
        raise UserAdministrationError("Confirmation username does not match.")
    _protect_last_owner(db, target, deleting=True)
    snapshot = {"username": target.username, "display_name": target.display_name, "role": target.role, "is_active": target.is_active}
    try:
        db.add(AuditLog(
            event_type="auth.user_deleted",
            entity_type="user",
            entity_id=target.id,
            actor_type="user",
            actor_user_id=actor.id,
            summary=f"Deleted user {target.username}.",
            before_json=snapshot,
            after_json=None,
            metadata_json=None,
        ))
        db.delete(target)
        db.flush()
        if commit: db.commit()
    except Exception:
        if commit: db.rollback()
        raise
