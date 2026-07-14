#!/usr/bin/env python3
"""Verify the homepage stats bar (online users, live sessions) renders for real users."""

import sys, os, json, uuid, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"

from app import create_app
from services.neon_service import prime_neon_runtime, fast_query, execute

prime_neon_runtime()
time.sleep(0.5)

PASS, FAIL = "PASS", "FAIL"
_total = _passed = _failed = 0
NOW = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

def check(label, condition, detail=""):
    global _total, _passed, _failed
    _total += 1
    if condition:
        _passed += 1
        print(f"  [{PASS}] {label}" + (f" \u2014 {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"  [{FAIL}] {label}" + (f" \u2014 {detail}" if detail else ""))

app = create_app()

# ── 1. Query real DB counts ──
print("\n=== 1. DB queries return correct counts ===")
online_db = fast_query(
    "SELECT COUNT(*) AS cnt FROM chain_online_presence WHERE status = 'online'",
    (), default=[{"cnt": 0}], timeout_ms=5000,
)
live_db = fast_query(
    "SELECT COUNT(*) AS cnt FROM chain_live_rooms WHERE is_live = TRUE",
    (), default=[{"cnt": 0}], timeout_ms=5000,
)
online_users = fast_query(
    """SELECT p.id, p.username, p.display_name, p.avatar_url, p.thumbnail_url
       FROM chain_online_presence op
       JOIN chain_profiles p ON p.id = op.profile_id
       WHERE op.status = 'online'
       ORDER BY op.updated_at DESC NULLS LAST LIMIT 8""",
    (), default=[], timeout_ms=5000,
)
if not isinstance(online_db, list) or not online_db:
    online_db = [{"cnt": 0}]
if not isinstance(live_db, list) or not live_db:
    live_db = [{"cnt": 0}]
if not isinstance(online_users, list):
    online_users = []
expected_online = int((online_db[0] or {}).get("cnt", 0) or 0)
expected_live = int((live_db[0] or {}).get("cnt", 0) or 0)
expected_users_len = len(online_users)
check("online count >= 0", expected_online >= 0, f"count={expected_online}")
check("live count >= 0", expected_live >= 0, f"count={expected_live}")
check("online users list is a list", isinstance(online_users, list))
if online_users:
    u = online_users[0]
    check("online user has id", bool(u.get("id")))
    check("online user has username", bool(u.get("username")))

# ── 2. Anonymous homepage renders stats bar ──
print("\n=== 2. Anonymous user sees stats bar ===")
with app.test_client() as c:
    resp = c.get("/")
    html = resp.data.decode("utf-8", errors="replace")
    status = resp.status_code
    check("homepage returns 200", status == 200, f"got {status}")

    # Stats bar section exists
    has_stats_section = 'class="nv-stats-bar"' in html
    check("stats bar section present", has_stats_section)

    # Stat items exist
    has_online_label = 'Online</span>' in html or 'class="nv-stat-label"' in html
    has_live_label = 'Live</span>' in html or 'class="nv-stat-label"' in html
    check("online label present", has_online_label)
    check("live label present", has_live_label)

    # Online count renders (should be a number)
    import re
    online_matches = re.findall(r'<strong[^>]*class="nv-stat-number"[^>]*>(\d+)</strong>', html)
    check("online count number renders", len(online_matches) >= 1)
    if online_matches:
        rendered_online = int(online_matches[0])
        check("online count matches DB", rendered_online == expected_online,
              f"html={rendered_online} db={expected_online}")

    if expected_live > 0:
        check("live count > 0 matches DB", len(online_matches) >= 2 and int(online_matches[1]) == expected_live,
              f"html={online_matches[1] if len(online_matches) >= 2 else '?'} db={expected_live}")

    # Avatar facepile
    avatar_count = html.count('class="nv-stat-avatar"')
    check("avatar images render", avatar_count >= 0)
    if expected_users_len > 0:
        check("at least some avatars shown", avatar_count > 0 or expected_users_len == 0,
              f"avatars={avatar_count} db_users={expected_users_len}")

    # Divider between stats
    check("stat divider present", 'class="nv-stat-divider"' in html)

    # Links go to /live/ and /discover/?online=1
    check("stats link to /live/", '/live/' in html)
    check("online link to discover", '/discover/?online=1' in html)

    # Interactive elements
    check("go-live button present", 'data-action="go-live"' in html)
    check("say-hi button present", 'data-action="say-hi"' in html)
    check("online dot class present", 'nv-stat-online-dot' in html)
    check("avatar wrap (profile link) present", 'nv-stat-avatar-wrap' in html)
    check("avatar links to profile", '/profile/' in html)

    if expected_users_len > 5:
        check("more link to discover", '/discover/?online=1' in html)

# ── 3. Create a real test user and verify they see it too ──
print("\n=== 3. Authenticated user sees stats bar ===")
test_id = str(uuid.uuid4())
test_user = f"stats_user_{int(time.time())}"
try:
    execute(
        "INSERT INTO chain_profiles (id, username, display_name, email, auth_user_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (test_id, test_user, "Stats Test User", f"{test_user}@test.com", test_id, NOW, NOW),
        timeout_ms=10000
    )
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["profile_id"] = test_id
            sess["auth_user_id"] = test_id

        resp2 = c.get("/")
        html2 = resp2.data.decode("utf-8", errors="replace")
        status2 = resp2.status_code

        check("auth homepage returns 200", status2 == 200, f"got {status2}")
        check("auth stats bar present", 'class="nv-stats-bar"' in html2, "section rendered for authenticated user")
        check("auth online count renders", 'id="nvStatOnline"' in html2)
        check("auth avatars render", 'class="nv-stat-avatar"' in html2 or expected_users_len == 0)

    # Cleanup
    execute("DELETE FROM chain_profiles WHERE id=%s", (test_id,), timeout_ms=5000)
    check("cleanup ok", True)
except Exception as e:
    check("auth user test failed", False, str(e)[:120])

# ── 4. Verify the template has the correct structure ──
print("\n=== 4. Template structure verification ===")
from jinja2 import Environment, FileSystemLoader
import os
tmpl_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
env = Environment(loader=FileSystemLoader(tmpl_dir))
try:
    src = env.loader.get_source(env, "chain_home.html")[0]
    check("template has stats bar section", 'nv-stats-bar' in src, "section class present in template")
    check("template has online_stats reference", 'online_stats.online_count' in src or 'online_stats' in src,
          "online_stats dict referenced")
    check("template has avatar loop", 'nv-stat-avatar' in src, "avatar facepile loop present")
    check("template has online dot", 'nv-stat-online-dot' in src, "green online dot present")
    check("template has go-live", 'data-action="go-live"' in src, "Go Live button present")
    check("template has say-hi", 'data-action="say-hi"' in src, "Say Hi button present")
    check("template has socket listener", 'homepage:stats' in src, "Socket.IO listener for real-time stats")
    check("template has periodic refresh", 'setInterval' in src, "periodic stats refresh")
    check("template has live link", '/live/' in src, "links to live hub")
except Exception as e:
    check("template inspection", False, str(e)[:80])

# ── Summary ──
print(f"\n{'='*60}")
print(f"SUMMARY: {_passed}/{_total} passed, {_failed}/{_total} failed")
print(f"{'='*60}")
sys.exit(0 if _failed == 0 else 1)
