# Phase Calls + Notifications

Date: 2026-06-28

## Confirmed breakages fixed

- Fixed notification center empty-state logic in `static/js/notifications_center.js` so the empty state appears only after the skeleton loader is gone.
- Fixed call screen status/template mismatch in `templates/calls/video.html` by normalizing `call.call_status` and `call.status`.
- Fixed fallback call template status mismatch in `templates/calls/notification_fallback.html` by normalizing status handling for ringing, connected, missed, ended, rejected, and cancelled states.
- Added legacy compatibility routes in `api_routes/call_routes.py` for UI paths already referenced by the app:
  - `GET /messages/calls/logs`
  - `POST /messages/calls/<log_id>/delete`
  - `POST /messages/calls/start`

## Audit notes

- Notifications:
  - Notification center routes and JS matched after the empty-state fix.
  - Primary notifications page routes and JS were already aligned.
- Calls:
  - WebRTC call APIs under `/calls/api/*` were present.
  - Legacy messages UI still referenced `/messages/calls/*` routes; compatibility aliases were missing and were added.
  - Call templates were mixing legacy `call_status` with newer WebRTC `status`; normalized in templates only.

## Validation

- `python3 -m py_compile app.py` ✅
- `python3 -m compileall api_routes services templates >/tmp/chain_compile.log` ✅
- `pytest -q tests 2>/tmp/chain_pytest_err.log || true` completed with `no tests ran in 0.00s`
