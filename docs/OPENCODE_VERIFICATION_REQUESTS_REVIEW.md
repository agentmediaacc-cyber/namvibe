# Verification Requests + Content Controls Review

**Commit:** `08e4e64`  
**Files reviewed:** 5 (4 feature files + 1 SQL schema)  
**Date:** 2026-06-28

---

## Files Reviewed

| # | File | Status |
|---|------|--------|
| 1 | `api_routes/verification_admin_routes.py` | ✅ Pass |
| 2 | `api_routes/content_controls_routes.py` | ⚠️ Fixed |
| 3 | `services/verification_request_service.py` | ✅ Pass |
| 4 | `templates/profile/verification_request.html` | ✅ Pass |
| 5 | `sql/058_phase158d_tables.sql` | ✅ Pass |

---

## Findings

### 1. Bug Fixed: Wrong table for "story" content type

**File:** `api_routes/content_controls_routes.py:14`  
**Issue:** `CONTENT_TABLES` mapped `"story"` → `"chain_stories"`. Every other service in the codebase uses `"chain_status_posts"` for story data. This caused all 8 content-control operations on stories (verify owner, delete, caption update, visibility update, lock toggle, share-url fetch, GET) to query the wrong table.

**Fix:** Changed `"chain_stories"` → `"chain_status_posts"`.

### 2. All routes verified

- `verification_admin_routes.py`: 7 admin routes, all with `@require_admin`
- `content_controls_routes.py`: 6 routes (4 with `@login_required`, 2 public)
- All routes registered via blueprints (`verification_admin_bp`, `content_controls_bp`)

### 3. Auth decorators correct

- Admin endpoints use `@require_admin` from `decorators`
- User endpoints use `@login_required` from `profile_routes`
- No missing or mismatched auth guards

### 4. SQL schema matches service code

- All 8 tables created in `058_phase158d_tables.sql` are referenced by `verification_request_service.py`
- Column names used in parameterized queries match schema exactly (no typos)
- No missing indexes or constraints needed by the service layer

### 5. Template links verified

- `verification_request.html` form submits to `/profile/api/verification/submit` — exists in `social_graph_routes.py:402`
- Admin verification template pages reference `/admin/verifications/api/*` endpoints

### 6. `login_required` import confirmed

- `content_controls_routes.py` imports from `api_routes.profile_routes` — function exists at line 100
- No circular import (profile_routes does not import from content_controls_routes)

---

## Runtime Verification

| Check | Result |
|-------|--------|
| `py_compile app.py` | ✅ Pass |
| `compileall api_routes services templates` | ✅ Pass |
| `verify_live_production_smoke.py` | ✅ All 17 routes PASS |
| `benchmark_production_routes.py` | ✅ All benchmarks PASS |

---

## Blocker Summary

None.

---

## Commit Message

```
fix: map "story" content type to correct table in content controls

Changes CONTENT_TABLES["story"] from "chain_stories" to
"chain_status_posts" so that content control operations (verify owner,
delete, caption update, visibility, lock, share-url, GET) query the
correct table.

Previously, all story content-control queries operated on an empty or
stale table, silently failing to find any stories.
```
