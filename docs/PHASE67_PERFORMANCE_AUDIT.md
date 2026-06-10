# Phase 67 — Enterprise Performance & Production Hardening Audit

## Summary
Audit performed across 107 service files, 45 route files, 136 templates, 5 premium JS bundles, and 29 CSS files.

---

## 1. Database Query Analysis

### Query Volume
- **876 explicit database query calls** across all service files
- 231 `fast_query()` calls, 229 `write_query()` calls
- 171 `safe_select()` calls, 74 `safe_insert()` calls
- 44 `table_exists()` calls in hot request paths

### N+1 Query Patterns (Critical)
| Location | Issue | Impact |
|----------|-------|--------|
| `live_service._notify_followers_live_stared()` | Fetches followers, then notifies each in a loop | O(n) queries per live start |
| `feed_service.get_personalized_feed()` | 5 sequential `safe_select` queries instead of JOINs | 5 queries per feed load |
| `trending_service.calculate_trending_scores()` | Loop with select-then-upsert per entity | O(n) per recalculation |
| `engagement_service` (like/comment/follow) | Multiple `safe_select` + `safe_insert` per action | 3-5 queries per interaction |
| `push_notification_engine.send_push_notification` | Fetches devices then enqueues per device in loop | O(n) per push send |

### Schema Introspection at Request Time (High Impact)
| File | Pattern | Frequency |
|------|---------|-----------|
| `homepage_service.py` | `get_table_columns()` per request | Every homepage load |
| `profile_service.py` | `table_exists()` + `get_table_columns()` | Every profile load |
| `live_service.py` | `get_cached_table_columns()` | Every live room operation |
| `content_service.py` | `get_table_columns()` | Every content write |
| `auth_service.py` | `table_exists()` | Every auth operation |

### Self-Healing Schema Recreation (Medium Impact)
| File | Tables Created at Startup |
|------|--------------------------|
| `content_service.py` | ~30 tables + ~15 indexes via `CREATE TABLE IF NOT EXISTS` |
| `message_delivery_service.py` | 1 table + 3 indexes |

---

## 2. Redis / Caching Analysis

### Current Coverage
- **517 Redis references** across codebase
- 20+ services import from `redis_service`
- Redis used for: caching, presence, rate limiting, pub/sub, job queues
- `engines.cache_engine` provides local-memory fallback

### Missing Cache Layers (Planned for Phase 67)
| Data | Current | Target |
|------|---------|--------|
| Profile lookups | Uncache | 5-min TTL |
| Feed tabs | Uncache | 2-min TTL |
| Notification counts | 30s polling | Real-time + 10s cache |
| Creator stats | Uncache | 10-min TTL |
| Marketplace home | Uncache | 5-min TTL |
| Dating discover | Uncache | 5-min TTL |

---

## 3. API Rate Limiting Coverage

### Current State
- Only **4 out of 45 route files** have explicit rate limits
- Global defaults: 200/day, 50/hour (too lenient)
- No per-user limits on auth, messages, wallet, marketplace, dating, AI

### Planned Limits
| Feature | Limit | Justification |
|---------|-------|---------------|
| Auth (login) | 10/min | Prevent brute force |
| Messages | 60/min | Prevent spam |
| Wallet | 30/min | Prevent abuse |
| Marketplace | 60/min | Prevent scraping |
| Dating | 60/min | Prevent rapid-fire |
| AI | 30/min | Prevent API cost abuse |

---

## 4. Background Jobs / Worker Analysis

### Current State
- **RQ (Redis Queue)** is the queue system (`rq==2.9.0`)
- Workers run on queues: `default`, `notifications`, `safety`, `wallet`
- `scheduler_service.py` manages periodic tasks
- `job_queue_service.py` provides `enqueue_unique_job()` with Redis fallback

### Expensive Tasks Not Yet in Workers
| Task | Service | Why It Should Be Offloaded |
|------|---------|---------------------------|
| Notification batch creation | `notification_engine.py` | Multiple DB inserts per notification |
| Analytics event tracking | `analytics_engine.py` | Fire-and-forget |
| AI history cleanup | `ai_assistant_service.py` | Periodic batch delete |
| Wallet reconciliation | `wallet_engine.py` | Periodic audit queries |
| Feed ranking | `feed_engine.py` | CPU-intensive scoring |

---

## 5. Frontend JavaScript Issues

| File | Issue | Severity |
|------|-------|----------|
| `ai_premium.js` (lines 109+115) | **Duplicate click listener on `#aiChatSend`** → double API requests | Critical |
| `homepage_premium.js` (line 114,180) | `wirePostActions` re-attaches listeners on every `loadMore()` | High |
| `notifications_premium.js` (line 68) | `S.items` array grows unboundedly on infinite scroll | High |
| `notifications_premium.js` (line 37) | Redundant 30s polling when WebSocket already provides updates | Medium |
| `ai_premium.js` (line 66) | Chat message DOM grows unboundedly, no pruning | Medium |
| `homepage_premium.js` (line 132) | `IntersectionObserver` never disconnected | Low |
| `notifications_premium.js` (line 214) | `IntersectionObserver` never disconnected | Low |

---

## 6. CSS / Mobile Issues

| File | Issue | Severity |
|------|-------|----------|
| All premium CSS | Missing `env(safe-area-inset-*)` for notched devices | Medium |
| Various tab bars | 40px touch targets instead of 44px minimum | Low |
| Some grids | `overflow-x: auto` without safe area padding | Low |

---

## 7. Security Audit Findings

| Area | Finding | Severity |
|------|---------|----------|
| Route coverage | ~90% of routes use `login_required` — remaining public routes audited | OK |
| Ownership checks | `wallet_routes.py`, `dating_routes.py`, `marketplace_routes.py` verify ownership | OK |
| CSRF | No CSRF token validation on POST endpoints (Flask-Limiter provides some protection) | Medium |
| Wallet | Amount validation uses integer cents, no negative balance supported | OK |
| Input sanitization | AI service sanitizes input, wallet validates amounts | OK |

---

## 8. Recommendations Summary

1. **Add database indexes** for frequently queried columns (Phase 67 SQL)
2. **Cache profile lookups, feed tabs, and notification counts** (Phase 67 Cache Layer)
3. **Add rate limits** to auth, messages, wallet, marketplace, dating, AI
4. **Offload expensive tasks** to RQ workers
5. **Fix frontend JS bugs** (duplicate listeners, unbounded arrays, redundant polling)
6. **Add mobile viewport meta** and safe-area support
7. **Performance monitoring dashboard** at `/admin/performance`
