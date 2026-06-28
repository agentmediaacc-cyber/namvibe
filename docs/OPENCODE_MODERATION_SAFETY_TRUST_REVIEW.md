# Moderation / Safety / Trust Review

**Date:** 2026-06-28

---

## Files Reviewed

### Route Files (6)

| # | File | Lines | Status |
|---|------|-------|--------|
| 1 | `api_routes/moderation_routes.py` | 279 | ⚠️ Fixed |
| 2 | `api_routes/safety_routes.py` | 234 | ✅ Pass |
| 3 | `api_routes/admin_safety_routes.py` | 64 | ✅ Pass |
| 4 | `api_routes/trust_routes.py` | 14 | ℹ️ Unregistered |
| 5 | `api_routes/security_routes.py` | 114 | ✅ Pass |
| 6 | `api_routes/content_controls_routes.py` | 229 | ⚠️ Fixed |

### Service Files (10)

| # | File | Status |
|---|------|--------|
| 1 | `services/moderation_engine.py` | ✅ Pass |
| 2 | `services/moderation_service.py` | ✅ Pass |
| 3 | `services/blocking_service.py` | ✅ Pass |
| 4 | `services/trust_score_service.py` | ✅ Pass |
| 5 | `services/security_service.py` | ✅ Pass |
| 6 | `services/safety_rate_limit_service.py` | ✅ Pass (see notes) |
| 7 | `services/spam_detection_service.py` | ✅ Pass (see notes) |
| 8 | `services/fraud_detection_service.py` | ✅ Pass (see notes) |
| 9 | `services/subscriber_content_service.py` | 100 | ⚠️ Fixed |
| 10 | `services/trust_scam_service.py` | 87 | ⚠️ Fixed |

### SQL Files (2)

| # | File | Status |
|---|------|--------|
| 1 | `sql/phase48_trust_safety_moderation.sql` | ✅ Pass |
| 2 | `sql/phase43_security_privacy.sql` | ✅ Pass |

### Templates (7)

| # | File | Status |
|---|------|--------|
| 1 | `templates/safety/report.html` | ✅ Pass |
| 2 | `templates/safety/trust_summary.html` | ✅ Pass |
| 3 | `templates/security/privacy.html` | ✅ Pass |
| 4 | `templates/security/devices.html` | ✅ Pass |
| 5 | `templates/security/security_events.html` | ✅ Pass |
| 6 | `templates/admin/safety_dashboard.html` | ✅ Pass |
| 7 | `templates/admin/moderation_queue.html` | ✅ Pass |

---

## Bug Fixes

### 1. `report_entity` returns wrong type to caller

**File:** `services/moderation_engine.py:81`  
**Called from:** `api_routes/moderation_routes.py:30`

`write_query(...)` with `RETURNING id` returns `[{"id": "uuid"}]` (list of dicts). The function returned this raw list. The caller passes it to `jsonify` as `report_id` — the frontend would receive `[{"id": "..."}]` instead of `"..."`.

**Fix:** Extract the actual UUID from the result: `result[0].get("id")`.

---

### 2. `get_media_access_level` references non-existent `visibility` column on `chain_media_uploads`

**File:** `services/subscriber_content_service.py:29-31`

Queried `SELECT visibility FROM chain_media_uploads` despite the table not having a `visibility` column in its DDL.

**Fix:** Use `get_cached_table_columns` to check for `visibility` before querying. If the column does not exist, skip `chain_media_uploads` and try `chain_posts` / `chain_reels` / `chain_subscriber_content` in order. Fall back to `"public"` if no table has visibility data.

### 3. `set_media_access_level` blindly UPDATES `visibility` on all tables including `chain_media_uploads`

**File:** `services/subscriber_content_service.py:61-65`

The UPDATE loop unconditionally ran `SET visibility = %s` on `chain_media_uploads`, `chain_posts`, and `chain_reels`. If any table lacks the column, the query raises a PostgreSQL error.

**Fix:** Check each table for the `visibility` column before running the UPDATE. Skip tables that lack it. Return `{"ok": False, "error": "..."}` if no table has the column.

### 4. `content_controls_routes.py` assumes columns exist on all mapped tables

**File:** `api_routes/content_controls_routes.py`

Every route (`edit_caption`, `delete_content`, `change_visibility`, `toggle_lock`, `get_share_url`, `get_content`, `_verify_owner`) hardcoded column references (`deleted_at`, `updated_at`, `caption`, `metadata`, `visibility`) without checking the table schema. The tables have different column sets:

| Column | chain_posts | chain_reels | chain_status_posts |
|--------|-------------|-------------|-------------------|
| `caption` | ❌ (has `body`) | ✅ | ✅ |
| `deleted_at` | ❌ | ✅ | ✅ (one variant) |
| `updated_at` | ❌ | ✅ | ❌ |
| `visibility` | ✅ | ✅ | ✅ |
| `locked` | ❌ | ❌ | ❌ |
| `metadata` | ❌ | ❌ | ❌ |

**Fix:** Added `_table_columns` / `_has_column` helpers that use `get_cached_table_columns`. All routes now:
- Query `deleted_at IS NULL` only if the column exists.
- Update `updated_at` only if the column exists.
- Pick the first available text column (`caption` → `body` → `description`) for `edit_caption`.
- Return a clear error if the required column is missing.

### 5. `increment_report_count` default dict key mismatch

**File:** `services/trust_scam_service.py:85`

`fast_query(..., default=[{"count": 0}])` used key `"count"` but the SQL returns `report_count`. If `fast_query` returned the default, `count[0].get("report_count", 0)` would silently return `0` (correct value but wrong key name).

**Fix:** Changed default to `[{"report_count": 0}]`.

---

## Blueprint Registration

| Blueprint | Variable | Registered in `app.py` |
|-----------|----------|------------------------|
| `safety_bp` | `safety_routes.py` | Line 513 ✅ |
| `moderation_bp` | `moderation_routes.py` | Line 497 ✅ (backward compat, empty) |
| `admin_safety_bp` | `admin_safety_routes.py` | Line 514 ✅ |
| `security_bp` | `security_routes.py` | Line 530 ✅ |
| `trust_bp` | `trust_routes.py` | **Not registered** ❌ |

The `trust_bp` blueprint (defined in `trust_routes.py`) is not registered in `app.py`. The single route it provides (`/api/trust/summary`) is duplicated via `safety_bp` in `moderation_routes.py:240`, so no functionality is lost. This file is dead code.

---

## Auth Guards

| Route | Guard | Correct? |
|-------|-------|----------|
| All `moderation_routes.py` user endpoints | `@login_required` | ✅ |
| All `safety_routes.py` user endpoints | `@login_required` | ✅ |
| All `safety_routes.py` admin endpoints | `@require_admin` | ✅ |
| All `admin_safety_routes.py` endpoints | `@require_admin` | ✅ |
| All `security_routes.py` endpoints | `@login_required` | ✅ |

---

## SQL Schema Cross-Reference

### `phase48_trust_safety_moderation.sql` — 8 tables

| Table | Columns | Service Usage | Match |
|-------|---------|---------------|-------|
| `chain_trust_scores` | 12 | `trust_score_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_user_reports` | 13 | `moderation_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_moderation_queue` | 12 | `moderation_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_moderation_actions` | 10 | `moderation_service.py` INSERT | ✅ |
| `chain_spam_events` | 8 | `spam_detection_service.py` INSERT | ✅ |
| `chain_fraud_events` | 9 | `fraud_detection_service.py` INSERT | ✅ |
| `chain_creator_verification_requests` | 9 | `creator_verification_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_rate_limit_events` | 9 | `safety_rate_limit_service.py` INSERT | ✅ |

### `phase43_security_privacy.sql` — 5 tables

| Table | Columns | Service Usage | Match |
|-------|---------|---------------|-------|
| `chain_device_sessions` | 11 | `security_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_security_events` | 6 | `security_service.py` INSERT/SELECT | ✅ |
| `chain_privacy_settings` | 9 | `security_service.py` INSERT/UPDATE/SELECT | ✅ |
| `chain_encryption_keys` | 6 | `encryption_service.py`, `e2ee_service.py` INSERT/SELECT/UPDATE | ⚠️ (see below) |
| `chain_trusted_devices` | 5 | `security_service.py` INSERT/SELECT/DELETE | ✅ |

**Note:** `chain_encryption_keys` in phase43 does not include `encrypted_private_key`. That column is added by `phase46_e2ee_activation.sql`. The `e2ee_service.py` references it — will fail if phase46 hasn't been applied.

### Content tables — column gaps (now guarded by runtime schema check)

| Column | chain_posts | chain_reels | chain_status_posts | chain_media_uploads |
|--------|-------------|-------------|-------------------|---------------------|
| `visibility` | ✅ | ✅ | ✅ | ❌ |
| `deleted_at` | ❌ | ✅ | ✅ (one variant) | ❌ |
| `updated_at` | ❌ | ✅ | ❌ | ❌ |
| `caption` | ❌ (has `body`) | ✅ | ✅ | ❌ |
| `locked` | ❌ | ❌ | ❌ | ❌ |
| `metadata` | ❌ | ❌ | ❌ | ❌ |

All routes in `content_controls_routes.py` and `subscriber_content_service.py` now use `get_cached_table_columns` to verify column existence at query-build time.

---

## Template Endpoint Cross-Reference

| Template | Endpoint | Route File | Match |
|----------|----------|------------|-------|
| `safety/report.html` | `POST /safety/api/report` | `safety_routes.py:82` | ✅ |
| `safety/trust_summary.html` | `GET /safety/api/trust-summary` | `safety_routes.py:108` | ✅ |
| `security/privacy.html` | `POST /privacy/api/settings` | `privacy_routes.py:19` | ✅ |
| `security/privacy.html` | `GET /encryption/api/status` | `encryption_routes.py:18` | ✅ |
| `security/privacy.html` | `POST /encryption/api/rotate` | `encryption_routes.py:28` | ✅ |
| `security/devices.html` | `POST /security/api/device/{id}/revoke` | `security_routes.py:31` | ✅ |
| `security/devices.html` | `POST /security/api/device/{id}/trust` | `security_routes.py:55` | ✅ |
| `security/devices.html` | `POST /security/api/device/{id}/untrust` | `security_routes.py:66` | ✅ |
| `security/devices.html` | `POST /security/api/logout-all-other-devices` | `security_routes.py:44` | ✅ |
| `admin/moderation_queue.html` | `GET /admin/safety/api/moderation-queue` | `safety_routes.py:143` | ✅ |
| `admin/safety_dashboard.html` | (static nav links) | all resolve | ✅ |

---

## Architectural Notes (not bugs)

### 1. In-memory-only enforcement in multi-worker environments

Three service modules rely on in-memory Python data structures for enforcement logic. In multi-process/multi-worker production, each worker has its own isolated state:

| Service | In-memory store | Impact |
|---------|----------------|--------|
| `safety_rate_limit_service.py` | `_FAKE_RATE_EVENTS` list | Rate limits never enforced across workers |
| `spam_detection_service.py` | `_FAKE_SPAM_EVENTS`, `_RECENT_CONTENT` | Message frequency and repeat detection broken across workers |
| `fraud_detection_service.py` | `_PAIR_ACTIONS` dict | Repeated-pair wallet activity detection broken across workers |

All three still write to their respective DB tables for audit, but the *decision* logic reads from in-memory only. Fixing this would require querying the DB for recent events instead of the in-memory list — a redesign, not a bug fix.

### 2. `trust_routes.py` — dead code

`trust_bp` is defined with a single route (`/api/trust/summary`) that duplicates `moderation_routes.py:240`. The blueprint is not registered in `app.py`. This file can be deleted or kept as-is.

---

## Runtime Verification

| Check | Result |
|-------|--------|
| `py_compile app.py` | ✅ |
| `compileall api_routes services templates` | ✅ |
| `verify_production_routes.py` | ✅ PASS |
| `benchmark_production_routes.py` | ✅ PASS |

---

## Summary

- **1 bug fixed (previous):** `report_entity` return value (list instead of scalar UUID)
- **4 bugs fixed (this phase):**
  1. `get_media_access_level` — guarded `visibility` column check on `chain_media_uploads`
  2. `set_media_access_level` — guarded `visibility` UPDATE against missing columns
  3. `content_controls_routes.py` — all routes now use runtime schema introspection; never reference missing columns
  4. `trust_scam_service.py` — default dict key corrected from `"count"` to `"report_count"`
- **1 dead file:** `trust_routes.py` (unregistered blueprint)
- **1 cross-phase schema dependency:** `encrypted_private_key` column added by phase46, not phase43
- **3 architecture concerns:** In-memory-only enforcement limits effectiveness in production
- **All routes, auth guards, SQL schemas, and template endpoints verified** — no other issues found

### Commit Message

```
fix(moderation+content-controls): schema-safe column access and default key fix

- subscriber_content_service.py: guard visibility column on
  chain_media_uploads with get_cached_table_columns before SELECT/UPDATE.
  Skip tables that lack the column; return error if none support it.
- content_controls_routes.py: add _has_column helper wrapping
  get_cached_table_columns. Every route dynamically builds SQL using
  only columns that exist (deleted_at, updated_at, caption/body,
  visibility, locked, metadata). Return clear errors for missing
  columns instead of crashing.
- trust_scam_service.py: fix default key in increment_report_count
  from "count" to "report_count".
```
