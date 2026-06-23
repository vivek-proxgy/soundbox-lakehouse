"""Unit tests for DuckDBService deduplication views."""

from __future__ import annotations

from pathlib import Path
import pytest
import pandas as pd
import duckdb

from app.config.settings import Settings
from app.services.duckdb_service import DuckDBService


def test_duckdb_deduplicates_by_updated_at(tmp_path: Path):
    # 1. Create temporary directory for local parquet files
    lakehouse_root = tmp_path / "lakehouse"
    merchants_dir = lakehouse_root / "merchants"
    merchants_dir.mkdir(parents=True)

    # 2. Write duplicate merchant records with different updated_at timestamps
    # Merchant 'm1' is updated from Name A to Name B
    df_batch1 = pd.DataFrame([
        {"id": "m1", "name": "Merchant Name A", "updated_at": "2026-06-20T08:00:00+00:00", "created_at": "2026-06-20T08:00:00+00:00"},
        {"id": "m2", "name": "Merchant Name C", "updated_at": "2026-06-20T08:05:00+00:00", "created_at": "2026-06-20T08:05:00+00:00"},
    ])
    df_batch2 = pd.DataFrame([
        # Update for m1
        {"id": "m1", "name": "Merchant Name B (Updated)", "updated_at": "2026-06-20T09:00:00+00:00", "created_at": "2026-06-20T08:00:00+00:00"},
    ])

    df_batch1.to_parquet(merchants_dir / "batch1.parquet", index=False)
    df_batch2.to_parquet(merchants_dir / "batch2.parquet", index=False)

    # 3. Initialize Settings with local root and upload_to_gcs=False
    settings = Settings(
        SOUNDBOX_DATABASE_TYPE="postgres",
        SOUNDBOX_DATABASE_HOST="localhost",
        SOUNDBOX_DATABASE_PORT=5432,
        SOUNDBOX_DATABASE_USERNAME="postgres",
        SOUNDBOX_DATABASE_PASSWORD="password",
        SOUNDBOX_DATABASE_NAME="test",
        SOUNDBOX_DATABASE_SSL_ENABLED=False,
        ENCRYPTION_KEY="0" * 64,
        IV="0" * 32,
        ENCRYPTION_METHOD="aes-256-cbc",
        GOOGLE_CLOUD_PROJECT="test-project",
        GCP_REGION="us-central1",
        GCS_BUCKET="test-bucket",
        WAREHOUSE_PATH="gs://test-bucket/soundbox",
        ICEBERG_NAMESPACE="soundbox",
        INGEST_MODE="incremental",
        INGEST_BATCH_SIZE=1000,
        WATERMARK_PREFIX="watermarks",
        LAKEHOUSE_LOCAL_ROOT=str(lakehouse_root),
        DUCKDB_THREADS=2,
        UPLOAD_TO_GCS=False,
        WRITE_LOCAL_PARQUET=True,
        INGEST_ENGINE="pandas",
        SPARK_APP_NAME="soundbox-lakehouse",
        SPARK_MASTER="local[*]",
        SPARK_ICEBERG_CATALOG="lakehouse",
        SPARK_ICEBERG_VERSION="1.5.2",
        SPARK_VERSION="3.5",
        SPARK_JDBC_NUM_PARTITIONS=1,
        SPARK_JDBC_FETCH_SIZE=100,
        SPARK_DECRYPT_PII=False
    )

    # 4. Run DuckDBService and query merchants view
    duckdb_svc = DuckDBService(settings)
    conn = duckdb_svc.get_connection()
    try:
        results = conn.execute("SELECT id, name, updated_at FROM merchants ORDER BY id").fetchall()
        # Verify deduplication has worked (only 2 records, m1 has the updated name B)
        assert len(results) == 2
        assert results[0] == ("m1", "Merchant Name B (Updated)", "2026-06-20T09:00:00+00:00")
        assert results[1] == ("m2", "Merchant Name C", "2026-06-20T08:05:00+00:00")
    finally:
        conn.close()
