"""Shared mock fixtures — no real Postgres or GCS in tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest


@pytest.fixture
def sample_merchants_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "organization_id": "22222222-2222-2222-2222-222222222222",
                "name": "CI Merchant",
                "city": "mumbai",
                "state": "maharashtra",
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            }
        ]
    )


@pytest.fixture
def sample_transactions_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "tx-1",
                "merchant_id": "11111111-1111-1111-1111-111111111111",
                "organization_id": "22222222-2222-2222-2222-222222222222",
                "amount": 99.5,
                "created_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
            },
            {
                "id": "tx-2",
                "merchant_id": "11111111-1111-1111-1111-111111111111",
                "organization_id": "22222222-2222-2222-2222-222222222222",
                "amount": 150.0,
                "created_at": datetime(2025, 1, 3, tzinfo=timezone.utc),
            },
        ]
    )


@pytest.fixture
def sample_export_frames(
    sample_merchants_df: pd.DataFrame,
    sample_transactions_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    return {
        "merchants": sample_merchants_df,
        "transactions": sample_transactions_df,
        "device_telemetry": pd.DataFrame(),
    }


@pytest.fixture(autouse=True)
def mock_all_settings_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_TYPE", "postgres")
    monkeypatch.setenv("DATABASE_HOST", "mock-host")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_USERNAME", "mock-user")
    monkeypatch.setenv("DATABASE_PASSWORD", "mock-pass")
    monkeypatch.setenv("DATABASE_NAME", "mock-db")
    monkeypatch.setenv("DATABASE_SSL_ENABLED", "false")
    monkeypatch.setenv("ENCRYPTION_KEY", "0000000000000000000000000000000000000000000000000000000000000000")
    monkeypatch.setenv("IV", "00000000000000000000000000000000")
    monkeypatch.setenv("ENCRYPTION_METHOD", "aes-256-cbc")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "mock-project")
    monkeypatch.setenv("GCP_REGION", "asia-south1")
    monkeypatch.setenv("GCS_BUCKET", "mock-bucket")
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://mock-bucket")
    monkeypatch.setenv("ICEBERG_NAMESPACE", "soundbox")
    monkeypatch.setenv("INGEST_MODE", "incremental")
    monkeypatch.setenv("INGEST_BATCH_SIZE", "5000")
    monkeypatch.setenv("WATERMARK_PREFIX", "watermarks")
    monkeypatch.setenv("LAKEHOUSE_LOCAL_ROOT", ".tmp/lakehouse")
    monkeypatch.setenv("DUCKDB_THREADS", "4")
    monkeypatch.setenv("UPLOAD_TO_GCS", "false")
    monkeypatch.setenv("WRITE_LOCAL_PARQUET", "true")
    monkeypatch.setenv("INGEST_ENGINE", "spark")
    monkeypatch.setenv("SPARK_APP_NAME", "soundbox-lakehouse-ingest")
    monkeypatch.setenv("SPARK_MASTER", "local[*]")
    monkeypatch.setenv("SPARK_ICEBERG_CATALOG", "lakehouse")
    monkeypatch.setenv("SPARK_ICEBERG_VERSION", "1.5.2")
    monkeypatch.setenv("SPARK_VERSION", "3.5")
    monkeypatch.setenv("SPARK_JDBC_NUM_PARTITIONS", "16")
    monkeypatch.setenv("SPARK_JDBC_FETCH_SIZE", "10000")
    monkeypatch.setenv("SPARK_DECRYPT_PII", "false")


@pytest.fixture
def lakehouse_settings_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Minimal env for ingest tests — no real DB connection."""
    monkeypatch.setenv("DATABASE_HOST", "mock-host")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_USERNAME", "mock-user")
    monkeypatch.setenv("DATABASE_PASSWORD", "mock-pass")
    monkeypatch.setenv("DATABASE_NAME", "mock-db")
    monkeypatch.setenv("LAKEHOUSE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setenv("UPLOAD_TO_GCS", "false")
    monkeypatch.setenv("INGEST_MODE", "full")
    return tmp_path

