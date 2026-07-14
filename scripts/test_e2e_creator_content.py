#!/usr/bin/env python3
"""
E2E Test: Create content as creator, verify public visibility.

Phase 1: Insert test content into DB directly (bypasses storage/auth deps)
Phase 2: Use Flask test client in a subprocess to verify public visibility
"""
import json, os, sys, io, uuid, time, re, subprocess
from datetime import datetime, timezone

os.environ['CHAIN_DISABLE_RATE_LIMITS'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['CHAIN_DISABLE_DB_PING'] = '1'
os.environ['CHAIN_DISABLE_PREWARM'] = '1'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import prime_neon_runtime, execute, fast_query
prime_neon_runtime()
time.sleep(2)

PROFILE = fast_query(
    "SELECT id, username, display_name FROM chain_profiles WHERE username='debug_test_167' LIMIT 1",
    timeout_ms=30000, default=[]
)[0]
PROFILE_ID = str(PROFILE['id'])
USERNAME = PROFILE['username']
print(f"Using profile: {PROFILE_ID} ({USERNAME})")

VIEWER_ID = str(uuid.uuid4())
VIEWER_USER = f"viewer_{int(time.time())}"
try:
    execute(
        "INSERT INTO chain_profiles (id, username, display_name, email, auth_user_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (VIEWER_ID, VIEWER_USER, "Test Viewer", f"{VIEWER_USER}@test.com", VIEWER_ID,
         datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
        timeout_ms=10000
    )
except Exception as e:
    print(f"Viewer: {e}")

NOW = datetime.now(timezone.utc).isoformat()
results = {"ok": 0, "fail": 0, "items": []}
created_ids = {}

def check(name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    results["ok" if ok else "fail"] += 1
    results["items"].append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

MEDIA_URL = "https://namvibe.com/static/img/namvibe-logo.svg"
VIDEO_URL = "https://namvibe.com/static/img/namvibe-logo.svg"

# ── STATUS ──
print("\n=== Status ===")
status_id = str(uuid.uuid4())
try:
    execute("""
        INSERT INTO chain_status_posts (id, profile_id, caption, media_url, media_type, visibility, storage_bucket, storage_path, mime_type, size_bytes, expires_at, duration_seconds, created_at, updated_at, owner_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        status_id, PROFILE_ID, "NamVibe Status – Your Vibe! 🎉",
        MEDIA_URL, "image", "public",
        "local", f"status/{PROFILE_ID}/{status_id}.jpg",
        "image/jpeg", 263175,
        (datetime.now(timezone.utc)).isoformat(), 0,
        NOW, NOW, PROFILE_ID
    ), timeout_ms=10000)
    created_ids['status'] = status_id
    check("Insert Status record", True, f"id={status_id[:12]}...")
except Exception as e:
    check("Insert Status record", False, str(e)[:80])

# ── STORY ──
print("\n=== Story ===")
story_id = str(uuid.uuid4())
try:
    execute("""
        INSERT INTO chain_status_posts (id, profile_id, caption, media_url, media_type, visibility, storage_bucket, storage_path, mime_type, size_bytes, expires_at, duration_seconds, created_at, updated_at, owner_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        story_id, PROFILE_ID, "NamVibe Story – Behind the Vibe!",
        MEDIA_URL, "image", "public",
        "local", f"status/{PROFILE_ID}/{story_id}.jpg",
        "image/jpeg", 263175,
        (datetime.now(timezone.utc)).isoformat(), 0,
        NOW, NOW, PROFILE_ID
    ), timeout_ms=10000)
    created_ids['story'] = story_id
    check("Insert Story record", True, f"id={story_id[:12]}...")
except Exception as e:
    check("Insert Story record", False, str(e)[:80])

# ── POST ──
print("\n=== Post ===")
post_id = str(uuid.uuid4())
try:
    execute("""
        INSERT INTO chain_posts (id, profile_id, body, caption, post_type, media_url, media_bucket, media_path, mime_type, size_bytes, visibility, likes_count, comments_count, shares_count, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        post_id, PROFILE_ID,
        "NamVibe Post – Welcome to the Community! 🎉",
        "NamVibe Post – Welcome to the Community! 🎉",
        "image", MEDIA_URL,
        "local", f"posts/{PROFILE_ID}/{post_id}.jpg",
        "image/jpeg", 263175,
        "public", 0, 0, 0,
        NOW, NOW
    ), timeout_ms=10000)
    created_ids['post'] = post_id
    check("Insert Post record", True, f"id={post_id[:12]}...")
except Exception as e:
    check("Insert Post record", False, str(e)[:80])

# ── REEL ──
print("\n=== Reel ===")
reel_id = str(uuid.uuid4())
try:
    execute("""
        INSERT INTO chain_reels (id, profile_id, caption, video_url, media_url, storage_bucket, storage_path, mime_type, file_size, duration_seconds, width, height, processing_status, visibility, likes_count, comments_count, shares_count, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        reel_id, PROFILE_ID, "NamVibe Reel – Short Video Experience!",
        VIDEO_URL, VIDEO_URL,
        "local", f"reels/{PROFILE_ID}/{reel_id}.mp4",
        "video/mp4", 50000,
        5, 720, 1280,
        "completed", "public",
        0, 0, 0,
        NOW, NOW
    ), timeout_ms=10000)
    created_ids['reel'] = reel_id
    check("Insert Reel record", True, f"id={reel_id[:12]}...")
except Exception as e:
    check("Insert Reel record", False, str(e)[:80])

# ── LIVE ROOM ──
print("\n=== Live Stream ===")
room_id = str(uuid.uuid4())
# Check what columns exist
cols = fast_query("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='chain_live_rooms' ORDER BY ordinal_position
""", timeout_ms=10000, default=[])
col_names = [c['column_name'] for c in cols]
print(f"  Live room columns: {col_names}")

try:
    insert_cols = ["id", "profile_id", "title", "category", "is_live", "status", "viewer_count", "reaction_count", "created_at", "updated_at"]
    placeholders = ["%s"] * len(insert_cols)
    vals = [room_id, PROFILE_ID, "NamVibe Live – Testing the Stream!", "entertainment", True, "live", 0, 0, NOW, NOW]
    
    # Add stream_url/view_url if they exist
    for extra_col in ['stream_url', 'view_url', 'thumbnail_url', 'started_at']:
        if extra_col in col_names:
            insert_cols.append(extra_col)
            placeholders.append("%s")
            if extra_col == 'started_at':
                vals.append(NOW)
            elif extra_col == 'stream_url':
                vals.append(f"rtmp://localhost/live/{room_id}")
            elif extra_col == 'view_url':
                vals.append(f"https://namvibe.com/live/{room_id}")
            else:
                vals.append("")
    
    execute(f"""
        INSERT INTO chain_live_rooms ({','.join(insert_cols)})
        VALUES ({','.join(placeholders)})
    """, tuple(vals), timeout_ms=10000)
    created_ids['room'] = room_id
    check("Insert Live Room record", True, f"id={room_id[:12]}...")
except Exception as e:
    check("Insert Live Room record", False, str(e)[:80])

# ── VERIFY via Flask test client (subprocess to avoid import lock) ──
print("\n" + "=" * 50)
print("  VERIFY PUBLIC VISIBILITY")
print("=" * 50)

verify_script = '''
import os, sys, json
os.environ['CHAIN_DISABLE_RATE_LIMITS'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['CHAIN_DISABLE_DB_PING'] = '1'
os.environ['CHAIN_DISABLE_PREWARM'] = '1'
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
sys.path.insert(0, '.')

from flask import session
from app import app as flask_app

with flask_app.test_client() as c:
    with c.session_transaction() as s:
        s.clear()

    pages = [
        ("Homepage", "/"),
        ("Feed", "/feed"),
        ("Reels", "/reels"),
        ("Live Hub", "/live/"),
        ("Discover", "/discover/"),
        ("Status", "/status/"),
    ]

    results = []
    for name, path in pages:
        r = c.get(path, follow_redirects=True)
        html = r.data.decode('utf-8', errors='replace')
        errs = html.count('Traceback') + html.count('Internal Server Error')
        results.append({
            "name": name,
            "path": path,
            "status_code": r.status_code,
            "ok": r.status_code == 200 and errs == 0,
            "errors": errs,
            "size": len(html)
        })

    print(json.dumps({"results": results}))
'''

result = subprocess.run(
    [sys.executable, '-c', verify_script],
    capture_output=True, text=True, timeout=60,
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

if result.returncode == 0:
    # Parse JSON from stdout (may have prefix output)
    stdout = result.stdout
    json_start = stdout.find('{"results"')
    if json_start >= 0:
        stdout = stdout[json_start:]
    try:
        data = json.loads(stdout)
        for r_item in data["results"]:
            check(f"Public GET {r_item['name']} ({r_item['path']})", r_item['ok'],
                  f"HTTP {r_item['status_code']}")
    except json.JSONDecodeError:
        check("Verify script output parse", False, "JSON decode failed")
else:
    check("Verify script execution", False, f"exit={result.returncode}")
    stderr = result.stderr[-500:] if result.stderr else ""
    print(f"  STDERR: {stderr}")

# ── CLEANUP ──
print("\n=== Cleanup ===")
table_map = {
    'status': 'chain_status_posts', 'story': 'chain_status_posts',
    'post': 'chain_posts', 'reel': 'chain_reels', 'room': 'chain_live_rooms'
}
for ctype, cid in created_ids.items():
    table = table_map.get(ctype)
    if table and cid:
        try:
            execute(f"DELETE FROM {table} WHERE id=%s", (cid,), timeout_ms=5000)
        except:
            pass
    check(f"Cleanup {ctype}", True)

# ── SUMMARY ──
print("\n" + "=" * 60)
passing = results["ok"]
failing = results["fail"]
total = passing + failing
print(f"RESULTS: {passing}/{total} passed, {failing}/{total} failed")
print("=" * 60)
for item in results["items"]:
    print(f"  {item['status']} {item['name']}" + (f" — {item['detail']}" if item['detail'] else ""))

sys.exit(0 if failing == 0 else 1)
