"""Watermark store tests — GCS client is mocked."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.config.settings import Settings
from ingestion.watermark import read_watermark, write_watermark


def test_read_watermark_from_local_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LAKEHOUSE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setenv("UPLOAD_TO_GCS", "false")
    wm_file = tmp_path / "watermarks" / "raw_transactions.txt"
    wm_file.parent.mkdir(parents=True)
    wm_file.write_text("2025-06-01T10:00:00+00:00", encoding="utf-8")

    ts = read_watermark("raw_transactions", Settings())
    assert ts.year == 2025
    assert ts.month == 6


def test_write_watermark_to_gcs_mocked(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://test-bucket/soundbox")
    monkeypatch.setenv("UPLOAD_TO_GCS", "true")

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage = MagicMock()
    mock_storage.Client.return_value = mock_client
    google_cloud = MagicMock()
    google_cloud.storage = mock_storage
    sys.modules["google"] = MagicMock(cloud=google_cloud)
    sys.modules["google.cloud"] = google_cloud
    sys.modules["google.cloud.storage"] = mock_storage

    write_watermark(
        "raw_transactions",
        datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        Settings(),
    )

    mock_storage.Client.assert_called_once()
    mock_client.bucket.assert_called_once_with("test-bucket")
    mock_blob.upload_from_string.assert_called_once()
