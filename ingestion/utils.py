"""Shared ingestion utility functions for both Pandas and Spark engines."""

from __future__ import annotations

import time
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

import pandas as pd

from app.config.settings import Settings
from ingestion.queries.base import TableExportSpec
from ingestion.watermark import read_watermark, write_watermark

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def get_watermark_since(spec: TableExportSpec, settings: Settings) -> datetime | None:
    """Retrieve the latest watermark timestamp in incremental mode."""
    if settings.ingest_mode == "incremental" and spec.watermark_column:
        return read_watermark(spec.name, settings)
    return None


def apply_watermark_filter(
    sql: str,
    watermark_column: str | None,
    since: datetime | None,
    param_style: str = "param",
) -> str:
    """Append watermark filter to raw SQL query string.

    If param_style is 'param', uses '%s' placeholder (for psycopg2).
    If param_style is 'literal', formats the ISO string directly (for Spark/JDBC).
    """
    if since is None or not watermark_column:
        return sql.strip()

    if param_style == "param":
        return f"{sql.strip()}\n  AND {watermark_column} > %s"
    else:
        return f"{sql.strip()}\n  AND {watermark_column} > '{since.isoformat()}'"


def write_local_snapshot(
    df: pd.DataFrame | DataFrame,
    table: str,
    settings: Settings,
) -> Path | str | None:
    """Write local parquet snapshots for DuckDB testing, supporting both Pandas and Spark DataFrames."""
    if not settings.write_local_parquet:
        return None

    is_pandas = isinstance(df, pd.DataFrame)
    if is_pandas:
        if df.empty:
            print(f"[ingest-local] Skip empty Pandas table {table}")
            return None
    else:
        if df.isEmpty():
            print(f"[ingest-local] Skip empty Spark table {table}")
            return None

    dest_dir = Path(settings.lakehouse_local_root) / table
    dest_dir.mkdir(parents=True, exist_ok=True)

    if is_pandas:
        if settings.ingest_mode == "incremental":
            timestamp = int(time.time())
            output = dest_dir / f"{table}_{timestamp}.parquet"
        else:
            for existing in dest_dir.glob("*.parquet"):
                existing.unlink()
            output = dest_dir / f"{table}_full.parquet"
        df.to_parquet(output, index=False, engine="pyarrow")
        print(f"[pandas-ingest] Wrote local parquet: {len(df):,} rows -> {output}")
        return output
    else:
        path = f"{settings.lakehouse_local_root}/{table}"
        write_mode = "append" if settings.ingest_mode == "incremental" else "overwrite"
        df.write.mode(write_mode).parquet(path)
        print(f"[spark-parquet] Wrote snapshot (mode={write_mode}) -> {path}")
        return path


def update_watermark_if_incremental(
    df: pd.DataFrame | DataFrame,
    spec: TableExportSpec,
    settings: Settings,
) -> None:
    """Compute the maximum watermark column value and save it in incremental mode."""
    if settings.ingest_mode != "incremental" or not spec.watermark_column:
        return

    is_pandas = isinstance(df, pd.DataFrame)
    latest = None

    if is_pandas:
        if not df.empty and spec.watermark_column in df.columns:
            latest_val = pd.to_datetime(df[spec.watermark_column]).max()
            if pd.notna(latest_val):
                latest = latest_val.to_pydatetime()
    else:
        if not df.isEmpty() and spec.watermark_column in df.columns:
            agg_result = df.agg({spec.watermark_column: "max"}).collect()
            if agg_result and agg_result[0][0] is not None:
                latest = agg_result[0][0]
                if isinstance(latest, str):
                    latest = datetime.fromisoformat(latest.replace("Z", "+00:00"))

    if latest is not None:
        write_watermark(spec.name, latest, settings)


def camel_to_snake(name: str) -> str:
    """Convert camelCase string to snake_case, also stripping leading underscores."""
    name = name.lstrip('_')
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def conform_dataframe_schema(
    df: pd.DataFrame | DataFrame,
    spec: TableExportSpec,
) -> pd.DataFrame | DataFrame:
    """Normalize column names (renaming mappings and auto-formatting snake_case) and apply target casts."""
    is_pandas = isinstance(df, pd.DataFrame)
    mapping = spec.column_mapping or {}
    
    # 1. Determine column renaming mapping
    rename_map = {}
    cols = list(df.columns) if is_pandas else df.columns
    
    for col in cols:
        if col in mapping:
            rename_map[col] = mapping[col]
        else:
            snake_name = camel_to_snake(col)
            if snake_name != col:
                rename_map[col] = snake_name

    # 2. Rename columns in DataFrame
    if rename_map:
        if is_pandas:
            df = df.rename(columns=rename_map)
        else:
            for src, dest in rename_map.items():
                if src in df.columns:
                    df = df.withColumnRenamed(src, dest)

    # 3. Apply explicit target column type casts if specified
    types = spec.column_types or {}
    for col, target_type in types.items():
        if col in df.columns:
            if is_pandas:
                if target_type == "string":
                    df[col] = df[col].astype(str)
                elif target_type == "double":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
            else:
                from pyspark.sql import functions as F
                if target_type == "string":
                    df = df.withColumn(col, F.col(col).cast("string"))
                elif target_type == "double":
                    df = df.withColumn(col, F.col(col).cast("double"))

    return df
