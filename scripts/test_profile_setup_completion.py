import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from services.neon_service import fetch_one


def main():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    auth_user_id = str(uuid.uuid4())
    username = f"devsetup_{uuid.uuid4().hex[:10]}"
    email = f"{username}@example.com"

    with client.session_transaction() as sess:
        sess["auth_user_id"] = auth_user_id
        sess["user_id"] = auth_user_id
        sess["access_token"] = "dev-token"
        sess["auth_email"] = email
        sess["email"] = email
        sess["username"] = username
        sess["full_name"] = "Dev Setup User"

    onboarding_get = client.get("/profile/onboarding", follow_redirects=False)
    print("onboarding_get_status", onboarding_get.status_code)

    form = {
        "full_name": "Dev Setup User",
        "display_name": "Dev Setup User",
        "username": username,
        "email": email,
        "phone": "+264811234567",
        "date_of_birth": "1990-01-01",
        "gender": "Prefer not to say",
        "country_of_birth": "Namibia",
        "country_origin": "Namibia",
        "region": "Khomas",
        "town": "Windhoek",
        "current_location": "Windhoek, Namibia",
        "current_residential_location": "Windhoek, Namibia",
        "residential_address": "1 Independence Avenue",
        "bio": "Testing CHAIN onboarding completion flow.",
        "website": "https://chain.example/profile",
        "skills": "Content Creation,Live Hosting,Community",
        "profile_theme": "Namibia Gold",
        "profile_visibility": "public",
        "allow_messages": "on",
        "allow_video_calls": "on",
        "allow_audio_calls": "on",
        "dating_mode_enabled": "on",
        "relationship_status": "Single",
        "looking_for": "Friends,Networking",
        "interests": "Tech,Media,Creators",
        "languages": "English,Oshiwambo",
        "profile_type": "creator",
        "onboarding_step": "complete",
    }

    onboarding_post = client.post("/profile/onboarding", data=form, follow_redirects=False)
    print("onboarding_post_status", onboarding_post.status_code)
    print("onboarding_post_location", onboarding_post.headers.get("Location"))
    assert onboarding_post.status_code == 302, onboarding_post.get_data(as_text=True)[:500]
    assert (onboarding_post.headers.get("Location") or "").endswith("/profile/")

    row = None
    for _ in range(5):
        row = fetch_one(
            "SELECT id, auth_user_id, username, profile_completed, onboarding_step FROM chain_profiles WHERE auth_user_id = %s LIMIT 1",
            [auth_user_id],
            timeout_ms=5000,
        )
        if row:
            break
        time.sleep(0.5)
    print("profile_row_exists", bool(row))
    print("profile_completed", bool((row or {}).get("profile_completed")))
    print("onboarding_step", (row or {}).get("onboarding_step"))
    assert row and row.get("id")
    assert row.get("auth_user_id") == auth_user_id

    with client.session_transaction() as sess:
        print("session_profile_id", sess.get("profile_id"))
        print("session_user_id", sess.get("user_id"))
        print("session_auth_user_id", sess.get("auth_user_id"))
        assert sess.get("profile_id") == row.get("id")
        assert sess.get("user_id") == auth_user_id
        assert sess.get("auth_user_id") == auth_user_id

    profile_response = client.get("/profile/", follow_redirects=False)
    print("profile_status", profile_response.status_code)
    print("profile_location", profile_response.headers.get("Location"))
    body = profile_response.get_data(as_text=True)
    print("profile_contains_ui", ("CHAIN Score" in body) or ("Social Feed" in body) or ("Creator Dashboard" in body))

    debug_response = client.get("/dev/profile-debug")
    debug_payload = debug_response.get_json() or {}
    print("debug_status", debug_response.status_code)
    print("debug_current_profile", bool(debug_payload.get("current_profile")))
    print("debug_bundle", bool(debug_payload.get("profile_bundle")))


if __name__ == "__main__":
    main()
