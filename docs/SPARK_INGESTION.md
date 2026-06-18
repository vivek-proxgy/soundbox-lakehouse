# PySpark + Iceberg ingestion (billions of rows)

Use **PySpark** when Postgres has millions/billions of rows. The **pandas** engine (`INGEST_ENGINE=pandas`) loads everything into one Python process and will OOM at scale.

```
soundbox Postgres  ──JDBC (parallel)──►  PySpark  ──►  Iceberg on GCS
                                              │
                                         watermarks (GCS)
                                              │
                                         DuckDB / Chanakya reads parquet sync
```

Reference: `AIML/scripts/spark_query_iceberg.py` (Spark + Iceberg + GCS catalog).

---

## When to use which engine

| Scale / Engine | INGEST_ENGINE | Execution Mode |
|----------------|---------------|----------------|
| Small scale (local / quick tests) | `pandas` | Local python process inside Cloud Run Job or local dev machine |
| High scale (production / dynamic) | `spark` | **Dataproc Serverless** (when run in Cloud Run / GCP) OR local PySpark (when run locally) |

When deployed to Cloud Run, selecting `INGEST_ENGINE=spark` will automatically package the codebase, upload staging files to GCS, and submit a **Dataproc Serverless** PySpark batch. The Cloud Run Job monitors the batch until completion.

---

## Environment variables (Spark)

Add to `.env` or Dataproc batch env:

```env
INGEST_ENGINE=spark
DATABASE_HOST=...
DATABASE_USERNAME=...
DATABASE_PASSWORD=...
DATABASE_NAME=...

WAREHOUSE_PATH=gs://soundbox-iceberg-warehouse/soundbox
GCS_BUCKET=soundbox-iceberg-warehouse
GOOGLE_CLOUD_PROJECT=your-project
GCP_REGION=asia-south1

SPARK_ICEBERG_CATALOG=lakehouse
SPARK_JDBC_NUM_PARTITIONS=32
SPARK_JDBC_FETCH_SIZE=10000
INGEST_MODE=incremental
SPARK_DECRYPT_PII=false
```

`DATABASE_*` — same as `on-prem-soundbox-backend/.env`.

---

## GCP setup (Dataproc Serverless)

### 1. Enable APIs

```bash
gcloud services enable dataproc.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com
```

### 2. GCS bucket + staging

```bash
export PROJECT_ID=your-project
export REGION=asia-south1
export BUCKET=soundbox-iceberg-warehouse

gcloud storage buckets create gs://${BUCKET} --location=${REGION}
gcloud storage buckets create gs://${BUCKET}/dataproc-staging --location=${REGION}
```

### 3. Service account

```bash
gcloud iam service-accounts create lakehouse-spark \
  --display-name="Lakehouse Spark Ingest"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:lakehouse-spark@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:lakehouse-spark@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/dataproc.editor"
```

### 4. Create Iceberg tables (once)

Spark expects tables under Hadoop catalog on GCS. Either:

- Run `python scripts/init_iceberg_tables.py` (PyIceberg, small env), **or**
- Run a one-off Spark SQL job:

```sql
CREATE NAMESPACE IF NOT EXISTS lakehouse.soundbox;
-- tables created on first append if using Spark 3.5 + Iceberg 1.5 with create-if-not-exists
```

### 5. Package code and submit batch

```bash
cd soundbox-lakehouse
zip -r lakehouse.zip app scripts

gcloud dataproc batches submit pyspark app/job/run_spark_ingestion.py \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --batch=lakehouse-ingest-$(date +%Y%m%d%H%M) \
  --deps-bucket=gs://${BUCKET}/dataproc-staging \
  --py-files=lakehouse.zip \
  --service-account=lakehouse-spark@${PROJECT_ID}.iam.gserviceaccount.com \
  --properties="\
spark.executor.instances=8,\
spark.executor.memory=8g,\
spark.driver.memory=4g,\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.lakehouse.type=hadoop,\
spark.sql.catalog.lakehouse.warehouse=gs://${BUCKET}/soundbox" \
  -- \
  --env DATABASE_HOST=...  # prefer Secret Manager env injection
```

Or use `scripts/submit_dataproc_serverless.sh` as a template.

### 6. Secrets (DATABASE_PASSWORD, ENCRYPTION_KEY)

Store in **Secret Manager** and mount into Dataproc via:

- Dataproc batch `--user-labels` + startup script, **or**
- Cloud Composer / Workflows that exports env before submit, **or**
- VPC + private IP to Postgres with password in Secret Manager accessed by metadata

Never hardcode passwords in the submit script.

### 7. Schedule (Cloud Scheduler → Dataproc)

```bash
gcloud scheduler jobs create http lakehouse-spark-ingest \
  --location=${REGION} \
  --schedule="0 */1 * * *" \
  --uri="https://${REGION}-dataproc.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/batches" \
  --http-method=POST \
  --oauth-service-account-email=lakehouse-spark@${PROJECT_ID}.iam.gserviceaccount.com \
  --message-body-from-file=dataproc_batch_request.json
```

(Use a small Cloud Function or Workflows step to submit the batch if Scheduler JSON is too large.)

---

## How parallel JDBC works

`app/spark/jdbc_reader.py`:

1. Reads watermark from GCS (`watermarks/<table>.txt`)
2. Adds `AND created_at > watermark` to SQL
3. Splits read across `SPARK_JDBC_NUM_PARTITIONS` using `EXTRACT(EPOCH FROM created_at)`
4. Each executor pulls a slice from Postgres in parallel

Tune for billions of rows:

| Variable | Guidance |
|----------|----------|
| `SPARK_JDBC_NUM_PARTITIONS` | 16–64 (match Postgres max_connections budget) |
| `SPARK_JDBC_FETCH_SIZE` | 10000–50000 |
| Dataproc executors | 8+ executors, 8g memory each |

---

## Local Spark test (small sample)

```powershell
pip install -r requirements.txt
$env:INGEST_ENGINE="spark"
$env:SPARK_MASTER="local[*]"
$env:WAREHOUSE_PATH="gs://your-bucket/soundbox"
# DATABASE_* + gcloud auth application-default login
python -m app.main
```

First run downloads Iceberg + JDBC jars via Maven (slow).

---

## Code layout

| Module | Role |
|--------|------|
| `app/spark/session.py` | SparkSession + Iceberg catalog on GCS |
| `app/spark/jdbc_reader.py` | Parallel Postgres JDBC |
| `app/spark/iceberg_sink.py` | `df.write.format("iceberg").append()` |
| `app/spark/decrypt.py` | Optional PII UDF (`SPARK_DECRYPT_PII=true`) |
| `app/job/run_spark_ingestion.py` | Orchestrates all tables |
| `app/main.py` | Routes `INGEST_ENGINE` pandas vs spark |

---

## DuckDB / AI service

After Spark writes Iceberg on GCS:

- Chanakya can **sync** latest parquet to `.tmp/iceberg_downloads/` (existing `sync_iceberg_snapshot.py` pattern), **or**
- Query GCS parquet directly with DuckDB + `httpfs`/`gcs` extension

Spark does **not** replace DuckDB for copilot queries — it replaces pandas for **ingest scale**.
