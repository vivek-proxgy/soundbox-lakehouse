"""Tests for Dataproc Serverless orchestration job."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config.settings import Settings
from app.job.run_dataproc_orchestration import run


@patch("app.job.run_dataproc_orchestration.storage.Client")
@patch("app.job.run_dataproc_orchestration.dataproc_v1.BatchControllerClient")
@patch("app.job.run_dataproc_orchestration.package_codebase")
def test_dataproc_orchestration_submits_batch(
    mock_package_codebase,
    mock_dataproc_client_class,
    mock_storage_client_class,
    monkeypatch: pytest.MonkeyPatch,
):
    # Setup environment
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://test-bucket/soundbox")
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("SPARK_ARTIFACTS_BUCKET", "spark-test-bucket")
    monkeypatch.setenv("DATAPROC_SERVERLESS", "true")

    # Mock Storage
    mock_storage_client = MagicMock()
    mock_storage_client_class.return_value = mock_storage_client
    mock_bucket = MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    # Mock Dataproc
    mock_dataproc_client = MagicMock()
    mock_dataproc_client_class.return_value = mock_dataproc_client

    # Mock operation returned by create_batch
    mock_operation = MagicMock()
    mock_dataproc_client.create_batch.return_value = mock_operation

    # Mock final batch status
    from google.cloud import dataproc_v1

    mock_batch = MagicMock()
    mock_batch.state = dataproc_v1.Batch.State.SUCCEEDED
    mock_batch.state_message = ""
    mock_dataproc_client.get_batch.return_value = mock_batch

    # Run orchestration
    cfg = Settings()
    result = run(cfg)

    # Asserts
    assert result["engine"] == "dataproc_serverless"
    assert result["state"] == "SUCCEEDED"

    # Verify package codebase was called
    mock_package_codebase.assert_called_once()

    # Verify file uploads to GCS
    assert mock_storage_client.bucket.call_count == 2
    mock_storage_client.bucket.assert_any_call("spark-test-bucket")

    # Verify create_batch was called with correct project and region
    mock_dataproc_client.create_batch.assert_called_once()
    call_args = mock_dataproc_client.create_batch.call_args
    request = call_args.kwargs["request"]

    assert request.parent == "projects/mock-project/locations/asia-south1"
    assert (
        request.batch.pyspark_batch.main_python_file_uri
        == "gs://spark-test-bucket/dataproc-staging/run_spark_ingestion.py"
    )
    assert (
        "gs://spark-test-bucket/dataproc-staging/lakehouse.zip"
        in request.batch.pyspark_batch.python_file_uris
    )
    assert (
        "gs://spark-test-bucket/spark-jars/postgresql-42.7.2.jar"
        in request.batch.pyspark_batch.jar_file_uris
    )

    # Verify that environment settings are forwarded
    properties = request.batch.runtime_config.properties
    assert properties["spark.executorEnv.DATABASE_HOST"] == "mock-host"
    assert properties["spark.driverEnv.DATABASE_HOST"] == "mock-host"
