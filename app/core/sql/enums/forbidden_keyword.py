from __future__ import annotations

from enum import StrEnum


class SqlForbiddenKeyword(StrEnum):
    """Destructive or non-read SQL keywords blocked at query time."""

    DROP = "DROP"
    DELETE = "DELETE"
    UPDATE = "UPDATE"
    INSERT = "INSERT"
    ALTER = "ALTER"
    CREATE = "CREATE"
    TRUNCATE = "TRUNCATE"
    RENAME = "RENAME"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    ATTACH = "ATTACH"
    COPY = "COPY"
    LOAD = "LOAD"
    INSTALL = "INSTALL"
    EXPORT = "EXPORT"
    PRAGMA = "PRAGMA"
    CALL = "CALL"
    EXEC = "EXEC"
    EXECUTE = "EXECUTE"

    @classmethod
    def all_keywords(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
