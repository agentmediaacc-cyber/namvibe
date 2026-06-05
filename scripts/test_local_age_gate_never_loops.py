import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    os.environ["FLASK_ENV"] = "development"
    os.environ["ENV"] = "development"
    os.environ["CHAIN_FAST_LOCAL"] = "1"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    auth_user_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    profile = {
        "id": profile_id,
        "auth_user_id": auth_user_id,
        "email": "local-age-loop@example.com",
        "username": "local_age_loop",
        "full_name": "Local Age Loop",
        "display_name": "Local Age Loop",
        "date_of_birth": None,
        "profile_completed": True,
        "is_verified": False,
        "email_verified": False,
        "wallet_balance": 0,
    }

    bundle = {
        "profile": profile,
        "stats": {"followers": 0, "following": 0, "likes": 0, "views": 0, "posts": 0, "reels": 0, "stories": 0, "rooms": 0},
        "content": {"posts": [], "reels": [], "rooms": [], "stories": [], "marketplace": [], "albums": []},
        "activity": {"rooms": [], "posts": [], "stories": [], "gifts": [], "favorites": [], "recent_views": []},
        "wallet": {"coin_balance": 0, "gift_earnings": 0, "pending_withdrawal": 0},
        "creator_tools": {},
        "actions": [],
        "presence": {"status": "offline"},
        "is_following": False,
        "is_page_liked": False,
    }

    dashboard = {
        "profile": {**profile, "chain_score": 0, "rank": "New Member", "profile_theme": "Dark Premium"},
        "viewer": profile,
        "stats": bundle["stats"],
        "content": bundle["content"],
        "wallet": bundle["wallet"],
        "creator": {},
        "marketplace": {"items": [], "featured_products": []},
        "dating": {},
        "achievements": [],
        "calls": {},
        "live": {"go_live_url": "/live/studio"},
        "ai": {},
        "portfolio": {"skills": []},
        "reputation": {},
        "completion": {"percentage": 100, "missing_fields": []},
        "permissions": {"can_message": True, "can_call": True, "can_contact_email": True},
        "presence": {"status": "offline"},
        "actions": [],
        "activity": {},
        "public_stats": {"posts": 0, "followers": 0, "reels": 0, "likes": 0},
        "level": {"title": "New Member", "score": 0, "next_target": 10, "progress_pct": 0},
        "pinned": {"posts": [], "reels": [], "products": []},
        "contact": {"message": True, "call": True, "email": True, "whatsapp": False},
        "theme_options": [],
    }

    with client.session_transaction() as sess:
        sess["auth_user_id"] = auth_user_id
        sess["user_id"] = auth_user_id
        sess["profile_id"] = profile_id
        sess["auth_email"] = profile["email"]
        sess["email"] = profile["email"]
        sess["username"] = profile["username"]
        sess["full_name"] = profile["full_name"]
        sess["age_check_required"] = True

    patches = [
        patch("api_routes.profile_routes.get_current_profile", return_value=profile),
        patch("services.profile_service.get_current_profile", return_value=profile),
        patch("api_routes.profile_routes.is_profile_complete", return_value=True),
        patch("api_routes.profile_routes.get_profile_bundle", return_value=bundle),
        patch("api_routes.profile_routes.build_profile_dashboard", return_value=dashboard),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
        patch("api_routes.profile_routes.best_effort_age_dob_update", return_value=True),
    ]

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        first_profile = client.get("/profile/", follow_redirects=False)
        print("first_profile_status", first_profile.status_code)
        print("first_profile_location", first_profile.headers.get("Location"))
        assert first_profile.status_code == 200
        assert first_profile.headers.get("Location") is None
        with client.session_transaction() as sess:
            assert sess.get("age_verified") is True
            assert sess.get("age_check_required") is False

        age_post = client.post("/profile/age-check", data={"date_of_birth": "30/06/1995"}, follow_redirects=False)
        print("age_post_status", age_post.status_code)
        print("age_post_location", age_post.headers.get("Location"))
        assert age_post.status_code == 302
        assert age_post.headers.get("Location") == "/profile/"
        with client.session_transaction() as sess:
            assert sess.get("age_verified") is True
            assert sess.get("age_check_required") is False
            assert sess.get("date_of_birth") == "1995-06-30"

        second_profile = client.get("/profile/", follow_redirects=False)
        print("second_profile_status", second_profile.status_code)
        print("second_profile_location", second_profile.headers.get("Location"))
        assert second_profile.status_code == 200
        assert second_profile.headers.get("Location") is None


if __name__ == "__main__":
    main()
