"""Parallel JDBC reads from soundbox Postgres into Spark DataFrames."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.config.settings import Settings, get_settings
from app.ingestion.queries import TableExportSpec
from app.ingestion.watermark_store import read_watermark

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


def _filtered_sql(spec: TableExportSpec, since: datetime | None) -> str:
    sql = spec.sql.strip()
    if since is not None and spec.watermark_column:
        sql = f"{sql}\n  AND {spec.watermark_column} > TIMESTAMP '{since.isoformat()}'"
    return sql


def _jdbc_subquery(spec: TableExportSpec, since: datetime | None) -> str:
    return f"({_filtered_sql(spec, since)}) spark_src"


def _epoch_subquery(spec: TableExportSpec, since: datetime | None) -> str:
    col = spec.watermark_column
    inner = _filtered_sql(spec, since)
    return (
        f"SELECT src.*, EXTRACT(EPOCH FROM src.{col})::bigint AS _spark_epoch "
        f"FROM ({inner}) src"
    )


def _jdbc_options(settings: Settings) -> dict[str, str]:
    settings.require_database()
    return {
        "url": settings.jdbc_url,
        "user": settings.database_username,
        "password": settings.database_password,
        "driver": "org.postgresql.Driver",
        "fetchsize": str(settings.spark_jdbc_fetch_size),
    }


def read_table(
    spark: SparkSession,
    spec: TableExportSpec,
    settings: Settings | None = None,
) -> DataFrame:
    """Read one table via JDBC with optional parallel partitions on created_at epoch."""
    cfg = settings or get_settings()
    since: datetime | None = None
    if cfg.ingest_mode == "incremental" and spec.watermark_column:
        since = read_watermark(spec.name, cfg)

    base_reader = (
        spark.read.format("jdbc")
        .options(**_jdbc_options(cfg))
        .option("dbtable", _jdbc_subquery(spec, since))
    )

    if cfg.spark_jdbc_num_partitions <= 1 or not spec.watermark_column:
        return base_reader.load()

    epoch_body = _epoch_subquery(spec, since)
    bounds_sql = (
        f"(SELECT MIN(_spark_epoch) AS lo, MAX(_spark_epoch) AS hi "
        f"FROM ({epoch_body}) t) bounds_row"
    )
    bounds = (
        spark.read.format("jdbc")
        .options(**_jdbc_options(cfg))
        .option("dbtable", bounds_sql)
        .load()
        .collect()[0]
    )
    lo, hi = bounds["lo"], bounds["hi"]
    if lo is None or hi is None or lo >= hi:
        return base_reader.load()

    parallel_table = f"({epoch_body}) spark_epoch_src"
    return (
        spark.read.format("jdbc")
        .options(**_jdbc_options(cfg))
        .option("dbtable", parallel_table)
        .option("partitionColumn", "_spark_epoch")
        .option("lowerBound", str(int(lo)))
        .option("upperBound", str(int(hi)))
        .option("numPartitions", str(cfg.spark_jdbc_num_partitions))
        .load()
        .drop("_spark_epoch")
    )


def latest_watermark(df: DataFrame, column: str) -> datetime | None:
    if column not in df.columns:
        return None
    row = df.agg({column: "max"}).collect()[0]
    value = row[0]
    if value is None:
        return None
    return value if isinstance(value, datetime) else value.to_pydatetime()
