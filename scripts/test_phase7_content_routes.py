from io import BytesIO
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ["DATABASE_URL"] = ""

from app import app


PROFILE_ID = "11111111-1111-4111-8111-111111111111"
AUTH_ID = "22222222-2222-4222-8222-222222222222"


def _login(client):
    with client.session_transaction() as session:
        session["auth_user_id"] = AUTH_ID
        session["user_id"] = AUTH_ID
        session["profile_id"] = PROFILE_ID
        session["auth_email"] = "phase7@example.com"
        session["email"] = "phase7@example.com"
        session["username"] = "phase7"
        session["full_name"] = "Phase Seven"
        session["profile_completed"] = True
        session["dev_profile_fallback"] = True
        session["dev_profile"] = {
            "id": PROFILE_ID,
            "auth_user_id": AUTH_ID,
            "username": "phase7",
            "full_name": "Phase Seven",
            "display_name": "Phase Seven",
            "profile_completed": True,
        }


def _assert_ok(label, response, statuses=(200, 201, 302)):
    if response.status_code not in statuses:
        body = response.get_data(as_text=True)[:500]
        raise AssertionError(f"{label}: expected {statuses}, got {response.status_code}: {body}")
    print(f"{label}: {response.status_code}")


def run():
    app.config["TESTING"] = True
    client = app.test_client()
    _login(client)

    response = client.post(
        "/posts/create",
        data={
            "caption": "Building CHAIN in Namibia #tech #socialapp",
            "town_tag": "Windhoek",
            "visibility": "public",
        },
        follow_redirects=False,
    )
    _assert_ok("create post route", response, statuses=(302,))

    response = client.post(
        "/media/upload",
        data={
            "upload_type": "post",
            "media": (BytesIO(b"\x89PNG\r\n\x1a\nphase7"), "phase7.png"),
        },
        content_type="multipart/form-data",
    )
    _assert_ok("upload media route", response, statuses=(201,))

    response = client.post(
        "/reels/upload",
        data={
            "caption": "Short update #socialapp",
            "music_title": "Original sound",
            "visibility": "public",
            "video": (BytesIO(b"\x00\x00\x00\x18ftypmp42phase7"), "phase7.mp4"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    _assert_ok("create reel route", response, statuses=(302,))

    response = client.post(
        "/status/create",
        data={
            "caption": "Story from Windhoek #tech",
            "visibility": "public",
        },
        follow_redirects=False,
    )
    _assert_ok("create story route", response, statuses=(302,))

    response = client.get("/search?q=%23tech")
    _assert_ok("hashtag/search route", response)
    assert "#tech" in response.get_data(as_text=True).lower()

    response = client.get("/")
    _assert_ok("homepage feed route", response)
    home = response.get_data(as_text=True).lower()
    assert "building chain" in home
    assert "short update" in home

    response = client.get("/profile/")
    _assert_ok("profile content route", response)
    profile = response.get_data(as_text=True).lower()
    assert "building chain" in profile


if __name__ == "__main__":
    run()
