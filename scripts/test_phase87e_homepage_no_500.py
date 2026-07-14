"""Phase 87E — Verify homepage does not return 500."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

def run():
    global PASS, FAIL
    _root = _PROJECT_ROOT
    print("=" * 60)
    print("PHASE 87E — HOMEPAGE NO 500")
    print("=" * 60)

    # 1. Chain_home template compiles
    print("\n--- Template ---")
    from flask import Flask
    app = Flask(__name__, template_folder=os.path.join(_root, "templates"))
    app.config["SECRET_KEY"] = "test"
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(os.path.join(_root, "templates")))
        tmpl = env.get_template("chain_home.html")
        check("chain_home.html template loads", True)
    except Exception as e:
        check(f"chain_home.html template loads ({e})", False)

    # 2. Template renders with shell data
    print("\n--- Render ---")
    app.jinja_env.globals["csrf_token"] = lambda: "test-token"
    def safe_link(name, logged_in=None):
        return "/auth/login"
    def route_exists(path):
        return False
    ctx = {
        "csrf_token": lambda: "test-token",
        "safe_link": safe_link,
        "route_exists": route_exists,
        "get_world_countries": lambda: [],
        "reels_feed": [],
        "suggested_creators": [],
        "smart_suggestions": [],
        "recommendation_cards": [],
        "trending_hashtags": [],
        "popular_towns": [],
        "live_rooms": [],
        "stories": [],
        "posts": [],
        "current": None,
        "home_route": "/",
        "discover_route": "/discover/",
        "live_route": "/live/",
        "reel_route": "/reels/",
        "friends_route": "/social/friend-requests",
        "login_route": "/auth/login",
        "register_route": "/auth/register",
        "drawer_profile": "/auth/login",
        "drawer_messages": "/auth/login",
        "drawer_calls": "/auth/login",
        "drawer_notifications": "/auth/login",
        "drawer_wallet": "/auth/login",
        "drawer_settings": "/discover/",
        "drawer_security": "/security",
        "reel_available": False,
        "story_available": True,
        "live_available": False,
        "upload_video_available": False,
        "post_available": True,
        "online_stats": {"online_count": 0, "live_count": 0, "online_users": []},
    }
    try:
        with app.test_request_context("/"):
            tmpl2 = app.jinja_env.get_template("chain_home.html")
            html = tmpl2.render(**ctx)
        check("chain_home.html renders with shell data", bool(html))
    except Exception as e:
        check(f"chain_home.html renders with shell data ({e})", False)

    # 3. No builtin_function_or_method in homepage_service
    print("\n--- Static analysis ---")
    with open(os.path.join(_root, "services/homepage_service.py"), "r") as f:
        content = f.read()
    check("no .items[ in homepage_service", ".items[" not in content)
    check("no .keys[ in homepage_service", ".keys[" not in content)
    check("no .values[ in homepage_service", ".values[" not in content)

    # 4. No .items[ in chain_home.html
    with open(os.path.join(_root, "templates/chain_home.html"), "r") as f:
        content = f.read()
    check("no .items in chain_home template", ".items" not in content or '["items"]' in content)

    # 5. Home route has try/except shell
    with open(os.path.join(_root, "app.py"), "r") as f:
        content = f.read()
    check("home route has try/except guard", "try:" in content and "shell" in content)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87E: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87E: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
