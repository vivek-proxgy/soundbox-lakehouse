"""Write Spark DataFrames to Iceberg tables on GCS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def iceberg_table_name(table: str, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    return f"{cfg.iceberg_table_prefix}.{table}"


def append_to_iceberg(
    df: DataFrame,
    table: str,
    settings: Settings | None = None,
) -> int:
    if df.isEmpty():
        return 0

    cfg = settings or get_settings()
    cfg.require_gcs()
    target = iceberg_table_name(table, cfg)
    count = df.count()
    spark = df.sparkSession
    if not spark.catalog.tableExists(target):
        df.writeTo(target).using("iceberg").tableProperty("write-format", "parquet").create()
    else:
        df.writeTo(target).append()
    print(f"[spark-iceberg] Appended {count:,} rows -> {target}")
    return count


def write_local_parquet_snapshot(
    df: DataFrame,
    table: str,
    settings: Settings | None = None,
) -> None:
    """Optional DuckDB-friendly snapshot (sample / latest partition only at scale)."""
    cfg = settings or get_settings()
    if not cfg.write_local_parquet or df.isEmpty():
        return
    path = f"{cfg.lakehouse_local_root}/{table}"
    df.write.mode("overwrite").parquet(path)
    print(f"[spark-parquet] Wrote snapshot -> {path}")
