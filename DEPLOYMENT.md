# Production deployment — Soundbox Intelligence Service

## Architecture

```
Mobile/Web → JWT → on-prem-soundbox-backend → X-API-Key → soundbox-lakehouse (Cloud Run Service)
                         ↓
                    Postgres (conversation history)
```

Lakehouse is **stateless** — the backend sends `conversation_history` on every request.

## Prerequisites

1. GCP project with Artifact Registry, Cloud Run, Secret Manager
2. Ingestion job populating parquet (local or GCS)
3. Shared secret `LAKEHOUSE_API_KEY` (32+ characters) in Secret Manager on **both** services

## Secrets (GCP Secret Manager)

| Secret | Used by |
|--------|---------|
| `LAKEHOUSE_API_KEY` | lakehouse API + soundbox-backend |
| `GEMINI_API_KEY` | lakehouse API |

```bash
echo -n "your-32-char-minimum-shared-secret" | gcloud secrets create LAKEHOUSE_API_KEY --data-file=-
echo -n "your-gemini-key" | gcloud secrets create GEMINI_API_KEY --data-file=-
```

Grant the Cloud Run service account `roles/secretmanager.secretAccessor` on both secrets.

## Deploy lakehouse

```bash
gcloud builds submit --config=cloudbuild.yaml
```

This pipeline only **builds, pushes, and deploys the image** — same minimal pattern as `on-prem-soundbox-backend/cloudbuild.yaml`. It does not set memory, secrets, env vars, or probes; configure those **once** on the Cloud Run service in GCP (console or `gcloud run services update`).

1. Builds and pushes the Docker image
2. Deploys **Cloud Run Job** `soundbox-lakehouse-ingest` (scheduled ingestion)
3. Deploys **Cloud Run Service** `soundbox-lakehouse-api` (Intelligence API — image only)

### One-time Cloud Run service setup (GCP console or gcloud)

Set these on `soundbox-lakehouse-api` before or after first deploy:

| Variable | Value |
|----------|-------|
| `RUN_MODE` | `server` |
| `AUTH_ENABLED` | `true` |
| `AUTH_API_KEY_ONLY` | `true` |
| `CORS_ENABLED` | `false` |
| `LAKEHOUSE_API_KEY` | Secret Manager |
| `GEMINI_API_KEY` | Secret Manager |

### Health probes

| Probe | Path | Purpose |
|-------|------|---------|
| Liveness | `GET /health` | Process alive |
| Readiness / startup | `GET /ready` | Auth, Gemini, parquet data available |

### Network

Restrict lakehouse to internal traffic only (recommended):

```bash
gcloud run services update soundbox-lakehouse-api \
  --region=asia-south1 \
  --ingress=internal-and-cloud-load-balancing
```

## Deploy soundbox-backend

Add to production environment:

```env
INTELLIGENCE_ENABLED=true
LAKEHOUSE_BASE_URL=https://soundbox-lakehouse-api-<hash>-as.a.run.app
LAKEHOUSE_API_KEY=<same secret as lakehouse>
LAKEHOUSE_TIMEOUT_MS=60000
INTELLIGENCE_MAX_HISTORY_TURNS=20
LAKEHOUSE_MAX_RETRIES=2
INTELLIGENCE_RETENTION_DAYS=90
INTELLIGENCE_SOFT_DELETE_PURGE_DAYS=7
CRON_ENABLED=true
```

Run database migration:

```bash
npm run migration:run
```

## Verify end-to-end

```bash
# 1. Lakehouse readiness
curl https://<lakehouse-url>/ready

# 2. Backend copilot (with user JWT)
curl -X POST https://<backend-url>/api/v1/intelligence/copilot/query \
  -H "Authorization: Bearer <user-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is today GMV?"}'
```

## Rate limiting note

Rate limits are in-memory per Cloud Run instance. For global limits across replicas, add Cloud Armor or Redis-backed throttling at the load balancer.

## Ingestion schedule

Schedule the ingest job (e.g. nightly):

```bash
gcloud scheduler jobs create http lakehouse-ingest-nightly \
  --schedule="0 2 * * *" \
  --uri="https://<region>-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<project>/jobs/soundbox-lakehouse-ingest:run" \
  --http-method=POST \
  --oauth-service-account-email=<sa>@<project>.iam.gserviceaccount.com
```
