# NamVibe Environment Variables Reference

> Never commit secrets to git. Use Google Secret Manager (Cloud Run) or Render Dashboard secrets (sync: false).

## Required (App Will Not Start Without These)

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Flask session signing key (≥32 chars, random) | `k3bX...mq9` |
| `DATABASE_URL` | Neon PostgreSQL connection string (pooler endpoint) | `postgresql://user:pass@ep-xxx-pooler.us-east-1.aws.neon.tech/neondb` |
| `REDIS_URL` or `REDIS_TLS_URL` | Upstash Redis with TLS | `rediss://default:pass@fluent-rabbit-xxx.upstash.io:6379` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon/public key | `eyJhbGci...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | `eyJhbGci...` |

## Environment Mode

| Variable | Recommended | Purpose |
|---|---|---|
| `FLASK_ENV` | `production` | Enables production security settings: secure cookies, CSRF strict, debug disabled |
| `ENV` | `production` | Secondary env indicator used by services |

## Authentication

| Variable | Default | Purpose |
|---|---|---|
| `ALLOW_LOCAL_AUTH_FALLBACK` | unset (false) | When `true`, allows local password auth when Supabase is unreachable. **Must be false or unset in production.** |
| `SUPABASE_JWT_SECRET` | — | JWT secret for verifying Supabase tokens locally |

## Deployment

| Variable | Purpose |
|---|---|
| `PORT` | HTTP port (set by Cloud Run / Render automatically) |
| `APP_BASE_URL` | Public base URL for the app (e.g. `https://namvibe.com`) |
| `APP_NAME` | Display name (default: `NamVibe`) |
| `APP_DOMAIN` | Domain for cookie and link generation |

## Redis / Caching

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_SSL_CERT_REQS` | `required` | SSL cert verification level: `required`, `optional`, `none` |
| `CHAIN_SOCKETIO_REDIS_MANAGER` | `1` | Set to `0` to disable Redis-backed Socket.IO (single-node mode) |
| `CHAIN_DISABLE_RATE_LIMITS` | unset | Set to `1` to disable rate limiting (development only) |

## Rate Limiting

| Variable | Default | Purpose |
|---|---|---|
| `CHAIN_DISABLE_RATE_LIMITS` | unset | Disables all rate limits when `1` |
| `RATELIMIT_STORAGE_URI` | auto | Override rate limit storage (defaults to Redis if available, memory otherwise) |

## File Uploads

| Variable | Default | Purpose |
|---|---|---|
| `MAX_CONTENT_LENGTH` | 100MB | Maximum upload size (set in app.py) |
| `CHAIN_ALLOW_LOCAL_UPLOADS` | unset | When `1`, uploads to local filesystem instead of Supabase (development only) |

## Call / WebRTC

| Variable | Purpose |
|---|---|
| `LIVEKIT_URL` | LiveKit server URL (for scalable video calls) |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `TURN_SERVER_URL` | TURN server URL for WebRTC relay |
| `TURN_USERNAME` | TURN server username |
| `TURN_PASSWORD` | TURN server credential |

## Monitoring & Error Tracking

| Variable | Purpose |
|---|---|
| `SENTRY_DSN` | Sentry DSN for error tracking (recommended for beta) |

## Feature Flags (Development Only)

| Variable | Purpose |
|---|---|
| `CHAIN_FAST_LOCAL` | When `1`, skips DB pings and prewarming for faster local dev |
| `CHAIN_TEST_MODE` | When `1`, skips Redis caching and uses direct DB queries |
| `CHAIN_DISABLE_DB_PING` | Skips DB health ping (fast local mode) |
| `CHAIN_ENABLE_SCHEDULER` | When `1`, starts the APScheduler background worker |
| `CHAIN_WARM_SCHEMA` | When `1`, pre-warms schema registry on startup |
| `CHAIN_DISABLE_PAYOUTS` | Emergency disable for payout endpoints |
| `CHAIN_DISABLE_REGISTRATION` | Emergency disable for new user registration |
| `CHAIN_MAINTENANCE_MODE` | When `1`, shows maintenance page to non-admins |
| `CHAIN_MAINTENANCE_MESSAGE` | Custom maintenance message |
| `CHAIN_TRUST_PROFILE_SCHEMA` | When `1` (default), uses static column cache for schema checks |
| `CHAIN_DEV_DIAGNOSTICS` | When `1`, registers `/dev/*` diagnostic routes |

## Database

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Neon PostgreSQL connection string |
| `DB_MIN_CONN` | `1` | Minimum pool connections |
| `DB_MAX_CONN` | `5` | Maximum pool connections |

## Worker / Queue

| Variable | Purpose |
|---|---|
| `CHAIN_ENABLE_SCHEDULER` | Enable background scheduler |
| `WORKER_CONCURRENCY` | Worker concurrency (default: 10) |
