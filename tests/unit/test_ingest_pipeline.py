"""Ingest pipeline tests — mocked Postgres export, no live DB."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pandas as pd

from app.config.settings import Settings
from ingestion.run import run
from app.utils.data_access import query_parquet_glob


def test_ingest_writes_parquet_and_duckdb_reads(
    lakehouse_settings_env,
    sample_export_frames,
):
    def mock_export_table(spec, settings):
        return sample_export_frames.get(spec.name, pd.DataFrame())

    with patch(
        "ingestion.pandas_engine.export_table",
        side_effect=mock_export_table,
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

    def mock_export_table(spec, settings):
        return sample_export_frames.get(spec.name, pd.DataFrame())

    with (
        patch(
            "ingestion.pandas_engine.export_table",
            side_effect=mock_export_table,
        ),
        patch("ingestion.pandas_engine.upload_to_gcs", return_value="gs://test-bucket/mock") as upload_mock,
    ):
        result = run(Settings())

    assert upload_mock.call_count == 2
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

    def mock_export_table(spec, settings):
        return empty_frames.get(spec.name, pd.DataFrame())

    with patch(
        "ingestion.pandas_engine.export_table",
        side_effect=mock_export_table,
    ):
        with pytest.raises(RuntimeError, match="No merchants exported"):
            run(Settings())
