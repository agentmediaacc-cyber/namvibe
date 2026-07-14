# Runtime Warming

Gunicorn workers serve requests immediately. They do not run homepage or Reels cache warming automatically.

Use the explicit warm script after the app is healthy:

```bash
gunicorn app:app --bind 0.0.0.0:8080 --workers 1 --worker-class gevent --timeout 300 --keep-alive 5
curl http://127.0.0.1:8080/healthz
python3 scripts/warm_production_runtime.py --all
```

Notes:

- `scripts/warm_production_runtime.py --homepage` warms only homepage caches.
- `scripts/warm_production_runtime.py --reels` warms only public Reel caches.
- `scripts/warm_production_runtime.py --all` warms schema metadata, homepage caches, and public Reel caches.
- The warm script uses shared Redis locks when available.
- Failed warming does not prevent process health.
- Mutations still invalidate caches through the normal application paths.
