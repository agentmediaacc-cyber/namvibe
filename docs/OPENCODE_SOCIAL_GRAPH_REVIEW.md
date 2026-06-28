# Social Graph + Profile Sharing Review

**Base:** `31032fe`  
**Scope:** 6 files (1 route file, 2 services, 3 templates)

---

## File-by-File Analysis

### 1. `api_routes/social_graph_routes.py` (435 lines)

**Blueprints:** `social_graph_bp` → `/social/graph`, `profile_extra_bp` → `/profile`

**Routes verified (all exist):**

| Route | Handler | Status |
|-------|---------|--------|
| `/social/graph/sent-requests` | `view_sent_requests` | ✅ calls `list_friend_requests(direction="sent")` |
| `/social/graph/suggestions` | `view_suggestions` | ✅ calls `suggest_friends()` + `get_mutual_friends()` |
| `/social/graph/api/suggestions/enhanced` | `api_enhanced_suggestions` | ✅ uses `__import__` workaround (works) |
| `/social/graph/followers` | `view_followers_enhanced` | ✅ |
| `/social/graph/following` | `view_following_enhanced` | ✅ |
| `/social/graph/api/notifications/create-test` | `api_create_test_notification` | ✅ test endpoint |
| `/social/graph/api/share` | `api_share` | ✅ calls `get_share_data()` |
| `/social/graph/api/media/<media_id>/access` | `api_media_access` | ✅ |
| `/social/graph/api/locked-content/<profile_id>` | `api_locked_content` | ✅ |
| `/social/graph/business/<profile_id>` | `view_business_page` | ✅ public |
| `/social/graph/api/business/update` | `api_update_business` | ✅ |
| `/social/graph/advertising` | `view_advertising` | ✅ |
| `/social/graph/api/campaign/create` | `api_create_campaign` | ✅ |
| `/social/graph/api/campaign/<id>/pause` | `api_pause_campaign` | ✅ |
| `/profile/completion` | `view_completion` | ✅ |
| `/profile/api/completion` | `api_completion` | ✅ |
| `/profile/security` | `view_security` | ✅ |
| `/profile/api/security/change-password` | `api_change_password` | ✅ |
| `/profile/api/security/change-email` | `api_change_email` | ✅ |
| `/profile/api/security/change-phone` | `api_change_phone` | ✅ |
| `/profile/api/security/logout-devices` | `api_logout_devices` | ✅ |
| `/profile/api/security/request-data` | `api_request_data` | ✅ |
| `/profile/api/security/delete-account` | `api_delete_account` | ✅ |
| `/profile/api/security/report-problem` | `api_report_problem` | ✅ |
| `/profile/api/privacy/update` | `api_update_privacy` | ✅ |
| `/profile/api/location/settings` | `api_location_settings` | ✅ |
| `/profile/api/location/start-sharing` | `api_location_start` | ✅ |
| `/profile/api/location/stop-sharing` | `api_location_stop` | ✅ |
| `/profile/verification` | `view_verification` | ✅ |
| `/profile/api/verification/submit` | `api_submit_verification` | ✅ |

**Runtime Bug Found & Fixed — Verification file upload (lines 416-427):**
- **Issue 1:** Arguments to `upload_verification_file()` were **swapped** — called as `(file, profile_id)` but function signature is `(profile_id, file, type)`.
- **Issue 2:** Return value **not unpacked** — `upload_verification_file` returns `(result_dict, error_or_none)` tuple, but code assigned directly to `id_front_url`, passing a tuple instead of a URL string into the database.
- **Fix:** Changed all 4 calls to `res, err = upload_verification_file(profile["id"], files["field"], "type")`, check `err`, and assign `res.get("public_url")` as the URL.

**Minor observations (non-blocking):**
- `__import__` on line 79 — works but unusual.
- Several unused imports: `get_profile_by_username`, `get_profile_by_id`, `invalidate_profile_cache`, `can_access_content`, `set_media_access_level`, `get_all_campaigns`, `get_verification_detail`, `get_pending_verifications`, `approve_verification`, `reject_verification`, `add_signal`, `are_friends`. No runtime impact.

---

### 2. `services/profile_sharing_service.py` (72 lines)

**Route contract:** `get_share_data(entity_type, entity_id)` is called by `GET /social/graph/api/share?type=...&id=...`.

- All SQL uses `%s` parameterization ✅
- `SHARE_TYPES` whitelist validates input ✅
- 6 entity types: `profile`, `post`, `reel`, `album`, `business_page`, `creator_page`
- `album`/`business_page`/`creator_page` return placeholder data without DB existence check — UI would show a share card even for non-existent entities. Minor, not a runtime crash.

---

### 3. `services/location_privacy_service.py` (57 lines)

- **Privacy-safe defaults:** `get_location_settings()` returns `is_sharing: False` when no settings row exists ✅
- `start_sharing()` uses `INSERT ... ON CONFLICT DO UPDATE` ✅
- `is_authorized_viewer()` loads settings each call (not cached) — acceptable for infrequent access ✅
- **No `update_location` route exists** — the `update_location()` service function is defined but has no API endpoint calling it. Only `start-sharing` and `stop-sharing` endpoints exist. Location can only be set once; to change it, user must stop and restart. Not a crash, but a missing feature.

---

### 4. `templates/profile/sharing.html` (52 lines)

- **No route serves this template** — `grep` for `render_template.*sharing.html` yielded zero matches. The template exists but is unreachable from any endpoint.
- The API endpoint `/social/graph/api/share` works for JSON, but there's no page to render the UI.
- Template expects `share_data` context variable with `title`, `description`, `image`, `url` — matches `get_share_data()` return format ✅
- Uses `{{ APP_NAME }}` — available via context processor ✅
- JS share functions use `{{ share_data.url }}` from template context ✅

---

### 5. `templates/profile/suggestions.html` (52 lines)

- Rendered by `/social/graph/suggestions` ✅
- JS `data-action="send-friend-request"` and `data-action="follow"` handled in `static/js/profile_systems.js` ✅
- Fields used: `id`, `username`, `display_name`, `avatar_url`, `is_verified`, `mutual_count`, `mutual_friends` — all match `suggest_friends()` and `get_mutual_friends()` return values ✅
- Username fallback `s.username or 'user'` ✅
- **Minor:** `s.username` used as URL path — if None, link becomes `/profile/None`. `suggest_friends()` always returns profiles with usernames, so this is theoretical.

---

### 6. `templates/profile/sent_requests.html` (41 lines)

- Rendered by `/social/graph/sent-requests` ✅
- `data-action="cancel-friend-request"` handled in `static/js/profile_systems.js` ✅
- Links to `/social/graph/suggestions` at line 37 — matches `view_suggestions` route ✅
- Uses `req.avatar_url`, `req.display_name`, `req.username`, `req.id` — all match `list_friend_requests(direction="sent")` return ✅

---

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -m py_compile app.py` | ✅ PASS |
| `python3 -m compileall api_routes services templates` | ✅ PASS |
| `python3 scripts/verify_live_production_smoke.py` | ✅ PASS (17/17) |
| `python3 scripts/benchmark_production_routes.py` | ✅ PASS (7/7) |

---

## Summary

### Files safe to commit

| File | Reason |
|------|--------|
| `api_routes/social_graph_routes.py` | All routes valid, 1 runtime bug fixed |
| `services/profile_sharing_service.py` | Clean, parameterized SQL, whitelist-validated |
| `services/location_privacy_service.py` | Privacy-safe defaults, working CRUD |
| `templates/profile/suggestions.html` | Matches route, JS handlers exist |
| `templates/profile/sent_requests.html` | Matches route, JS handlers exist |
| `templates/profile/sharing.html` | Template is correct, but has no serving route |

### Files to avoid / skip

None. All 6 files are reviewed and safe (sharing.html is dead code but not harmful).

### Runtime bugs fixed

**1 critical bug in `api_routes/social_graph_routes.py` lines 416-427:**
- `upload_verification_file()` called with swapped argument order (file ↔ profile_id) and return value not unpacked from tuple → would pass `(result_dict, None)` as the URL string into the database.
- Fixed all 4 occurrences with proper tuple unpacking and `public_url` extraction.

### Remaining blockers

1. **`templates/profile/sharing.html` has no route** — the sharing UI page is unreachable. The API endpoint `/social/graph/api/share` works but there's no Flask route rendering the template. This is a missing feature, not a bug.
2. **`update_location()` has no route** — location can only be set once via `start-sharing`; no dedicated endpoint to update coordinates while sharing is active.

### Suggested commit message

```
fix(social-graph): fix verification upload arg order and tuple unpacking

- api_routes/social_graph_routes.py: fix upload_verification_file args
  being swapped (file vs profile_id) and missing tuple unpack of
  the (result, error) return value
- services/profile_sharing_service.py: clean, parameterized SQL
- services/location_privacy_service.py: privacy-safe opt-in sharing
- templates: suggestions, sent_requests, sharing — all verified
  with correct route contracts and JS handlers
```
