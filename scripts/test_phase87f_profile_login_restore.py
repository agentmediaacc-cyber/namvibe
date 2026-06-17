#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}{' - ' + detail if detail else ''}")
    if not ok:
        raise AssertionError(name)


PROFILE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "auth_user_id": "22222222-2222-2222-2222-222222222222",
    "email": "phase87f@example.com",
    "normalized_email": "phase87f@example.com",
    "username": "phase87f",
    "username_slug": "phase87f",
    "handle": "phase87f",
    "full_name": "Phase 87F",
    "display_name": "Phase 87F",
    "bio": "",
    "profile_completed": True,
    "date_of_birth": "1990-01-01",
    "email_verified": True,
    "is_verified": True,
    "created_at": "2026-01-01T00:00:00+00:00",
    "followers_count": 4,
    "following_count": 3,
    "friends_count": 2,
    "posts_count": 1,
    "reels_count": 1,
    "total_likes": 7,
    "profile_views": 9,
    "chain_score": 42,
}


def fake_fast_query(sql, params=None, **kwargs):
    text = " ".join(str(sql).lower().split())
    params = tuple(params or ())
    if "information_schema.columns" in text:
        return [{"column_name": key} for key in PROFILE.keys()]
    if "from chain_profiles" in text:
        needle_values = {str(value).strip().lower().lstrip("@") for value in params if value is not None}
        profile_values = {
            PROFILE["email"],
            PROFILE["normalized_email"],
            PROFILE["username"],
            PROFILE["username_slug"],
            PROFILE["handle"],
            PROFILE["auth_user_id"],
            PROFILE["id"],
        }
        if needle_values.intersection({str(value).lower().lstrip("@") for value in profile_values}):
            return [dict(PROFILE)]
    return kwargs.get("default", [])


def fake_bundle(*args, **kwargs):
    return {
        "profile": dict(PROFILE),
        "stats": {
            "posts": 1,
            "reels": 1,
            "followers": 4,
            "following": 3,
            "friends": 2,
            "likes": 7,
            "views": 9,
            "visitors_this_week": 5,
        },
        "content": {"posts": [], "reels": [], "rooms": [], "stories": []},
        "wallet": {},
        "creator": {},
        "marketplace": {"items": [], "featured_products": []},
        "dating": {},
        "portfolio": {"skills": []},
        "ai": {},
        "live": {"go_live_url": "/live/studio"},
        "reputation": {},
        "pinned": {"posts": [], "reels": [], "products": []},
        "public_stats": {"posts": 1, "followers": 4, "reels": 1, "likes": 7},
        "completion": {"percentage": 100, "missing_fields": []},
        "level": {"title": "New Member", "score": 42, "progress_pct": 20},
        "presence": {"status": "offline"},
        "contact": {"message": True, "call": True, "email": True},
        "is_following": False,
    }


def main():
    from services.neon_service import get_cached_table_columns, is_circuit_open
    from services import auth_service

    check("is_circuit_open import works", callable(is_circuit_open))
    check("get_cached_table_columns import works", callable(get_cached_table_columns))

    with patch("services.auth_service.fast_query", side_effect=fake_fast_query), \
         patch("services.auth_service.get_cached_table_columns", return_value=set(PROFILE.keys())), \
         patch("services.auth_service.safe_select", return_value=[]), \
         patch("services.auth_service.get_auth_user_by_email", return_value=None):
        by_email = auth_service._find_login_profile(" PHASE87F@example.com ")
        by_username = auth_service._find_login_profile("@phase87f")
        check("login lookup finds existing profile by email", bool(by_email and by_email["id"] == PROFILE["id"]))
        check("login lookup finds existing profile by username", bool(by_username and by_username["id"] == PROFILE["id"]))

    with patch("services.auth_service._find_login_profile", return_value=dict(PROFILE)), \
         patch("services.auth_service.get_supabase") as supabase:
        supabase.return_value.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
        ok, message = auth_service.login_chain_user("phase87f@example.com", "wrong-password")
        check("no account not found for existing email", ok is False and "account not found" not in str(message).lower(), message)

    import app as app_module
    check("app imports successfully", callable(getattr(app_module, "create_app", None)))

    from flask import Flask
    from api_routes.auth_routes import auth_bp
    from api_routes.profile_routes import profile_bp
    from api_routes.social_routes import social_bp

    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY="phase87f-test", APP_NAME="NamVibe")
    app.jinja_env.filters["datetime"] = lambda value: str(value)[:10] if value else ""
    app.jinja_env.filters["hashtag_links"] = lambda value: value or ""
    app.jinja_env.globals["csrf_token"] = lambda: "phase87f"
    app.jinja_env.globals["apk_csrf_token"] = lambda path="": "phase87f"
    app.context_processor(lambda: {"APP_NAME": "NamVibe", "current_year": 2026})
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(social_bp, url_prefix="/social")
    client = app.test_client()

    login_get = client.get("/auth/login")
    check("/auth/login GET returns 200", login_get.status_code == 200, str(login_get.status_code))

    patches = [
        patch("api_routes.profile_routes.get_current_profile", return_value=dict(PROFILE)),
        patch("api_routes.profile_routes.get_profile_by_id", return_value=dict(PROFILE)),
        patch("api_routes.profile_routes.get_profile_by_username", return_value=dict(PROFILE)),
        patch("api_routes.profile_routes.get_profile_bundle", side_effect=fake_bundle),
        patch("api_routes.profile_routes.build_profile_dashboard", return_value={}),
        patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)),
        patch("api_routes.profile_routes.is_profile_complete", return_value=True),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
    ]
    for item in patches:
        item.start()
    try:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["profile_id"] = PROFILE["id"]
            sess["auth_user_id"] = PROFILE["auth_user_id"]
            sess["user_id"] = PROFILE["auth_user_id"]
            sess["email"] = PROFILE["email"]
            sess["auth_email"] = PROFILE["email"]
            sess["username"] = PROFILE["username"]

        profile_resp = client.get("/profile/")
        check("/profile/ with valid session returns 200", profile_resp.status_code == 200, str(profile_resp.status_code))
        check("/profile/ does not redirect login", "/auth/login" not in profile_resp.location if profile_resp.location else True)

        public_resp = client.get("/profile/@phase87f")
        check("/profile/@username returns 200", public_resp.status_code == 200, str(public_resp.status_code))

        html = profile_resp.get_data(as_text=True)
        for label in ("Posts", "Reels", "Followers", "Following", "Friends"):
            check(f"profile page contains clickable card: {label}", label in html and "stat-card" in html)
        check("followers link uses /social/@username", "/social/@phase87f/followers" in html)
        check("following link uses /social/@username", "/social/@phase87f/following" in html)
        check("friends link uses /social/@username", "/social/@phase87f/friends" in html)

        template = (ROOT / "templates/profile/index.html").read_text()
        check("old /followers /following /friends links not used in profile template",
              all(old not in template for old in ('href="/followers"', 'href="/following"', 'href="/friends"')))
    finally:
        for item in reversed(patches):
            item.stop()

    route_text = "\n".join(str(rule) for rule in app.url_map.iter_rules())
    check("profile and social routes registered", "/profile/" in route_text and "/social/@<username>/followers" in route_text)


if __name__ == "__main__":
    main()
