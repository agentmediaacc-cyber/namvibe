# Phase 77 — Production Deployment Verification

## 10-Area Verification Report

### 1. Environment

| Check | Status | Detail |
|---|---|---|
| `DATABASE_URL` | ✅ Documented | `.env.production.example` has blank entry; Neon PostgreSQL expected |
| `REDIS_URL` | ✅ Documented | `.env.production.example` has blank entry |
| `SECRET_KEY` | ⚠️ Weak fallback | Hardcoded `"chain-premium-default-secret"` if env var missing; `.env` has `chain-local-dev-secret-change-later` |
| `SESSION_COOKIE_SECURE` | ✅ Prod=True | Set to `is_prod` (line 239); `True` when `FLASK_ENV=production` |
| `SESSION_COOKIE_HTTPONLY` | ✅ True | Hardcoded `True` in both config blocks |
| `SESSION_COOKIE_SAMESITE` | ⚠️ Lax | `'Lax'` — `'Strict'` would be more secure |
| `PERMANENT_SESSION_LIFETIME` | ⚠️ 30 days | Overridden from 7 to 30 days — excessive for social platform |
| `CHAIN_DEV_TOOLS` | ✅ Should be 0 | Gate on message upgrade routes; must be `0` in production |
| `FLASK_DEBUG` | ✅ False | Debug is `False` in both production and dev branches |
| `CHAIN_ENV` | ⚠️ Not checked | `app.py._is_production_env()` checks `FLASK_ENV` and `ENV` but NOT `CHAIN_ENV` |

### 2. Gunicorn

| Check | Status | Detail |
|---|---|---|
| Worker count formula | ✅ | `cpu_count() * 2 + 1` in `gunicorn.conf.py` |
| Effective workers | ⚠️ Overridden | `systemd/chain.service` passes `--workers 2`, overriding config |
| Timeout | ✅ 60s | `timeout = 60` |
| Keepalive | ✅ 5s | `keepalive = 5` |
| Worker class | ⚠️ Default `sync` | Not specified in config; WebSocket needs `gevent-websocket` |
| WebSocket worker | ✅ | `chain-realtime.service` uses `GeventWebSocketWorker -w 1` |
| Worker connections | ✅ 1000 | `worker_connections = 1000` |
| Memory per worker | ⚠️ ~200MB estimate | 9 workers × ~200MB ≈ 1.8GB; 2 workers × ~200MB ≈ 400MB |

### 3. Nginx

| Check | Status | Detail |
|---|---|---|
| WebSocket upgrade | ✅ | `proxy_set_header Upgrade $http_upgrade` configured |
| Static file serving | ✅ | `alias /var/www/chain_app/static/` with `expires 30d` |
| Cache headers | ✅ | `Cache-Control: public, no-transform` on static, `max-age=30` on discoverable pages |
| Gzip | ❌ **Missing** | No `gzip` directives |
| Brotli | ❌ **Missing** | No `brotli` directives |
| Upload limit | ✅ 100MB | `client_max_body_size 100M` |
| HTTPS | ❌ **No SSL block** | Only port 80 server block; no `listen 443 ssl` |
| HSTS | ❌ **Missing** | No `Strict-Transport-Security` header |

### 4. SSL

| Check | Status | Detail |
|---|---|---|
| HTTPS redirect | ❌ | Not in example config; VPS runbook uses certbot to add |
| Secure cookies | ✅ | `SESSION_COOKIE_SECURE=True` in production |
| HSTS | ❌ | Listed as desired in `security_hardening_service.py` but never set |
| Certbot readiness | ✅ | Documented in VPS runbook (Step 3) |

### 5. Storage

| Check | Status | Detail |
|---|---|---|
| Profile photos | ✅ Supabase | `chain-avatars`, `chain-covers` buckets; local fallback at `static/uploads/profile/` |
| Story media | ✅ Supabase | `chain-stories` bucket; 24h auto-expiry via scheduler |
| Reels | ⚠️ Mixed | Local `static/uploads/reels/` primary; Supabase `chain-reels` via legacy path |
| Voice notes | ✅ Supabase | `chain-messages` bucket via `upload_media_file()` |
| Upload cleanup | ⚠️ Partial | Story expiry works (every 15min). Orphaned files in `static/uploads/` accumulate. Supabase objects not deleted on DB soft-delete. |

### 6. Messaging

| Check | Status | Detail |
|---|---|---|
| WebSocket reconnect | ✅ | 10 attempts, 1-10s delay, 0.5 jitter, reconnect banner |
| Offline delivery | ⚠️ Partial | Messages persist in DB; delivery state machine `queued→sending→delivered→seen`; no push notification queue |
| Read receipts | ✅ | `mark_thread_seen()`, `delivery_status='seen'`, double-check UI |
| Typing indicators | ✅ | 10s TTL; 300ms debounce start; 1000ms debounce stop |
| Group chat reliability | ✅ | Mesh topology, ICE restart, host transfer, 32 max participants |
| Client retry | ✅ | `maxRetries=5`, `retryDelay=3000ms`, `localStorage` pending queue |

### 7. Calls

| Check | Status | Detail |
|---|---|---|
| WebRTC config | ✅ | ICE restart, connection state monitoring, reconnection overlay |
| STUN | ✅ | `stun:stun.l.google.com:19302` (configurable via env var) |
| TURN | ❌ **Not configured** | `TURN_SERVER_URL` env var is empty; calls may fail on symmetric NAT |
| Call timeout | ✅ 30s server / 15s client | Server marks as `missed` after 30s; client shows "No answer" after 15s |
| Busy detection | ✅ | Server checks both caller/receiver for active calls; client emits `call:busy` |
| Reconnect handling | ✅ | ICE state monitoring, `call:reconnecting`/`call:reconnected` events, 30s overlay timeout |
| Rate limit | ✅ | 3 calls per 30s to same receiver; 10s duplicate prevention |

### 8. Monitoring

| Check | Status | Detail |
|---|---|---|
| Health endpoints | ✅ | `/healthz`, `/health/db`, `/health/redis`, `/health/realtime`, `/health/supabase` |
| Error logging | ✅ | Structured JSON to stdout; Sentry optional via `SENTRY_DSN` |
| Slow query logging | ✅ | `>500ms` threshold in `neon_service.py`; budget-based in `query_optimizer.py` |
| Worker monitoring | ⚠️ Minimal | Gunicorn logs to stdout; RQ worker has no heartbeat monitoring |
| Redis monitoring | ⚠️ Partial | Health checks (ping, latency, circuit state); no hit-ratio or memory monitoring |
| Metrics | ⚠️ In-memory only | Route latency (p50/p95) stored in `defaultdict(deque(maxlen=200))`; resets on restart |
| Alerting | ❌ In-memory only | `_ALERTS = []` list; no email/Slack/PagerDuty delivery |

### 9. Security

| Check | Status | Detail |
|---|---|---|
| Auth bypass | ❌ **~50+ unprotected routes** | `system_routes.py` (18 routes), `production_routes.py` (12), `live_routes.py` (20+) have NO auth |
| Admin route protection | ⚠️ Partial | `admin_routes.py` uses `@require_admin`/`@require_master_admin`; `admin_safety_routes.py` uses `@login_required` (user-level, not admin) |
| CSRF | ❌ **No CSRF protection** | No `WTF_CSRF_ENABLED`, no CSRF middleware, no `csrf_token` in templates |
| Rate limits | ✅ | Global 200/day 50/hour; per-endpoint limits for auth, messages, wallet, dating |
| Upload validation | ⚠️ Extension-only | No MIME type or magic byte verification; old `save_upload()` has zero validation |
| JWT validation | ❌ **Non-functional** | Bearer token parsing is a placeholder comment — does nothing |
| Session lifetime | ⚠️ 30 days | Excessive window for hijacking |
| Password policy | ⚠️ Weak | Only minimum 8 chars; no complexity requirements |

### 10. Backup

| Check | Status | Detail |
|---|---|---|
| Database backup | ❌ **No automated backup** | Referenced `scripts/backup_db.sh` does not exist; Neon provides automatic snapshots (external) |
| Media backup | ❌ **No automated backup** | Referenced `scripts/sync_media_backup.sh` does not exist |
| Restore procedure | ⚠️ Documented only | Disaster recovery doc describes procedure; referenced `scripts/restore_media.py` does not exist |
| Backup env vars | ❌ Not set | `CHAIN_BACKUP_LOCATION`, `BACKUP_BUCKET`, `DATABASE_BACKUP_URL` not in `.env` or `.env.production.example` |

---

## Verdict

| Area | Score | GO/NO-GO |
|---|---|---|
| 1. Environment | 85/100 | GO (minor: session lifetime, CHAIN_ENV inconsistency) |
| 2. Gunicorn | 75/100 | GO (workers override in systemd needs fixing) |
| 3. Nginx | 60/100 | **NO-GO** (no HTTPS, no gzip, no HSTS) |
| 4. SSL | 50/100 | **NO-GO** (no SSL in example config, no HSTS) |
| 5. Storage | 80/100 | GO (upload cleanup gaps documented) |
| 6. Messaging | 90/100 | GO (solid; TURN is the only gap) |
| 7. Calls | 75/100 | GO (TURN gap documented; can deploy without) |
| 8. Monitoring | 70/100 | GO (in-memory metrics acceptable for initial launch; add persistent later) |
| 9. Security | 50/100 | **NO-GO** (~50 unprotected routes, no CSRF, broken JWT, weak passwords) |
| 10. Backup | 30/100 | **NO-GO** (no backup scripts exist, restore not tested) |

**Overall: 67/100 — DEPLOYMENT NOT RECOMMENDED until security and backup gaps are addressed.**

---

## Required Actions Before Deployment

### Critical (BLOCKING)
1. **Remove `@login_required` gap on system_routes.py** — add `require_admin` to all 18 routes
2. **Remove `@login_required` gap on production_routes.py** — add `require_admin` to all 12 routes
3. **Add CSRF protection** — enable Flask-WTF CSRF, add tokens to all forms
4. **Fix JWT Bearer token validation** in `api_auth_service.py` — actually verify tokens via Supabase
5. **Set SECRET_KEY** to a strong random value via env var (not the dev default)

### High (RECOMMENDED BEFORE DEPLOYMENT)
6. **Add HTTPS redirect** to nginx config
7. **Add HSTS header** to nginx config
8. **Add gzip compression** to nginx config
9. **Create backup scripts** (`backup_db.sh`, `sync_media_backup.sh`)
10. **Set `CHAIN_BACKUP_LOCATION`** env var for production
11. **Add MIME type validation** for file uploads (not just extension)

### Medium (DO WITHIN FIRST WEEK)
12. **Reduce session lifetime** from 30 days to 7 days
13. **Fix `chain.service` workers override** — remove `--workers 2` to respect `gunicorn.conf.py`
14. **Add TURN server** for WebRTC calls behind NAT
15. **Set up external alert delivery** (Slack webhook for circuit breakers)
16. **Add password complexity** requirements
