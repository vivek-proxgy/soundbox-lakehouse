"""Ingest pipeline tests — mocked Postgres export, no live DB."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config.settings import Settings
from app.job.run_ingestion import run
from app.utils.data_access import query_parquet_glob


def test_ingest_writes_parquet_and_duckdb_reads(
    lakehouse_settings_env,
    sample_export_frames,
):
    with patch(
        "app.job.run_ingestion.export_all_tables",
        return_value=sample_export_frames,
    ):
        result = run(Settings())

    counts = result["counts"]
    assert counts["merchants"] == 1
    assert counts["transactions"] == 2
    assert result["gcs"] == {}

    tx_glob = lakehouse_settings_env / "transactions" / "*.parquet"
    rows = query_parquet_glob(
        tx_glob,
        "SELECT count(*) AS n, round(sum(amount), 2) AS gmv FROM data",
    )
    assert rows[0][0] == 2
    assert float(rows[0][1]) == 249.5


def test_ingest_uploads_to_gcs_when_enabled(
    lakehouse_settings_env,
    sample_export_frames,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("UPLOAD_TO_GCS", "true")
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://test-bucket/soundbox")

    with (
        patch(
            "app.job.run_ingestion.export_all_tables",
            return_value=sample_export_frames,
        ),
        patch("app.job.run_ingestion.sync_table", return_value={"rows": 1}) as sync_mock,
    ):
        result = run(Settings())

    assert sync_mock.call_count == 2
    assert "merchants" in result["gcs"]
    assert "transactions" in result["gcs"]


def test_ingest_fails_when_full_mode_has_no_merchants(
    lakehouse_settings_env,
    sample_export_frames,
):
    empty_frames = {
        **sample_export_frames,
        "merchants": sample_export_frames["merchants"].iloc[0:0],
    }

    with patch("app.job.run_ingestion.export_all_tables", return_value=empty_frames):
        with pytest.raises(RuntimeError, match="No merchants exported"):
            run(Settings())
