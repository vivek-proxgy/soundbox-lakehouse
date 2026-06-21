from __future__ import annotations

from enum import StrEnum


class ApiHeader(StrEnum):
    API_KEY = "X-API-Key"
    REQUEST_ID = "X-Request-ID"
    AUTHORIZATION = "Authorization"
