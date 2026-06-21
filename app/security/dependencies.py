"""FastAPI security dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import Settings, get_settings
from app.core.http_errors import forbidden, unauthorized
from app.core.messages.error_messages import ErrorMessage
from app.routes.enums.api_path import ApiPath
from app.security.auth import AuthContext, decode_access_token, validate_api_key
from app.security.enums.api_header import ApiHeader
from app.security.enums.auth_method import AuthMethod
from app.security.enums.auth_role import AuthRole

_bearer = HTTPBearer(auto_error=False)


def get_auth_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias=ApiHeader.API_KEY.value)] = None,
) -> AuthContext | None:
    if request.url.path in ApiPath.public_paths():
        return None

    if not settings.auth_enabled:
        return AuthContext(
            user_id=settings.anonymous_user_id,
            session_id=None,
            role=None,
            org_id=None,
            auth_method=AuthMethod.DISABLED,
        )

    if x_api_key:
        ctx = validate_api_key(x_api_key, settings)
    elif credentials and credentials.credentials:
        if settings.auth_api_key_only:
            raise unauthorized(ErrorMessage.API_KEY_REQUIRED.value)
        ctx = decode_access_token(credentials.credentials, settings)
    else:
        raise unauthorized(ErrorMessage.AUTH_REQUIRED.value)

    request.state.user_id = ctx.user_id
    request.state.org_id = ctx.org_id
    return ctx


def require_auth(
    ctx: Annotated[AuthContext | None, Depends(get_auth_context)],
) -> AuthContext:
    if ctx is None:
        raise unauthorized(ErrorMessage.AUTH_REQUIRED.value)
    return ctx


def require_privileged_role(
    ctx: Annotated[AuthContext, Depends(require_auth)],
) -> AuthContext:
    if ctx.role not in AuthRole.privileged_roles():
        raise forbidden(ErrorMessage.FORBIDDEN.value)
    return ctx
