#!/usr/bin/env python3
"""
End-to-end content reality test (stories, reels, notifications).

 - Uses real Neon DB and Redis when available
 - Captures Socket.IO emits by monkey-patching emit entrypoints
 - Exercises story create/view/react/reply flows, reel like/comment/share/save, and notification creation/broadcast

Run: python3 scripts/test_content_reality.py
"""
import os
import sys
import uuid
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
app = create_app()

from services.neon_service import fast_query, write_query, get_pool_status
import services.socketio_service as socksvc
import services.socket_events as sockev
import flask_socketio as flask_socketio

from services import content_service, status_service
import services.stories_service as stories_service
import services.reels_engine as reels_engine
import services.engagement_service as engagement_service
import services.notification_engine as notification_engine
import services.presence_service as presence_service

client = app.test_client()

CAPTURED_EMITS = []

def capture_emit(profile_id, event, payload):
    CAPTURED_EMITS.append({"profile_id": str(profile_id), "event": event, "payload": payload})


def capture_generic_emit(event, payload=None, room=None, include_self=True):
    profile_id = None
    try:
        if room and isinstance(room, str) and room.startswith("profile:"):
            profile_id = room.split(":", 1)[1]
        else:
            from flask import session as _session
            profile_id = _session.get("profile_id")
    except Exception:
        profile_id = None
    CAPTURED_EMITS.append({"profile_id": str(profile_id) if profile_id else None, "event": event, "payload": payload})


def capture_flask_emit(event, payload=None, room=None, include_self=True):
    return capture_generic_emit(event, payload, room=room, include_self=include_self)


def noop_join_room(room):
    return None


def login(pid):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True


def call_with_request_session(pid, fn, *args, **kwargs):
    from flask import session as flask_session
    with app.test_request_context('/', method='POST'):
        flask_session["profile_id"] = pid
        flask_session["auth_user_id"] = pid
        flask_session["user_id"] = pid
        flask_session["access_token"] = "test-token"
        flask_session["_permanent"] = True
        return fn(*args, **kwargs)


def check(label, ok, detail=None):
    print(("[PASS] " if ok else "[FAIL] ") + label + (f" — {detail}" if detail and not ok else ""))
    return ok


def run():
    print("\n=== CONTENT REALITY TEST ===\n")
    print("DB pool status:", get_pool_status())

    # patch emits
    socksvc_emit_orig = socksvc.emit_to_profile
    socksvc_emit_thread_orig = socksvc.emit_to_thread
    socksvc_emit_live_orig = socksvc.emit_to_live_room
    socksvc__emit_async_orig = getattr(socksvc, '_emit_async', None)
    socksvc_socketio_emit_orig = getattr(socksvc.socketio, 'emit', None)

    sockev_emit_orig = getattr(sockev, 'emit', None)
    flask_socketio_emit_orig = getattr(flask_socketio, 'emit', None)
    sockev_join_orig = getattr(sockev, 'join_room', None)
    sockev_leave_orig = getattr(sockev, 'leave_room', None)

    socksvc.emit_to_profile = capture_emit
    socksvc.emit_to_thread = lambda thread_id, event, payload: capture_generic_emit(event, payload, room=f"thread:{thread_id}")
    socksvc.emit_to_live_room = lambda room_id, event, payload: capture_generic_emit(event, payload, room=f"live:{room_id}")
    if socksvc__emit_async_orig is not None:
        socksvc._emit_async = lambda event, payload, room=None, include_self=True: capture_generic_emit(event, payload, room=room, include_self=include_self)
    if socksvc_socketio_emit_orig is not None:
        try:
            socksvc.socketio.emit = lambda event, payload=None, room=None, include_self=True: capture_generic_emit(event, payload, room=room, include_self=include_self)
        except Exception:
            pass

    try:
        flask_socketio.emit = capture_flask_emit
    except Exception:
        pass
    if sockev_emit_orig is not None:
        sockev.emit = capture_flask_emit

    sockev.join_room = noop_join_room
    sockev.leave_room = noop_join_room

    try:
        # create test profiles
        a = str(uuid.uuid4())
        b = str(uuid.uuid4())
        for pid, uname_base in [(a, 'e2e_content_owner'), (b, 'e2e_content_viewer')]:
            uname = f"{uname_base}_{pid[:8]}"
            write_query("INSERT INTO chain_profiles (id, auth_user_id, username, display_name, created_at) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (id) DO NOTHING", (pid, pid, uname, uname))

        CAPTURED_EMITS.clear()

        # STORIES: create story for A
        rec = content_service.create_story_record(a, caption="E2E story test")
        story = rec[0] if isinstance(rec, tuple) else rec
        story_id = story.get('id') if story else None
        check('created story record', bool(story), str(story))

        # verify status_service.get_status
        s = status_service.get_status(story_id)
        check('status fetched by id', bool(s), str(s))

        # viewer B views story -> should emit status:viewed to owner A
        CAPTURED_EMITS.clear()
        try:
            presence_service.set_online(b)
        except Exception:
            pass
        # Use stories_service.record_story_view so views and reactions live in chain_story_views
        stories_service.record_story_view(story_id, b)
        viewed = [e for e in CAPTURED_EMITS if e.get('event') == 'status:viewed' and e.get('profile_id') == a]
        check('status:viewed emitted to owner', len(viewed) > 0, json.dumps(CAPTURED_EMITS, default=str))
        if viewed:
            payload = viewed[0].get('payload') or {}
            check('view payload has status_id and viewer_id', 'status_id' in payload and 'viewer_id' in payload, str(payload))

        # react to story using stories_service (updates likes)
        ok = stories_service.react_to_story(story_id, b, 'like')
        check('react_to_story executed', ok)
        story_with_views = stories_service.get_story_with_views(story_id)
        # reaction may be stored on view row
        reactions = [v for v in (story_with_views or {}).get('views', []) if v.get('viewer_id') == b and v.get('reaction')]
        check('reaction recorded for viewer', len(reactions) > 0, str(story_with_views))

        # REELS: insert a reel row directly to avoid storage/upload
        reel_id = str(uuid.uuid4())
        write_query("INSERT INTO chain_reels (id, profile_id, caption, video_url, status, visibility, processing_status, created_at) VALUES (%s,%s,%s,%s,'published','public','ready',now()) ON CONFLICT (id) DO NOTHING", (reel_id, a, 'E2E reel', 'http://example.local/video.mp4'))
        r = reels_engine.get_reel(reel_id)
        check('reel created and retrievable', bool(r), str(r))

        # like reel by B (should create reaction + notification)
        CAPTURED_EMITS.clear()
        like_res = engagement_service.toggle_like(b, 'reel', reel_id)
        check('toggle_like returned success', like_res.get('success') is True, str(like_res))
        # notification should be emitted to owner A
        notif_emits = [e for e in CAPTURED_EMITS if e.get('event') == 'notification:new' and e.get('profile_id') == a]
        check('notification emitted for reel like', len(notif_emits) > 0, json.dumps(CAPTURED_EMITS, default=str))

        # comment on reel
        CAPTURED_EMITS.clear()
        comment_res = engagement_service.add_comment(b, 'reel', reel_id, 'Nice video')
        check('add_comment success', comment_res.get('success') is True, str(comment_res))
        # comment should create notification
        notif_emits = [e for e in CAPTURED_EMITS if e.get('event') == 'notification:new' and e.get('profile_id') == a]
        check('notification emitted for reel comment', len(notif_emits) > 0, json.dumps(CAPTURED_EMITS, default=str))

        # share reel (increments shares_count)
        before = fast_query('SELECT shares_count FROM chain_reels WHERE id = %s', (reel_id,), default=[{'shares_count': 0}])[0].get('shares_count')
        reels_engine.share_reel(reel_id, b)
        after = fast_query('SELECT shares_count FROM chain_reels WHERE id = %s', (reel_id,), default=[{'shares_count': 0}])[0].get('shares_count')
        check('share increments shares_count', after >= before + 1, f'{before} -> {after}')

        # save reel
        save_res = engagement_service.toggle_save(b, 'reel', reel_id)
        check('toggle_save success', save_res.get('success') is True, str(save_res))

        # NOTIFICATIONS: create a direct notification and ensure emit + DB record
        CAPTURED_EMITS.clear()
        nid = notification_engine.create_notification(a, 'test_event', 'Test Title', body='hello', actor_profile_id=b, entity_type='reel', entity_id=reel_id)
        check('create_notification returned id', bool(nid), str(nid))
        notif_emits = [e for e in CAPTURED_EMITS if e.get('event') == 'notification:new' and e.get('profile_id') == a]
        check('notification:new emitted to recipient', len(notif_emits) > 0, json.dumps(CAPTURED_EMITS, default=str))
        # list_notifications should include the new notification
        items = notification_engine.list_notifications(a, limit=10)
        found = any(i for i in items if str(i.get('id')) == str(nid))
        check('notification present in list_notifications', found, str(items)[:200])

    finally:
        # restore patches
        socksvc.emit_to_profile = socksvc_emit_orig
        socksvc.emit_to_thread = socksvc_emit_thread_orig
        socksvc.emit_to_live_room = socksvc_emit_live_orig
        if socksvc__emit_async_orig is not None:
            socksvc._emit_async = socksvc__emit_async_orig
        if socksvc_socketio_emit_orig is not None:
            try:
                socksvc.socketio.emit = socksvc_socketio_emit_orig
            except Exception:
                pass
        if flask_socketio_emit_orig is not None:
            try:
                flask_socketio.emit = flask_socketio_emit_orig
            except Exception:
                pass
        if sockev_emit_orig is not None:
            try:
                sockev.emit = sockev_emit_orig
            except Exception:
                pass
        if sockev_join_orig is not None:
            sockev.join_room = sockev_join_orig
        if sockev_leave_orig is not None:
            sockev.leave_room = sockev_leave_orig


if __name__ == '__main__':
    run()
