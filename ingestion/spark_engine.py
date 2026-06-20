"""PySpark ingestion engine — local Spark session, DataFrame extracts, PII decryption, GCS Iceberg sink."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from app.config.settings import Settings, get_settings
from app.utils.decryption import decrypt_field
from ingestion.queries import EXPORT_TABLES, TableExportSpec
from ingestion.utils import (
    apply_watermark_filter,
    conform_dataframe_schema,
    get_watermark_since,
    update_watermark_if_incremental,
    write_local_snapshot,
)

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


# =====================================================================
# Spark Session Configuration
# =====================================================================

def spark_config(settings: Settings) -> dict[str, str]:
    """Return Spark config map — testable without starting a JVM."""
    settings.require_gcs()
    catalog = settings.spark_iceberg_catalog
    warehouse = settings.warehouse_uri

    return {
        "spark.app.name": settings.spark_app_name,
        "spark.master": settings.spark_master,
        "spark.jars.packages": settings.spark_jar_packages,
        "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        f"spark.sql.catalog.{catalog}": "org.apache.iceberg.spark.SparkCatalog",
        f"spark.sql.catalog.{catalog}.type": "hadoop",
        f"spark.sql.catalog.{catalog}.warehouse": warehouse,
        "spark.hadoop.fs.gs.impl": "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem",
        "spark.hadoop.fs.AbstractFileSystem.gs.impl": (
            "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFS"
        ),
        "spark.sql.sources.partitionOverwriteMode": "dynamic",
    }


def create_spark_session(settings: Settings) -> SparkSession:
    from pyspark.sql import SparkSession

    builder = SparkSession.builder
    for key, value in spark_config(settings).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


# =====================================================================
# Postgres DataFrame Reader (JDBC Subquery approach)
# =====================================================================

def _jdbc_options(settings: Settings, table_or_subquery: str) -> dict[str, str]:
    settings.require_database()
    return {
        "url": settings.jdbc_url,
        "user": settings.database_username,
        "password": settings.database_password,
        "dbtable": table_or_subquery,
        "driver": "org.postgresql.Driver",
        "fetchsize": str(settings.spark_jdbc_fetch_size),
    }


def read_table_df(
    spark: SparkSession,
    spec: TableExportSpec,
    settings: Settings,
) -> DataFrame:
    """Read a table from PostgreSQL using the Spark JDBC driver and a subquery."""
    since = get_watermark_since(spec, settings)
    
    # Format the query with watermark constraints
    query_sql = apply_watermark_filter(spec.sql, spec.watermark_column, since, param_style="literal")
    
    # Wrap in parentheses as a subquery alias for Spark JDBC
    dbtable_subquery = f"({query_sql}) AS temp_export"
    opts = _jdbc_options(settings, dbtable_subquery)
    
    return spark.read.format("jdbc").options(**opts).load()


# =====================================================================
# PII Decryption Transform
# =====================================================================

def _decrypt_udf():
    return F.udf(decrypt_field, StringType())


def maybe_decrypt_columns(df: DataFrame, spec: TableExportSpec) -> DataFrame:
    if not spec.decrypt_columns:
        return df
    decrypt = _decrypt_udf()
    for column in spec.decrypt_columns:
        if column in df.columns:
            df = df.withColumn(column, decrypt(F.col(column)))
    return df


# =====================================================================
# Iceberg Writer
# =====================================================================

def iceberg_table_name(table: str, settings: Settings) -> str:
    return f"{settings.iceberg_table_prefix}.{table}"


def append_to_iceberg(
    df: DataFrame,
    table: str,
    settings: Settings,
) -> int:
    """Append DataFrame contents to the GCS Iceberg table."""
    if df.isEmpty():
        return 0

    settings.require_gcs()
    target = iceberg_table_name(table, settings)
    count = df.count()
    spark = df.sparkSession
    
    if not spark.catalog.tableExists(target):
        df.writeTo(target).using("iceberg").tableProperty("write-format", "parquet").create()
    else:
        df.writeTo(target).append()
        
    print(f"[spark-iceberg] Appended {count:,} rows -> {target}")
    return count


# =====================================================================
# Spark Jobs Orchestration
# =====================================================================

def run(settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    cfg.require_database()
    cfg.require_gcs()

    print(
        f"[spark-engine] Starting Spark Ingest mode={cfg.ingest_mode} "
        f"warehouse={cfg.warehouse_uri}"
    )

    spark = create_spark_session(cfg)
    counts = {}

    try:
        for spec in EXPORT_TABLES:
            print(f"[spark-engine] Starting {spec.name} ingestion...")
            df = read_table_df(spark, spec, cfg)
            df = conform_dataframe_schema(df, spec)
            
            if cfg.spark_decrypt_pii:
                df = maybe_decrypt_columns(df, spec)
                
            count = append_to_iceberg(df, spec.name, cfg)
            counts[spec.name] = count
            
            if count > 0:
                write_local_snapshot(df, spec.name, cfg)
                update_watermark_if_incremental(df, spec, cfg)
                
            print(f"[spark-engine] Complete. Ingested {count:,} records.")
    finally:
        spark.stop()

    summary = {
        "engine": "spark",
        "counts": counts,
        "mode": cfg.ingest_mode,
        "warehouse": cfg.warehouse_uri,
    }
    print("[spark-engine] Ingestion complete:", summary)
    return summary
