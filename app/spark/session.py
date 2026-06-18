"""Build a SparkSession configured for Iceberg on GCS (AIML pattern)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def spark_config(settings: Settings | None = None) -> dict[str, str]:
    """Return Spark config map — testable without starting a JVM."""
    cfg = settings or get_settings()
    cfg.require_gcs()
    catalog = cfg.spark_iceberg_catalog
    warehouse = cfg.warehouse_uri

    return {
        "spark.app.name": cfg.spark_app_name,
        "spark.master": cfg.spark_master,
        "spark.jars.packages": cfg.spark_jar_packages,
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


def create_spark_session(settings: Settings | None = None) -> SparkSession:
    from pyspark.sql import SparkSession

    cfg = settings or get_settings()
    builder = SparkSession.builder
    for key, value in spark_config(cfg).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def stop_spark(spark: Any) -> None:
    if spark is not None:
        spark.stop()
