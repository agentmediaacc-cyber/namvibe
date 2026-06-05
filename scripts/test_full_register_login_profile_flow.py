import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    email = f"fullflow_{uuid.uuid4().hex[:10]}@example.com"
    username = f"fullflow_{uuid.uuid4().hex[:8]}"
    password = "Password123!"
    fake_rows = {}

    def fake_ensure_profile(uid, defaults=None):
        defaults = defaults or {}
        row = fake_rows.get(uid)
        if not row:
            row = {
                "id": str(uuid.uuid4()),
                "auth_user_id": uid,
                "email": defaults.get("email"),
                "normalized_email": defaults.get("normalized_email") or defaults.get("email"),
                "username": defaults.get("username"),
                "full_name": defaults.get("full_name"),
                "display_name": defaults.get("display_name") or defaults.get("full_name"),
                "phone": defaults.get("phone"),
                "country_origin": defaults.get("country_origin"),
                "current_country": defaults.get("current_country") or defaults.get("country"),
                "country": defaults.get("country") or defaults.get("current_country"),
                "current_location": defaults.get("current_location"),
                "region": defaults.get("region"),
                "town": defaults.get("town"),
                "email_verified": False,
                "is_verified": False,
                "profile_completed": True,
                "wallet_balance": 0,
            }
            fake_rows[uid] = row
        row.update({key: value for key, value in defaults.items() if value is not None})
        row["auth_user_id"] = uid
        return row, None

    def fake_update_profile(profile_id, payload):
        for row in fake_rows.values():
            if row.get("id") == profile_id:
                row.update({key: value for key, value in payload.items() if value is not None})
                return row
        return None

    def fake_safe_select(table, columns="*", limit=20, filters=None, order_by="created_at", desc=True):
        if table != "chain_profiles":
            return []
        filters = filters or {}
        for row in fake_rows.values():
            if all(row.get(key) == value for key, value in filters.items()):
                return [row]
        return []

    def fake_current_profile():
        profile_id = None
        with client.session_transaction() as sess:
            profile_id = sess.get("profile_id")
        if profile_id:
            for row in fake_rows.values():
                if row.get("id") == profile_id:
                    return row
        return next(iter(fake_rows.values()), None)

    def fake_profile_bundle(profile_id=None, username=None, viewer=None):
        profile = None
        for row in fake_rows.values():
            if row.get("id") == profile_id or row.get("username") == username:
                profile = row
                break
        if not profile:
            return None
        return {
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

    def fake_dashboard(profile=None, viewer=None, bundle=None):
        profile = (bundle or {}).get("profile") or profile or {}
        return {
            "profile": {**profile, "chain_score": 0, "rank": "New Member", "profile_theme": "Dark Premium"},
            "viewer": viewer or profile,
            "stats": (bundle or {}).get("stats", {}),
            "content": (bundle or {}).get("content", {}),
            "wallet": (bundle or {}).get("wallet", {}),
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

    supabase = MagicMock()
    supabase.auth.sign_up.return_value = SimpleNamespace(
        user=SimpleNamespace(id=auth_user_id, email=email, user_metadata={}),
        session=None,
    )
    supabase.auth.sign_in_with_password.side_effect = Exception("email not confirmed")

    form = {
        "email": email,
        "password": password,
        "confirm_password": password,
        "username": username,
        "full_name": "Full Flow Tester",
        "phone_code": "+264",
        "phone": "811234567",
        "country_origin": "Namibia",
        "current_country": "Namibia",
        "region": "Khomas",
        "town": "Windhoek",
        "agreement_true_details": "on",
        "agreement_identity_use": "on",
        "agreement_username_privacy": "on",
        "agreement_standards": "on",
        "agreement_no_abuse": "on",
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
    }

    patches = [
        patch("services.auth_service.get_supabase", return_value=supabase),
        patch("services.auth_service.get_auth_user_by_email", return_value=None),
        patch("services.auth_service.safe_select", side_effect=fake_safe_select),
        patch("services.auth_service._supabase_auth_email_exists", return_value=False),
        patch("services.auth_service._profile_exists_by_username", return_value=False),
        patch("services.auth_service.ensure_neon_profile", side_effect=fake_ensure_profile),
        patch("services.auth_service._ensure_profile_dependencies", return_value=None),
        patch("services.profile_service._neon_update_profile", side_effect=fake_update_profile),
        patch("services.profile_service.get_profile_by_username", side_effect=lambda value: next((row for row in fake_rows.values() if row.get("username") == value), None)),
        patch("services.profile_service.get_profile_by_id", side_effect=lambda value: next((row for row in fake_rows.values() if row.get("id") == value), None)),
        patch("services.profile_service.get_current_profile", side_effect=fake_current_profile),
        patch("api_routes.profile_routes.get_current_profile", side_effect=fake_current_profile),
        patch("api_routes.profile_routes.get_profile_bundle", side_effect=fake_profile_bundle),
        patch("api_routes.profile_routes.build_profile_dashboard", side_effect=fake_dashboard),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
        patch("api_routes.profile_routes.best_effort_age_dob_update", side_effect=lambda profile_id, auth_id, dob: bool(fake_update_profile(profile_id, {"date_of_birth": dob}))),
    ]

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15]:
        get_register = client.get("/auth/register")
        print("get_register_status", get_register.status_code)
        assert get_register.status_code == 200

        register_response = client.post("/auth/register", data=form, follow_redirects=False)
        print("register_status", register_response.status_code)
        print("register_location", register_response.headers.get("Location"))
        assert register_response.status_code == 302, register_response.get_data(as_text=True)[:500]
        assert register_response.headers.get("Location") == "/profile/"

        with client.session_transaction() as sess:
            print("session_auth_user_id", sess.get("auth_user_id"))
            print("session_user_id", sess.get("user_id"))
            print("session_profile_id", sess.get("profile_id"))
            print("session_email", sess.get("email"))
            assert sess.get("auth_user_id") == auth_user_id
            assert sess.get("user_id") == auth_user_id
            assert sess.get("profile_id")
            assert sess.get("email") == email

        profile_response = client.get("/profile/", follow_redirects=False)
        print("profile_first_status", profile_response.status_code)
        print("profile_first_location", profile_response.headers.get("Location"))
        assert profile_response.status_code in (200, 302)
        if profile_response.status_code == 302:
            assert "/profile/age-check" in profile_response.headers.get("Location", "")

        age_response = client.post("/profile/age-check", data={"date_of_birth": "30/06/1995"}, follow_redirects=False)
        print("age_check_status", age_response.status_code)
        print("age_check_location", age_response.headers.get("Location"))
        assert age_response.status_code == 302
        assert age_response.headers.get("Location") == "/profile/"
        with client.session_transaction() as sess:
            assert sess.get("age_verified") is True
            assert sess.get("age_check_required") is False
            assert sess.get("date_of_birth") == "1995-06-30"

        profile_after_age = client.get("/profile/", follow_redirects=False)
        profile_body = profile_after_age.get_data(as_text=True)
        print("profile_after_age_status", profile_after_age.status_code)
        assert profile_after_age.status_code == 200, profile_body[:500]

        client.get("/auth/logout")
        username_login = client.post("/auth/login", data={"login_id": username, "password": password}, follow_redirects=False)
        print("username_login_status", username_login.status_code)
        print("username_login_location", username_login.headers.get("Location"))
        assert username_login.status_code == 302
        assert username_login.headers.get("Location") == "/profile/"

        client.get("/auth/logout")
        email_login = client.post("/auth/login", data={"login_id": email, "password": password}, follow_redirects=False)
        print("email_login_status", email_login.status_code)
        print("email_login_location", email_login.headers.get("Location"))
        assert email_login.status_code == 302
        assert email_login.headers.get("Location") == "/profile/"

        profile_final = client.get("/profile/", follow_redirects=False)
        final_body = profile_final.get_data(as_text=True)
        print("profile_final_status", profile_final.status_code)
        print("profile_final_contains_not_verified", "Not Verified" in final_body)
        assert profile_final.status_code == 200, final_body[:500]
        assert "Not Verified" in final_body


if __name__ == "__main__":
    main()
