# Render Free Test Deployment

Deploy chain-app to Render's free tier using the existing Dockerfile.
Neon + Upstash Redis work on Render free plan.

---

## Prerequisites

- GitHub repo with this code pushed
- Render account (https://render.com)
- env var values ready (from `.env`):

  | Variable | Source |
  |---|---|
  | `SECRET_KEY` | `.env` |
  | `DATABASE_URL` | `.env` (Neon) |
  | `REDIS_URL` | `.env` (Upstash `rediss://...`) |
  | `SUPABASE_URL` | `.env` |
  | `SUPABASE_ANON_KEY` | `.env` |
  | `SUPABASE_SERVICE_ROLE_KEY` | `.env` |
  | `APP_BASE_URL` | `https://<your-app>.onrender.com` (set *after* deploy) |

---

## Option A: Blueprint (render.yaml)

Fastest — uses the existing `render.yaml` in the repo.

1. Render Dashboard → **New + Blueprint**
2. Connect your GitHub repo
3. Render reads `render.yaml` and creates the `chain-app` service
4. Go to **Environment** tab → fill in all `sync: false` secrets:
   - `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - `APP_BASE_URL` (set to your deployed URL after creation)
5. Click **Apply**
6. Wait for build + deploy (~5 min)

---

## Option B: Manual (Dashboard)

1. Render Dashboard → **New + Web Service**
2. Connect your GitHub repo
3. Settings:

   | Field | Value |
   |---|---|
   | Name | `chain-app` |
   | Runtime | `Docker` |
   | Build Command | *(leave default)* |
   | Start Command | *(leave default)* |
   | Plan | **Free** |
   | Region | `Oregon (US West)` |
   | Health Check Path | `/healthz` |

4. **Environment Variables** — add these (all):

   ```
   FLASK_ENV=production
   ENV=production
   REDIS_SSL_CERT_REQS=required
   SECRET_KEY=<from .env>
   DATABASE_URL=<from .env>
   REDIS_URL=<from .env>            # rediss://... for Upstash
   SUPABASE_URL=<from .env>
   SUPABASE_ANON_KEY=<from .env>
   SUPABASE_SERVICE_ROLE_KEY=<from .env>
   APP_BASE_URL=https://chain-app.onrender.com   # update after deploy
   ```

5. Click **Create Web Service**
6. Wait for build + deploy (~5 min)

---

## Post-deploy

### 1. Update APP_BASE_URL

After the first deploy, Render assigns a URL like `https://chain-app.onrender.com`.
Update the `APP_BASE_URL` env var to this value and **Deploy** → **Clear build cache & deploy**.

### 2. Verify

```bash
curl https://chain-app.onrender.com/healthz
curl https://chain-app.onrender.com/
curl https://chain-app.onrender.com/health/redis
```

Or use the smoke test:

```bash
python3 scripts/test_cloudrun_smoke.py --url https://chain-app.onrender.com
```

### 3. Check Redis

```bash
curl https://chain-app.onrender.com/health/redis
```

Expect:

```json
{
  "connected": true,
  "redis_url_scheme": "rediss",
  "ssl_cert_reqs": "required"
}
```

### 4. Free tier notes

| Limit | Render free | Impact |
|---|---|---|
| Sleep after inactivity | 15 min | First request after idle is slow (~10s cold start) |
| Build minutes | 500 / mo | Plenty for a test deploy |
| Bandwidth | 100 GB / mo | Fine for testing |
| Postgres | No built-in | Use Neon (external, free) |
| Redis | No built-in | Use Upstash (external, free) |

### 5. Wake-up cron (optional)

To prevent idle sleep on the free tier, set a cron job anywhere (GitHub Actions,
cron-job.org, UptimeRobot) that pings `/healthz` every 10 minutes.

---

## Troubleshooting

**Build fails with `ERROR: failed to solve`**  
→ Check Render's Docker build logs. Common issues:
- Out of memory: Free tier has limited build RAM. Retry.
- `pip install` timeout: Requirements already cached, retry.

**App crashes at startup**  
→ Check Render's Runtime logs. Most common cause: missing env var.
→ All required env vars must be set (see list above).

**`/healthz` returns 503**  
→ One or more upstream services (DB, Redis) are unreachable.
→ Check `/health/redis` and `/health/db` for specific failures.

**Redis reports `connected: false`**  
→ Verify `REDIS_URL` in Render env vars is the full `rediss://...` string.
→ Verify `REDIS_SSL_CERT_REQS=required` is set (or omit it — default is required).
