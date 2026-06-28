#!/usr/bin/env python3
"""Phase 164B: Debug every core flow against live server."""
import sys, os, json, requests, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("NAMVIBE_BASE", "https://namvibe.com")
PASS = 0
FAIL = 0
RESULTS = {}

def check(label, ok, detail=""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS[label] = {"status": status, "detail": detail[:200]}
    print(f"  {status}  {label}  {detail[:200]}")

session = requests.Session()
session.verify = False
import urllib3
urllib3.disable_warnings()

print(f"=== Phase 164B — Live Failure Debug @ {BASE} ===\n")

# 0. Health check
try:
    r = session.get(f"{BASE}/healthz", timeout=15)
    check("HEALTHZ", r.status_code == 200 and r.json().get("ok"), f"HTTP {r.status_code} {r.text[:100]}")
except Exception as e:
    check("HEALTHZ", False, str(e))

# 1. GET homepage
try:
    r = session.get(BASE, timeout=15)
    check("HOMEPAGE", r.status_code == 200 and "NamVibe" in r.text[:300], f"HTTP {r.status_code}")
except Exception as e:
    check("HOMEPAGE", False, str(e))

# 2. GET csrf token / check CSRF
csrf = ""
try:
    r = session.get(f"{BASE}/auth/csrf" if False else BASE, timeout=15)
    import re
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
    if m:
        csrf = m.group(1)
        check("CSRF_TOKEN_FOUND", True, f"token={csrf[:20]}...")
    else:
        check("CSRF_TOKEN_FOUND", False, "no csrf meta tag found")
except Exception as e:
    check("CSRF_TOKEN_FOUND", False, str(e))

# 3. GET /api/home/feed (JSON)
try:
    r = session.get(f"{BASE}/api/home/feed", headers={"Accept": "application/json"}, timeout=15)
    if r.status_code in (200, 401):
        check("API_HOME_FEED", r.status_code < 400, f"HTTP {r.status_code}")
    else:
        check("API_HOME_FEED", False, f"HTTP {r.status_code} {r.text[:100]}")
except Exception as e:
    check("API_HOME_FEED", False, str(e))

# 4. Test like endpoint response shape
try:
    r = session.post(f"{BASE}/api/home/post/test-id/like",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     json={}, timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("LIKE_ENDPOINT_SHAPE", True, f"HTTP {status} keys={list(j.keys())} ok={j.get('ok')} result={j.get('result')}")
    except Exception as e:
        check("LIKE_ENDPOINT_SHAPE", False, f"HTTP {status} not json: {e}")
except Exception as e:
    check("LIKE_ENDPOINT_SHAPE", False, str(e))

# 5. Test reel like endpoint response shape
try:
    r = session.post(f"{BASE}/reels/api/reels/test-id/like",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     json={}, timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("REEL_LIKE_ENDPOINT_SHAPE", True, f"HTTP {status} keys={list(j.keys())} success={j.get('success')} liked={j.get('liked')}")
    except Exception as e:
        check("REEL_LIKE_ENDPOINT_SHAPE", False, f"HTTP {status} not json: {e}")
except Exception as e:
    check("REEL_LIKE_ENDPOINT_SHAPE", False, str(e))

# 6. Test comment endpoint shape
try:
    r = session.post(f"{BASE}/api/comments/post/test-id",
                     headers={"X-CSRFToken": csrf, "Content-Type": "application/json"} if csrf else {"Content-Type": "application/json"},
                     json={"body": "test"}, timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("COMMENT_ENDPOINT_SHAPE", True, f"HTTP {status} keys={list(j.keys())} success={j.get('success')}")
    except Exception as e:
        check("COMMENT_ENDPOINT_SHAPE", False, f"HTTP {status} not json: {e}")
except Exception as e:
    check("COMMENT_ENDPOINT_SHAPE", False, str(e))

# 7. Test reel comment endpoint
try:
    r = session.post(f"{BASE}/reels/api/reels/test-id/comment",
                     headers={"X-CSRFToken": csrf, "Content-Type": "application/json"} if csrf else {"Content-Type": "application/json"},
                     json={"body": "test"}, timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("REEL_COMMENT_ENDPOINT_SHAPE", True, f"HTTP {status} keys={list(j.keys())} success={j.get('success')}")
    except Exception as e:
        check("REEL_COMMENT_ENDPOINT_SHAPE", False, f"HTTP {status} not json: {e}")
except Exception as e:
    check("REEL_COMMENT_ENDPOINT_SHAPE", False, str(e))

# 8. Test reel upload endpoint (no file, just shape)
try:
    r = session.post(f"{BASE}/reels/api/reels/create",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("REEL_CREATE_ENDPOINT", True, f"HTTP {status} keys={list(j.keys())} error={j.get('error')}")
    except:
        check("REEL_CREATE_ENDPOINT", False, f"HTTP {status} not json: {r.text[:100]}")
except Exception as e:
    check("REEL_CREATE_ENDPOINT", False, str(e))

# 9. Test post create endpoint (no file, just shape)
try:
    r = session.post(f"{BASE}/posts/api/posts/create",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("POST_CREATE_ENDPOINT", True, f"HTTP {status} keys={list(j.keys())} error={j.get('error')}")
    except:
        check("POST_CREATE_ENDPOINT", False, f"HTTP {status} not json: {r.text[:100]}")
except Exception as e:
    check("POST_CREATE_ENDPOINT", False, str(e))

# 10. Test story create endpoint
try:
    r = session.post(f"{BASE}/status/api/status/create",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     timeout=15)
    status = r.status_code
    try:
        j = r.json()
        check("STORY_CREATE_ENDPOINT", True, f"HTTP {status} keys={list(j.keys())} error={j.get('error')}")
    except:
        check("STORY_CREATE_ENDPOINT", False, f"HTTP {status} not json: {r.text[:100]}")
except Exception as e:
    check("STORY_CREATE_ENDPOINT", False, str(e))

# 11. Test story feed
try:
    r = session.get(f"{BASE}/api/stories/feed", timeout=15)
    check("STORY_FEED_ENDPOINT", r.status_code < 400, f"HTTP {r.status_code}")
except Exception as e:
    check("STORY_FEED_ENDPOINT", False, str(e))

# 12. Test save endpoint
try:
    r = session.post(f"{BASE}/api/home/post/test-id/save",
                     headers={"X-CSRFToken": csrf} if csrf else {},
                     json={}, timeout=15)
    try:
        j = r.json()
        check("SAVE_ENDPOINT_SHAPE", True, f"HTTP {r.status_code} keys={list(j.keys())}")
    except:
        check("SAVE_ENDPOINT_SHAPE", False, f"HTTP {r.status_code} not json")
except Exception as e:
    check("SAVE_ENDPOINT_SHAPE", False, str(e))

# 13. CSRF token endpoint
try:
    r = session.get(f"{BASE}/auth/csrf", timeout=15)
    check("CSRF_GET_ENDPOINT", r.status_code < 500, f"HTTP {r.status_code} {r.text[:100]}")
except Exception as e:
    check("CSRF_GET_ENDPOINT", False, str(e))

# 14. Notification endpoint
try:
    r = session.get(f"{BASE}/api/notifications", timeout=15)
    check("NOTIFICATION_ENDPOINT", r.status_code < 500, f"HTTP {r.status_code} {r.text[:100]}")
except Exception as e:
    check("NOTIFICATION_ENDPOINT", False, str(e))

print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*60}")
for label, result in sorted(RESULTS.items()):
    print(f"  {result['status']:4s}  {label}")
print(f"{'='*60}")
sys.exit(0 if FAIL == 0 else 1)
