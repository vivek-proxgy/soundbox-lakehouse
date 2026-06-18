"""Orchestrator to package, upload, and run Spark ingestion on Dataproc Serverless."""

from __future__ import annotations

import datetime
import os
import tempfile
import zipfile
from typing import Any

from google.cloud import dataproc_v1
from google.cloud import storage

from app.config.settings import Settings, get_settings
from app.spark.session import spark_config


def package_codebase(zip_path: str) -> None:
    """Package the app/ and scripts/ directories into a ZIP file."""
    print(f"[dataproc-orchestrator] Packaging app and scripts to {zip_path}...")
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(os.path.join(current_dir, "app")):
            # Skip cache directories
            if any(p in root for p in ("__pycache__", ".pytest_cache", ".ruff_cache")):
                continue
            for file in files:
                if file.endswith(".pyc"):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, current_dir)
                zipf.write(file_path, arcname)

        for root, dirs, files in os.walk(os.path.join(current_dir, "scripts")):
            if "__pycache__" in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, current_dir)
                zipf.write(file_path, arcname)


def upload_file_to_gcs(local_path: str, bucket_name: str, destination_blob: str) -> str:
    """Upload a local file to GCS and return its gs:// URI."""
    print(f"[dataproc-orchestrator] Uploading {local_path} to gs://{bucket_name}/{destination_blob}...")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(local_path)
    return f"gs://{bucket_name}/{destination_blob}"


def run(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    cfg.require_gcs()

    # Bucket to store spark staging files
    artifacts_bucket = cfg.spark_artifacts_bucket or cfg.gcs_bucket
    if not artifacts_bucket:
        raise RuntimeError("Either SPARK_ARTIFACTS_BUCKET or GCS_BUCKET must be set to run Dataproc Serverless.")

    # 1. Package and upload codebase zip
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_local_path = os.path.join(tmpdir, "lakehouse.zip")
        package_codebase(zip_local_path)

        zip_gcs_uri = upload_file_to_gcs(
            zip_local_path,
            artifacts_bucket,
            "dataproc-staging/lakehouse.zip",
        )

        # 2. Upload the main ingestion script (app/job/run_spark_ingestion.py)
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        main_script_local = os.path.join(current_dir, "app", "job", "run_spark_ingestion.py")

        main_script_gcs_uri = upload_file_to_gcs(
            main_script_local,
            artifacts_bucket,
            "dataproc-staging/run_spark_ingestion.py",
        )

    # 3. Build Dataproc properties & environment configuration
    properties = {}

    # Get Spark session config (extensions, catalog config, warehouse path)
    for k, v in spark_config(cfg).items():
        if k != "spark.master":  # Dataproc Serverless manages master internally
            properties[k] = str(v)

    # Forward settings as environment variables so Dataproc executes with the same configuration
    env_mapping = {
        "database_type": "DATABASE_TYPE",
        "database_host": "DATABASE_HOST",
        "database_port": "DATABASE_PORT",
        "database_username": "DATABASE_USERNAME",
        "database_password": "DATABASE_PASSWORD",
        "database_name": "DATABASE_NAME",
        "database_ssl_enabled": "DATABASE_SSL_ENABLED",
        "encryption_key": "ENCRYPTION_KEY",
        "iv": "IV",
        "encryption_method": "ENCRYPTION_METHOD",
        "google_cloud_project": "GOOGLE_CLOUD_PROJECT",
        "gcp_region": "GCP_REGION",
        "gcs_bucket": "GCS_BUCKET",
        "warehouse_path": "WAREHOUSE_PATH",
        "iceberg_namespace": "ICEBERG_NAMESPACE",
        "spark_artifacts_bucket": "SPARK_ARTIFACTS_BUCKET",
        "ingest_mode": "INGEST_MODE",
        "ingest_batch_size": "INGEST_BATCH_SIZE",
        "watermark_prefix": "WATERMARK_PREFIX",
        "lakehouse_local_root": "LAKEHOUSE_LOCAL_ROOT",
        "duckdb_threads": "DUCKDB_THREADS",
        "upload_to_gcs": "UPLOAD_TO_GCS",
        "write_local_parquet": "WRITE_LOCAL_PARQUET",
        "ingest_engine": "INGEST_ENGINE",
        "spark_app_name": "SPARK_APP_NAME",
        "spark_master": "SPARK_MASTER",
        "spark_iceberg_catalog": "SPARK_ICEBERG_CATALOG",
        "spark_iceberg_version": "SPARK_ICEBERG_VERSION",
        "spark_version": "SPARK_VERSION",
        "spark_jdbc_num_partitions": "SPARK_JDBC_NUM_PARTITIONS",
        "spark_jdbc_fetch_size": "SPARK_JDBC_FETCH_SIZE",
        "spark_decrypt_pii": "SPARK_DECRYPT_PII",
    }

    for attr, env_name in env_mapping.items():
        val = getattr(cfg, attr)
        if val is not None:
            val_str = "true" if isinstance(val, bool) else str(val)
            # Add to executor and driver environment variables
            properties[f"spark.executorEnv.{env_name}"] = val_str
            properties[f"spark.driverEnv.{env_name}"] = val_str

    # 4. Initialize Dataproc client and submit CreateBatchRequest
    print(f"[dataproc-orchestrator] Initializing Dataproc BatchControllerClient for region {cfg.gcp_region}...")
    endpoint = f"{cfg.gcp_region}-dataproc.googleapis.com:443"
    client = dataproc_v1.BatchControllerClient(
        client_options={"api_endpoint": endpoint}
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_id = f"lakehouse-ingest-{timestamp}"

    # Target PostgreSQL JAR path
    jar_file_uris = [
        f"gs://{artifacts_bucket}/spark-jars/postgresql-42.7.2.jar"
    ]

    # Service Account configuration
    # Fall back to lakehouse-spark@PROJECT_ID.iam.gserviceaccount.com if not explicitly provided in environment
    spark_sa = os.environ.get(
        "SPARK_SERVICE_ACCOUNT",
        f"lakehouse-spark@{cfg.google_cloud_project}.iam.gserviceaccount.com",
    )

    batch = {
        "pyspark_batch": {
            "main_python_file_uri": main_script_gcs_uri,
            "python_file_uris": [zip_gcs_uri],
            "jar_file_uris": jar_file_uris,
        },
        "runtime_config": {
            "properties": properties,
        },
        "environment_config": {
            "execution_config": {
                "service_account": spark_sa,
            }
        },
    }

    parent = f"projects/{cfg.google_cloud_project}/locations/{cfg.gcp_region}"

    request = dataproc_v1.CreateBatchRequest(
        parent=parent,
        batch=batch,
        batch_id=batch_id,
    )

    print(f"[dataproc-orchestrator] Submitting Dataproc Serverless batch {batch_id}...")
    operation = client.create_batch(request=request)

    print(f"[dataproc-orchestrator] Waiting for batch execution to complete: {operation.operation.name}")
    # Wait for the LRO to complete
    operation.result()

    # Query final status
    batch_name = f"{parent}/batches/{batch_id}"
    final_batch = client.get_batch(name=batch_name)
    state_name = final_batch.state.name

    print(f"[dataproc-orchestrator] Dataproc Serverless batch finished with state: {state_name}")

    if final_batch.state != dataproc_v1.Batch.State.SUCCEEDED:
        error_msg = f"Dataproc Serverless batch {batch_id} failed with state {state_name}."
        if final_batch.state_message:
            error_msg += f" Details: {final_batch.state_message}"
        raise RuntimeError(error_msg)

    summary = {
        "engine": "dataproc_serverless",
        "batch_id": batch_id,
        "state": state_name,
        "project": cfg.google_cloud_project,
        "region": cfg.gcp_region,
    }
    return summary
