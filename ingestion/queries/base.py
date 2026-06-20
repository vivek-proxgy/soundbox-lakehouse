"""Base class for soundbox-backend table query specifications."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableExportSpec:
    name: str
    sql: str
    watermark_column: str | None = None
    decrypt_columns: tuple[str, ...] = ()
    column_mapping: dict[str, str] = field(default_factory=dict)
    column_types: dict[str, str] = field(default_factory=dict)
