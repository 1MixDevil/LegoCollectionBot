"""Роли и доступ к функциям бота."""

from typing import Final

ROLE_ADMIN: Final = "admin"
ROLE_MEMBER: Final = "member"
ROLE_PREMIUM: Final = "premium"

VALID_ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM})

ROLE_LABELS = {
    ROLE_ADMIN: "Администратор",
    ROLE_MEMBER: "Участник",
    ROLE_PREMIUM: "Premium",
}

# Функции → роли, которым разрешено
FEATURES: dict[str, frozenset[str]] = {
    "my_collection": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "add": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "photo_search": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "figure_card": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "wishlist": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "settings": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "help": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "marketplace": frozenset({ROLE_ADMIN}),
    "tierlist": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "tierlist_serials": frozenset({ROLE_ADMIN, ROLE_MEMBER, ROLE_PREMIUM}),
    "tierlist_keyword": frozenset({ROLE_ADMIN, ROLE_PREMIUM}),
    "tierlist_all": frozenset({ROLE_ADMIN, ROLE_PREMIUM}),
    "update_catalog": frozenset({ROLE_ADMIN}),
    "admin_panel": frozenset({ROLE_ADMIN}),
}


def normalize_role(role: str | None) -> str:
    if role in VALID_ROLES:
        return role
    return ROLE_MEMBER


def can_access(role: str | None, feature: str) -> bool:
    role = normalize_role(role)
    allowed = FEATURES.get(feature)
    if not allowed:
        return False
    return role in allowed
