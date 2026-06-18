#!/usr/bin/env bash
# Submit PySpark ingest to Dataproc Serverless (GCP) — Iceberg on GCS.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${GCP_REGION:?Set GCP_REGION}"
: "${ICEBERG_WAREHOUSE_BUCKET:?Set ICEBERG_WAREHOUSE_BUCKET}"
: "${SPARK_ARTIFACTS_BUCKET:?Set SPARK_ARTIFACTS_BUCKET}"

JOB_NAME="${DATAPROC_BATCH_NAME:-soundbox-lakehouse-ingest}"
MAIN_PYTHON="app/job/run_spark_ingestion.py"

# Clean up zip file on exit
cleanup() {
  rm -f lakehouse.zip
}
trap cleanup EXIT

# Package codebase
echo "[spark-deploy] Zipping app and scripts..."
zip -q -r lakehouse.zip app scripts

echo "[spark-deploy] Submitting Dataproc batch to region ${GCP_REGION}..."
gcloud dataproc batches submit pyspark "${MAIN_PYTHON}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --region="${GCP_REGION}" \
  --batch="${JOB_NAME}-$(date +%Y%m%d%H%M%S)" \
  --deps-bucket="gs://${SPARK_ARTIFACTS_BUCKET}/dataproc-staging" \
  --py-files="lakehouse.zip" \
  --jars="gs://${SPARK_ARTIFACTS_BUCKET}/spark-jars/postgresql-42.7.2.jar" \
  --properties="\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.lakehouse.type=hadoop,\
spark.sql.catalog.lakehouse.warehouse=gs://${ICEBERG_WAREHOUSE_BUCKET}/soundbox" \
  -- \
  --env-file /dev/null
