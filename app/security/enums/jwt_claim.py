from __future__ import annotations

from enum import StrEnum


class JwtClaim(StrEnum):
    """JWT payload claim names shared with on-prem-soundbox-backend."""

    ID = "id"
    SUB = "sub"
    SESSION_ID = "sessionId"
    TYPE = "type"
    ROLE = "role"
    ORGANIZATION_ID = "organizationId"
    ORG_ID = "org_id"
    EXP = "exp"
