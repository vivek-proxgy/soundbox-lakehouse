from __future__ import annotations

from enum import StrEnum


class AuthMethod(StrEnum):
    JWT = "jwt"
    API_KEY = "api_key"
    DISABLED = "disabled"
