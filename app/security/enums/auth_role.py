from __future__ import annotations

from enum import StrEnum


class AuthRole(StrEnum):
    """AuthenticationRoles."""

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    CHECKER = "checker"
    MAKER = "maker"
    USER = "user"
    MERCHANT = "merchant"
    SERVICE = "service"

    @classmethod
    def privileged_roles(cls) -> frozenset[AuthRole]:
        return frozenset({cls.SUPERADMIN, cls.ADMIN, cls.SERVICE})
