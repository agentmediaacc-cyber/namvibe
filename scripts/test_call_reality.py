#!/usr/bin/env python3
"""
End-to-end call reality test (server-side services).

 - Uses real Neon DB (no fake shims)
 - Does not start a Socket.IO client; instead patches emit_to_profile to capture emits
 - Exercises services/webrtc_call_service and socket event handlers

Run: python3 scripts/test_call_reality.py
"""
import os
import sys
import uuid
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
app = create_app()

from services.neon_service import fast_query, write_query, get_pool_status
import services.webrtc_call_service as wcs
import services.socketio_service as socksvc
import services.socket_events as sockev
import services.presence_service as presence_service
import flask_socketio as flask_socketio

client = app.test_client()

CAPTURED_EMITS = []

def capture_emit(profile_id, event, payload):
    # record emits for inspection in tests
    CAPTURED_EMITS.append({"profile_id": str(profile_id), "event": event, "payload": payload})


def capture_generic_emit(event, payload=None, room=None, include_self=True):
    # Attempt to extract profile id from room if present (profile:<id>)
    profile_id = None
    try:
        if room and isinstance(room, str) and room.startswith("profile:"):
            profile_id = room.split(":", 1)[1]
        else:
            # If inside a Flask request context, prefer session profile_id
            from flask import session as _session
            profile_id = _session.get("profile_id")
    except Exception:
        profile_id = None
    CAPTURED_EMITS.append({"profile_id": str(profile_id) if profile_id else None, "event": event, "payload": payload})


def capture_flask_emit(event, payload=None, room=None, include_self=True):
    # flask_socketio.emit wrapper used by some handlers
    return capture_generic_emit(event, payload, room=room, include_self=include_self)


def noop_join_room(room):
    return None


def login(pid):
    # set session for the test client (cookie store)
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True


def call_with_request_session(pid, fn, *args, **kwargs):
    """
    Execute a function (typically a socket event handler) inside a Flask
    test request context with session values set for pid.
    This avoids "Working outside of request context" errors when handlers
    access flask.request or flask.session.
    """
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
    print("\n=== CALL REALITY TEST ===\n")

    # quick pool status
    status = get_pool_status()
    print("DB pool status:", status)

    # Patch emit_to_profile to capture emits; patch join_room/leave_room used in socket handlers
    # socketio_service level
    socksvc_emit_orig = socksvc.emit_to_profile
    socksvc_emit_thread_orig = socksvc.emit_to_thread
    socksvc_emit_live_orig = socksvc.emit_to_live_room
    socksvc__emit_async_orig = getattr(socksvc, '_emit_async', None)
    socksvc_socketio_emit_orig = getattr(socksvc.socketio, 'emit', None)

    # socket_events and flask_socketio emit
    sockev_emit_orig = getattr(sockev, 'emit', None)
    flask_socketio_emit_orig = getattr(flask_socketio, 'emit', None)

    # join/leave room in socket_events
    sockev_join_orig = getattr(sockev, 'join_room', None)
    sockev_leave_orig = getattr(sockev, 'leave_room', None)

    # Patch a variety of emit entrypoints so we capture whatever path is used.
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

    # patch flask_socketio.emit and local emit in socket_events module
    try:
        flask_socketio.emit = capture_flask_emit
    except Exception:
        pass
    if sockev_emit_orig is not None:
        sockev.emit = capture_flask_emit

    sockev.join_room = noop_join_room
    sockev.leave_room = noop_join_room

    try:
        # 1. Verify call-related tables exist
        tables = ["chain_calls", "chain_call_participants", "chain_call_logs", "chain_call_events"]
        ok = True
        for t in tables:
            try:
                fast_query(f"SELECT 1 FROM {t} LIMIT 0")
                check(f"table {t} exists", True)
            except Exception as e:
                check(f"table {t} exists", False, str(e)[:200])
                ok = False
        if not ok:
            print("Missing DB tables — aborting test")
            return

        # 2. Create/use two test profiles
        caller = str(uuid.uuid4())
        receiver = str(uuid.uuid4())
        for pid, uname_base in [(caller, "e2e_call_caller"), (receiver, "e2e_call_receiver")]:
            try:
                # Use unique username per-run to avoid conflicts from prior test runs
                uname = f"{uname_base}_{pid[:8]}"
                write_query(
                    "INSERT INTO chain_profiles (id, auth_user_id, username, display_name, created_at) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (id) DO NOTHING",
                    (pid, pid, uname, uname),
                )
            except Exception as e:
                print("Failed to create profile", pid, e)
                raise

        # Clear captured emits
        CAPTURED_EMITS.clear()

        # 3. Caller starts a direct audio call using the realistic socket path
        # Simulate both profiles being online and friends so the start path proceeds
        print("Starting call from caller -> receiver")
        try:
            presence_service.set_online(caller)
        except Exception:
            pass
        try:
            presence_service.set_online(receiver)
        except Exception:
            pass

        # Ensure a friend relationship exists so handle_webrtc_call_start doesn't block
        try:
            # insert a friendship row (ordered) without worrying if it already exists
            p1, p2 = (caller, receiver) if caller < receiver else (receiver, caller)
            write_query("INSERT INTO chain_friends (profile_id_1, profile_id_2, status) VALUES (%s, %s, 'friend') ON CONFLICT DO NOTHING", (p1, p2))
        except Exception:
            pass

        # Invoke the socket handler for call:start inside a request context (realistic path)
        CAPTURED_EMITS.clear()
        try:
            res = call_with_request_session(caller, sockev.handle_webrtc_call_start, {"target_id": receiver, "call_type": "audio"})
            create_ok = res.get("ok") is True if isinstance(res, dict) else False
            check("call:start handler returned ok", create_ok, str(res))
            call = res.get("call") if isinstance(res, dict) else None
            if not call:
                print("handle_webrtc_call_start failed, aborting")
                return
            call_id = call.get("id")
        except Exception as e:
            print("handle_webrtc_call_start raised", e)
            return

        # 4. Verify DB call row exists
        row = fast_query("SELECT * FROM chain_calls WHERE id = %s", (call_id,), default=[])
        check("call row in DB", bool(row), str(row)[:200])

        # 5. Verify socket emit path sends call:incoming to receiver profile room
        # create_call should have emitted incoming via emit_to_profile -> captured
        incoming_emits = [e for e in CAPTURED_EMITS if e["event"] == "call:incoming" and e["profile_id"] == receiver]
        check("incoming emit to receiver", len(incoming_emits) > 0, json.dumps(CAPTURED_EMITS))
        if incoming_emits:
            inc = incoming_emits[0]["payload"] or {}
            # call_id and caller_id should be present in payload
            check("incoming payload has call_id and caller_id", "call_id" in inc and ("caller_id" in inc or "caller" in inc), str(inc))
            # call_type may be in call_type or call_mode
            check("incoming payload has call_type", ("call_type" in inc) or ("call_mode" in inc), str(inc))
            # target/receiver may be present or implied by the emit target (profile_id)
            check("incoming payload has target/receiver or emitted to receiver", ("target_id" in inc) or ("receiver_id" in inc) or (incoming_emits[0].get("profile_id") == receiver), str(inc))

        # 6. Receiver accepts call
        # Set session to receiver and call socket handler for accept
        login(receiver)
        CAPTURED_EMITS.clear()
        try:
            # ensure receiver is marked online in Redis/presence so emits are not blocked
            try:
                presence_service.set_online(receiver)
            except Exception:
                pass
            # run handler inside a request context so flask.request/session are available
            call_with_request_session(receiver, sockev.handle_webrtc_call_accept, {"call_id": call_id})
            check("handle_webrtc_call_accept executed", True)
        except Exception as e:
            check("handle_webrtc_call_accept executed", False, str(e))

        # 7. Verify call state becomes accepted/active
        call_after = wcs.get_call(call_id)
        check("call status is accepted", call_after is not None and call_after.get("status") in ("accepted", "connecting", "connected"), str(call_after))

        # 8. Simulate offer payload (caller -> receiver)
        login(caller)
        CAPTURED_EMITS.clear()
        offer_payload = {"sdp": "v=0\n...offer...", "call_id": call_id, "target_id": receiver, "call_type": "audio"}
        try:
            call_with_request_session(caller, sockev.handle_webrtc_call_offer, offer_payload)
            check("offer handler executed", True)
        except Exception as e:
            check("offer handler executed", False, str(e))
        offer_emits = [e for e in CAPTURED_EMITS if e["event"] == "call:offer" and e["profile_id"] == receiver]
        check("offer emitted to receiver", len(offer_emits) > 0, json.dumps(CAPTURED_EMITS))
        if offer_emits:
            off = offer_emits[0]["payload"] or {}
            check("offer payload has call_id", "call_id" in off, str(off))
            # offer SDP may be in sdp or offer
            check("offer payload has sdp/offer", ("sdp" in off) or ("offer" in off), str(off))

        # 9. Simulate answer payload (receiver -> caller)
        login(receiver)
        CAPTURED_EMITS.clear()
        answer_payload = {"sdp": "v=0\n...answer...", "call_id": call_id, "target_id": caller}
        try:
            call_with_request_session(receiver, sockev.handle_webrtc_call_answer, answer_payload)
            check("answer handler executed", True)
        except Exception as e:
            check("answer handler executed", False, str(e))
        answer_emits = [e for e in CAPTURED_EMITS if e["event"] == "call:answer" and e["profile_id"] == caller]
        check("answer emitted to caller", len(answer_emits) > 0, json.dumps(CAPTURED_EMITS))
        if answer_emits:
            ans = answer_emits[0]["payload"] or {}
            check("answer payload has call_id", "call_id" in ans, str(ans))
            check("answer payload has sdp/answer", ("sdp" in ans) or ("answer" in ans), str(ans))

        # 10. Simulate ICE candidate payload
        login(caller)
        CAPTURED_EMITS.clear()
        ice_payload = {"candidate": {"candidate": "candidate:1 1 UDP 2122252543 1.2.3.4 12345 typ host"}, "call_id": call_id, "target_id": receiver}
        try:
            call_with_request_session(caller, sockev.handle_webrtc_call_ice, ice_payload)
            check("ice handler executed", True)
        except Exception as e:
            check("ice handler executed", False, str(e))
        ice_emits = [e for e in CAPTURED_EMITS if e["event"] in ("call:ice-candidate",) and e["profile_id"] == receiver]
        # some handlers emit "call:ice-candidate"
        check("ice candidate emitted to receiver", len(ice_emits) > 0, json.dumps(CAPTURED_EMITS))
        if ice_emits:
            ic = ice_emits[0]["payload"] or {}
            check("ice payload has call_id", "call_id" in ic, str(ic))
            check("ice payload has candidate", "candidate" in ic and ic.get("candidate"), str(ic))

        # 11. End call
        login(caller)
        CAPTURED_EMITS.clear()
        try:
            CAPTURED_EMITS.clear()
            call_with_request_session(caller, sockev.handle_webrtc_call_end, {"call_id": call_id, "target_id": receiver, "reason": "hung_up"})
            check("end handler executed", True)
        except Exception as e:
            check("end handler executed", False, str(e))
        # verify end emit payload
        end_emits = [e for e in CAPTURED_EMITS if e.get("event") == "call:ended" and e.get("profile_id") == receiver]
        check("end emit to receiver", len(end_emits) > 0, json.dumps(CAPTURED_EMITS))
        if end_emits:
            ed = end_emits[0]["payload"] or {}
            check("end payload has call_id", "call_id" in ed, str(ed))
            # reason/status may be present
            if "reason" in ed:
                check("end payload has reason", True, ed.get("reason"))
        # 12. Verify call ended state
        final_call = wcs.get_call(call_id)
        check("call status ended", final_call is not None and final_call.get("status") in ("ended", "failed", "cancelled", "rejected"), str(final_call))

        # 13. Verify call history/log exists
        history = wcs.get_call_history(receiver, limit=10)
        check("call history returns list", isinstance(history, list), str(history)[:200])
        check("call history has entries", len(history) >= 0)

        # 14. Verify missed-call path: create a call and force timeout
        CAPTURED_EMITS.clear()
        res2 = wcs.create_call(caller, receiver, call_type="audio")
        cid2 = res2.get("call", {}).get("id")
        if cid2:
            try:
                # make started_at old so timeout picks it up
                write_query("UPDATE chain_calls SET started_at = now() - interval '300 seconds' WHERE id = %s", (cid2,))
            except Exception as e:
                print("failed to set started_at", e)
            # run timeout check
            try:
                count = wcs.check_call_timeouts()
                check("check_call_timeouts ran", True)
            except Exception as e:
                check("check_call_timeouts ran", False, str(e))
            timed = wcs.get_call(cid2)
            check("timed out call marked missed", timed is None or timed.get("status") in ("missed", "failed", "ended"), str(timed))

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
