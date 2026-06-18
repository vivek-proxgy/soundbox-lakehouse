"""Postgres reader tests — psycopg2 and read_sql are mocked."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.config.settings import Settings
from app.ingestion.postgres_reader import export_table
from app.ingestion.queries import TRANSACTIONS_SPEC


@pytest.fixture
def db_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_HOST", "mock-host")
    monkeypatch.setenv("DATABASE_USERNAME", "user")
    monkeypatch.setenv("DATABASE_PASSWORD", "pass")
    monkeypatch.setenv("DATABASE_NAME", "db")
    monkeypatch.setenv("INGEST_MODE", "full")
    return Settings()


def test_export_table_uses_mock_connection(db_settings: Settings):
    frame = pd.DataFrame(
        [
            {
                "id": "tx-1",
                "merchant_id": "m-1",
                "amount": 10.0,
                "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
            }
        ]
    )
    mock_conn = MagicMock()

    with (
        patch("app.ingestion.postgres_reader.psycopg2.connect", return_value=mock_conn) as connect_mock,
        patch("app.ingestion.postgres_reader.pd.read_sql", return_value=frame) as read_sql_mock,
        patch("app.ingestion.postgres_reader.write_watermark") as watermark_mock,
    ):
        result = export_table(TRANSACTIONS_SPEC, db_settings)

    connect_mock.assert_called_once()
    read_sql_mock.assert_called_once()
    watermark_mock.assert_not_called()
    mock_conn.close.assert_called_once()
    assert len(result) == 1
    assert result.iloc[0]["amount"] == 10.0


def test_export_table_writes_watermark_in_incremental_mode(
    db_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("INGEST_MODE", "incremental")
    settings = Settings()
    frame = pd.DataFrame(
        [
            {
                "id": "tx-1",
                "merchant_id": "m-1",
                "amount": 10.0,
                "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
            }
        ]
    )

    with (
        patch("app.ingestion.postgres_reader.psycopg2.connect", return_value=MagicMock()),
        patch("app.ingestion.postgres_reader.pd.read_sql", return_value=frame),
        patch("app.ingestion.postgres_reader.read_watermark") as read_wm_mock,
        patch("app.ingestion.postgres_reader.write_watermark") as write_wm_mock,
    ):
        read_wm_mock.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
        export_table(TRANSACTIONS_SPEC, settings)

    write_wm_mock.assert_called_once()
