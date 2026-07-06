# NamVibe Local Cloudflare Runbook

## Start local origin

```bash
./scripts/start_namvibe_local_cloudflare.sh
```

This script:
- kills stale listeners on port `8080`
- removes a stale Gunicorn PID file
- exports local-only fast startup flags
- starts Gunicorn with one `eventlet` worker on `0.0.0.0:8080`

## Run Cloudflare tunnel

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run namvibe
```

## Test local and domain

```bash
./scripts/test_namvibe_local_domain.sh
./scripts/smoke_namvibe_core_routes.sh
```

Optional overrides:

```bash
DOMAIN=example.com PORT=8080 ./scripts/test_namvibe_local_domain.sh
PORT=8080 ./scripts/smoke_namvibe_core_routes.sh
```

## Homepage interaction debugging

Like and comment fixes for the homepage live in the inline JavaScript inside `templates/chain_home.html`.

The real browser test for homepage interactions is `scripts/browser_test_homepage_interactions.py`.

Run it with:

```bash
./scripts/start_namvibe_local_cloudflare.sh
NAMVIBE_PUBLIC_BASE_URL=http://127.0.0.1:8080 ./venv/bin/python scripts/browser_test_homepage_interactions.py
```

This test:
- logs in as `alpha_user` when credentials are available
- waits for `NAMVIBE_HOME_INTERACTIONS_READY`
- waits for `NAMVIBE_HOME_LIKES_READY`
- selects only real post cards with `data-type="post"`
- ignores live-room cards
- verifies the like toggle flow
- verifies comment submit
- saves screenshots to `/tmp`

Troubleshooting:
- If Like calls `/api/home/post/<id>/like` but the ID is a live room ID, fix feed card typing.
- If the browser console shows `SyntaxError`, run `node --check` on the extracted inline script.
- If `curl` tests pass but the browser fails, run the Playwright browser test.
- If stale code appears, check these build markers in the browser:

```js
window.NAMVIBE_HOME_BUILD
window.NAMVIBE_HOME_INTERACTIONS_READY
window.NAMVIBE_HOME_LIKES_READY
```

## Read logs

```bash
tail -n 80 logs/gunicorn_error.log
tail -n 80 logs/gunicorn_access.log
```

## What Cloudflare 524 means

Cloudflare `524` means Cloudflare connected to the origin but the origin did not send a complete HTTP response before Cloudflare timed out. In this project that usually points to slow startup, blocking request handling, or a worker stuck on DB/network work before returning a response.

## Stop Gunicorn

```bash
kill "$(cat logs/gunicorn.pid)"
```

If the PID file is stale or the port is still busy:

```bash
lsof -ti tcp:8080
kill <pid>
```

## Warning

`CHAIN_FAST_LOCAL=1`, `CHAIN_DISABLE_PREWARM=1`, `CHAIN_DISABLE_DB_PING=1`, and `CHAIN_DISABLE_SCHEMA_CHECK=1` are for local startup testing only. Do not enable them in real production unless you explicitly want reduced startup checks and degraded health coverage.
