# NamVibe Go-Live Checklist

Use this checklist before public launch. Phase 50 validates application readiness, but production readiness still depends on deployed infrastructure.

## Infrastructure

- VPS or hosting environment provisioned.
- Domain DNS points to the production host.
- Firewall allows only required ports: HTTP/HTTPS, SSH, Redis only if private.
- Application process supervised by systemd or equivalent.

## Database

- `DATABASE_URL` configured for production Neon/PostgreSQL.
- All migrations through Phase 50 applied.
- Connection pool verified.
- Database backup schedule configured and tested.

## Redis

- `REDIS_URL` or `CHAIN_REDIS_URL` configured.
- Redis is private or access-controlled.
- Redis health endpoint returns connected status.
- Rate limiting and queue workers use Redis in production.

## Workers

- At least one worker process deployed:
  `python scripts/run_worker.py --worker-name worker-1 --worker-type default --interval 2 --queues default,notifications,safety,wallet`
- Worker heartbeat appears in `/system/api/workers`.
- Failed job retry path tested.

## Scheduler

- Scheduler process deployed:
  `python scripts/run_scheduler.py --interval 10`
- Scheduled tasks visible in `/system/api/scheduled-tasks`.
- Call timeout, notification, payout, safety, media, and trust jobs are enabled.

## Backups

- Database backups configured.
- Media/storage backups configured.
- Backup location recorded in environment.
- Restore procedure documented and tested.

## SSL

- HTTPS certificate installed.
- HTTP redirects to HTTPS.
- Secure cookies enabled.
- HSTS configured at proxy or app layer.

## Domain

- Production domain configured via `CHAIN_PUBLIC_DOMAIN` or `APP_DOMAIN`.
- OAuth/callback URLs updated for production.
- Push notification origins updated.

## Monitoring

- `/healthz` monitored by uptime checks.
- `/system/api/health` reviewed after deploy.
- Queue depth and failed jobs monitored.
- Worker heartbeats monitored.

## Alerts

- Critical alerts reviewed daily until automated delivery is wired.
- Alert resolution flow tested.
- Database, Redis, worker, scheduler, storage, wallet, safety, and notification components tracked.

## Wallet Review

- Payout workflow reviewed by an admin.
- Wallet fraud rules enabled.
- Payout review worker running.
- Platform fee calculations verified.

## Safety Review

- Report flow tested.
- Moderation queue reviewed.
- Spam and fraud event logging verified.
- Trust score summary verified.

## Security Review

- Strong `SECRET_KEY` configured.
- Debug mode disabled.
- CSRF enabled.
- Rate limits configured with Redis.
- Session cookies secure, HttpOnly, and SameSite.

## Performance Review

- Run `python scripts/benchmark_chain.py`.
- Health endpoint under 300ms.
- Queue stats under 100ms.
- Trust summary under 200ms.
- No known blocking background work remains in request paths.
