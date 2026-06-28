# Notifications Review

**Date:** 2026-06-28

---

## Files Reviewed

### Route Files (4)

| # | File | Lines | Blueprint | Prefix | Registered |
|---|------|-------|-----------|--------|------------|
| 1 | `api_routes/notification_routes.py` | 180 | `notification_engine` | (none) | ✅ Line 487 |
| 2 | `api_routes/notification_center_routes.py` | 157 | `notification_center` | (none) | ✅ Line 535 |
| 3 | `api_routes/push_notification_routes.py` | 168 | `push_notifications_api` | `/notifications` | ✅ Line 533 |
| 4 | `api_routes/push_routes.py` | 93 | `push` | `/push` | ✅ Line 529 |

### Service Files (8)

| # | File | Status |
|---|------|--------|
| 1 | `services/notification_engine.py` | ✅ |
| 2 | `services/notification_center_service.py` | ✅ |
| 3 | `services/notification_service.py` | ✅ |
| 4 | `services/notification_queue_service.py` | ✅ |
| 5 | `services/notification_grouping_service.py` | ✅ |
| 6 | `services/push_notification_engine.py` | ✅ |
| 7 | `services/push_notification_service.py` | ✅ |
| 8 | `services/push_token_service.py` | ✅ |

### SQL Files

- `sql/phase60_notifications.sql` — creates `chain_notifications`, `chain_notification_preferences`
- `sql/phase32_push_notifications.sql` — creates `chain_push_subscriptions`, `chain_notification_preferences`
- `sql/phase45_push_notifications.sql` — creates `chain_notification_queue`, `chain_push_tokens`

All tables exist and match service column usage.

---

## Findings

### Bugs Found: **0**

All endpoints, auth guards, and template cross-references verified clean.

### Blueprint Registration

All 4 blueprints are imported and registered in `app.py`:
- `notification_engine_bp` → line 487
- `push_bp` → line 529
- `push_notifications_api_bp` → line 533
- `notification_center_bp` → line 535

### Auth Guards

| Route Set | Guard | Correct? |
|-----------|-------|----------|
| `notification_routes.py` — all user endpoints | `@login_required` | ✅ |
| `notification_routes.py` — `api_unread_count` | No decorator (handles logged-out state) | ✅ |
| `notification_center_routes.py` — user endpoints | `@login_required` | ✅ |
| `notification_center_routes.py` — `api_unread_count`, `api_tabs_config` | No decorator | ✅ |
| `push_notification_routes.py` — all user endpoints | `@login_required` | ✅ |
| `push_notification_routes.py` — `api_vapid_public_key` | No decorator | ✅ (public) |
| `push_routes.py` — all endpoints | `@login_required` | ✅ |

### Template Endpoint Cross-Reference

Both notification JS files were checked and all endpoints match:

**`static/js/namvibe_notifications.js`** (used by `index.html`):
- `GET /api/notifications` → `notification_routes.py:30` ✅
- `POST /api/notifications/read-group` → `notification_routes.py:105` ✅
- `POST /notifications/api/read/<id>` → `notification_routes.py:85` ✅
- `POST /api/notifications/read-all` → `notification_routes.py:95` ✅
- `GET /api/notifications/unread-count` → `notification_routes.py:56` ✅
- `GET /api/notifications/preferences` → `notification_routes.py:146` ✅
- `POST /api/notifications/preferences` → `notification_routes.py:156` ✅

**`static/js/notifications_center.js`** (used by `center.html`):
- `GET /api/notifications/center/list` → `notification_center_routes.py:34` ✅
- `POST /api/notifications/center/read/<id>` → `notification_center_routes.py:75` ✅
- `POST /api/notifications/center/delete/<id>` → `notification_center_routes.py:95` ✅
- `POST /api/notifications/center/read-all` → `notification_center_routes.py:85` ✅
- `POST /api/notifications/center/delete-selected` → `notification_center_routes.py:105` ✅
- `GET /api/notifications/center/unread-count` → `notification_center_routes.py:58` ✅
- `GET /api/notifications/center/preferences` → `notification_center_routes.py:134` ✅
- `POST /api/notifications/center/preferences` → `notification_center_routes.py:144` ✅

### SQL Schema

| Table | Created in | Used by | Match |
|-------|-----------|---------|-------|
| `chain_notifications` | `phase60_notifications.sql` | `notification_center_service.py` | ✅ |
| `chain_notification_queue` | `phase45_push_notifications.sql` | `notification_queue_service.py`, `push_notification_routes.py` | ✅ |
| `chain_notification_preferences` | `phase32_push_notifications.sql`, `phase60_notifications.sql` | `notification_engine.py`, `notification_center_service.py`, `push_notification_service.py` | ✅ |
| `chain_push_subscriptions` | `phase32_push_notifications.sql` | `push_notification_service.py` | ✅ |
| `chain_push_tokens` | `phase45_push_notifications.sql`, `phase69_realtime_communication_fix.sql` | `push_token_service.py` | ✅ |

No `chain_notification_mutes` table needed — mute state is stored as `muted_types` JSONB in `chain_notification_preferences`.

---

## Runtime Verification

| Check | Result |
|-------|--------|
| `py_compile app.py` | ✅ |
| `compileall api_routes services templates` | ✅ |
| `verify_live_production_smoke.py` | ✅ All 17 routes PASS |
| `benchmark_production_routes.py` | ✅ All benchmarks PASS |

---

## Summary

**0 bugs found.** All notification route files are well-structured with correct auth guards, all template endpoints resolve, all SQL tables exist, all 8 service files exist and are importable.
