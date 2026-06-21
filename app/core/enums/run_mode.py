from __future__ import annotations

from enum import IntEnum, StrEnum


class RunMode(StrEnum):
    """Process run mode — must be set explicitly via RUN_MODE env."""

    SERVER = "server"
    INGEST = "ingest"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(mode.value for mode in cls)


class ServerDefaults(IntEnum):
    """Default server runtime values."""

    PORT = 8080


# Cloud Run / Docker require binding all interfaces for ingress routing.
DEFAULT_BIND_HOST = "0.0.0.0"
