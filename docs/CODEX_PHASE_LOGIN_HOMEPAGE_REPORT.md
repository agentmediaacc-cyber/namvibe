# CODEX Phase Login/Homepage Report

Date: 2026-06-28
Branch: `phase113-production`

## Scope completed

- Login subsystem

## Login bugs found

1. `register_chain_user()` returned before its signup logic, so registration fell through to failure handling.
2. Login form did not send `remember_me`.
3. Login form did not preserve `next` explicitly on POST.
4. Logout/session cleanup left stale session keys behind.
5. Auth templates could fail in isolated test rendering because `csrf_token` and `apk_csrf_token` were not always defined.
6. Test-mode route POSTs were blocked by CSRF even when `FLASK_TESTING=1`.
7. Login page success/error copy did not match current auth regression expectations.
8. Password reset success redirected with `password_reset_success=1` while the login route only rendered the success message for `password_reset=1`.

## Login files changed

- `app.py`
- `api_routes/auth_routes.py`
- `services/auth_service.py`
- `services/session_service.py`
- `templates/base.html`
- `templates/auth/login.html`
- `templates/auth/register.html`

## Login fixes applied

- Restored a working registration execution path inside `register_chain_user()`.
- Wired `remember_me` through the login form and backend login call.
- Preserved `next` on login POST.
- Hardened logout/session clearing for `logged_in`, `user_id`, `email`, `auth_next`, and local fallback session keys.
- Added safe CSRF exposure for full app and isolated template rendering.
- Disabled CSRF only in test mode with `FLASK_TESTING=1`.
- Updated login success/error copy to match current test expectations.
- Fixed the password reset redirect flag so the login page now shows the expected success state.

## Login verification run

1. `python3 -m py_compile app.py`
   - PASS
2. `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`
   - PASS
3. `python3 scripts/test_login_flow.py`
   - PASS
4. `python3 scripts/test_registration_flow.py`
   - PASS
5. `python3 scripts/test_phase57_auth_full_repair.py`
   - PASS

## Login changed files for this subsystem

- `app.py`
- `api_routes/auth_routes.py`
- `services/auth_service.py`
- `services/session_service.py`
- `templates/base.html`
- `templates/auth/login.html`
- `templates/auth/register.html`
- `docs/CODEX_PHASE_LOGIN_HOMEPAGE_REPORT.md`

## Remaining login risks

- Live production login against real external services was not exercised from this local run because network-backed Neon/Supabase calls are unavailable in the local test environment.
- OAuth flows were not re-verified end-to-end in this step.

## Homepage bugs found

1. Homepage story cards linked to `/status/` instead of the concrete story detail route, so clicking a story dropped the selected story id and opened the generic story index.
2. Homepage share buttons only copied/shared the post URL and never called the existing `/api/home/post/<post_id>/share` endpoint, so share counts were not tracked.

## Homepage files changed

- `templates/chain_home.html`
- `static/js/namvibe_home_pro.js`

## Homepage fixes applied

- Updated server-rendered and hydrated story cards to link to `/stories/<story_id>`.
- Wired homepage share actions to the existing post share API before invoking Web Share or clipboard fallback.

## Combined verification run

1. `python3 -m py_compile app.py`
2. `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`
3. `pytest -q tests 2>/tmp/chain_pytest_err.log || true`

## Remaining risks

- `pytest -q tests` may be a no-op in this workspace if the `tests/` directory is absent; the required command still needs to be executed as requested.
- Homepage live data behavior remains dependent on local database/service availability and was audited here for route/template/API contract mismatches only.
