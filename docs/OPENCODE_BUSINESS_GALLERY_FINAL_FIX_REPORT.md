# Business + Gallery Final Fix Report

## Schema Mismatch Fixed

`chain_business_hours` table schema:
- `id` UUID PRIMARY KEY
- `profile_id` UUID UNIQUE REFERENCES chain_profiles(id)
- `hours` JSONB DEFAULT '{}'
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

**Before:** Code used non-existent flat columns: `page_id`, `day`, `open_time`, `close_time`, `is_closed`, `day_of_week`

**After:** Uses JSONB `hours` column via existing `business_page_service.py` helpers.

## Changes

### `api_routes/profile_routes.py`

**Added:** `_normalize_business_hours(form)` helper (lines 1655-1680)
- Extracts `hours_{day}_{open,close,closed}` from flat form fields
- Validates HH:MM format for non-closed days
- Returns a clean dict keyed by day name, suitable for JSONB storage
- Allowed days: `monday` through `sunday`

**Changed:** `business_page_update()` (line 1711)
- Old: TODO-commented flat-column SQL
- New: Calls `update_business_profile(page_id, opening_hours=hours)` from `business_page_service.py`, which performs a correct JSONB UPSERT

**Changed:** `business_page()` (lines 1742-1744)
- Old: `page["hours"] = {}` (hardcoded empty)
- New: `SELECT hours FROM chain_business_hours WHERE profile_id = %s` → `page["hours"] = hours_raw[0]["hours"] if hours_raw else {}`

### Other files

No changes needed — all other files already use the correct JSONB schema:
- `services/business_page_service.py` — already uses `profile_id` + `hours` JSONB
- `templates/business/page.html` — already reads `.get('open','')`, `.get('close','')`, `.get('closed')` from the hours dict
- Form field names `hours_{day}_open` etc. are HTML field names, not DB columns

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -m py_compile app.py` | ✅ PASS |
| `python3 -m compileall api_routes services templates` | ✅ PASS |
| `scripts/verify_live_production_smoke.py` | ✅ PASS |
| `scripts/benchmark_production_routes.py` | ✅ PASS |

Grep for old column names (`page_id`, `day_of_week`, `open_time`, `close_time`, `is_colsed`):

Search targeted `api_routes/profile_routes.py`, `services/business_page_service.py`, `templates/business/`, `templates/profile/business.html`, `templates/profile/advertising.html`:
- `api_routes/profile_routes.py`: No DB-column-level references remain (only valid form-field-name references in `_normalize_business_hours`)
- `services/business_page_service.py`: No references found
- `templates/business/`: No references found
- `templates/profile/business.html`: No references found
- `templates/profile/advertising.html`: No references found

All other files already correct.

## Files Changed

| File | Change |
|------|--------|
| `api_routes/profile_routes.py` | Added `_normalize_business_hours()` helper; replaced flat-column business-hours logic with JSONB read/write via `business_page_service.py` |

No other files modified.

## Files Safe to Commit (14 files)

```
api_routes/creator_routes.py
api_routes/gallery_routes.py
api_routes/ad_admin_routes.py
api_routes/profile_routes.py
services/business_page_service.py
static/css/business.css
static/css/business_flyer_generator.css
static/css/gallery.css
static/js/business_flyer_generator.js
templates/business/page.html
templates/business/flyer_generator.html
templates/gallery/index.html
templates/profile/business.html
templates/profile/advertising.html
```

## Remaining Blockers

None. All known issues from the previous review have been addressed:
1. ✅ `flyer_generator.html` — fixed extends
2. ✅ `gallery_routes.py` — fixed `save_media_file` args
3. ✅ `business/page.html` — fixed follow/unfollow URL
4. ✅ `profile_routes.py` — fixed business hours schema mismatch

## Suggested Commit Message

```
feat(business): add business pages, advertising campaigns, and gallery with albums
```

Includes:
- Creator campaign create/end endpoints
- Gallery CRUD, upload, albums, visibility controls
- Admin ad campaign approval dashboard
- Business page view/settings with JSONB hours
- Flyer generator with canvas preview/download
- Business and advertising templates
- All associated CSS/JS assets
