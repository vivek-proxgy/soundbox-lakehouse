"""Service contracts (ports) for intelligence layer."""

from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class DataQueryPort(Protocol):
    def query_to_df(self, sql: str) -> pd.DataFrame: ...


class IntelligenceQueryPort(Protocol):
    def query_with_ai(self, user_prompt: str) -> dict[str, Any]: ...

    def is_configured(self) -> bool: ...
