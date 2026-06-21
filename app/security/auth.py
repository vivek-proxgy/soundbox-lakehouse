"""JWT validation compatible with on-prem-soundbox-backend access tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import HTTPException

from app.config.settings import Settings
from app.core.http_errors import unauthorized
from app.core.messages.error_messages import ErrorMessage
from app.security.enums.auth_method import AuthMethod
from app.security.enums.auth_role import AuthRole
from app.security.enums.jwt_claim import JwtClaim
from app.security.enums.token_type import TokenType


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    session_id: str | None
    role: AuthRole | None
    org_id: str | None
    auth_method: AuthMethod


def decode_access_token(token: str, settings: Settings) -> AuthContext:
    secret = settings.auth_jwt_secret
    if not secret:
        raise unauthorized(ErrorMessage.AUTH_NOT_CONFIGURED.value)

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": [JwtClaim.EXP.value, JwtClaim.SUB.value]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized(ErrorMessage.TOKEN_EXPIRED.value) from exc
    except jwt.InvalidTokenError as exc:
        raise unauthorized(ErrorMessage.TOKEN_INVALID.value) from exc

    token_type = payload.get(JwtClaim.TYPE.value)
    if token_type and token_type != TokenType.ACCESS.value:
        raise unauthorized(ErrorMessage.TOKEN_TYPE_INVALID.value)

    user_id = payload.get(JwtClaim.ID.value) or payload.get(JwtClaim.SUB.value)
    if not user_id:
        raise unauthorized(ErrorMessage.TOKEN_PAYLOAD_INVALID.value)

    raw_role = payload.get(JwtClaim.ROLE.value)
    role = AuthRole(raw_role) if raw_role in AuthRole._value2member_map_ else None

    return AuthContext(
        user_id=str(user_id),
        session_id=payload.get(JwtClaim.SESSION_ID.value),
        role=role,
        org_id=payload.get(JwtClaim.ORGANIZATION_ID.value) or payload.get(JwtClaim.ORG_ID.value),
        auth_method=AuthMethod.JWT,
    )


def validate_api_key(api_key: str, settings: Settings) -> AuthContext:
    expected = settings.lakehouse_api_key
    if not expected:
        raise unauthorized(ErrorMessage.API_KEY_NOT_CONFIGURED.value)
    if api_key != expected:
        raise unauthorized(ErrorMessage.API_KEY_INVALID.value)

    return AuthContext(
        user_id=settings.service_user_id,
        session_id=None,
        role=AuthRole.SERVICE,
        org_id=None,
        auth_method=AuthMethod.API_KEY,
    )
