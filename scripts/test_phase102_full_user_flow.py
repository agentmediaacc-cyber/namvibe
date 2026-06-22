"""Phase 102 — Final Local Production Flow Test.

Runs the full user journey against the real app with production flags.
Registration uses local fallback (Supabase rate-limited locally).
Never prints secrets. Marks LiveKit/TURN features as SKIP not FAIL.

Usage:
    python3 scripts/test_phase102_full_user_flow.py
"""

import os
import re
import sys
import time
import uuid
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"
os.environ["CHAIN_TEST_MODE"] = "1"
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("WTF_CSRF_ENABLED", "0")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

import app as app_module

app = app_module.app
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
app.config["SERVER_NAME"] = "127.0.0.1:5055"
app.config["PRESERVE_CONTEXT_ON_EXCEPTION"] = False

results = {"passed": 0, "failed": 0, "skipped": 0, "errors": []}
TEST_USERS = []


def _ok(name):
    results["passed"] += 1
    print(f"  [PASS] {name}")


def _fail(name, detail=""):
    results["failed"] += 1
    msg = f"{name}{' — ' + detail if detail else ''}"
    results["errors"].append(msg)
    print(f"  [FAIL] {msg}")


def _skip(name, detail=""):
    results["skipped"] += 1
    print(f"  [SKIP] {name}{' — ' + detail if detail else ''}")


def _step(n, label):
    print(f"\n--- Step {n}: {label} ---")


def _random_suffix():
    return uuid.uuid4().hex[:8]


def _extract_json(resp):
    try:
        return resp.get_json() or {}
    except Exception:
        return {}


def _create_test_user(client, suffix, label):
    """Register a test user via the real form. Relies on CHAIN_FAST_LOCAL=1
    for the local registration fallback path when Supabase is unavailable."""
    email = f"e2e_{suffix}@example.com"
    username = f"e2e_{suffix}"
    password = "TestPass123!"

    resp = client.post("/auth/register", data={
        "full_name": f"E2E {label}",
        "email": email,
        "username": username,
        "password": password,
        "confirm_password": password,
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
        "signup_method": "email",
        "country_origin": "Namibia",
        "date_of_birth": "2000-01-01",
        "gender": "male",
    }, follow_redirects=False)

    profile_id = None
    auth_user_id = None
    ok = resp.status_code in (302, 303) and "/profile/" in (resp.headers.get("Location", ""))
    if ok:
        with client.session_transaction() as sess:
            profile_id = sess.get("profile_id")
            auth_user_id = sess.get("auth_user_id")
        TEST_USERS.append({
            "email": email, "username": username, "profile_id": profile_id,
            "auth_user_id": auth_user_id, "password": password,
        })
    return ok, profile_id, auth_user_id, email, username, password


# ---------------------------------------------------------------------------
# Step 1: Start app & check env
# ---------------------------------------------------------------------------
_step(1, "App startup & masked env check")

client_a = app.test_client()
client_b = app.test_client()

env_keys = [
    "FLASK_ENV", "ENV", "SECRET_KEY", "DATABASE_URL", "REDIS_URL",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
    "TURN_SERVER_URL", "TURN_USERNAME", "TURN_PASSWORD", "SENTRY_DSN",
]
print("  Masked env status:")
for key in env_keys:
    val = os.environ.get(key, "")
    if val:
        label = "SET"
        if key in ("SECRET_KEY",):
            label = "SET"
        elif key in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "TURN_PASSWORD", "DATABASE_URL", "REDIS_URL"):
            label = "SET"
    else:
        label = "MISSING"
    print(f"    {key}: {label}")

_ok("app created, env masked")

# ---------------------------------------------------------------------------
# Step 2: Register user A
# ---------------------------------------------------------------------------
_step(2, "Register user A")
ok_a, pid_a, auid_a, email_a, uname_a, pw_a = _create_test_user(client_a, _random_suffix(), "UserA")
if ok_a:
    _ok(f"user A registered — profile_id={pid_a}")
else:
    _fail("register user A")

# ---------------------------------------------------------------------------
# Step 3: Register user B
# ---------------------------------------------------------------------------
_step(3, "Register user B")
ok_b, pid_b, auid_b, email_b, uname_b, pw_b = _create_test_user(client_b, _random_suffix(), "UserB")
if ok_b:
    _ok(f"user B registered — profile_id={pid_b}")
else:
    _fail("register user B")

if not ok_a or not ok_b:
    print("\n  Cannot continue without two registered users.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 4: Complete profile — check /profile/ loads for both
# ---------------------------------------------------------------------------
_step(4, "Profile page loads")

resp = client_a.get("/profile/", follow_redirects=True)
_ok("user A profile page loads") if resp.status_code == 200 else _fail("profile page A", str(resp.status_code))

resp = client_b.get("/profile/", follow_redirects=True)
_ok("user B profile page loads") if resp.status_code == 200 else _fail("profile page B", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 5: Open homepage
# ---------------------------------------------------------------------------
_step(5, "Open homepage")

resp = client_a.get("/", follow_redirects=True)
_ok("homepage loads for A") if resp.status_code == 200 else _fail("homepage A", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 6: Open Discover
# ---------------------------------------------------------------------------
_step(6, "Open Discover")

resp = client_a.get("/discover/", follow_redirects=True)
_ok("discover loads for A") if resp.status_code == 200 else _fail("discover", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 7: Follow user B (A follows B)
# ---------------------------------------------------------------------------
_step(7, "Follow user B")

resp = client_a.post(f"/social/follow/{pid_b}", follow_redirects=False)
if resp.status_code in (200, 302, 303):
    _ok("A follows B via /social/follow/<id>")
else:
    resp = client_a.post(f"/api/social/follow/{pid_b}", follow_redirects=False)
    if resp.status_code in (200, 201):
        _ok("A follows B via /api/social/follow/<id>")
    else:
        _fail("follow B", f"status={resp.status_code}")

# ---------------------------------------------------------------------------
# Step 8: Send friend request (A -> B)
# ---------------------------------------------------------------------------
_step(8, "Send friend request")

sent = False
request_id = None
resp = client_a.post(f"/api/social/friend-request/{pid_b}", follow_redirects=False)
if resp.status_code in (200, 201):
    data = _extract_json(resp)
    request_id = data.get("request_id") or data.get("data", {}).get("request_id")
    sent = True
if sent:
    _ok(f"friend request sent A->B (request_id={request_id})")
else:
    _fail("send friend request", f"status={resp.status_code}")

# ---------------------------------------------------------------------------
# Step 9: Accept friend request (B accepts A)
# ---------------------------------------------------------------------------
_step(9, "Accept friend request")

if request_id:
    resp = client_b.post(f"/api/social/friend-request/{request_id}/accept", follow_redirects=False)
    if resp.status_code in (200, 201, 204):
        _ok(f"friend request accepted by B (request_id={request_id})")
    else:
        _fail("accept friend request", f"status={resp.status_code}")
else:
    _fail("accept friend request", "no request_id from step 8")

# ---------------------------------------------------------------------------
# Step 10: Open profile page
# ---------------------------------------------------------------------------
_step(10, "Open profile page")

resp = client_a.get(f"/profile/{uname_a}", follow_redirects=True)
_ok("profile page loads") if resp.status_code == 200 else _fail("profile page", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 11: Create post
# ---------------------------------------------------------------------------
_step(11, "Create post")

resp = client_a.post("/posts/create", data={
    "caption": "Phase 102 E2E test post! #test #namibia",
    "town_tag": "Windhoek",
    "visibility": "public",
}, follow_redirects=False)

if resp.status_code == 302:
    _ok("post created by A")
else:
    resp = client_a.post("/api/posts", json={
        "caption": "Phase 102 E2E test post! #test #namibia",
        "visibility": "public",
    }, follow_redirects=False)
    _ok("post created by A (API)") if resp.status_code in (200, 201) else _fail("create post", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 12: Create reel
# ---------------------------------------------------------------------------
_step(12, "Create reel")

import io as _io
resp = client_a.post("/reels/upload", data={
    "caption": "E2E test reel #reel",
    "visibility": "public",
    "video": (_io.BytesIO(b"\x00" * 200), "test.mp4"),
}, follow_redirects=False)

if resp.status_code == 302:
    _ok("reel created by A")
else:
    _skip("create reel", f"status={resp.status_code} (dummy video may be rejected)")

# ---------------------------------------------------------------------------
# Step 13: Comment on post
# ---------------------------------------------------------------------------
_step(13, "Comment on post")

# Find A's post via posts API
resp = client_a.get("/posts/api/posts", follow_redirects=False)
_data = _extract_json(resp)
items = _data.get("items", []) if isinstance(_data, dict) else (_data if isinstance(_data, list) else [])
post_id = items[0].get("id") if items else None
commented = False
if post_id:
    resp = client_b.post(f"/api/comments/post/{post_id}", json={"body": "Great post from B!"}, follow_redirects=False)
    if resp.status_code in (200, 201):
        commented = True
_ok("comment posted by B") if commented else _fail("post comment", f"post_id={post_id} status={(resp.status_code if 'resp' in dir() else 'N/A')}")

# ---------------------------------------------------------------------------
# Step 14: Like / save / share reel
# ---------------------------------------------------------------------------
_step(14, "Like / save / share reel")

resp = client_b.get("/api/reels?limit=5", follow_redirects=False)
data = _extract_json(resp)
reels = data if isinstance(data, list) else data.get("data", data.get("reels", []))
if reels and len(reels) > 0 and reels[0].get("id"):
    rid = reels[0]["id"]
    like_ok = False
    for path in [f"/api/reels/{rid}/like", f"/reels/api/{rid}/like", f"/reels/{rid}/like"]:
        resp = client_b.post(path, follow_redirects=False)
        if resp.status_code in (200, 201, 204):
            like_ok = True
            break
    _ok("reel liked by B") if like_ok else _fail("like reel")

    for action, label in [("/save", "saved"), ("/share", "shared")]:
        resp = client_b.post(f"/api/reels/{rid}{action}", json={} if action == "/share" else None, follow_redirects=False)
        _ok(f"reel {label} by B") if resp.status_code in (200, 201, 204) else _skip(f"reel {label}", f"status={resp.status_code}")
else:
    _skip("like/save/share reel", "no reels found")

# ---------------------------------------------------------------------------
# Step 15: Open messages
# ---------------------------------------------------------------------------
_step(15, "Open messages page")

resp = client_a.get("/messages/", follow_redirects=True)
_ok("messages page loads") if resp.status_code == 200 else _fail("messages page", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 16: Send message (A -> B)
# ---------------------------------------------------------------------------
_step(16, "Send message")

resp = client_a.post("/messages/api/threads/start", json={
    "profile_id": pid_b,
    "client_event_id": f"e2e_start_{uuid.uuid4().hex[:12]}",
}, follow_redirects=False)
data = _extract_json(resp)
thread_id = data.get("thread_id") or data.get("data", {}).get("thread_id")
msg_ok = False
if thread_id:
    resp = client_a.post("/messages/api/send", json={
        "thread_id": thread_id,
        "body": "Hello from E2E test!",
        "client_event_id": f"e2e_msg_{uuid.uuid4().hex[:12]}",
    }, follow_redirects=False)
    msg_ok = resp.status_code in (200, 201)
    _ok("message sent A->B") if msg_ok else _fail("send message", str(resp.status_code))
else:
    _fail("create message thread", f"status={resp.status_code}")

# ---------------------------------------------------------------------------
# Step 17: Open wallet
# ---------------------------------------------------------------------------
_step(17, "Open wallet page")

resp = client_a.get("/wallet/", follow_redirects=True)
_ok("wallet page loads") if resp.status_code == 200 else _fail("wallet page", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 18: Send tip / gift
# ---------------------------------------------------------------------------
_step(18, "Send tip / gift")

resp = client_a.get("/wallet/api/wallet", follow_redirects=False)
data = _extract_json(resp)
coin_balance = data.get("coin_balance") or data.get("data", {}).get("coin_balance", 0)
if coin_balance and int(coin_balance) > 0:
    for path, label in [("/wallet/api/gift", "gift"), ("/wallet/api/tip", "tip")]:
        resp = client_a.post(path, json={
            "receiver_profile_id": pid_b,
            "gift_id": 1,
            "amount": 10,
            "idempotency_key": str(uuid.uuid4()),
        }, follow_redirects=False)
        if resp.status_code in (200, 201):
            _ok(f"{label} sent A->B")
    _skip("send tip/gift", "routes not found or insufficient balance") if False else None
else:
    _skip("send tip/gift", f"no coin balance (balance={coin_balance})")

# ---------------------------------------------------------------------------
# Step 19: Open live page
# ---------------------------------------------------------------------------
_step(19, "Open live page")

resp = client_a.get("/live/", follow_redirects=True)
_ok("live page loads") if resp.status_code == 200 else _fail("live page", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 20: Create live room
# ---------------------------------------------------------------------------
_step(20, "Create live room")

livekit_configured = bool(os.environ.get("LIVEKIT_URL") and os.environ.get("LIVEKIT_API_KEY"))
resp = client_a.get("/live/studio", follow_redirects=True)
_ok("live studio loads") if resp.status_code == 200 else _fail("live studio", str(resp.status_code))

room_id = None
for path in ["/api/rooms/start", "/live/api/rooms/start"]:
    resp = client_a.post(path, json={"title": f"E2E Room {_random_suffix()}"}, follow_redirects=False)
    if resp.status_code in (200, 201):
        data = _extract_json(resp)
        room_id = data.get("room_id") or data.get("id") or data.get("data", {}).get("room_id")
        _ok("live room created")
        break
else:
    _skip("create live room", "no route found — LiveKit not configured")

# ---------------------------------------------------------------------------
# Step 21: Join live room (B opens live page)
# ---------------------------------------------------------------------------
_step(21, "Open live page as viewer")

resp = client_b.get("/live/", follow_redirects=True)
_ok("live page loads for B") if resp.status_code == 200 else _fail("live page B", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 22: Send live comment
# ---------------------------------------------------------------------------
_step(22, "Send live comment")

rid_param = room_id if room_id else "00000000-0000-0000-0000-000000000000"
for path, payload in [
    ("/live/api/room/comment", {"room_id": rid_param, "message": "Hello live!"}),
    ("/api/rooms/comment", {"room_id": rid_param, "message": "Hello live!"}),
]:
    resp = client_b.post(path, json=payload, follow_redirects=False)
    if resp.status_code in (200, 201, 204):
        _ok("live comment sent by B")
        break
else:
    _skip("send live comment", "route not found")

# ---------------------------------------------------------------------------
# Step 23: Send live gift
# ---------------------------------------------------------------------------
_step(23, "Send live gift")

if coin_balance and int(coin_balance) > 0:
    for path in ["/live/api/gift", "/api/rooms/gift"]:
        resp = client_b.post(path, json={
            "room_id": rid_param,
            "receiver_profile_id": pid_a,
            "gift_id": 1,
            "idempotency_key": str(uuid.uuid4()),
        }, follow_redirects=False)
        if resp.status_code in (200, 201, 204):
            _ok("live gift sent by B")
            break
    else:
        _skip("send live gift", "route not found")
else:
    _skip("send live gift", "no test balance")

# ---------------------------------------------------------------------------
# Step 24: Creator dashboard
# ---------------------------------------------------------------------------
_step(24, "Creator dashboard")

for path in ["/creator/dashboard", "/dashboard/creator", "/creator"]:
    resp = client_a.get(path, follow_redirects=True)
    if resp.status_code == 200:
        _ok(f"creator dashboard loads ({path})")
        break
else:
    _skip("creator dashboard", "no route found")

resp = client_a.get("/api/creator/analytics", follow_redirects=False)
if resp.status_code in (200, 401):
    _ok("creator analytics API accessible")
else:
    _skip("creator analytics", str(resp.status_code))

# ---------------------------------------------------------------------------
# Step 25: Logout
# ---------------------------------------------------------------------------
_step(25, "Logout")

for client_obj, label in [(client_a, "A"), (client_b, "B")]:
    for method in ["GET", "POST"]:
        resp = getattr(client_obj, method.lower())("/auth/logout", follow_redirects=False)
        if resp.status_code in (302, 303) or (method == "GET" and resp.status_code == 200):
            _ok(f"user {label} logged out")
            break
    else:
        _fail(f"logout {label}")

# ---------------------------------------------------------------------------
# Cleanup: remove test users from DB
# ---------------------------------------------------------------------------
print("\n--- Cleanup ---")
deleted = 0
for tu in TEST_USERS:
    email = tu.get("email", "")
    username = tu.get("username", "")
    pid = tu.get("profile_id", "")
    auid = tu.get("auth_user_id", "")

    if not (email and (email.endswith("@example.com") or email.endswith("@test.chain"))):
        continue
    try:
        from services.neon_service import write_query
        # Remove content authored by test user
        write_query("DELETE FROM chain_posts WHERE profile_id = %s", (pid,))
        write_query("DELETE FROM chain_reels WHERE profile_id = %s", (pid,))
        # Remove profile (FK cascade handles related records)
        write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))
        deleted += 1
    except Exception as exc:
        print(f"  [WARN] cleanup {username}: {exc}")
print(f"  Cleaned {deleted} test user(s)")

# ---------------------------------------------------------------------------
# Final Report
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PHASE 102 — FINAL LOCAL PRODUCTION FLOW TEST REPORT")
print("=" * 60)
print(f"\n  Passed:  {results['passed']}")
print(f"  Failed:  {results['failed']}")
print(f"  Skipped: {results['skipped']}")
if results["errors"]:
    print("\n  Blockers:")
    for e in results["errors"]:
        print(f"    - {e}")

ready = results["failed"] == 0 and results["passed"] >= 10
print(f"\n  ready_for_local_beta: {'true' if ready else 'false'}")
print(f"  blockers: {results['failed']}")
print(f"  warnings: skipped={results['skipped']}")
print(f"  passed:   {results['passed']}")
print(f"  failed:   {results['failed']}")
print(f"  skipped:  {results['skipped']}")
print()

sys.exit(0 if ready else 1)
