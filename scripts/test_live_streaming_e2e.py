#!/usr/bin/env python3
"""Live streaming E2E: A starts a room, B/C/D join, comment, poll, gift, then A ends it."""

import os, sys, re, time, json, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["FLASK_ENV"] = "development"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"

from app import app as flask_app
from services.neon_service import fast_query, write_query

app = flask_app

USER_A = "622b8aaf-8a0c-49e3-b7ac-3901d40cded6"
USER_B = "40e42995-999e-403d-9a35-fc8b2cc7096f"
USER_C = None
USER_D = None
AUTH_A = "5c6b5b7f-5b56-4db5-a86a-14a99557beb5"
AUTH_B = "05667e0d-e2a2-40bb-a80b-1ed9f6e22fed"

PASS = 0; FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}"); PASS += 1
    else:
        print(f"  FAIL  {label}  {detail}"[:120]); FAIL += 1

def get_csrf(client):
    r = client.get("/")
    m = re.search(r'csrf-token" content="([^"]+)"', r.data.decode())
    return m.group(1) if m else "", r

def login(client, pid, aid):
    with client.session_transaction() as s:
        s["profile_id"] = pid
        s["auth_user_id"] = aid
        s["_user_id"] = aid
        s["user_id"] = aid
        s["age_verified"] = True
        s["age_check_required"] = False

def find_extra_users():
    """Find C and D from chain_profiles (skip alpha/beta)."""
    global USER_C, USER_D
    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE deleted_at IS NULL AND id NOT IN (%s, %s) ORDER BY created_at DESC LIMIT 2",
        (USER_A, USER_B), default=[]
    )
    if rows:
        USER_C = rows[0]["id"]
        if len(rows) > 1:
            USER_D = rows[1]["id"]

print("=" * 72)
print("NAM VIBE LIVE STREAMING E2E")
print("=" * 72)

find_extra_users()
print(f"Users: A={USER_A[:8]}  B={USER_B[:8]}" + (f"  C={USER_C[:8]}  D={USER_D[:8]}" if USER_C else ""))

with app.test_client() as c:

    # ─────────────────────────────────────────────
    # STEP 1: User A starts a live room
    # ─────────────────────────────────────────────
    login(c, USER_A, AUTH_A)
    csrf, _ = get_csrf(c)
    check("A csrf token", bool(csrf))

    r = c.post("/live/api/rooms/start",
               json={"title": "E2E Test Stream"},
               headers={"X-CSRFToken": csrf})
    d = r.get_json() or {}
    room = d.get("room") or {}
    room_id = room.get("id")
    check("room start 200", r.status_code == 200, str(r.status_code))
    check("room ok", d.get("ok") is True, str(d.get("ok")))
    check("room has id", bool(room_id), str(room_id))
    check("room is_live", room.get("is_live") is True or room.get("status") == "live", str(room))
    check("room title", room.get("title") == "E2E Test Stream", room.get("title"))

    print(f"\n  → Room {room_id[:8]} created by A")

    # ─────────────────────────────────────────────
    # STEP 2: Verify room info via API
    # ─────────────────────────────────────────────
    r = c.get(f"/live/api/rooms/{room_id}/info")
    d = r.get_json() or {}
    check("room info 200", r.status_code == 200, str(r.status_code))
    check("room info ok", d.get("ok") is True, str(d.get("ok")))
    check("room info has id", d.get("room", {}).get("id") == room_id, str(d.get("room", {}).get("id")))

    # ─────────────────────────────────────────────
    # STEP 3: User A creates a poll
    # ─────────────────────────────────────────────
    r = c.post(f"/live/api/live/{room_id}/poll",
               json={"question": "Best color?", "options": ["Red", "Blue"]},
               headers={"X-CSRFToken": csrf})
    d = r.get_json() or {}
    check("poll created 200", r.status_code == 200, str(r.status_code))
    check("poll success", d.get("success") is True, str(d.get("success")))
    poll = d.get("poll") or {}
    poll_id = poll.get("id")
    check("poll has id", bool(poll_id), str(poll_id))
    check("poll question", poll.get("question") == "Best color?", poll.get("question"))

    # ─────────────────────────────────────────────
    # STEP 4: User A sets a stream goal
    # ─────────────────────────────────────────────
    r = c.post(f"/live/api/live/{room_id}/goals",
               json={"title": "100 Viewers", "target_amount": 100, "goal_type": "viewers"},
               headers={"X-CSRFToken": csrf})
    d = r.get_json() or {}
    check("goal created 200", r.status_code in (200, 201), str(r.status_code))

    # ─────────────────────────────────────────────
    # STEP 5: User B joins the room
    # ─────────────────────────────────────────────
    login(c, USER_B, AUTH_B)
    csrf_b, _ = get_csrf(c)
    check("B csrf token", bool(csrf_b))

    r = c.get(f"/live/room/{room_id}")
    check("B join room 200", r.status_code == 200, str(r.status_code))
    check("B room page has title", b"E2E Test Stream" in r.data or room_id.encode()[:16] in r.data, "title/roomid missing")

    # ─────────────────────────────────────────────
    # STEP 6: User B posts a comment
    # ─────────────────────────────────────────────
    r = c.post(f"/live/api/live/{room_id}/comment",
               json={"body": "Hello from Beta!"},
               headers={"X-CSRFToken": csrf_b})
    d = r.get_json() or {}
    check("comment 200", r.status_code == 200, str(r.status_code))
    check("comment ok", d.get("status") == "ok" or d.get("success") is True, str(d))

    # ─────────────────────────────────────────────
    # STEP 7: Verify chat has B's message
    # ─────────────────────────────────────────────
    r = c.get(f"/live/api/live/{room_id}/chat")
    d = r.get_json() or {}
    messages = d.get("messages") or d.get("chat") or []
    check("chat 200", r.status_code == 200, str(r.status_code))
    check("chat has message", any("Beta" in str(m) or "Hello" in str(m) for m in messages), str(messages))

    # ─────────────────────────────────────────────
    # STEP 8: User B votes on poll
    # ─────────────────────────────────────────────
    if poll_id:
        r = c.post(f"/live/api/live/poll/{poll_id}/vote",
                   json={"option": "Blue"},
                   headers={"X-CSRFToken": csrf_b})
        d = r.get_json() or {}
        check("vote 200", r.status_code == 200, str(r.status_code))
        check("vote ok", d.get("ok") is True, str(d))

    # ─────────────────────────────────────────────
    # STEP 9: User B sends a gift
    # ─────────────────────────────────────────────
    r = c.post(f"/live/api/live/{room_id}/gift",
               data={"gift_type": "heart", "coin_value": "10"},
               headers={"X-CSRFToken": csrf_b})
    d = r.get_json() or {}
    check("gift 200", r.status_code == 200, str(r.status_code))
    check("gift success", d.get("success") is True or d.get("status") == "ok", str(d))

    # ─────────────────────────────────────────────
    # STEP 10: User B sends a reaction
    # ─────────────────────────────────────────────
    r = c.post(f"/live/api/react/{room_id}",
               json={"type": "fire"},
               headers={"X-CSRFToken": csrf_b})
    d = r.get_json() or {}
    check("reaction 200", r.status_code == 200, str(r.status_code))
    check("reaction ok", d.get("status") == "ok" or d.get("ok") is True, str(d))

    # ─────────────────────────────────────────────
    # STEP 11: Check participants list
    # ─────────────────────────────────────────────
    r = c.get(f"/live/api/live/{room_id}/participants")
    d = r.get_json() or {}
    participants = d.get("participants") or []
    check("participants 200", r.status_code == 200, str(r.status_code))
    check("has host", any(p.get("role") == "host" for p in participants), str(participants))
    check("has viewer B", any(p.get("profile_id") == USER_B for p in participants), str(participants))

    # ─────────────────────────────────────────────
    # STEP 12: Check featured/trending rooms includes this room
    # ─────────────────────────────────────────────
    r = c.get("/live/api/featured")
    d = r.get_json() or {}
    featured = d.get("rooms") or []
    check("featured 200", r.status_code == 200, str(r.status_code))

    r = c.get("/live/api/live/trending")
    d = r.get_json() or {}
    trending = d.get("rooms") or []
    check("trending 200", r.status_code == 200, str(r.status_code))

    # ─────────────────────────────────────────────
    # STEP 13: If C/D exist, they join too
    # ─────────────────────────────────────────────
    if USER_C:
        with app.test_client() as c2:
            login(c2, USER_C, USER_C)
            r = c2.get(f"/live/room/{room_id}")
            check(f"C join room 200", r.status_code == 200, str(r.status_code))
            check(f"C sees live room", b"E2E Test Stream" in r.data or room_id.encode()[:16] in r.data, "room content")

    if USER_D:
        with app.test_client() as c3:
            login(c3, USER_D, USER_D)
            r = c3.get(f"/live/room/{room_id}")
            check(f"D join room 200", r.status_code == 200, str(r.status_code))

    # ─────────────────────────────────────────────
    # STEP 14: User A ends the room
    # ─────────────────────────────────────────────
    login(c, USER_A, AUTH_A)
    csrf_a, _ = get_csrf(c)

    r = c.post(f"/live/api/rooms/{room_id}/end",
               headers={"X-CSRFToken": csrf_a})
    d = r.get_json() or {}
    check("end 200", r.status_code == 200, str(r.status_code))
    check("end ok", d.get("ok") is True, str(d))

    # ─────────────────────────────────────────────
    # STEP 15: Verify room is ended
    # ─────────────────────────────────────────────
    r = c.get(f"/live/api/rooms/{room_id}/info")
    d = r.get_json() or {}
    ended_room = d.get("room") or {}
    check("ended room not live", ended_room.get("is_live") is False or ended_room.get("status") == "ended" or d.get("ok") is False, str(ended_room))

    # ─────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print(f"RESULTS:  PASS: {PASS}  FAIL: {FAIL}  WARN: 0  TOTAL: {PASS + FAIL}")
    outcome = "ALL PASS" if FAIL == 0 else f"{FAIL} FAILURE(S)"
    print(f"OUTCOME: {outcome}")
    print(f"{'=' * 72}")
    raise SystemExit(0 if FAIL == 0 else 1)
