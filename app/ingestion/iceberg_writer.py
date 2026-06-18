"""Upload parquet batches directly to GCS under table/data/ directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.config.settings import Settings, get_settings


def upload_parquet_file(
    table: str,
    parquet_path: Path,
    settings: Settings | None = None,
) -> str:
    """Upload a parquet file to GCS under the warehouse prefix (Hadoop catalog structure)."""
    cfg = settings or get_settings()
    cfg.require_gcs()

    from google.cloud import storage

    warehouse = cfg.warehouse_uri.removeprefix("gs://")
    bucket_name, _, prefix = warehouse.partition("/")
    blob_name = f"{prefix.rstrip('/')}/{table}/data/{parquet_path.name}"

    client = storage.Client(project=cfg.google_cloud_project or None)
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).upload_from_filename(str(parquet_path))
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"[gcs] Uploaded {parquet_path.name} -> {gcs_uri}")
    return gcs_uri


def sync_table(
    table: str,
    df: pd.DataFrame,
    local_parquet: Path | None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Sync local parquet file to GCS in Hadoop Catalog structure."""
    cfg = settings or get_settings()
    result: dict[str, Any] = {"rows": 0}

    if cfg.upload_to_gcs and not df.empty:
        if local_parquet and local_parquet.exists():
            result["gcs_staging_uri"] = upload_parquet_file(table, local_parquet, cfg)
            result["rows"] = len(df)
            print(f"[sync] Uploaded raw parquet for {table}. Bypassed pyiceberg catalog write.")

    return result
