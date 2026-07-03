#!/usr/bin/env python3
"""
NAM VIBE FULL SOCIAL E2E — Profile · Messaging · Groups · Calls · Notifications
"""
import os, sys, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["FLASK_ENV"] = "development"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"

from app import app as flask_app
from services.neon_service import fast_query, write_query
from services.messaging_engine import get_or_create_direct_thread

app = flask_app

USER_A = "622b8aaf-8a0c-49e3-b7ac-3901d40cded6"
USER_B = "40e42995-999e-403d-9a35-fc8b2cc7096f"

PASS = 0; FAIL = 0; WARN = 0

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

print("\n" + "=" * 72)
print("NAM VIBE FULL SOCIAL E2E")
print("=" * 72)

with app.test_client() as c:
    login(c, USER_A, "5c6b5b7f-5b56-4db5-a86a-14a99557beb5")
    csrf, homepage_resp = get_csrf(c)
    check("CSRF token", bool(csrf))
    check("homepage 200", homepage_resp.status_code == 200)

    # === STEP 1: Accept friend request (B -> A) ===
    print("\n--- STEP 1: Accept friend request (B->A) ---")
    fr = fast_query(
        "SELECT id FROM chain_friend_requests WHERE recipient_profile_id = %s AND status = 'pending'",
        (USER_A,), default=[]
    )
    if fr:
        req_id = fr[0]["id"]
        ar = c.post(f"/api/social/friend-request/{req_id}/accept", headers={"X-CSRFToken": csrf})
        ad = ar.get_json() or {}
        check("accept 200", ar.status_code == 200)
        check("state=friends", ad.get("state") == "friends", str(ad))
    else:
        check("already friends", True, "no pending request (already accepted)")

    nf = fast_query(
        "SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type IN ('friend_request_accepted','friend_accepted')",
        (USER_B,), default=[]
    )
    check("friend_accepted notif for B", len(nf) > 0)

    # === STEP 2: Profile ===
    print("\n--- STEP 2: Profile page ---")
    pr = c.get("/profile/")
    check("profile 200", pr.status_code == 200, str(pr.status_code))
    ph = pr.data.decode()
    check("profile has reels", 'reel' in ph.lower() or 'film' in ph.lower())
    check("profile bell icon", 'bell' in ph.lower() or 'notif' in ph.lower())
    check("profile display name", 'nv-display-name' in ph)
    check("profile stats", 'nv-stats' in ph)
    check("profile tabs", 'nv-tabs' in ph or 'data-tab' in ph)
    check("profile message btn", 'data-action="message"' in ph or 'Message' in ph)

    # === STEP 3: Reels in DB ===
    print("\n--- STEP 3: Reels from User A ---")
    reels = fast_query(
        "SELECT id FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 5",
        (USER_A,), default=[]
    )
    check("User A has reels", len(reels) > 0)
    rid = reels[0]["id"] if reels else None

    if rid:
        rr = c.get(f"/reels/{rid}")
        check("reel detail viewable", rr.status_code in (200, 302), str(rr.status_code))

    # === STEP 4: Message A->B ===
    print("\n--- STEP 4: Send message A->B ---")
    tid = get_or_create_direct_thread(USER_A, USER_B)
    check("direct thread", bool(tid), f"tid={tid}")

    body = f"Hello Beta! msg {int(time.time())}"
    sr = c.post("/messages/api/messages/send",
                json={"thread_id": tid, "body": body},
                headers={"X-CSRFToken": csrf})
    sd = sr.get_json() or {}
    check("send 200", sr.status_code == 200, str(sr.status_code))
    check("send success", sd.get("success") is True, str(sd))
    mid = sd.get("message_id") or sd.get("id")
    check("message_id", bool(mid))

    # Verify via API response
    msg_obj = sd.get("message", {})
    check("body matches API", msg_obj.get("body") == body, f"got {str(msg_obj.get('body',''))[:50]}")

    # === STEP 5: Seen & typing ===
    print("\n--- STEP 5: Seen & typing ---")
    seen_r = c.post(f"/messages/api/messages/{tid}/seen", headers={"X-CSRFToken": csrf})
    check("seen 200", seen_r.status_code == 200, str(seen_r.status_code))

    typing_r = c.post(f"/messages/messages/typing/{tid}", json={"typing": True}, headers={"X-CSRFToken": csrf})
    check("typing 200", typing_r.status_code == 200, str(typing_r.status_code))

    # === STEP 6: Public group ===
    print("\n--- STEP 6: Public group creation ---")
    gname = f"NamVibe Community {int(time.time())}"
    gr = c.post("/messages/api/group/create",
                json={"name": gname, "visibility": "public"},
                headers={"X-CSRFToken": csrf})
    gd = gr.get_json() or {}
    check("group 201", gr.status_code == 201, str(gr.status_code))
    check("group created", bool(gd.get("group")))
    gid = gd.get("group", {}).get("id") if gd.get("group") else (gd.get("group_id") or gd.get("thread_id"))
    check("group_id", bool(gid), f"got {gid}")

    # === STEP 7: B joins group ===
    print("\n--- STEP 7: B joins group ---")
    login(c, USER_B, "05667e0d-e2a2-40bb-a80b-1ed9f6e22fed")
    csrf_b, _ = get_csrf(c)

    jr = c.post(f"/messages/api/groups/{gid}/join", headers={"X-CSRFToken": csrf_b})
    jd = jr.get_json() or {}
    check("join 200", jr.status_code == 200, str(jr.status_code))
    check("join success", jd.get("success") or jd.get("ok"), str(jd))

    # B posts in group
    pr2 = c.post(f"/messages/api/groups/{gid}/post",
                 json={"body": f"I joined! {int(time.time())}"},
                 headers={"X-CSRFToken": csrf_b})
    check("group post", pr2.status_code in (200, 201), str(pr2.status_code))

    # === STEP 8: Unread ===
    print("\n--- STEP 8: Unread counts ---")
    ur = c.get("/api/notifications/unread-count")
    ud = ur.get_json() or {}
    check("unread 200", ur.status_code == 200)
    check("unread has count", "count" in ud or "unread_count" in ud)

    # === STEP 9: Call A->B ===
    print("\n--- STEP 9: Calling ---")
    login(c, USER_A, "5c6b5b7f-5b56-4db5-a86a-14a99557beb5")
    csrf_a, _ = get_csrf(c)
    cr = c.post("/calls/api/start",
                json={"receiver_id": USER_B, "call_type": "audio"},
                headers={"X-CSRFToken": csrf_a})
    cd = cr.get_json() or {}
    check("call 200", cr.status_code in (200, 201), f"got {cr.status_code}: {cd}")
    check("call created", cd.get("success") or cd.get("ok") or bool(cd.get("call")), str(cd))

    # === STEP 10: B replies ===
    print("\n--- STEP 10: B replies ---")
    login(c, USER_B, "05667e0d-e2a2-40bb-a80b-1ed9f6e22fed")
    csrf_b2, _ = get_csrf(c)
    reply_body = f"Hey Alpha! Got it! {int(time.time())}"
    rr2 = c.post("/messages/api/messages/send",
                 json={"thread_id": tid, "body": reply_body},
                 headers={"X-CSRFToken": csrf_b2})
    rd = rr2.get_json() or {}
    check("reply 200", rr2.status_code == 200, str(rr2.status_code))
    check("reply success", rd.get("success") is True, str(rd))

print("\n" + "=" * 72)
print(f"RESULTS:  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}  TOTAL: {PASS + FAIL + WARN}")
if FAIL == 0:
    print("OUTCOME: ALL PASS")
else:
    print(f"OUTCOME: {FAIL} FAILURE(S)")
print("=" * 72)
raise SystemExit(0 if FAIL == 0 else 1)
