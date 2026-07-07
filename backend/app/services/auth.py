from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User, UserSession

DEFAULT_SESSION_DAYS = 30


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
    return normalized


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


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = normalize_username(username)
    return db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()


def create_user(db: Session, *, username: str, password: str, commit: bool = True) -> User:
    normalized = normalize_username(username)
    if get_user_by_username(db, normalized) is not None:
        raise ValueError("Username already exists")

    user = User(
        username=normalized,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    if commit:
        db.commit()
        db.refresh(user)
    return user


def create_first_user(db: Session, *, username: str, password: str, commit: bool = True) -> User:
    if is_setup_complete(db):
        raise ValueError("Setup is already complete")
    return create_user(db, username=username, password=password, commit=commit)


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
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


def has_any_user(db: Session) -> bool:
    return db.query(User.id).first() is not None

