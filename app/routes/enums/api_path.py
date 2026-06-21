from __future__ import annotations

from enum import StrEnum


class ApiPath(StrEnum):
    """Registered API paths — single source of truth for routing and middleware."""

    HEALTH = "/health"
    READY = "/ready"
    DOCS = "/docs"
    REDOC = "/redoc"
    OPENAPI = "/openapi.json"

    INTELLIGENCE_ASK = "/api/v1/intelligence/ask"
    INTELLIGENCE_SQL = "/api/v1/intelligence/sql"
    INTELLIGENCE_COPILOT_QUERY = "/api/v1/intelligence/copilot/query"
    INTELLIGENCE_COPILOT_EXPORT_EXCEL = "/api/v1/intelligence/copilot/export/excel"
    INTELLIGENCE_COPILOT_EXPORT_PDF = "/api/v1/intelligence/copilot/export/pdf"

    INTERNAL_INGEST = "/api/v1/internal/ingest"

    @classmethod
    def public_paths(cls) -> frozenset[str]:
        return frozenset({cls.HEALTH, cls.READY, cls.DOCS, cls.REDOC, cls.OPENAPI})

    @classmethod
    def rate_limit_exempt_paths(cls) -> frozenset[str]:
        return cls.public_paths()

    @classmethod
    def audit_path_fragments(cls) -> frozenset[str]:
        return frozenset({"/intelligence/", "/internal/"})
