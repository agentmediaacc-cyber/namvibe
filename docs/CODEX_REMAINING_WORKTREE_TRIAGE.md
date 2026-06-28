# CODEX Remaining Worktree Triage

## Command Snapshot

### `git diff --stat`
- 46 tracked files still modified after commit `79527c5`
- Heavy concentration in:
  - auth/profile/homepage/services
  - messaging/calls/notifications
  - templates and frontend JS

### `git status --short`
- Modified tracked files remain across `api_routes/`, `services/`, `static/js/`, and `templates/`
- Large untracked set remains across:
  - new route/service/template feature work
  - audit/test scripts
  - reports/docs
  - one SQL file

### `git diff --name-only`
- Remaining tracked modifications:
  - `api_routes/auth_routes.py`
  - `api_routes/call_routes.py`
  - `api_routes/creator_routes.py`
  - `api_routes/gallery_routes.py`
  - `api_routes/homepage_api.py`
  - `api_routes/notification_routes.py`
  - `api_routes/profile_routes.py`
  - `api_routes/social_routes.py`
  - `api_routes/wallet_routes.py`
  - `scripts/test_phase161_photo_post_display.py`
  - `scripts/test_phase161_reel_upload_reflection.py`
  - `services/auth_service.py`
  - `services/engagement_service.py`
  - `services/homepage_phase141_service.py`
  - `services/homepage_service.py`
  - `services/messaging_engine.py`
  - `services/neon_service.py`
  - `services/notification_center_service.py`
  - `services/payout_service.py`
  - `services/profile_completion_service.py`
  - `services/profile_service.py`
  - `services/profile_view_service.py`
  - `services/redis_service.py`
  - `services/relationship_cache_service.py`
  - `services/session_service.py`
  - `services/supabase_safe.py`
  - `services/viral_feed_service.py`
  - `static/js/namvibe_home_pro.js`
  - `static/js/namvibe_messages_pro.js`
  - `static/js/namvibe_notifications.js`
  - `static/js/notifications_center.js`
  - `templates/admin/verifications.html`
  - `templates/auth/login.html`
  - `templates/auth/register.html`
  - `templates/base.html`
  - `templates/calls/notification_fallback.html`
  - `templates/calls/video.html`
  - `templates/chain_home.html`
  - `templates/messages/index.html`
  - `templates/messages/thread.html`
  - `templates/posts/detail.html`
  - `templates/profile/partials/profile_tabs.html`
  - `templates/profile/privacy.html`
  - `templates/profile/security.html`
  - `templates/reels/detail.html`
  - `templates/safety/report.html`

## 1. Safe Production Fixes

### Files
- `api_routes/auth_routes.py`
- `api_routes/homepage_api.py`
- `api_routes/notification_routes.py`
- `api_routes/wallet_routes.py`
- `services/auth_service.py`
- `services/homepage_phase141_service.py`
- `services/homepage_service.py`
- `services/neon_service.py`
- `services/notification_center_service.py`
- `services/payout_service.py`
- `services/profile_completion_service.py`
- `services/profile_service.py`
- `services/profile_view_service.py`
- `services/redis_service.py`
- `services/relationship_cache_service.py`
- `services/session_service.py`
- `services/supabase_safe.py`
- `services/viral_feed_service.py`
- `static/js/namvibe_home_pro.js`
- `static/js/namvibe_notifications.js`
- `static/js/notifications_center.js`
- `templates/auth/login.html`
- `templates/auth/register.html`
- `templates/base.html`
- `templates/chain_home.html`
- `templates/profile/privacy.html`
- `templates/profile/security.html`

### Purpose
- Likely hardening existing auth/session/homepage/notification/profile/runtime behavior without introducing entirely new surfaces.
- These files align with the previously audited login/homepage/profile/notifications/performance phases.

### Risk Level
- Medium.
- They touch core runtime paths and should be reviewed in a second focused commit, but they are more plausibly release-oriented fixes than feature additions.

### Recommendation
- Keep.
- Commit later in a separate, focused hardening pass after targeted review and rerun of the relevant smoke tests.

## 2. New Features

### Files
- `api_routes/ad_admin_routes.py`
- `api_routes/content_controls_routes.py`
- `api_routes/social_graph_routes.py`
- `api_routes/verification_admin_routes.py`
- `services/business_page_service.py`
- `services/location_privacy_service.py`
- `services/profile_sharing_service.py`
- `services/subscriber_content_service.py`
- `services/trust_scam_service.py`
- `services/verification_request_service.py`
- `sql/058_phase158d_tables.sql`
- `static/css/business.css`
- `static/css/business_flyer_generator.css`
- `static/css/gallery.css`
- `static/js/business_flyer_generator.js`
- `templates/business/flyer_generator.html`
- `templates/business/page.html`
- `templates/errors/post_not_found.html`
- `templates/gallery/index.html`
- `templates/profile/advertising.html`
- `templates/profile/business.html`
- `templates/profile/completion.html`
- `templates/profile/sent_requests.html`
- `templates/profile/sharing.html`
- `templates/profile/suggestions.html`
- `templates/profile/verification_request.html`

### Purpose
- New admin surfaces, content controls, social graph flows, verification admin, business/gallery/profile feature surfaces, and new schema support.

### Risk Level
- High.
- These are not “safe release cleanup” changes. They expand product surface area and may require migrations, permission review, and UX/runtime validation.

### Recommendation
- Keep in branch if they are intentional.
- Do not mix into a production-hardening push.
- Commit later as separate feature PRs/commits after dedicated review.

## 3. Audit/Test Scripts

### Files
- `scripts/test_phase161_photo_post_display.py`
- `scripts/test_phase161_reel_upload_reflection.py`
- All untracked `scripts/audit_*`
- All untracked `scripts/test_phase158d_*`
- All untracked `scripts/test_phase159_*`
- All untracked `scripts/test_phase160_*`
- All untracked `scripts/test_phase162_*`
- All untracked `scripts/test_phase165_*`
- `scripts/verify_production_routes.py`
- `scripts/verify_wallet_routes.py`
- `test_bug_verification.py`
- `test_bug_verification_fixed.py`
- `scripts/debug_phase164b_live_failures.py`

### Purpose
- One-off audits, reality checks, regression probes, debug harnesses, and feature-specific verification scripts.

### Risk Level
- Low to Medium.
- Low runtime risk if unshipped, but high repo-noise risk if committed without curation.
- Some may be valuable; many are likely transient audit artifacts.

### Recommendation
- Keep selectively.
- Commit later only if the team wants these retained as permanent verification tooling.
- Otherwise ignore or move to a narrower audit branch.

## 4. Reports/Docs

### Files
- `docs/CODEX_CHAIN_CONTINUATION_REPORT.md`
- `docs/CODEX_PHASE_CALLS_NOTIFICATIONS_REPORT.md`
- `docs/CODEX_PHASE_LOGIN_HOMEPAGE_REPORT.md`
- `docs/CODEX_PHASE_PROFILE_MESSAGES_REPORT.md`
- `docs/CODEX_PHASE_WALLET_PRODUCTION_REPORT.md`
- `docs/performance/index_recommendations.md`
- `docs/performance/performance_report.md`
- `docs/performance/query_optimization_report.md`
- `audit_results.json`

### Purpose
- Audit records, phase summaries, performance notes, and generated analysis output.

### Risk Level
- Low.
- Main risk is clutter and stale guidance, not runtime behavior.

### Recommendation
- Keep if the repository intentionally stores audit history.
- Commit later in a documentation-only commit.
- `audit_results.json` is more likely generated output and should probably be ignored unless explicitly needed.

## 5. Risky or Unclear Changes

### Files
- `api_routes/call_routes.py`
- `api_routes/creator_routes.py`
- `api_routes/gallery_routes.py`
- `api_routes/profile_routes.py`
- `api_routes/social_routes.py`
- `services/engagement_service.py`
- `services/messaging_engine.py`
- `templates/admin/verifications.html`
- `templates/calls/notification_fallback.html`
- `templates/calls/video.html`
- `templates/messages/index.html`
- `templates/messages/thread.html`
- `templates/posts/detail.html`
- `templates/profile/partials/profile_tabs.html`
- `templates/reels/detail.html`
- `templates/safety/report.html`

### Purpose
- Likely mixes of real fixes plus new behavior across calls, creator/gallery/profile/social, engagement, messaging, verification admin UI, and detail views.

### Risk Level
- High.
- These touch user-facing behavior, live communication, moderation/safety, and admin workflows.
- They need targeted review for permissions, route wiring, UI/API compatibility, and migration expectations.

### Recommendation
- Keep in branch for now.
- Do not push as part of the hardened production commit set.
- Review and split into:
  - real production fixes
  - feature work
  - audit leftovers

## 6. Files That Should Be Reverted or Ignored

### Files
- `audit_results.json`
- likely temporary debug/output scripts and local bug files:
  - `scripts/debug_phase164b_live_failures.py`
  - `test_bug_verification.py`
  - `test_bug_verification_fixed.py`

### Purpose
- Generated output or ad hoc debugging/bug reproduction material.

### Risk Level
- Medium for repository hygiene, low for runtime.

### Recommendation
- Revert or ignore unless a maintainer explicitly wants them preserved.
- Prefer `.gitignore` or a separate scratch branch for generated/debug artifacts.

## Overall Triage Recommendation

- Safe to keep local:
  - the remaining production-hardening candidates
  - feature work that is intentionally in progress
- Safe to commit later:
  - reviewed production fixes
  - curated audit scripts
  - docs/reports in doc-only commits
- Should not be mixed into the current production hardening release:
  - new feature surfaces
  - unclear call/profile/social/messaging UI rewires
  - generated/debug artifacts

## Next Best Action

1. Split the remaining worktree into three follow-up commits:
   - production/runtime fixes
   - feature additions
   - docs/audits
2. Drop or ignore generated/debug artifacts.
3. Re-review the high-risk route/service/template set before any push that includes them.
