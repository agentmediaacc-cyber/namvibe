# NamVibe Beta Monitoring Plan

## Health Endpoints

All health endpoints return JSON. Monitor these with an external uptime checker (e.g., Pingdom, UptimeRobot, or a cron job).

| Endpoint | Expected Status | Frequency | Action on Failure |
|---|---|---|---|
| `GET /healthz` | 200 | every 1 min | Alert devops — app may be down |
| `GET /health/db` | 200 (connected: true) | every 5 min | Check Neon pool, restart if circuit breaker open |
| `GET /health/redis` | 200 or 503 | every 5 min | 503 is OK if fallback mode is reported — check Redis separately |
| `GET /health/realtime` | 200 | every 5 min | Check Socket.IO and WebSocket status |

## Key Metrics to Watch

### App Health

| Metric | Threshold | Action |
|---|---|---|
| HTTP 5xx rate | >1% of requests | Check Sentry/logs, rollback if critical |
| HTTP 4xx rate | >10% of requests | May indicate auth or routing issue |
| p95 response time | >2000ms | Check for slow queries, Neon pool contention |
| Request throughput | sudden drop | May indicate routing or proxy issue |

### Neon Database

| Metric | Threshold | Action |
|---|---|---|
| Connection pool usage | >80% | Increase `DB_MAX_CONN` or investigate leaks |
| Query latency (p95) | >1000ms | Check for missing indexes or slow queries |
| Circuit breaker trips | >0 | Investigate root cause — likely timeout or connection failure |
| Slow queries (logged) | >10 per minute | Review query patterns, add indexes |

### Redis

| Metric | Threshold | Action |
|---|---|---|
| Memory usage | >80% of maxmemory-policy | Increase Redis memory limit or investigate keys |
| Cache hit rate | <50% | Check if caching is working correctly |
| Circuit breaker trips | >0 | Check Redis connectivity, network, auth |
| Fallback activations | >0 | Redis may be down — check and restart |

### Socket.IO / Realtime

| Metric | Threshold | Action |
|---|---|---|
| Emit failures | >5 per hour | Check Redis message queue, Socket.IO server |
| Connection errors | >10 per hour | Check WebSocket connectivity, gevent worker |

### Core Features

| Event | Monitor | Action on Spike |
|---|---|---|
| Registration failures | Logs + Sentry | Check Supabase auth, rate limits |
| Login failures | Logs + Sentry | Check Supabase auth, session service |
| Message send failures | Logs + Sentry | Check messaging engine, Neon DB |
| Call start failures | Logs + Sentry | Check WebRTC signaling, TURN server |
| Wallet transaction failures | Logs + Sentry | Check wallet engine, ledger service |
| Payout request failures | Logs + Sentry | Check payout service, admin approval |
| Upload failures | Logs + Sentry | Check Supabase storage, file size limits |

## Log Monitoring

### Critical Patterns (Alert Immediately)

```
CRITICAL
FATAL
Traceback (most recent call last)
Unhandled exception
Circuit breaker open
Connection pool exhausted
SSL connection closed unexpectedly
Cannot publish to redis
```

### Warning Patterns (Review Daily)

```
WARNING
slow_query (latency > 2000ms)
rate_limited
CSRF token missing
Login failed
Registration failed
```

## Alerting Setup

### Beta Phase (Manual)

- Review Sentry errors once per day
- Scan logs for critical patterns every morning
- Check health endpoints manually or via simple cron script

### Recommended Automated Alerts (Before Public Launch)

1. **Health endpoint failure** — external uptime monitor
2. **5xx error spike** — Sentry alert rule
3. **Circuit breaker open** — log-based alert
4. **Redis memory >80%** — Redis provider alert
5. **Neon storage >80%** — Neon Console alert
6. **Payout failure** — Sentry alert

## Dashboard Setup

Create a simple dashboard (spreadsheet or Grafana) tracking:

```
Date  | Health | DB ms | Redis ms | 5xx count | Regs | Msgs | Calls | Payouts
------|--------|--------|----------|-----------|------|------|-------|---------
06/22 | OK     | 45ms   | 12ms     | 3         | 5    | 120  | 8     | 0
```

Review this dashboard daily during the beta.

## Post-Beta Monitoring Frequency

| Phase | Check Frequency |
|---|---|
| First 24 hours | every 30 min |
| First week | every 2 hours |
| After stable | once per day |
