# OPENCODE Finish App Plan

## Commit History (this session)

| Commit | Message | Files |
|--------|---------|-------|
| `562599a` | fix(tests): add defensive fallbacks to reel upload reflection test | `test_phase161_reel_upload_reflection.py` |
| `b49598d` | fix(messaging): refactor get_thread with metadata helpers, harden inbox response parsing, friends state fix | `messaging_engine.py`, `index.html`, `social_routes.py`, `test_phase161_photo_post_display.py` |

Base: `ec7ca6e` — fix(profile): add missing API guards and subscriber status context

## Methodology

Every changed file was reviewed by inspecting `git diff ec7ca6e -- <file>` and classified as:
- **Fix** — hardened error handling, bug compatibility, defensive fallback, API path fix
- **New Feature** — entirely new UI, new route, new page, new capability
- **Mixed** — intertwined fix + feature; skipped to avoid contamination

Files with mixed/non-fix changes were left dirty for separate feature commits.

## Phase Results

### Phase A: Messaging
- ✅ `services/messaging_engine.py` — single-query `get_thread()`, `_load_thread_message_metadata()`, `get_thread_metadata()`, deleted body, edited flag, new columns
- ✅ `templates/messages/index.html` — response parsing resilience (`json.message`, `json.thread` fallback)
- ❌ `templates/messages/thread.html` — entirely new UI (reaction badges, reply previews, metadata load) → skip

### Phase B: Calls
- ❌ `api_routes/call_routes.py` — 3 new legacy route aliases only → skip

### Phase C: Posts/Reels
- ❌ `templates/posts/detail.html` — mixed: like endpoint fix intertwined with comment refactoring → skip
- ❌ `templates/reels/detail.html` — same pattern → skip
- ✅ `scripts/test_phase161_photo_post_display.py` — defensive record fallback, db_available
- ✅ `scripts/test_phase161_reel_upload_reflection.py` — same defensive pattern

### Phase D: Profile/Social
- ✅ `api_routes/social_routes.py` — unfollow when state is "friends" not just "following"
- ❌ `api_routes/profile_routes.py` — 2 new business page endpoints → skip
- ❌ `templates/profile/partials/profile_tabs.html` — adds Gallery tab button → skip

### Phase E: Admin/Verification/Safety
- ❌ `templates/admin/verifications.html` — complete rewrite, new dashboard UI → skip
- ❌ `templates/safety/report.html` — complete rewrite, full-page report UI → skip

### Phase F: New Features (not committed)
All untracked files plus the following tracked-but-skipped files are new features:

| Category | Files |
|----------|-------|
| Business Pages | `profile_routes.py` (2 endpoints), `business_page_service.py`, `templates/business/`, `static/css/business*` |
| Gallery | `gallery_routes.py`, `templates/gallery/`, `static/css/gallery.css` |
| Creator/Ads | `creator_routes.py` (2 campaign endpoints), `templates/profile/advertising.html` |
| Content Controls | `content_controls_routes.py` |
| Social Graph | `social_graph_routes.py`, `services/location_privacy_service.py`, `services/profile_sharing_service.py` |
| Verification | `verification_admin_routes.py`, `services/verification_request_service.py`, `templates/profile/verification_request.html` |
| Trust/Safety | `services/trust_scam_service.py`, `services/subscriber_content_service.py` |
| Templates | `templates/messages/thread.html`, `templates/posts/detail.html`, `templates/reels/detail.html` |
| Tests | 20+ new audit/test scripts under `scripts/` |
| Docs | 6 CODEX reports under `docs/` |

**Recommendation:** Do not commit new features in the same commit as production fixes. Each feature area should be reviewed, tested, and committed independently.

## Remaining Work (untouched)

The following tracked-but-modified files were NOT reviewed in this session (from prior triage). They require separate classification:

### Services
`auth_service.py`, `engagement_service.py`, `homepage_phase141_service.py`, `homepage_service.py`, `neon_service.py`, `notification_center_service.py`, `payout_service.py`, `profile_completion_service.py`, `profile_service.py`, `profile_view_service.py`, `redis_service.py`, `relationship_cache_service.py`, `session_service.py`, `supabase_safe.py`, `viral_feed_service.py`

### API Routes
`auth_routes.py`, `homepage_api.py`, `notification_routes.py`, `wallet_routes.py`

### Static JS
`namvibe_home_pro.js`, `namvibe_messages_pro.js`, `namvibe_notifications.js`, `notifications_center.js`

### Templates
`auth/login.html`, `auth/register.html`, `base.html`, `chain_home.html`, `profile/privacy.html`, `profile/security.html`, `calls/notification_fallback.html`, `calls/video.html`

## Verification

Every commit was verified with:
1. `python3 -m py_compile app.py`
2. `python3 -m compileall api_routes services templates`
3. `python3 scripts/verify_live_production_smoke.py`
4. `python3 scripts/benchmark_production_routes.py`

All passed.
