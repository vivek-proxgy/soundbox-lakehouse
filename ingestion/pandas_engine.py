"""Pandas ingestion engine — postgres export, decrypt, and Parquet writing."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2

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


def _connect(settings: Settings) -> psycopg2.extensions.connection:
    settings.require_database()
    connect_kwargs: dict[str, Any] = {
        "host": settings.database_host,
        "port": settings.database_port,
        "user": settings.database_username,
        "password": settings.database_password,
        "dbname": settings.database_name,
    }
    if settings.database_ssl_enabled:
        connect_kwargs["sslmode"] = "require"
    print(
        f"[pandas-ingest] Connecting to {settings.database_host}:"
        f"{settings.database_port}/{settings.database_name}"
    )
    return psycopg2.connect(**connect_kwargs)


def _decrypt_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = df[column].apply(decrypt_field)
    return df


def upload_to_gcs(table: str, local_path: Path, settings: Settings) -> str:
    settings.require_gcs()
    from google.cloud import storage

    warehouse = settings.warehouse_uri.removeprefix("gs://")
    bucket_name, _, prefix = warehouse.partition("/")
    blob_name = f"{prefix.rstrip('/')}/{table}/data/{local_path.name}"

    client = storage.Client(project=settings.google_cloud_project or None)
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).upload_from_filename(str(local_path))
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"[pandas-ingest] Uploaded GCS -> {gcs_uri}")
    return gcs_uri


def export_table(spec: TableExportSpec, settings: Settings) -> pd.DataFrame:
    since = get_watermark_since(spec, settings)
    sql = apply_watermark_filter(spec.sql, spec.watermark_column, since, param_style="param")

    conn = _connect(settings)
    try:
        if since is not None:
            df = pd.read_sql(sql, conn, params=[since])
        else:
            df = pd.read_sql(sql, conn)
    finally:
        conn.close()

    if df.empty:
        print(f"[pandas-ingest] {spec.name}: 0 rows extracted")
        return df

    df = conform_dataframe_schema(df, spec)
    df = _decrypt_columns(df, spec.decrypt_columns)

    update_watermark_if_incremental(df, spec, settings)

    print(f"[pandas-ingest] {spec.name}: {len(df):,} rows extracted")
    return df


def run(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    cfg.require_database()

    print(
        f"[pandas-ingest] Starting ingest mode={cfg.ingest_mode} "
        f"warehouse={cfg.warehouse_uri or '(local only)'}"
    )

    counts: dict[str, int] = {}
    gcs_results: dict[str, Any] = {}

    for spec in EXPORT_TABLES:
        df = export_table(spec, cfg)
        counts[spec.name] = len(df)

        local_path = None
        if cfg.write_local_parquet:
            local_path = write_local_snapshot(df, spec.name, cfg)

        if cfg.upload_to_gcs and cfg.warehouse_uri and not df.empty and local_path:
            gcs_uri = upload_to_gcs(spec.name, Path(local_path), cfg)
            gcs_results[spec.name] = {"gcs_staging_uri": gcs_uri, "rows": len(df)}

    if counts.get("merchants", 0) == 0 and cfg.ingest_mode == "full":
        raise RuntimeError(
            "No merchants exported. Check DATABASE_* env vars match soundbox-backend."
        )

    summary = {
        "counts": counts,
        "gcs": gcs_results,
        "mode": cfg.ingest_mode,
        "warehouse": cfg.warehouse_uri,
    }
    print("[pandas-ingest] Ingest complete:", summary)
    return summary
