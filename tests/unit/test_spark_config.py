"""Spark session config tests — no JVM / PySpark required."""

import pytest

from app.config.settings import Settings
from app.spark.session import spark_config


def test_spark_config_uses_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INGEST_ENGINE", "spark")
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://my-bucket/soundbox")
    monkeypatch.setenv("SPARK_ICEBERG_CATALOG", "lakehouse")
    monkeypatch.setenv("SPARK_VERSION", "3.5")
    monkeypatch.setenv("SPARK_ICEBERG_VERSION", "1.5.2")

    cfg = Settings()
    conf = spark_config(cfg)

    assert cfg.ingest_engine == "spark"
    assert conf["spark.sql.catalog.lakehouse.warehouse"] == "gs://my-bucket/soundbox"
    assert "iceberg-spark-runtime-3.5_2.12:1.5.2" in conf["spark.jars.packages"]
    assert "postgresql:postgresql:42.7.2" in conf["spark.jars.packages"]


def test_jdbc_url_from_database_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_HOST", "10.0.0.5")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_NAME", "sbiaudiopod")

    cfg = Settings()
    assert cfg.jdbc_url == "jdbc:postgresql://10.0.0.5:5432/sbiaudiopod"


def test_ingest_engine_validation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INGEST_ENGINE", "invalid")
    with pytest.raises(ValueError, match="INGEST_ENGINE"):
        Settings()
