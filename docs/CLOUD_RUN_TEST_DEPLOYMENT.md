# NamVibe Cloud Run Test Deployment

This document describes how to deploy NamVibe to Google Cloud Run for testing purposes.

## Prerequisites

1.  **Google Cloud Project**: You must have a GCP project with billing enabled.
2.  **gcloud CLI**: Installed and authenticated (`gcloud auth login`).
3.  **Docker**: Installed locally for building (optional if using Cloud Build).
4.  **Core Services**:
    *   **Postgres (Neon/Supabase)**: `DATABASE_URL`
    *   **Redis**: `REDIS_URL`
    *   **Supabase**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

## Environment Variables

The following environment variables must be configured in Cloud Run:

| Variable | Description |
| :--- | :--- |
| `ENV` | Set to `production` |
| `FLASK_ENV` | Set to `production` |
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Redis connection string (e.g. `redis://...`) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Your Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key (for storage admin) |
| `APP_BASE_URL` | The public URL of your Cloud Run service |

## Building and Deploying

### Option 1: Using Cloud Build (Recommended)

This builds the image on Google Cloud and deploys it.

```bash
# 1. Build and push to Artifact Registry / GCR
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/chain-app

# 2. Deploy to Cloud Run
gcloud run deploy chain-app \
  --image gcr.io/YOUR_PROJECT_ID/chain-app \
  --platform managed \
  --region YOUR_REGION \
  --allow-unauthenticated \
  --set-env-vars="ENV=production,FLASK_ENV=production,SECRET_KEY=...,DATABASE_URL=...,REDIS_URL=...,SUPABASE_URL=...,SUPABASE_ANON_KEY=...,SUPABASE_SERVICE_ROLE_KEY=..."
```

### Option 2: Using YAML Configuration

Update `cloudrun.yaml` with your project details and run:

```bash
gcloud run services replace cloudrun.yaml
```

## Health Checks

After deployment, verify the service is running:

*   **App Status**: `https://YOUR_URL/healthz`
*   **Database**: `https://YOUR_URL/health/db`
*   **Redis**: `https://YOUR_URL/health/redis`
*   **Supabase**: `https://YOUR_URL/health/supabase`

## Limitations on Cloud Run

*   **Socket.IO / WebSockets**: Cloud Run supports WebSockets, but it requires **Session Affinity** to be enabled if using multiple instances. Without session affinity, clients may fail to handshake or disconnect frequently.
*   **WebRTC**: Large scale WebRTC (calls) is NOT recommended on Cloud Run due to the request/response nature and potential port limitations.
*   **Background Workers**: Cloud Run is "request-aware". If no requests are active, the CPU is throttled. Background workers (like those in `workers/`) may not run reliably unless they are triggered by a request or a separate job system (Cloud Run Jobs).
*   **Static Assets**: While served by Flask, for high production load it is recommended to use a CDN or Cloud Storage for static files.
*   **Local Storage**: `static/uploads` is ephemeral. Files saved here will be lost when the container restarts. **Always use Supabase Storage for permanent media.**

## Recommendations

For full production with heavy Realtime/WebRTC usage, a **VPS (Virtual Private Server)** or **GCE (Compute Engine)** is recommended to maintain persistent connections and reliable background processing. Cloud Run is excellent for stateless API scaling and frontend hosting.
