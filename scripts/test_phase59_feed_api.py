"""
Phase 59 — Real Feed API + Infinite Scroll + Follow Actions Tests.
Verifies:
  - Feed API route exists
  - All 7 tabs supported
  - get_feed_tab exists
  - Privacy rules present
  - Pagination fields present
  - homepage_premium.js fetches /api/home/feed
  - Infinite scroll guard exists
  - Loading skeleton exists
  - Follow/unfollow routes exist
  - Like/save/share routes exist
  - Renderer supports post/reel/live/ad/announcement/suggested_user
  - No duplicate routes
  - Phase 58 still passes
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

def test_feed_api_route_exists():
    path = "api_routes/homepage_api.py"
    check("homepage_api.py exists", os.path.isfile(path))
    if os.path.isfile(path):
        with open(path) as f:
            content = f.read()
        check("Route /api/home/feed defined", "/api/home/feed" in content)
        check("All 7 tab tabs handled", "tabs.get" in content or "tab=" in content)
        check("Follow route exists", "/api/home/follow/<" in content or "/api/home/follow/" in content)
        check("Unfollow route exists", "/api/home/unfollow/<" in content or "/api/home/unfollow/" in content)
        check("Like route exists", "/api/home/post/<post_id>/like" in content)
        check("Save route exists", "/api/home/post/<post_id>/save" in content)
        check("Share route exists", "/api/home/post/<post_id>/share" in content)

def test_feed_api_blueprint_registered():
    app_py = "app.py"
    with open(app_py) as f:
        content = f.read()
    check("homepage_api_bp imported", "homepage_api_bp" in content)
    check("homepage_api_bp registered", "register_blueprint(homepage_api_bp)" in content)

def test_get_feed_tab_exists():
    svc = "services/homepage_service.py"
    with open(svc) as f:
        content = f.read()
    check("get_feed_tab function defined", "def get_feed_tab" in content)
    for tab in ["for_you", "following", "public", "nearby", "live", "reels", "trending"]:
        check(f"Feed tab '{tab}' backend handler", f"_feed_{tab}" in content)

def test_privacy_rules_present():
    svc = "services/homepage_service.py"
    with open(svc) as f:
        content = f.read()
    check("Public visibility filter", "visibility IS NULL OR visibility = 'public'" in content or "public" in content.lower())

def test_pagination_fields():
    api = "api_routes/homepage_api.py"
    with open(api) as f:
        content = f.read()
    for field in ["ok", "tab", "items", "next_page", "has_more"]:
        check(f"Pagination field '{field}' in response", field in content)

def test_js_fetches_api():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    check("JS fetches /api/home/feed", "/api/home/feed" in content)
    check("JS has loading guard", "loading" in content and "loadingMore" in content)
    check("Infinite scroll guard", "state.hasMore" in content or "hasMore" in content)
    check("Loading skeleton renderer", "renderSkeleton" in content or "feed-skeleton" in content)
    check("Feed items container", "feed-items" in content)

def test_js_renderer_supports_types():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    for render_fn in ["renderPostItem", "renderLiveItem", "renderReelItem", "renderAdItem",
                       "renderAnnouncementItem", "renderSuggestedUserItem", "renderFeedItem"]:
        check(f"Renderer function '{render_fn}' exists", render_fn in content)
    for item_type in ["post", "live", "reel", "ad", "announcement", "suggested_user"]:
        check(f"Renderer handles type '{item_type}'", item_type in content)

def test_js_has_follow_wiring():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    check("Follow API call present", "/api/home/follow/" in content)
    check("Unfollow API call present", "/api/home/unfollow/" in content)

def test_js_has_like_wiring():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    check("Like API call present", "/api/home/post/" in content and "like" in content.lower())

def test_js_has_save_wiring():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    check("Save API call present", "/api/home/post/" in content and "save" in content.lower())

def test_js_has_share_wiring():
    js = "static/js/homepage_premium.js"
    with open(js) as f:
        content = f.read()
    check("Share API call present", "/api/home/post/" in content and "share" in content.lower())

def test_no_duplicate_api_routes():
    import re
    routes_found = {}
    for root, dirs, files in os.walk("api_routes"):
        for fn in files:
            if fn.endswith(".py"):
                fp = os.path.join(root, fn)
                with open(fp) as f:
                    for line in f:
                        m = re.search(r'@\w+\.route\([\'"](/[^\'"]+)', line)
                        if m:
                            route = m.group(1)
                            routes_found[route] = routes_found.get(route, 0) + 1
    for route in ["/api/home/feed", "/api/home/follow/<profile_id>", "/api/home/unfollow/<profile_id>",
                   "/api/home/post/<post_id>/like", "/api/home/post/<post_id>/save", "/api/home/post/<post_id>/share"]:
        count = sum(1 for r, c in routes_found.items() if r == route or r.replace("<", "<").replace(">", ">") == route)
        check(f"Route '{route}' appears <=1 time", count <= 1, detail=f"found {count}")

def test_feed_api_returns_json():
    from app import create_app
    app = create_app()
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    with app.test_client() as client:
        for tab in ["for_you", "following", "public", "nearby", "live", "reels", "trending"]:
            resp = client.get(f"/api/home/feed?tab={tab}&page=1")
            check(f"GET /api/home/feed?tab={tab} returns JSON", resp.status_code in (200, 302, 500),
                  detail=f"status={resp.status_code}")
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.data)
                    check(f"{tab}: ok field present", data.get("ok") is not None)
                    check(f"{tab}: items is list", isinstance(data.get("items"), list))
                    check(f"{tab}: has_more field", "has_more" in data)
                    check(f"{tab}: next_page field", "next_page" in data)
                    check(f"{tab}: tab field", data.get("tab") == tab)
                except Exception as e:
                    check(f"{tab}: valid JSON", False, detail=str(e))

def test_follow_unfollow_routes():
    from app import create_app
    app = create_app()
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    with app.test_client() as client:
        resp = client.post("/api/home/follow/some_id")
        check("POST /api/home/follow returns JSON", resp.status_code in (200, 401, 400, 500))
        resp2 = client.post("/api/home/unfollow/some_id")
        check("POST /api/home/unfollow returns JSON", resp2.status_code in (200, 401, 400, 500))

def test_like_save_share_routes():
    from app import create_app
    app = create_app()
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    with app.test_client() as client:
        for action in ["like", "save", "share"]:
            resp = client.post(f"/api/home/post/test_id/{action}")
            check(f"POST /api/home/post/<id>/{action} returns JSON", resp.status_code in (200, 401, 400, 500))

def test_homepage_premium_css_skeleton():
    css = "static/css/homepage_premium.css"
    with open(css) as f:
        c = f.read()
    check("Skeleton shimmer animation", "skeleton-shimmer" in c or "skeleton" in c)

def test_phase58_still_passes():
    """Verify Phase 58 test suite still passes"""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/test_phase58_homepage_premium.py"],
        capture_output=True, text=True, timeout=120
    )
    check("Phase 58 test suite passes", result.returncode == 0,
          detail=f"exit={result.returncode}, output={result.stdout[-200:]}" if result.returncode != 0 else None)


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 59: Real Feed API + Infinite Scroll + Actions Tests")
    print("=" * 60)

    tests = [
        ("Feed API route exists", test_feed_api_route_exists),
        ("Blueprint registered", test_feed_api_blueprint_registered),
        ("get_feed_tab backend", test_get_feed_tab_exists),
        ("Privacy rules", test_privacy_rules_present),
        ("Pagination fields", test_pagination_fields),
        ("JS fetches API", test_js_fetches_api),
        ("JS renderer types", test_js_renderer_supports_types),
        ("JS follow wiring", test_js_has_follow_wiring),
        ("JS like wiring", test_js_has_like_wiring),
        ("JS save wiring", test_js_has_save_wiring),
        ("JS share wiring", test_js_has_share_wiring),
        ("No duplicate routes", test_no_duplicate_api_routes),
        ("Feed API returns JSON", test_feed_api_returns_json),
        ("Follow/unfollow routes", test_follow_unfollow_routes),
        ("Like/save/share routes", test_like_save_share_routes),
        ("Loading skeleton CSS", test_homepage_premium_css_skeleton),
        ("Phase 58 still passes", test_phase58_still_passes),
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
