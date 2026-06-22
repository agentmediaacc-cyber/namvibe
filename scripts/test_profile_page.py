"""Route-level smoke test for the NamVibe profile page."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def install_profile_fakes():
    import api_routes.profile_routes as routes
    import services.social_action_policy as policy

    profile = {
        "id": "profile-test",
        "auth_user_id": "auth-test",
        "username": "moon",
        "display_name": "Moon Creator",
        "full_name": "Moon Creator",
        "bio": "Building NamVibe from Windhoek.",
        "town": "Windhoek",
        "region": "Khomas",
        "country": "Namibia",
        "created_at": "2026-01-01T00:00:00+00:00",
        "email_verified": True,
        "phone_verified": False,
        "identity_verified": False,
        "visibility": "public",
    }

    routes.get_current_profile = lambda: profile
    routes.get_profile_by_username = lambda username: profile if username == "moon" else None
    routes.record_profile_view = lambda *args, **kwargs: None
    routes.verify_profile_age = lambda viewer: (True, None)
    routes.is_profile_complete = lambda viewer: True
    routes.get_my_notifications = lambda: ([], [], 0)
    routes.get_profile_bundle = lambda **kwargs: {
        "profile": profile,
        "stats": {"posts": 0, "reels": 0, "followers": 0, "following": 0, "friends": 0, "likes": 0, "views": 0},
        "content": {"posts": [], "reels": [], "rooms": [], "stories": [], "marketplace": []},
        "wallet": {"coin_balance": 0, "gift_earnings": 0, "pending_withdrawal": 0},
        "creator_tools": {"studio_enabled": True},
        "presence": {"status": "offline", "last_seen": None},
        "marketplace": {"items": []},
    }
    routes.build_profile_dashboard = lambda **kwargs: {}
    policy.get_action_policy = lambda viewer_id, target: {"can_view_full_profile": True, "can_view_posts": True, "can_view_reels": True, "can_view_media": True}
    policy.can_view_profile = lambda viewer_id, target: {"can_view_full_profile": True}
    return profile


def run():
    print("=" * 60)
    print("PROFILE PAGE TEST")
    print("=" * 60)

    from app import app

    profile = install_profile_fakes()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["profile_id"] = profile["id"]
            sess["auth_user_id"] = profile["auth_user_id"]
            sess["user_id"] = profile["auth_user_id"]
            sess["username"] = profile["username"]
            sess["age_check_required"] = False
        response = client.get("/profile/")
        html = response.get_data(as_text=True)

    check("profile page returns 200", response.status_code == 200, f"status={response.status_code}")
    check("username rendered", "@moon" in html)
    check("no duplicate tabs", html.count("data-profile-tabbar") == 1)
    check("no debug reconnect text", "Reconnecting..." not in html and "Close</button>" not in html)
    check("profile completion card exists", "data-profile-completion-card" in html)
    check("avatar fallback rendered", "data-avatar-fallback=\"initials\"" in html)
    check("cover fallback rendered", "data-cover-fallback=\"1\"" in html)

    total = PASS + FAIL
    print(f"\nPROFILE PAGE TEST: {'PASS' if FAIL == 0 else 'FAIL'} ({PASS}/{total})")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
