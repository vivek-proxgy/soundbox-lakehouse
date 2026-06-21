from __future__ import annotations

from enum import IntEnum


class ApiKeyPolicy(IntEnum):
    """Minimum requirements for API key secrets."""

    MIN_LENGTH = 32
