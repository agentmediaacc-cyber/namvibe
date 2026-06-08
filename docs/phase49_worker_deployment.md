# Phase 49 Worker Deployment

Phase 49 adds CHAIN background jobs, workers, scheduled tasks, Redis hardening, and safe fallback behavior.

## Local commands

Run one worker pass:

```bash
python scripts/run_worker.py --worker-name worker-1 --worker-type default --once
```

Run a continuous worker:

```bash
python scripts/run_worker.py --worker-name worker-1 --worker-type default --interval 2 --queues default,notifications,safety,wallet
```

Run scheduler once:

```bash
python scripts/run_scheduler.py --once
```

Run scheduler loop:

```bash
python scripts/run_scheduler.py --interval 10
```

Check queue health:

```bash
python scripts/queue_health.py
```

## VPS systemd examples

Worker service:

```ini
[Unit]
Description=CHAIN background worker
After=network.target

[Service]
WorkingDirectory=/opt/chain_app
Environment=FLASK_ENV=production
Environment=REDIS_URL=redis://127.0.0.1:6379/0
ExecStart=/opt/chain_app/venv/bin/python scripts/run_worker.py --worker-name worker-1 --worker-type default --interval 2 --queues default,notifications,safety,wallet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Scheduler service:

```ini
[Unit]
Description=CHAIN scheduler
After=network.target

[Service]
WorkingDirectory=/opt/chain_app
Environment=FLASK_ENV=production
Environment=REDIS_URL=redis://127.0.0.1:6379/0
ExecStart=/opt/chain_app/venv/bin/python scripts/run_scheduler.py --interval 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Redis recommendation

Use a local Redis instance on single VPS deployments and a managed Redis-compatible service for multi-host deployments. Set:

```bash
REDIS_URL=redis://127.0.0.1:6379/0
```

The queue system remains safe if Redis is unavailable. It falls back to database-backed or in-memory behavior depending on environment and database availability.

## Environment variables

- `REDIS_URL` or `CHAIN_REDIS_URL`: Redis connection string.
- `CHAIN_REDIS_CONNECT_TIMEOUT`: Redis connect timeout in seconds.
- `CHAIN_REDIS_SOCKET_TIMEOUT`: Redis socket timeout in seconds.
- `CHAIN_MEDIA_CLEANUP_DRY_RUN`: keep media cleanup in dry-run mode when `1`.
- `CHAIN_FAST_LOCAL`: force local/fallback behavior outside production.
- `CHAIN_TEST_FAKE_DB`: force in-memory behavior for tests.

## Limitations

Phase 49 provides the infrastructure foundation. Horizontal scaling is only active after Redis, worker processes, and scheduler processes are deployed and supervised in the production environment.
