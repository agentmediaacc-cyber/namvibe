# CODEX Phase Profile + Messages Report

Date: 2026-06-28
Branch: `phase113-production`

## Scope completed

- Profile routes/templates/services
- Messages routes/templates/services

## Confirmed profile breakages found

1. Profile stats counted stories from `chain_stories` while active story creation and reads use `chain_status_posts`, causing story counts on profile surfaces to drift or stay at zero.
2. Profile content loaded story previews from `chain_stories` instead of `chain_status_posts`, causing story sections on profile surfaces to miss current story records.

## Confirmed messages breakages found

1. `static/js/namvibe_messages_pro.js` required `json.ok` for successful sends, but the existing send API returns `success`, so successful sends were treated as failures in the premium inbox flow.
2. `templates/messages/index.html` expected `/messages/api/thread/<thread_id>` to return `messages` at top level, but the route returns a wrapped thread payload under `message`, so inbox thread loading rendered empty conversations.
3. `services/messaging_engine.get_thread()` did not include `message_type`, `location_lat`, `location_lng`, or `edited_at`, while `templates/messages/thread.html` uses those fields for voice-note rendering, map links, and edited-state display.

## Files changed

- `services/profile_service.py`
- `static/js/namvibe_messages_pro.js`
- `templates/messages/index.html`
- `services/messaging_engine.py`

## Fixes applied

- Switched profile story stats and story content queries to `chain_status_posts`.
- Kept profile story previews aligned with the current story data model by selecting `video_url` alongside existing fields.
- Updated premium inbox send handling to accept either `ok` or `success` from the existing message send API.
- Updated inbox thread loading to accept the wrapped thread response shape returned by `/messages/api/thread/<thread_id>`.
- Expanded server-side thread message selection so the thread template receives voice-note type, map coordinates, and edited-state data it already expects.

## Verification run

1. `python3 -m py_compile app.py`
   - PASS
2. `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`
   - PASS
3. `pytest -q tests 2>/tmp/chain_pytest_err.log || true`
   - No tests ran; `tests/` is not present in this workspace.

## Remaining risks

- The premium inbox page still contains several legacy client flows and alias routes; this pass fixed only directly confirmed route/template/API mismatches.
- End-to-end realtime verification for typing, receipts, and socket-delivered message updates was not exercised from a live browser session in this turn.
