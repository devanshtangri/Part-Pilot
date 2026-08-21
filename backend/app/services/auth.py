from __future__ import annotations

import hashlib
import io
import re
import secrets
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import AuditLog, User, UserSession
from app.services.authorization import ROLE_OWNER, ROLE_VIEWER, normalize_user_role

DEFAULT_SESSION_DAYS = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9._]+$")
BUILTIN_AVATAR_IDS = (
    "initials",
    "chip",
    "circuit",
    "terminal",
    "storage",
    "rocket",
)


@dataclass(frozen=True)
class SessionToken:
    token: str
    session: UserSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """Normalize DB datetimes for SQLite-safe auth/session comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("Username cannot be empty")
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("Username can only contain lowercase letters, numbers, period, and underscore")
    return normalized


def normalize_display_name(display_name: str | None, fallback_username: str) -> str:
    normalized = (display_name or "").strip()
    if not normalized:
        normalized = fallback_username
    if len(normalized) > 160:
        raise ValueError("Display name must be 160 characters or fewer")
    return normalized


def normalize_avatar_id(avatar_id: str | None) -> str:
    normalized = (avatar_id or "initials").strip().lower()
    if normalized not in BUILTIN_AVATAR_IDS:
        raise ValueError("Invalid built-in avatar")
    return normalized


def update_user_profile(
    db: Session,
    *,
    user: User,
    username: str,
    display_name: str,
    avatar_id: str,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> User:
    normalized_username = normalize_username(username)
    normalized_display_name = normalize_display_name(
        display_name, normalized_username
    )
    normalized_avatar = normalize_avatar_id(avatar_id)

    existing = db.execute(
        select(User).where(
            User.username == normalized_username,
            User.id != user.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("Username already exists")

    before = {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_id": user.avatar_id,
    }
    after = {
        "username": normalized_username,
        "display_name": normalized_display_name,
        "avatar_id": normalized_avatar,
    }
    changed_fields = [
        key for key in after if before.get(key) != after.get(key)
    ]

    try:
        user.username = normalized_username
        user.display_name = normalized_display_name
        user.avatar_id = normalized_avatar
        if changed_fields:
            db.add(
                AuditLog(
                    event_type="auth.profile_updated",
                    entity_type="user",
                    entity_id=user.id,
                    actor_type="user" if actor_user_id is not None else "system",
                    actor_user_id=actor_user_id,
                    summary="Updated current-user profile",
                    before_json=before,
                    after_json=after,
                    metadata_json={"changed_fields": changed_fields},
                )
            )
        db.flush()
        if commit:
            db.commit()
            db.refresh(user)
    except Exception:
        if commit:
            db.rollback()
        raise
    return user


# PARTPILOT:CUSTOM_AVATAR_SERVICE:V598
MAX_AVATAR_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_AVATAR_SOURCE_PIXELS = 20_000_000
AVATAR_IMAGE_EDGE_PX = 256
AVATAR_IMAGE_MIME = "image/webp"
ALLOWED_AVATAR_SOURCE_FORMATS = {"PNG", "JPEG", "WEBP"}


class AvatarImageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedAvatarImage:
    data: bytes
    mime_type: str
    sha256: str
    size_bytes: int


def normalize_avatar_image(payload: bytes) -> NormalizedAvatarImage:
    if not payload:
        raise AvatarImageValidationError("Avatar image is empty")
    if len(payload) > MAX_AVATAR_UPLOAD_BYTES:
        raise AvatarImageValidationError("Avatar image exceeds the 5 MiB limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as probe:
                source_format = str(probe.format or "").upper()
                width, height = probe.size
                probe.verify()
            if source_format not in ALLOWED_AVATAR_SOURCE_FORMATS:
                raise AvatarImageValidationError(
                    "Avatar image must be PNG, JPEG, or WebP"
                )
            if (
                width < 1
                or height < 1
                or width * height > MAX_AVATAR_SOURCE_PIXELS
            ):
                raise AvatarImageValidationError(
                    "Avatar image dimensions are unsupported"
                )
            with Image.open(io.BytesIO(payload)) as source:
                image = ImageOps.exif_transpose(source)
                if image.width * image.height > MAX_AVATAR_SOURCE_PIXELS:
                    raise AvatarImageValidationError(
                        "Avatar image dimensions are unsupported"
                    )
                has_alpha = (
                    image.mode in {"RGBA", "LA"}
                    or "transparency" in image.info
                )
                image = image.convert("RGBA" if has_alpha else "RGB")
                image = ImageOps.fit(
                    image,
                    (AVATAR_IMAGE_EDGE_PX, AVATAR_IMAGE_EDGE_PX),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                output = io.BytesIO()
                image.save(
                    output,
                    format="WEBP",
                    quality=88,
                    method=6,
                )
    except AvatarImageValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise AvatarImageValidationError("Avatar image is invalid") from exc

    normalized = output.getvalue()
    if not normalized:
        raise AvatarImageValidationError("Avatar image normalization failed")
    digest = hashlib.sha256(normalized).hexdigest()
    return NormalizedAvatarImage(
        data=normalized,
        mime_type=AVATAR_IMAGE_MIME,
        sha256=digest,
        size_bytes=len(normalized),
    )


def _avatar_image_metadata(user: User) -> dict[str, object]:
    present = user.avatar_image_data is not None
    if present:
        if (
            user.avatar_image_mime != AVATAR_IMAGE_MIME
            or not user.avatar_image_sha256
            or user.avatar_image_size_bytes is None
            or user.avatar_image_size_bytes < 1
            or len(user.avatar_image_data or b"") != user.avatar_image_size_bytes
            or hashlib.sha256(user.avatar_image_data or b"").hexdigest()
            != user.avatar_image_sha256
        ):
            raise AvatarImageValidationError(
                "Stored avatar image metadata is inconsistent"
            )
    elif any(
        value is not None
        for value in (
            user.avatar_image_mime,
            user.avatar_image_sha256,
            user.avatar_image_size_bytes,
        )
    ):
        raise AvatarImageValidationError(
            "Stored avatar image metadata is inconsistent"
        )
    return {
        "has_custom_avatar": present,
        "mime_type": user.avatar_image_mime if present else None,
        "sha256": user.avatar_image_sha256 if present else None,
        "size_bytes": user.avatar_image_size_bytes if present else None,
    }


def set_user_avatar_image(
    db: Session,
    *,
    user: User,
    image: NormalizedAvatarImage,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> bool:
    before = _avatar_image_metadata(user)
    if before["sha256"] == image.sha256:
        return False
    try:
        user.avatar_image_data = image.data
        user.avatar_image_mime = image.mime_type
        user.avatar_image_sha256 = image.sha256
        user.avatar_image_size_bytes = image.size_bytes
        after = _avatar_image_metadata(user)
        db.add(
            AuditLog(
                event_type="auth.avatar_image_updated",
                entity_type="user",
                entity_id=user.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Updated current-user profile image",
                before_json=before,
                after_json=after,
                metadata_json={"normalized_edge_px": AVATAR_IMAGE_EDGE_PX},
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(user)
    except Exception:
        if commit:
            db.rollback()
        raise
    return True


def clear_user_avatar_image(
    db: Session,
    *,
    user: User,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> bool:
    before = _avatar_image_metadata(user)
    if not before["has_custom_avatar"]:
        return False
    try:
        user.avatar_image_data = None
        user.avatar_image_mime = None
        user.avatar_image_sha256 = None
        user.avatar_image_size_bytes = None
        after = _avatar_image_metadata(user)
        db.add(
            AuditLog(
                event_type="auth.avatar_image_removed",
                entity_type="user",
                entity_id=user.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Removed current-user profile image",
                before_json=before,
                after_json=after,
                metadata_json=None,
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(user)
    except Exception:
        if commit:
            db.rollback()
        raise
    return True


def user_avatar_image_metadata(user: User) -> dict[str, object]:
    return _avatar_image_metadata(user)


def hash_session_token(token: str) -> str:
    if not token:
        raise ValueError("Session token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def get_user_count(db: Session) -> int:
    return int(db.query(User).count())


def is_setup_complete(db: Session) -> bool:
    return get_user_count(db) > 0


def has_any_user(db: Session) -> bool:
    return db.query(User.id).first() is not None


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    return db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    role: str = ROLE_OWNER,
    commit: bool = True,
) -> User:
    normalized_username = normalize_username(username)
    normalized_display_name = normalize_display_name(display_name, normalized_username)
    normalized_role = normalize_user_role(role)

    if get_user_by_username(db, normalized_username) is not None:
        raise ValueError("Username already exists")

    user = User(
        username=normalized_username,
        display_name=normalized_display_name,
        password_hash=hash_password(password),
        role=normalized_role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    if commit:
        db.commit()
        db.refresh(user)
    return user


def create_first_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    commit: bool = True,
) -> User:
    if is_setup_complete(db):
        raise ValueError("Setup is already complete")
    return create_user(
        db,
        username=username,
        password=password,
        display_name=display_name,
        role=ROLE_OWNER,
        commit=commit,
    )


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    try:
        user = get_user_by_username(db, username)
    except ValueError:
        return None

    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    user.last_login_at = _naive_utc_now()
    db.flush()
    return user


def create_session(
    db: Session,
    *,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
    days: int = DEFAULT_SESSION_DAYS,
    commit: bool = True,
) -> SessionToken:
    if days <= 0:
        raise ValueError("Session duration must be positive")

    token = generate_session_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=_naive_utc_now() + timedelta(days=days),
        revoked_at=None,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.flush()
    if commit:
        db.commit()
        db.refresh(session)
    return SessionToken(token=token, session=session)


def get_session_by_token(db: Session, token: str) -> UserSession | None:
    token_hash = hash_session_token(token)
    return db.execute(select(UserSession).where(UserSession.token_hash == token_hash)).scalar_one_or_none()


def is_session_active(session: UserSession) -> bool:
    expires_at = _to_naive_utc(session.expires_at)
    revoked_at = _to_naive_utc(session.revoked_at)
    return revoked_at is None and expires_at is not None and expires_at > _naive_utc_now()


def get_user_by_session_token(db: Session, token: str) -> User | None:
    session = get_session_by_token(db, token)
    if session is None or not is_session_active(session):
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_user_for_session_token(db: Session, token: str) -> User | None:
    return get_user_by_session_token(db, token)


def logout_session(db: Session, token: str, *, commit: bool = True) -> bool:
    session = get_session_by_token(db, token)
    if session is None:
        return False
    if session.revoked_at is None:
        session.revoked_at = _naive_utc_now()
        db.flush()
        if commit:
            db.commit()
    return True


def revoke_session(db: Session, token: str, *, commit: bool = True) -> bool:
    return logout_session(db, token, commit=commit)

# PARTPILOT:PASSWORD_SESSION_ADMIN_SERVICE:V584
class CurrentPasswordInvalidError(ValueError):
    pass


class PasswordReuseError(ValueError):
    pass


class CurrentSessionUnavailableError(ValueError):
    pass


class SessionNotFoundError(LookupError):
    pass


class CurrentSessionRevocationError(ValueError):
    pass


def require_current_session(
    db: Session,
    *,
    user: User,
    token: str,
) -> UserSession:
    session = get_session_by_token(db, token)
    if (
        session is None
        or session.user_id != user.id
        or not is_session_active(session)
    ):
        raise CurrentSessionUnavailableError("Current session is unavailable")
    return session


def list_user_sessions(
    db: Session,
    *,
    user: User,
    current_session: UserSession,
) -> list[UserSession]:
    if current_session.user_id != user.id or not is_session_active(current_session):
        raise CurrentSessionUnavailableError("Current session is unavailable")

    sessions = list(
        db.execute(
            select(UserSession).where(UserSession.user_id == user.id)
        ).scalars()
    )
    sessions.sort(
        key=lambda item: _to_naive_utc(item.created_at) or datetime.min,
        reverse=True,
    )
    sessions.sort(
        key=lambda item: (
            0
            if item.id == current_session.id
            else (1 if is_session_active(item) else 2)
        )
    )
    return sessions


def change_password(
    db: Session,
    *,
    user: User,
    current_session: UserSession,
    current_password: str,
    new_password: str,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> int:
    if current_session.user_id != user.id or not is_session_active(current_session):
        raise CurrentSessionUnavailableError("Current session is unavailable")
    if not verify_password(current_password, user.password_hash):
        raise CurrentPasswordInvalidError("Current password is incorrect")
    if len(new_password) < 8 or len(new_password) > 256:
        raise ValueError("New password must be between 8 and 256 characters")
    if verify_password(new_password, user.password_hash):
        raise PasswordReuseError("New password must be different from the current password")

    new_password_hash = hash_password(new_password)
    now = _naive_utc_now()
    other_active_sessions = list(
        db.execute(
            select(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.id != current_session.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        ).scalars()
    )

    try:
        user.password_hash = new_password_hash
        for session in other_active_sessions:
            session.revoked_at = now

        db.add(
            AuditLog(
                event_type="auth.password_changed",
                entity_type="user",
                entity_id=user.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Changed account password",
                before_json=None,
                after_json=None,
                metadata_json={
                    "revoked_other_sessions": len(other_active_sessions),
                    "preserved_current_session_id": current_session.id,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(user)
            db.refresh(current_session)
    except Exception:
        if commit:
            db.rollback()
        raise

    return len(other_active_sessions)


def revoke_user_session(
    db: Session,
    *,
    user: User,
    current_session: UserSession,
    session_id: int,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> tuple[UserSession, bool]:
    if current_session.user_id != user.id or not is_session_active(current_session):
        raise CurrentSessionUnavailableError("Current session is unavailable")

    target = db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
        )
    ).scalar_one_or_none()
    if target is None:
        raise SessionNotFoundError("Session not found")
    if target.id == current_session.id:
        raise CurrentSessionRevocationError(
            "Use logout to end the current session"
        )
    if target.revoked_at is not None:
        return target, False

    was_active = is_session_active(target)
    try:
        target.revoked_at = _naive_utc_now()
        db.add(
            AuditLog(
                event_type="auth.session_revoked",
                entity_type="session",
                entity_id=target.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Revoked account session",
                before_json=None,
                after_json=None,
                metadata_json={
                    "target_session_id": target.id,
                    "was_active": was_active,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(target)
    except Exception:
        if commit:
            db.rollback()
        raise

    return target, True


def revoke_all_other_sessions(
    db: Session,
    *,
    user: User,
    current_session: UserSession,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> int:
    if current_session.user_id != user.id or not is_session_active(current_session):
        raise CurrentSessionUnavailableError("Current session is unavailable")

    now = _naive_utc_now()
    targets = list(
        db.execute(
            select(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.id != current_session.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        ).scalars()
    )
    if not targets:
        return 0

    try:
        for session in targets:
            session.revoked_at = now
        db.add(
            AuditLog(
                event_type="auth.other_sessions_revoked",
                entity_type="user",
                entity_id=user.id,
                actor_type="user" if actor_user_id is not None else "system",
                actor_user_id=actor_user_id,
                summary="Revoked all other active sessions",
                before_json=None,
                after_json=None,
                metadata_json={
                    "revoked_sessions": len(targets),
                    "preserved_current_session_id": current_session.id,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(current_session)
    except Exception:
        if commit:
            db.rollback()
        raise

    return len(targets)
