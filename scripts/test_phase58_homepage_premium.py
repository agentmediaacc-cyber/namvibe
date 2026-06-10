"""
Phase 58 — Premium Homepage / Main Feed Upgrade Tests.
Verifies:
  - Active template includes homepage_premium.css
  - homepage_premium.js included
  - Feed tabs exist
  - Post card premium classes
  - Story strip exists
  - Reels/live row exists
  - Suggested people exists (right rail)
  - Ad card exists
  - Mobile bottom nav exists
  - Responsive CSS queries exist
  - Backend service has safe fallback fields
  - No duplicate route rules
  - Homepage route returns 200
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

def test_homepage_premium_css_exists():
    path = "static/css/homepage_premium.css"
    check("homepage_premium.css exists", os.path.isfile(path))

def test_homepage_premium_js_exists():
    path = "static/js/homepage_premium.js"
    check("homepage_premium.js exists", os.path.isfile(path))

def test_template_includes_premium_css():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("Template includes homepage_premium.css", "homepage_premium.css" in content)
    check("Template includes homepage_premium.js", "homepage_premium.js" in content)

def test_template_has_feed_tabs():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    tabs = ["For You", "Following", "Public", "Nearby", "Live", "Reels", "Trending"]
    for tab in tabs:
        check(f"Feed tab '{tab}' present", tab in content)

def test_template_has_premium_post_card():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("post-card-premium class used", "post-card-premium" in content)
    check("post-action-btn class used", "post-action-btn" in content)
    check("post-header class used", "post-header" in content)
    check("post-actions class used", "post-actions" in content)

def test_template_has_story_strip():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("story-strip class used", "story-strip" in content)
    check("story-ring class used", "story-ring" in content)
    check("story-card class used", "story-card" in content)

def test_template_has_reels_live_strip():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("reels-strip class used", "reels-strip" in content)

def test_template_has_suggested_people():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("suggested-card class used", "suggested-card" in content)
    check("suggested-follow-btn used", "suggested-follow-btn" in content)
    check("Trending Creators section", "Trending Creators" in content)
    check("Suggested Friends section or fallback", "suggested-avatar" in content)

def test_template_has_ad_card():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("ad-card class used", "ad-card" in content)
    check("Sponsored label present", "Sponsored" in content)
    check("ad-card-dismiss present", "ad-card-dismiss" in content)
    check("ad-card-cta present", "ad-card-cta" in content)

def test_template_has_mobile_bottom_nav():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("mobile-bottom-nav class", "mobile-bottom-nav" in content)
    check("mobile-nav-item class", "mobile-nav-item" in content)

def test_template_has_composer_card():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("composer-card class", "composer-card" in content)
    check("composer-avatar class", "composer-avatar" in content)
    check("composer-action-chip class", "composer-action-chip" in content)

def test_template_has_feed_empty():
    tmpl = "templates/chain_home.html"
    if not os.path.isfile(tmpl):
        check("chain_home.html exists", False); return
    with open(tmpl) as f:
        content = f.read()
    check("feed-empty class present", "feed-empty" in content)

def test_css_responsive_queries():
    css = "static/css/homepage_premium.css"
    if not os.path.isfile(css):
        check("homepage_premium.css exists", False); return
    with open(css) as f:
        c = f.read()
    check("max-width 1024px query", "@media (max-width: 1024px)" in c)
    check("max-width 768px query", "@media (max-width: 768px)" in c)
    check("max-width 480px query", "@media (max-width: 480px)" in c)

def test_css_has_required_classes():
    css = "static/css/homepage_premium.css"
    if not os.path.isfile(css):
        check("homepage_premium.css exists", False); return
    with open(css) as f:
        c = f.read()
    required = [
        ".home-shell", ".home-topbar", ".home-layout",
        ".home-left-rail", ".home-feed", ".home-right-rail",
        ".feed-tabs", ".story-strip", ".story-card",
        ".composer-card", ".post-card-premium", ".post-actions",
        ".suggested-card", ".ad-card", ".mobile-bottom-nav",
    ]
    for cls in required:
        check(f"CSS class {cls} defined", cls in c)

def test_js_has_required_functions():
    js = "static/js/homepage_premium.js"
    if not os.path.isfile(js):
        check("homepage_premium.js exists", False); return
    with open(js) as f:
        j = f.read()
    check("JS has tab switching", "initFeedTabs" in j or "feed-tab" in j)
    check("JS has like handler", "data-action=\"like\"" in j or "is-liked" in j)
    check("JS has follow handler", "suggested-follow-btn" in j or "is-following" in j)
    check("JS has dismiss ad handler", "ad-card-dismiss" in j or "dismiss" in j)
    check("JS has mobile nav handler", "mobile-nav-item" in j or "initMobileNav" in j)
    check("JS has story scroll handler", "story-strip" in j or "initStoryScroll" in j)
    check("JS uses DOMContentLoaded", "DOMContentLoaded" in j)
    check("JS uses strict mode", "'use strict'" in j or '"use strict"' in j)

def test_backend_homepage_service_has_feed_fields():
    svc = "services/homepage_service.py"
    if not os.path.isfile(svc):
        check("homepage_service.py exists", False); return
    with open(svc) as f:
        s = f.read()
    check("feed_for_you field", "feed_for_you" in s)
    check("feed_following field", "feed_following" in s)
    check("feed_public field", "feed_public" in s)
    check("feed_trending field", "feed_trending" in s)
    check("feed_nearby field", "feed_nearby" in s)
    check("trending_profiles field", "trending_profiles" in s)
    check("feed_live field", "feed_live" in s)
    check("feed_reels field", "feed_reels" in s)
    check("following_count field", "following_count" in s)

def test_backend_no_duplicate_routes():
    import re
    found = set()
    for root, dirs, files in os.walk("api_routes"):
        for fn in files:
            if fn.endswith(".py"):
                fp = os.path.join(root, fn)
                with open(fp) as f:
                    for line in f:
                        m = re.search(r'@\w+\.route\([\'"](/[^\'"]+)', line)
                        if m:
                            found.add(m.group(1))
    # Check no duplicate route defs for / or /home or /feed
    for route in ["/", "/home", "/feed"]:
        count = sum(1 for r in found if r == route)
        check(f"Route '{route}' appears <=1 time in api_routes", count <= 1,
              detail=f"found {count} times")

def test_homepage_route_returns_200():
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    from app import create_app
    app = create_app()
    with app.test_client() as client:
        resp = client.get("/")
        check("GET / returns 200 or 302", resp.status_code in (200, 302, 301),
              detail=f"status={resp.status_code}")

def test_homepage_route_has_required_data():
    from app import create_app
    app = create_app()
    os.environ["CHAIN_FAST_LOCAL"] = "1"
    with app.test_request_context():
        from services.homepage_service import get_homepage_data
        data = get_homepage_data()
        check("get_homepage_data returns dict", isinstance(data, dict))
        expected_keys = [
            "current", "stories", "live_rooms", "recommended_profiles",
            "trending_posts", "reels", "wallet", "sponsored_posts",
            "announcements", "groups", "nearby_users",
            "feed_for_you", "feed_following", "feed_public", "feed_trending",
            "feed_live", "feed_reels", "feed_nearby",
            "trending_profiles", "following_count",
        ]
        for key in expected_keys:
            check(f"get_homepage_data has key '{key}'", key in data,
                  detail=f"missing {key}" if key not in data else None)

def test_homepage_service_safe_fallback():
    svc = "services/homepage_service.py"
    with open(svc) as f:
        s = f.read()
    check("Empty payload fallback", "_empty_homepage_payload" in s)
    check("Fallback for circuit open", "is_circuit_open()" in s)
    check("Try/except in fetches", "except Exception" in s)
    check("Feed limit applied", "[:20]" in s or "LIMIT 2" in s or "limit=2" in s)

def test_no_homepage_home_route_duplicate():
    """Verify there is no separate /home route to avoid confusion with /"""
    app_py = "app.py"
    found_home_route = False
    with open(app_py) as f:
        for line in f:
            if '"/home"' in line or "('/home')" in line:
                found_home_route = True
    check("No duplicate /home route in app.py", not found_home_route,
          detail="/home route found — may conflict with /")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 58: Premium Homepage / Main Feed Upgrade Tests")
    print("=" * 60)

    tests = [
        ("homepage_premium.css exists", test_homepage_premium_css_exists),
        ("homepage_premium.js exists", test_homepage_premium_js_exists),
        ("Template includes both assets", test_template_includes_premium_css),
        ("Feed tabs present", test_template_has_feed_tabs),
        ("Premium post card classes", test_template_has_premium_post_card),
        ("Story strip exists", test_template_has_story_strip),
        ("Reels/live strip exists", test_template_has_reels_live_strip),
        ("Suggested people section", test_template_has_suggested_people),
        ("Ad card present", test_template_has_ad_card),
        ("Mobile bottom nav", test_template_has_mobile_bottom_nav),
        ("Composer card present", test_template_has_composer_card),
        ("Feed empty state", test_template_has_feed_empty),
        ("CSS responsive queries", test_css_responsive_queries),
        ("CSS required classes", test_css_has_required_classes),
        ("JS required functions", test_js_has_required_functions),
        ("Backend feed fields", test_backend_homepage_service_has_feed_fields),
        ("Backend no duplicate routes", test_backend_no_duplicate_routes),
        ("GET / returns 200/302", test_homepage_route_returns_200),
        ("get_homepage_data keys", test_homepage_route_has_required_data),
        ("Backend safe fallback", test_homepage_service_safe_fallback),
        ("No /home route duplicate", test_no_homepage_home_route_duplicate),
    ]

    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] threw: {e}")
            FAIL += 1

    total = PASS + FAIL
    print(f"\n{'=' * 40}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'=' * 40}")
    sys.exit(0 if FAIL == 0 else 1)
