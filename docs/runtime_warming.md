# Runtime Warming

Gunicorn workers should start serving requests immediately.

Use the explicit warmer after the app is healthy:

```bash
python3 scripts/warm_production_runtime.py --homepage
python3 scripts/warm_production_runtime.py --reels
python3 scripts/warm_production_runtime.py --all
```

Notes:

- Worker startup no longer runs homepage or Reel warming automatically.
- The warmer is cache-first and will verify existing shared cache without forcing Neon work unless `--force-refresh` is used.
- Use `--check-database` only when you explicitly want a standalone Neon readiness probe.
- Shared Redis locking remains in place for the warm stages.
- The warmer exits nonzero if verification fails.
