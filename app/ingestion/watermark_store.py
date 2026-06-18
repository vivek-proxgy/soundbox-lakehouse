"""Read / write ingestion watermarks (GCS or local file)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import Settings, get_settings

DEFAULT_WATERMARK = "1970-01-01T00:00:00+00:00"


def _watermark_key(table: str, settings: Settings) -> str:
    return f"{settings.watermark_prefix.rstrip('/')}/{table}.txt"


def read_watermark(table: str, settings: Settings | None = None) -> datetime:
    cfg = settings or get_settings()
    raw = _read_watermark_raw(table, cfg)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromisoformat(DEFAULT_WATERMARK)


def write_watermark(table: str, value: datetime, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    payload = value.isoformat()
    _write_watermark_raw(table, payload, cfg)


def _read_watermark_raw(table: str, settings: Settings) -> str:
    key = _watermark_key(table, settings)
    warehouse = settings.warehouse_uri

    if warehouse.startswith("gs://") and settings.upload_to_gcs:
        try:
            from google.cloud import storage

            bucket_name = settings.gcs_bucket or warehouse.removeprefix("gs://").split("/")[0]
            blob_path = key
            if "/" in warehouse.removeprefix("gs://"):
                prefix = warehouse.removeprefix("gs://").split("/", 1)[1]
                blob_path = f"{prefix.rstrip('/')}/{key}"

            client = storage.Client(project=settings.google_cloud_project or None)
            blob = client.bucket(bucket_name).blob(blob_path)
            if blob.exists():
                return blob.download_as_text().strip()
        except Exception as exc:
            print(f"[watermark] GCS read failed for {table}: {exc}")

    local = Path(settings.lakehouse_local_root) / key
    if local.exists():
        return local.read_text(encoding="utf-8").strip()
    return DEFAULT_WATERMARK


def _write_watermark_raw(table: str, payload: str, settings: Settings) -> None:
    key = _watermark_key(table, settings)
    warehouse = settings.warehouse_uri

    if warehouse.startswith("gs://") and settings.upload_to_gcs:
        from google.cloud import storage

        bucket_name = settings.gcs_bucket or warehouse.removeprefix("gs://").split("/")[0]
        blob_path = key
        if "/" in warehouse.removeprefix("gs://"):
            prefix = warehouse.removeprefix("gs://").split("/", 1)[1]
            blob_path = f"{prefix.rstrip('/')}/{key}"

        client = storage.Client(project=settings.google_cloud_project or None)
        client.bucket(bucket_name).blob(blob_path).upload_from_string(payload)
        print(f"[watermark] Updated GCS {blob_path} -> {payload}")
        return

    local = Path(settings.lakehouse_local_root) / key
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(payload, encoding="utf-8")
    print(f"[watermark] Updated local {local} -> {payload}")
