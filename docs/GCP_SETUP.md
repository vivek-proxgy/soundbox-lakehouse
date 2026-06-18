# Soundbox Lakehouse — GCP setup

This service ingests **soundbox-backend Postgres** into **GCS Iceberg** parquet. The AI service (Chanakya) reads those snapshots with **DuckDB** — it never queries the main DB at runtime.

```
soundbox-backend Postgres
        │  (batch / scheduled)
        ▼
Cloud Run Job  (soundbox-lakehouse)
        │  incremental watermarks on GCS
        ▼
GCS Iceberg warehouse  (gs://<bucket>/soundbox/...)
        │  sync or direct read
        ▼
DuckDB analysis  →  AI / Chanakya copilot
```

---

## 1. GCP resources to create

| Resource | Purpose |
|----------|---------|
| **GCS bucket** | Iceberg data + watermarks, e.g. `gs://soundbox-iceberg-warehouse` |
| **Cloud SQL (Postgres)** | Optional PyIceberg **catalog** metadata (recommended for production) |
| **Artifact Registry** | Docker image for the ingest job |
| **Cloud Run Job** | Runs `python -m app.main` on a schedule |
| **Cloud Scheduler** | Triggers the job every 15–60 min |
| **Service account** | GCS write + Cloud SQL client (if used) |
| **Secret Manager** | `DATABASE_PASSWORD`, `ENCRYPTION_KEY`, `IV` |

---

## 2. Environment variables

### Soundbox database (same as `on-prem-soundbox-backend/.env`)

| Variable | Example | Where to set |
|----------|---------|--------------|
| `DATABASE_HOST` | `34.180.35.187` or Cloud SQL IP | Cloud Run Job env / Secret |
| `DATABASE_PORT` | `5432` | Cloud Run Job env |
| `DATABASE_USERNAME` | `postgres` | Cloud Run Job env |
| `DATABASE_PASSWORD` | *(secret)* | **Secret Manager** → env ref |
| `DATABASE_NAME` | `sbiaudiopod` / `backup` | Cloud Run Job env |
| `DATABASE_SSL_ENABLED` | `true` for Cloud SQL public IP | Cloud Run Job env |

### Decryption (encrypted merchant names)

| Variable | Where |
|----------|-------|
| `ENCRYPTION_KEY` | Secret Manager (same as soundbox-backend) |
| `IV` | Secret Manager |

### GCS / Iceberg

| Variable | Example |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | `your-gcp-project` |
| `GCP_REGION` | `asia-south1` |
| `GCS_BUCKET` | `soundbox-iceberg-warehouse` |
| `WAREHOUSE_PATH` | `gs://soundbox-iceberg-warehouse/soundbox` |
| `ICEBERG_NAMESPACE` | `soundbox` |
| `UPLOAD_TO_GCS` | `true` |
| `INGEST_MODE` | `incremental` (or `full` for first run) |
---

## 3. GitHub Actions (CI/CD secrets & vars)

Set in **GitHub → Repository → Settings → Secrets and variables → Actions**:

### Secrets

| Name | Value |
|------|-------|
| `ENCRYPTION_KEY` | Hex key from soundbox-backend |
| `IV` | IV from soundbox-backend |
| `GCP_SA_KEY` | Service account JSON (for optional GCS CI job) |
| `DATABASE_PASSWORD` | Only if running remote DB smoke tests |

### Variables

| Name | Value |
|------|-------|
| `GCS_BUCKET` | `soundbox-iceberg-warehouse` |
| `WAREHOUSE_PATH` | `gs://soundbox-iceberg-warehouse/soundbox` |
| `GOOGLE_CLOUD_PROJECT` | GCP project id |
| `GCP_REGION` | `asia-south1` |

CI runs **fully mocked tests** — no Postgres service container and no GCS credentials required in GitHub Actions.

---

## 4. One-time setup commands

```bash
# 1. Create bucket
gcloud storage buckets create gs://soundbox-iceberg-warehouse --location=asia-south1

# 2. Service account
gcloud iam service-accounts create lakehouse-ingest \
  --display-name="Soundbox Lakehouse Ingest"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:lakehouse-ingest@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# 3. Build & push image
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/lakehouse/ingest:latest \
  -f Dockerfile .


# 5. Ingest job
gcloud run jobs create soundbox-lakehouse-ingest \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/lakehouse/ingest:latest \
  --region $REGION \
  --service-account lakehouse-ingest@$PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets "DATABASE_PASSWORD=db-password:latest,ENCRYPTION_KEY=encryption-key:latest,IV=iv:latest" \
  --set-env-vars "DATABASE_HOST=...,DATABASE_NAME=...,WAREHOUSE_PATH=...,UPLOAD_TO_GCS=true,INGEST_MODE=incremental"

# 6. Schedule every 30 minutes
gcloud scheduler jobs create http lakehouse-ingest-schedule \
  --location $REGION \
  --schedule "*/30 * * * *" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/soundbox-lakehouse-ingest:run" \
  --http-method POST \
  --oauth-service-account-email lakehouse-ingest@$PROJECT_ID.iam.gserviceaccount.com
```

---

## 5. Local run (no GCS)

```powershell
# Copy .env.example → .env and fill DATABASE_* from soundbox-backend
copy .env.example .env

pip install -r requirements.txt
$env:UPLOAD_TO_GCS="false"
python -m app.main
```

Parquet lands in `.tmp/lakehouse/` — DuckDB / Chanakya can read the same layout.

---

## 6. Incremental vs full

| Mode | Env | Behaviour |
|------|-----|-----------|
| `incremental` | `INGEST_MODE=incremental` | Reads watermark from GCS, pulls only `created_at > watermark` |
| `full` | `INGEST_MODE=full` | Full table export (first run or rebuild) |

Watermarks stored at: `gs://<bucket>/watermarks/<table>.txt`

---

## 7. What is NOT real-time

New rows in soundbox Postgres appear in Iceberg **after the next job run** (scheduler interval). This is batch ingestion by design — the AI service reads the lakehouse snapshot, not live DB.

---

## 8. Billions of rows — PySpark

For large-scale ingest use **PySpark + Dataproc Serverless**, not the pandas engine or Cloud Run.

See **[docs/SPARK_INGESTION.md](SPARK_INGESTION.md)** for full setup (`INGEST_ENGINE=spark`, parallel JDBC, Dataproc batch submit).
