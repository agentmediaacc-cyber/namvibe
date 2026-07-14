# Cloud Run Redis Setup

The app needs a managed Redis instance for real-time features on Cloud Run.
The current `.env` has `REDIS_URL=redis://localhost:6379/0` — works locally,
but on Cloud Run there is no localhost Redis, so features fall back to
in-memory (degraded real-time, no cross-instance Socket.IO, no caching).

Two options below. Pick one.

---

## Option A: Upstash Redis (Recommended for test deploy)

Upstash offers a free tier (10 MB) with TLS — zero config, no VPC needed.

### 1. Create a database

- Go to https://console.upstash.com/ -> Create Database
- Name: `chain-app-redis`
- Region: `us-west-1` (or any, latency is low)
- TLS: **Enabled** (required for Cloud Run over public internet)
- Eviction: `allkeys-lru`
- Click Create

### 2. Copy the Redis URL

On the database details page, find **REST URL** or **UPSTASH_REDIS_REST_URL**.
You need the **Redis TLS connection string**, which looks like:

```
rediss://usw1-valid-koala-12345.upstash.io:6379
```

Note `rediss://` (TLS) not `redis://` — Cloud Run requires TLS for external
connections.

### 3. Update Google Secret Manager

```bash
echo -n 'rediss://usw1-valid-koala-12345.upstash.io:6379' | \
gcloud secrets versions add chain-redis-url \
  --project YOUR_PROJECT_ID --data-file=- --quiet
```

### 4. Re-deploy

The next `gcloud run deploy` will pick up the new secret version.

---

## Option B: Google Memorystore (Production)

Memorystore Redis runs inside your VPC — lower latency, no public internet
exposure, but requires a Serverless VPC Access connector.

### 1. Create the VPC connector

```bash
gcloud compute networks vpc-access connectors create redis-connector \
  --region us-central1 \
  --network default \
  --range 10.8.0.0/28 \
  --project YOUR_PROJECT_ID
```

### 2. Create the Redis instance

```bash
gcloud redis instances create chain-app-redis \
  --size=1 \
  --region=us-central1 \
  --redis-config maxmemory-policy=allkeys-lru \
  --project YOUR_PROJECT_ID
```

Get the internal IP:

```bash
gcloud redis instances describe chain-app-redis \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --format='value(host)'
# e.g. 10.65.123.4
```

### 3. Update Google Secret Manager

```bash
echo -n 'redis://10.65.123.4:6379/0' | \
gcloud secrets versions add chain-redis-url \
  --project YOUR_PROJECT_ID --data-file=- --quiet
```

### 4. Deploy Cloud Run with VPC connector

```bash
gcloud run deploy chain-app \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --image gcr.io/YOUR_PROJECT_ID/chain-app:latest \
  --vpc-connector redis-connector \
  --vpc-egress private-ranges-only
```

The `private-ranges-only` egress ensures only traffic to private IPs (the
Memorystore Redis) goes through the VPC connector — internet traffic uses
the default Cloud Run path (no extra cost).

---

## Verification

After deploying with either option, check Redis health:

```bash
curl https://<your-cloud-run-url>/health/redis
```

Expect:

```json
{
  "service": "redis",
  "status": "ok",
  "connected": true,
  "fallback": false,
  "latency_ms": 1.2,
  "circuit_state": "closed"
}
```

If `status` is `"degraded"` and `fallback` is `true`, Redis is not
reachable — check the connection string and VPC connector (if Memorystore).

---

## Cost comparison (approximate)

| Option   | Monthly cost | Setup time | Notes                        |
|----------|-------------|------------|------------------------------|
| Upstash  | $0 (free)   | 5 minutes  | TLS required, no VPC needed  |
| Upstash  | ~$1.50/mo   | 5 minutes  | 100 MB plan                  |
| Memorystore | ~$25/mo   | 15 minutes | VPC connector ~$18/mo + Redis ~$7/mo |

Upstash is recommended for test/development. Memorystore is recommended for
production with compliance requirements.
