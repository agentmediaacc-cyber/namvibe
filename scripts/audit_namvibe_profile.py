"""Audit NamVibe production profile page wiring."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def read(rel):
    with open(os.path.join(ROOT, rel), "r") as f:
        return f.read()


def render_sample_profile():
    import api_routes.profile_routes as routes
    import services.social_action_policy as policy
    from app import app

    profile = {
        "id": "profile-audit",
        "auth_user_id": "auth-audit",
        "username": "moon",
        "display_name": "Moon Creator",
        "full_name": "Moon Creator",
        "bio": "Real creator profile.",
        "created_at": "2026-01-01T00:00:00+00:00",
        "email_verified": True,
        "phone_verified": False,
        "is_verified": False,
        "visibility": "public",
    }

    routes.get_current_profile = lambda: None
    routes.get_profile_by_username = lambda username: profile if username == "moon" else None
    routes.record_profile_view = lambda *args, **kwargs: None
    routes.get_profile_bundle = lambda **kwargs: {
        "profile": profile,
        "stats": {"posts": 0, "reels": 0, "followers": 0, "following": 0, "likes": 0, "views": 0},
        "content": {"posts": [], "reels": [], "rooms": [], "stories": [], "marketplace": []},
        "wallet": {},
        "creator_tools": {},
        "presence": {"status": "offline", "last_seen": None},
        "marketplace": {"items": []},
    }
    routes.build_profile_dashboard = lambda **kwargs: {}
    policy.get_action_policy = lambda viewer_id, target: {"can_view_full_profile": True, "can_view_posts": True, "can_view_reels": True, "can_view_media": True}
    policy.can_view_profile = lambda viewer_id, target: {"can_view_full_profile": True}

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        return client.get("/profile/@moon").get_data(as_text=True)


def run():
    print("=" * 60)
    print("NAMVIBE PROFILE AUDIT")
    print("=" * 60)

    base = read("templates/base.html")
    tpl = read("templates/profile/index.html")
    base_profile = read("templates/profile/base_profile.html")
    css = read("static/css/namvibe_profile_pro.css")
    js = read("static/js/namvibe_profile_pro.js")
    completion = read("services/profile_completion_service.py")
    view_service = read("services/profile_view_service.py")

    html = render_sample_profile()

    check("no duplicate tab groups in rendered HTML", html.count('data-profile-tabbar') == 1)
    check('no visible "Reconnecting..." string in rendered profile HTML', "Reconnecting..." not in html)
    check("base reconnect debug text removed", "Reconnecting... <button" not in base)
    check("avatar fallback exists", "data-avatar-fallback=\"initials\"" in tpl and "nv-avatar-fallback" in css)
    check("cover fallback exists", "nv-cover-fallback" in tpl and "nv-cover-fallback" in css)

    from services.profile_completion_service import calculate_profile_completion
    pct = calculate_profile_completion({"username": "moon", "full_name": "Moon"}).get("percent")
    check("completion score service returns 0-100", isinstance(pct, int) and 0 <= pct <= 100)
    check("weighted completion model present", "COMPLETION_WEIGHTS" in completion and '"avatar": 15' in completion)
    check("shop tab hidden when no shop", "has_shop" in view_service and "{% if pv.has_shop %}" in tpl)
    check("Saved/Liked hidden from visitors", "{% if own_profile %}" in tpl and "saved-panel" in tpl and "liked-panel" in tpl)
    check("Dashboard hidden from visitors unless owner/creator", "show_dashboard_tab" in view_service and "{% if pv.show_dashboard_tab %}" in tpl)
    check("verification statuses are state based", "state" in view_service and "nv-trust-row {{ item.state }}" in tpl)
    check("mobile CSS exists", "@media (max-width: 640px)" in css and "overflow-x: auto" in css)
    check("template compiles", "Moon Creator" in html and "data-profile-completion-card" not in html)
    check("new profile assets loaded", "namvibe_profile_pro.css" in base_profile and "namvibe_profile_pro.js" in base_profile and "data-profile-tabbar" in tpl)
    check("profile JS handles tabs", "data-tab-target" in js and "data-tab-panel" in js)

    total = PASS + FAIL
    print(f"\nNAMVIBE PROFILE AUDIT: {'PASS' if FAIL == 0 else 'FAIL'} ({PASS}/{total})")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
