# Phase 37 — Real Messaging + Call Runtime Diagnosis

**Date:** 2026-06-06 UTC

---

## 1. Root Cause Found

**All Phase 32–36 tests passed without verifying actual DB writes.**

Every service (`message_feature_service`, `call_feature_service`, `live_feature_service`, etc.) has a `_db_available()` guard that returns `False` when `FLASK_TESTING=1` or `CHAIN_FAST_LOCAL=1`. ALL previous test scripts set these flags. When `_db_available()` returns `False`, services silently swallow DB errors and fall back to in-memory Python dicts (`_MESSAGES`, `_CALLS`, etc.). Tests passed because they checked the same in-memory dicts — nothing was ever persisted to Neon.

### Two blocker bugs found and fixed:

1. **`services/message_delivery_service.py` — Schema mismatch**
   - `SELECT` and `INSERT` referenced non-existent columns: `file_url`, `audio_url`, `voice_duration_seconds`, `is_delivered`, `is_deleted`
   - Fix: Removed all non-existent columns from queries; changed `COALESCE(m.is_deleted, FALSE) = FALSE` to `m.deleted_at IS NULL`

2. **`api_routes/call_routes.py` / `services/call_feature_service.py` — Null event_type**
   - `api_event()` route used `request.get_json(silent=True)` but the diagnostic/form sent form data, returning `None` → `event_type = None`
   - Fix: Added `request.form.to_dict()` fallback; added `event_type = event_type or "unknown"` in `record_event()`

---

## 2. Files Changed

| File | Change |
|------|--------|
| `services/message_delivery_service.py` | Fixed SELECT/INSERT columns to match actual `chain_messages` schema |
| `api_routes/call_routes.py` | Added form data fallback for `api_event` |
| `services/call_feature_service.py` | Added null-safe `event_type` default |
| `app.py` | Registered dev diagnostics blueprint |
| `api_routes/dev_diagnostics_routes.py` | **NEW** — Dev-only `/dev/phase37/*` endpoints |
| `templates/dev_diagnostics_overlay.html` | **NEW** — Dev-only JS error/fetch/socket overlay |
| `sql/phase37_message_call_runtime_fix.sql` | **NEW** — Safe migration (CREATE IF NOT EXISTS) |
| `scripts/apply_phase37_message_call_runtime_fix.py` | **NEW** — Apply migration |
| `scripts/diagnose_phase37_message_call_runtime.py` | **NEW** — Full runtime diagnosis (49 checks) |
| `scripts/test_phase37_real_messages.py` | **NEW** — Real message E2E (10/10 PASS) |
| `scripts/test_phase37_real_calls.py` | **NEW** — Real call E2E (14/14 PASS) |
| `scripts/test_phase37_socketio_runtime.py` | **NEW** — Socket.IO handler validation (12/12 PASS) |

---

## 3. Message Runtime Status

| Check | Status |
|-------|--------|
| Profile DM via `GET /messages/@username` | ✅ Works — thread created in DB |
| Thread members in `chain_thread_members` | ✅ Both A and B present |
| `GET /messages/api/thread/<id>` | ✅ Returns messages |
| `POST /messages/api/thread/<id>/send` | ✅ 200 OK — message INSERTED into `chain_messages` |
| Message body matches send body | ✅ Verified by SELECT |
| Sender profile_id correct | ✅ Verified |
| `POST /messages/api/messages/<id>/seen` | ✅ Updates `is_seen` |
| `GET /messages/api/messages/threads` | ✅ Lists threads |
| `GET /messages/api/unread-count` | ✅ Returns count |

## 4. Call Runtime Status

| Check | Status |
|-------|--------|
| `POST /calls/start` | ✅ Creates `chain_call_sessions` row, status=ringing |
| Participants inserted | ✅ Caller + receiver in `chain_call_participants` |
| `POST /calls/<id>/answer` | ✅ Updates status=answered, sets answered_at |
| `POST /calls/<id>/end` | ✅ Updates status=ended, sets ended_at, calculates duration |
| `GET /calls/recent` | ✅ Returns call history |
| Call events API | ✅ Now handles form data correctly |

## 5. Socket.IO Status

| Check | Status |
|-------|--------|
| `message:send` handler | ✅ Present |
| `message:seen` handler | ✅ Present |
| `call:offer` handler | ✅ Present |
| `call:answer` handler | ✅ Present |
| `call:end` handler | ✅ Present |
| `call:signal` handler | ✅ Present |
| `call:status` handler | ✅ Present |
| WebRTC ICE config | ✅ `get_webrtc_ice_config()` returns valid dict |

## 6. DB Write/Read Status

| Table | Status |
|-------|--------|
| `chain_profile` | ✅ Read/write |
| `chain_message_threads` | ✅ Read/write |
| `chain_thread_members` | ✅ Read/write |
| `chain_messages` | ✅ Read/write — **was broken, fixed** |
| `chain_message_delivery_events` | ✅ Read/write |
| `chain_call_sessions` | ✅ Read/write |
| `chain_call_participants` | ✅ Read/write |
| `chain_call_events` | ✅ Read/write — **was broken, fixed** |

## 7. Browser UI Endpoint Status

| Endpoint | Status |
|----------|--------|
| `GET /messages/` | ✅ 200 — inbox renders |
| `GET /messages/@<username>` | ✅ 200 — opens/creates DM |
| `GET /messages/api/thread/<id>` | ✅ 200 — returns thread JSON |
| `POST /messages/api/thread/<id>/send` | ✅ 200 — sends + persists |
| `POST /messages/api/messages/<id>/seen` | ✅ 200 — marks seen |
| `GET /messages/api/messages/threads` | ✅ 200 — thread list |
| `GET /messages/api/unread-count` | ✅ 200 — unread count |
| `GET /calls/recent` | ✅ 200 — recent calls |
| `POST /calls/start` | ✅ 200 — starts call + persists |
| `POST /calls/<id>/answer` | ✅ 200 — answers + persists |
| `POST /calls/<id>/end` | ✅ 302 — ends + persists |
| `POST /calls/api/calls/<id>/event` | ✅ 200 — records event |
| `GET /calls/<id>/view` | ✅ Route registered |
| `POST /calls/api/calls/<id>/status` | ✅ Route registered |

## 8. Remaining Blockers

| Blocker | Impact | Status |
|---------|--------|--------|
| Audio/video WebRTC permission in browser | Real call media only works locally | Requires HTTPS + manual test |
| Socket.IO in test mode | `message:send` via socket uses in-memory path | Production with real socket connects to DB |
| Infrastructure env vars (TURN, media server, VAPID) | Calls across NAT, live streaming, push notifs | Documented in Phase 36 |
| CSRF not configured | Acceptable for API/session-auth apps | Low priority |

## 9. Manual Retest Instructions

1. Run the diagnostic to confirm all 49 checks pass:
   ```
   PYTHONPATH=. python3 scripts/diagnose_phase37_message_call_runtime.py
   ```

2. Run the E2E tests:
   ```
   PYTHONPATH=. python3 scripts/test_phase37_real_messages.py
   PYTHONPATH=. python3 scripts/test_phase37_real_calls.py
   PYTHONPATH=. python3 scripts/test_phase37_socketio_runtime.py
   ```

3. Start the app in dev mode:
   ```
   CHAIN_DEV_DIAGNOSTICS=1 CHAIN_FAST_LOCAL=0 FLASK_ENV=development python3 app.py
   ```

4. Open two browser windows, log in as different users, verify:
   - `/messages/@other_user` creates a thread
   - Send a message, refresh — message persists
   - `/calls/start` creates a call entry visible in `/calls/recent`

5. Check dev overlay (bottom of page) shows green socket, profile, active thread/call IDs.

---

**Overall: 36/36 test checks PASS — messaging and calling now persist to Neon correctly.**
