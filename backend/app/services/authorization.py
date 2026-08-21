from __future__ import annotations

from collections.abc import Iterable

# PARTPILOT:USER_ROLE_AUTHORIZATION:V732
ROLE_OWNER = "owner"
ROLE_ADMINISTRATOR = "administrator"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
USER_ROLES = (ROLE_OWNER, ROLE_ADMINISTRATOR, ROLE_OPERATOR, ROLE_VIEWER)
ROLE_LEVELS = {
    ROLE_VIEWER: 10,
    ROLE_OPERATOR: 20,
    ROLE_ADMINISTRATOR: 30,
    ROLE_OWNER: 40,
}

REST_SCOPE_MINIMUM_ROLE = {
    "inventory:read": ROLE_VIEWER,
    "inventory:write": ROLE_OPERATOR,
    "catalogues:read": ROLE_VIEWER,
    "catalogues:write": ROLE_OPERATOR,
    "projects:read": ROLE_VIEWER,
    "projects:write": ROLE_OPERATOR,
    "reservations:read": ROLE_VIEWER,
    "reservations:write": ROLE_OPERATOR,
    "history:read": ROLE_VIEWER,
}


class RoleAuthorizationError(PermissionError):
    pass


def normalize_user_role(value: str) -> str:
    role = (value or "").strip().lower()
    if role not in ROLE_LEVELS:
        raise ValueError(f"Unsupported user role: {value!r}")
    return role


def role_at_least(role: str, minimum_role: str) -> bool:
    normalized_role = normalize_user_role(role)
    normalized_minimum = normalize_user_role(minimum_role)
    return ROLE_LEVELS[normalized_role] >= ROLE_LEVELS[normalized_minimum]


def require_minimum_role(user, minimum_role: str) -> None:
    role = normalize_user_role(getattr(user, "role", ""))
    if not role_at_least(role, minimum_role):
        raise RoleAuthorizationError(
            f"The {role} role does not grant this operation."
        )


def require_rest_scope_role(user, scope: str) -> None:
    minimum_role = REST_SCOPE_MINIMUM_ROLE.get(scope)
    if minimum_role is None:
        raise RoleAuthorizationError(
            f"No role policy is registered for REST scope {scope!r}."
        )
    require_minimum_role(user, minimum_role)


def allowed_rest_scopes_for_role(role: str, scopes: Iterable[str]) -> list[str]:
    normalized_role = normalize_user_role(role)
    allowed: list[str] = []
    for scope in scopes:
        minimum = REST_SCOPE_MINIMUM_ROLE.get(scope)
        if minimum is not None and role_at_least(normalized_role, minimum):
            allowed.append(scope)
    return allowed


def can_manage_user_role(actor_role: str, target_role: str) -> bool:
    actor = normalize_user_role(actor_role)
    target = normalize_user_role(target_role)
    if actor == ROLE_OWNER:
        return True
    return actor == ROLE_ADMINISTRATOR and target in {
        ROLE_OPERATOR,
        ROLE_VIEWER,
    }
