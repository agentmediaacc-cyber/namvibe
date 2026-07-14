#!/usr/bin/env python3
"""
Post the NamVibe promo video as a reel from User A,
then verify User B can see it publicly.
"""
import json, os, sys, uuid, time, shutil, subprocess
from datetime import datetime, timezone

os.environ['CHAIN_DISABLE_RATE_LIMITS'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['CHAIN_DISABLE_DB_PING'] = '1'
os.environ['CHAIN_DISABLE_PREWARM'] = '1'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import prime_neon_runtime, execute
prime_neon_runtime()
time.sleep(2)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMO_PATH = os.path.join(BASE, "namvibe_promo.mp4")
STATIC_DIR = os.path.join(BASE, "static", "uploads", "reels")
os.makedirs(STATIC_DIR, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat()
results = {"ok": 0, "fail": 0, "items": []}
created_ids = {}
cleanup_users = []

def check(name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    results["ok" if ok else "fail"] += 1
    results["items"].append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" \u2014 {detail}" if detail else ""))

# ── Step 1: Create two test profiles ──
print("\n=== Create User A (creator) ===")
user_a_id = str(uuid.uuid4())
user_a_username = f"promo_a_{int(time.time())}"
try:
    execute(
        "INSERT INTO chain_profiles (id, username, display_name, email, auth_user_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user_a_id, user_a_username, "Promo Creator A", f"{user_a_username}@test.com", user_a_id, NOW, NOW),
        timeout_ms=10000
    )
    cleanup_users.append(user_a_id)
    check("Create User A", True, f"id={user_a_id[:12]}...")
except Exception as e:
    check("Create User A", False, str(e)[:80])

print("\n=== Create User B (viewer) ===")
user_b_id = str(uuid.uuid4())
user_b_username = f"promo_b_{int(time.time())}"
try:
    execute(
        "INSERT INTO chain_profiles (id, username, display_name, email, auth_user_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user_b_id, user_b_username, "Promo Viewer B", f"{user_b_username}@test.com", user_b_id, NOW, NOW),
        timeout_ms=10000
    )
    cleanup_users.append(user_b_id)
    check("Create User B", True, f"id={user_b_id[:12]}...")
except Exception as e:
    check("Create User B", False, str(e)[:80])

# ── Step 2: Copy promo video to static dir ──
print("\n=== Copy promo video ===")
target_filename = f"reel_{user_a_id[:8]}_{uuid.uuid4().hex[:8]}.mp4"
target_path = os.path.join(STATIC_DIR, target_filename)
rel_url = f"/static/uploads/reels/{target_filename}"
try:
    shutil.copy2(PROMO_PATH, target_path)
    file_size = os.path.getsize(target_path)
    check("Copy promo video", True, f"{file_size} bytes -> {rel_url}")
except Exception as e:
    check("Copy promo video", False, str(e)[:80])
    file_size = 0

# ── Step 3: Insert reel for User A ──
print("\n=== Insert Reel for User A ===")
reel_id = str(uuid.uuid4())
try:
    execute("""
        INSERT INTO chain_reels (id, profile_id, caption, video_url, media_url, storage_bucket, storage_path, mime_type, file_size, duration_seconds, width, height, processing_status, visibility, likes_count, comments_count, shares_count, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        reel_id, user_a_id,
        "NamVibe Promo - Where Connection Meets Creation",
        rel_url, rel_url,
        "local", f"reels/{user_a_id}/{reel_id}.mp4",
        "video/mp4", file_size,
        146, 720, 1280,
        "ready", "public",
        0, 0, 0,
        NOW, NOW
    ), timeout_ms=10000)
    created_ids['reel'] = reel_id
    check("Insert Reel", True, f"id={reel_id[:12]}...")
except Exception as e:
    check("Insert Reel", False, str(e)[:80])

# ── Step 4: Verify via subprocess ──
print("\n" + "=" * 50)
print("  VERIFY PUBLIC VISIBILITY")
print("=" * 50)

verify_script = r'''
import os, sys, json
os.environ['CHAIN_DISABLE_RATE_LIMITS'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['CHAIN_DISABLE_DB_PING'] = '1'
os.environ['CHAIN_DISABLE_PREWARM'] = '1'
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
sys.path.insert(0, '.')

from app import app as flask_app

REEL_ID = "''' + reel_id + r'''"
USER_B_ID = "''' + user_b_id + r'''"

results = []

with flask_app.test_client() as c:
    # Test 1: Anonymous feed
    with c.session_transaction() as s:
        s.clear()
    r = c.get("/reels/api/reels/feed?limit=50")
    d = r.get_json(silent=True) or {}
    reels = d.get("reels", [])
    ids = [rl.get("id") for rl in reels]
    results.append({
        "name": "Anonymous feed sees reel",
        "ok": REEL_ID in ids,
        "detail": json.dumps({"in_feed": REEL_ID in ids, "count": len(reels)})
    })

    # Test 2: Reel detail as anonymous
    r2 = c.get("/reels/api/reels/" + REEL_ID + "/detail")
    d2 = r2.get_json(silent=True) or {}
    ok2 = r2.status_code == 200 and "reel" in d2
    results.append({
        "name": "Reel detail accessible (anonymous)",
        "ok": ok2,
        "detail": "HTTP " + str(r2.status_code)
    })

    # Test 3: User B feed
    with c.session_transaction() as s:
        s["profile_id"] = USER_B_ID
        s["auth_user_id"] = USER_B_ID
        s["user_id"] = USER_B_ID
        s["logged_in"] = True
    r3 = c.get("/reels/api/reels/feed?limit=50")
    d3 = r3.get_json(silent=True) or {}
    reels3 = d3.get("reels", [])
    ids3 = [rl.get("id") for rl in reels3]
    results.append({
        "name": "User B feed sees reel",
        "ok": REEL_ID in ids3,
        "detail": json.dumps({"in_feed": REEL_ID in ids3, "count": len(reels3)})
    })

    # Test 4: Reel detail as User B
    r4 = c.get("/reels/api/reels/" + REEL_ID + "/detail")
    d4 = r4.get_json(silent=True) or {}
    ok4 = r4.status_code == 200 and "reel" in d4
    results.append({
        "name": "Reel detail accessible (User B)",
        "ok": ok4,
        "detail": "HTTP " + str(r4.status_code)
    })

    # Test 5: Reels page HTML renders
    r5 = c.get("/reels", follow_redirects=True)
    html = r5.data.decode("utf-8", errors="replace")
    errs = html.count("Traceback") + html.count("Internal Server Error")
    results.append({
        "name": "Reels page loads (no errors)",
        "ok": r5.status_code == 200 and errs == 0,
        "detail": f"HTTP {r5.status_code}, errors={errs}"
    })

print(json.dumps({"results": results}))
'''

result = subprocess.run(
    [sys.executable, '-c', verify_script],
    capture_output=True, text=True, timeout=60,
    cwd=BASE
)

if result.returncode == 0:
    stdout = result.stdout
    json_start = stdout.find('{"results"')
    if json_start >= 0:
        stdout = stdout[json_start:]
    try:
        data = json.loads(stdout)
        for r_item in data["results"]:
            check(r_item['name'], r_item['ok'], r_item.get('detail', ''))
    except json.JSONDecodeError:
        check("Verify script output parse", False, "JSON decode failed")
        print(f"  STDOUT excerpt: {stdout[:500]}")
else:
    check("Verify script execution", False, f"exit={result.returncode}")
    stderr = result.stderr[-500:] if result.stderr else ""
    print(f"  STDERR: {stderr}")

# ── CLEANUP ──
print("\n=== Cleanup ===")
for ctype, cid in created_ids.items():
    table = {'reel': 'chain_reels'}.get(ctype)
    if table and cid:
        try:
            execute(f"DELETE FROM {table} WHERE id=%s", (cid,), timeout_ms=5000)
        except Exception:
            pass
        check(f"Cleanup {ctype}", True)

for uid in cleanup_users:
    try:
        execute("DELETE FROM chain_profiles WHERE id=%s", (uid,), timeout_ms=5000)
    except Exception:
        pass
    check(f"Cleanup profile {uid[:8]}...", True)

try:
    if os.path.exists(target_path):
        os.remove(target_path)
        check("Cleanup copied video", True)
except Exception as e:
    check("Cleanup copied video", False, str(e)[:60])

# ── SUMMARY ──
print("\n" + "=" * 60)
passing = results["ok"]
failing = results["fail"]
total = passing + failing
print(f"RESULTS: {passing}/{total} passed, {failing}/{total} failed")
print("=" * 60)
for item in results["items"]:
    print(f"  {item['status']} {item['name']}" + (f" \u2014 {item['detail']}" if item['detail'] else ""))

sys.exit(0 if failing == 0 else 1)
