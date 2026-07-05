# Production Startup Checklist

## Gunicorn

- Start Gunicorn with the intended worker class and one or more known-good workers.
- Confirm the PID file is created.
- Confirm the process is listening on the expected port.
- Check `logs/gunicorn_error.log` immediately after boot.

## Cloudflare Tunnel

- Start the tunnel only after local origin is healthy.
- Confirm `https://namvibe.com/healthz` returns `200`.
- Confirm `https://namvibe.com/` returns `200`.
- A Cloudflare `524` means Cloudflare reached the origin but the origin did not answer in time.

## Redis

- Verify Redis is reachable or confirm fallback mode is acceptable for the environment.
- Check `/health/redis`.
- Confirm Socket.IO startup does not fail when Redis is unavailable.

## Neon

- Verify the database is reachable with `/health/db`.
- Watch latency and connection-pool errors in `logs/gunicorn_error.log`.
- Confirm startup does not block on schema introspection or import-time queries.

## Supabase

- Verify `/health/supabase`.
- Confirm auth and storage configuration are present.
- Confirm Supabase issues do not block public homepage startup.

## Health Endpoints

- Public lightweight health:
  - `/healthz`
- Deeper dependency health:
  - `/health/db`
  - `/health/redis`
  - `/health/supabase`
  - `/system/api/health`

## Smoke Tests

```bash
./scripts/test_namvibe_local_domain.sh
./scripts/smoke_namvibe_core_routes.sh
./scripts/smoke_namvibe_database.sh
```

## Logs

```bash
tail -n 80 logs/gunicorn_error.log
tail -n 80 logs/gunicorn_access.log
```

## Recovery Steps

1. Stop Gunicorn with the PID file or kill the stale listener on the port.
2. Clear a stale PID file if present.
3. Restart local origin and confirm `/healthz`.
4. Re-run the smoke scripts.
5. If Cloudflare still returns `524`, inspect request latency, DB connectivity, Redis connectivity, and worker boot logs.
