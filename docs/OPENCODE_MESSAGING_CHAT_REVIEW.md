# Messaging / Chat Review

**Date:** 2026-06-28

---

## Files Reviewed

### Route Files (6)

| # | File | Lines | Blueprint | Registered? | Status |
|---|------|-------|-----------|-------------|--------|
| 1 | `api_routes/message_routes.py` | 1202+ | `messages` (`/messages`) | ✅ app.py:484 | ✅ Pass |
| 2 | `api_routes/messaging_routes.py` | 309 | `messaging_api` (`/api/messages`) | ✅ app.py:485 | ✅ Pass |
| 3 | `api_routes/message_production_routes.py` | 217 | `message_production` (`/messages/api`) | ✅ app.py:1340 | ✅ Pass |
| 4 | `api_routes/message_upgrade_routes.py` | 251 | `message_upgrade` (`/messages`) | ❌ Not registered | ℹ️ Dev-only |
| 5 | `api_routes/inbox_routes.py` | 97 | `inbox` (`/inbox`) | ✅ app.py:545 | ⚠️ Fixed |
| 6 | `api_routes/chat_routes.py` | 58 | `chat_v2` (`/chat`) | ❌ Not registered | ℹ️ Orphan |

### Service Files (10)

| # | File | Status |
|---|------|--------|
| 1 | `services/messaging_engine.py` | ✅ Pass |
| 2 | `services/message_feature_service.py` | ✅ Pass |
| 3 | `services/message_delivery_service.py` | ✅ Pass |
| 4 | `services/message_thread_service.py` | ✅ Pass |
| 5 | `services/message_receipt_service.py` | ✅ Pass |
| 6 | `services/message_media_service.py` | ✅ Pass |
| 7 | `services/thread_security_service.py` | ✅ Pass |
| 8 | `services/relationship_gate_service.py` | ✅ Pass |
| 9 | `services/friendship_service.py` | ✅ Pass |
| 10 | `services/group_feature_service.py` | ✅ Pass |

---

## Critical Bug Fixed: `inbox_routes.py` Queries Nonexistent Tables

**File:** `api_routes/inbox_routes.py`  
**Impact:** All 3 inbox routes (`/inbox/`, `/inbox/sent`, `/inbox/new`) would crash at runtime with `relation "chain_threads" does not exist`.

The original code queried two tables that **do not exist** in any SQL migration:

| Used by `inbox_routes.py` | Actual table in schema |
|---|---|
| `chain_threads` | ❌ Does not exist |
| `chain_thread_participants` | ❌ Does not exist |

Additional column mismatches:
- `m.sender_id` → should be `m.sender_profile_id`
- `t.last_message`, `t.last_message_at` → neither exists on `chain_message_threads`
- `t.is_archived` → lives on `chain_thread_members`, not the thread table
- `p.display_name` → should be `p.full_name`

The file was the **only file in the entire codebase** referencing `chain_threads` or `chain_thread_participants`. These table names appear nowhere else — not in Python, not in SQL, not in configuration.

**Fix:** Rewrote all 3 queries to use the actual schema:
- `chain_message_threads` (with `thread_name`, `deleted_at`)
- `chain_thread_members` (with `is_archived`, `profile_id`)
- `chain_messages` (with `sender_profile_id`, `body`, `created_at`)
- `chain_profiles` (with `avatar_url`, `full_name`)
- `chain_blocks` (for `/inbox/blocked` — was already correct)

The `/inbox/blocked` route was the only one that worked (queries `chain_blocks` + `chain_profiles` which exist).

---

## Dead Code / Orphaned Files

### `api_routes/chat_routes.py` (58 lines)

Defines `chat_v2` blueprint with prefix `/chat`. Contains 4 routes (inbox, thread, start chat, send). The blueprint is **never imported or registered** in `app.py`. The functionality is duplicated by `message_routes.py`.

### `api_routes/message_upgrade_routes.py` (251 lines)

Defines `message_upgrade` blueprint with prefix `/messages`. All routes are gated by `CHAIN_DEV_TOOLS` env var. Uses session-only storage (no DB). This is a **dev-only mock tool** — intentionally inactive in production. The blueprint is not registered in `app.py`.

---

## Blueprint Registration Summary

| Blueprint | Variable | Prefix | Routes | Registered |
|-----------|----------|--------|--------|------------|
| `messages` | `message_bp` | `/messages` | ~50 (inbox, threads, send, groups, wallet, AI, polls, location, etc.) | ✅ Line 484 |
| `messaging_api` | `messaging_api_bp` | `/api/messages` | ~15 (thread messages, send, delivered, seen, delete, forward, upload, unread, groups) | ✅ Line 485 |
| `message_production` | `message_production_bp` | `/messages/api` | ~16 (thread, send, voice, unread, presence, reactions, edit, delete) | ✅ Line 1340 |
| `inbox` | `inbox_bp` | `/inbox` | 4 (main, new, sent, blocked) | ✅ Line 545 |
| `message_upgrade` | `message_upgrade_bp` | `/messages` | ~16 (dev-only mock) | ❌ Not registered |
| `chat_v2` | `chat_bp` | `/chat` | 4 (inbox, thread, start, send) | ❌ Not registered |

---

## Auth Guards

| Route Set | Guard | Correct? |
|-----------|-------|----------|
| `message_routes.py` — all user-facing | `@login_required` | ✅ |
| `messaging_routes.py` — all endpoints | `@login_required` | ✅ |
| `message_production_routes.py` — all endpoints | `@login_required` | ✅ |
| `inbox_routes.py` — all routes | Manual profile check | ✅ (renders login page if not authenticated) |

---

## Imports Verified

All 10 service files imported by route files exist and have matching function signatures:
- `services.messaging_engine` (list_threads, get_thread, send_message, etc.)
- `services.message_feature_service` (as `phase29_messages`)
- `services.group_feature_service` (as `phase29_groups`)
- `services.message_delivery_service` (retry_message)
- `services.message_thread_service` (latest_messages, create_group, etc.)
- `services.message_media_service` (upload_message_media, validate_message_attachment)
- `services.message_receipt_service` (mark_message_delivered, mark_message_seen)
- `services.thread_security_service` (can_access_thread)
- `services.relationship_gate_service` (relationship_status)
- `services.friendship_service` (require_friendship_or_403)

Dynamic import at `message_routes.py:1121` (`from services.socket_events import _SOCKET_RATE_LIMITS`) is valid — the file exists and defines the constant.

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

- **1 critical bug fixed:** `inbox_routes.py` queries `chain_threads` + `chain_thread_participants` (tables don't exist). Rewrote SQL to use `chain_message_threads` + `chain_thread_members` with correct columns.
- **2 dead files identified:** `chat_routes.py` and `message_upgrade_routes.py` have unregistered blueprints
- **All 10 service imports verified** — no missing files, all function signatures match
- **All route registrations, auth guards, and template endpoints verified** — no other issues

### Commit Message

```
fix: rewrite inbox routes to query real tables chain_message_threads + chain_thread_members

inbox_routes.py queried chain_threads and chain_thread_participants which
do not exist in any SQL migration — all 3 inbox routes would crash at
runtime with "relation does not exist". Also fixed column mismatches:
sender_id → sender_profile_id, display_name → full_name, and replaced
non-existent columns (last_message, last_message_at, is_archived on
wrong table) with correct subqueries.
```
