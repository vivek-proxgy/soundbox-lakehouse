"""Queries package containing query specifications for ingestion tables."""

from __future__ import annotations

from ingestion.queries.base import TableExportSpec
from ingestion.queries.merchants import MERCHANTS_SPEC
from ingestion.queries.transactions import TRANSACTIONS_SPEC
from ingestion.queries.device_telemetry import TELEMETRY_SPEC

EXPORT_TABLES: tuple[TableExportSpec, ...] = (
    MERCHANTS_SPEC,
    TRANSACTIONS_SPEC,
    TELEMETRY_SPEC,
)

__all__ = (
    "TableExportSpec",
    "MERCHANTS_SPEC",
    "TRANSACTIONS_SPEC",
    "TELEMETRY_SPEC",
    "EXPORT_TABLES",
)
