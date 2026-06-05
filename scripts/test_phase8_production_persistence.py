import os
import sys
import uuid
from io import BytesIO

os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["ENV"] = os.environ.get("ENV") or "production"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app
from services.content_service import ensure_content_schema, upload_folder_status, verify_content_tables
from services.neon_service import fast_query, write_query


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _assert_status(label, response, statuses=(200, 201, 302)):
    _assert(response.status_code in statuses, f"{label}: expected {statuses}, got {response.status_code}: {response.get_data(as_text=True)[:500]}")
    print(f"{label}: {response.status_code}")


def _create_test_profile():
    profile_id = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    username = f"phase8_{uuid.uuid4().hex[:10]}"
    rows = write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, email, username, display_name, full_name, profile_completed, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, now())
        RETURNING id, auth_user_id, username
        """,
        (profile_id, auth_id, f"{username}@example.com", username, "Phase 8 Persistence", "Phase 8 Persistence"),
        timeout_ms=8000,
    )
    _assert(rows, "could not create production persistence test profile")
    return rows[0]


def _login(client, profile):
    with client.session_transaction() as session:
        session["auth_user_id"] = str(profile["auth_user_id"])
        session["user_id"] = str(profile["auth_user_id"])
        session["profile_id"] = str(profile["id"])
        session["username"] = profile["username"]
        session["email"] = f"{profile['username']}@example.com"
        session["auth_email"] = f"{profile['username']}@example.com"
        session["full_name"] = "Phase 8 Persistence"
        session["profile_completed"] = True
        session["age_verified"] = True
        session["age_check_required"] = False


def run():
    schema = ensure_content_schema()
    _assert(not schema.get("skipped"), "schema bootstrap skipped; production persistence test requires Neon mode")
    _assert(schema.get("ok"), f"schema bootstrap incomplete: {schema}")

    tables = verify_content_tables()
    _assert(tables.get("ok"), f"missing content tables: {tables.get('missing')}")
    folders = upload_folder_status()
    _assert(all(item["exists"] and item["writable"] for item in folders.values()), f"upload folders not ready: {folders}")

    profile = _create_test_profile()
    hashtag = f"phase8_{uuid.uuid4().hex[:8]}"
    caption = f"Phase 8 production post #{hashtag}"
    reel_caption = f"Phase 8 production reel #{hashtag}"
    story_caption = f"Phase 8 production story #{hashtag}"

    app.config["TESTING"] = True
    client = app.test_client()
    _login(client, profile)

    response = client.post(
        "/posts/create",
        data={
            "caption": caption,
            "link_url": "https://www.namvibe.com/",
            "town_tag": "Windhoek",
            "visibility": "public",
        },
        follow_redirects=False,
    )
    _assert_status("create post", response, statuses=(302,))
    post_rows = fast_query("SELECT id FROM chain_posts WHERE profile_id = %s AND caption = %s LIMIT 1", (profile["id"], caption), timeout_ms=5000, default=[])
    _assert(post_rows, "post did not persist in Neon")

    response = client.get("/")
    _assert_status("reload homepage", response)
    post_after_home = fast_query("SELECT id FROM chain_posts WHERE profile_id = %s AND caption = %s LIMIT 1", (profile["id"], caption), timeout_ms=5000, default=[])
    _assert(post_after_home, "post was not persistent after homepage reload")

    response = client.post(
        "/reels/upload",
        data={
            "caption": reel_caption,
            "music_title": "Phase 8 Original Sound",
            "visibility": "public",
            "video": (BytesIO(b"\x00\x00\x00\x18ftypmp42phase8"), "phase8.mp4"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    _assert_status("create reel", response, statuses=(302,))
    reel_rows = fast_query("SELECT id FROM chain_reels WHERE profile_id = %s AND caption = %s LIMIT 1", (profile["id"], reel_caption), timeout_ms=5000, default=[])
    _assert(reel_rows, "reel did not persist in Neon")

    response = client.get("/reels/")
    _assert_status("reload reels page", response)
    reel_after_reload = fast_query("SELECT id FROM chain_reels WHERE profile_id = %s AND caption = %s LIMIT 1", (profile["id"], reel_caption), timeout_ms=5000, default=[])
    _assert(reel_after_reload, "reel was not persistent after reels page reload")

    response = client.post(
        "/status/create",
        data={"caption": story_caption, "visibility": "public"},
        follow_redirects=False,
    )
    _assert_status("create story", response, statuses=(302,))
    story_rows = fast_query(
        "SELECT id FROM chain_status_posts WHERE profile_id = %s AND caption = %s AND expires_at > now() LIMIT 1",
        (profile["id"], story_caption),
        timeout_ms=5000,
        default=[],
    )
    _assert(story_rows, "active story did not persist in Neon")

    response = client.get(f"/search?q=%23{hashtag}")
    _assert_status("search hashtag", response)
    _assert(hashtag in response.get_data(as_text=True).lower(), "hashtag not searchable after content creation")

    response = client.post(
        "/media/upload",
        data={"upload_type": "post", "media": (BytesIO(b"\x89PNG\r\n\x1a\nphase8"), "phase8.png")},
        content_type="multipart/form-data",
    )
    _assert_status("create media upload record", response, statuses=(201,))
    media_rows = fast_query("SELECT id FROM chain_media_uploads WHERE profile_id = %s ORDER BY created_at DESC LIMIT 1", (profile["id"],), timeout_ms=5000, default=[])
    _assert(media_rows, "media upload metadata did not persist in Neon")

    response = client.post(
        "/media/upload",
        data={"upload_type": "post", "media": (BytesIO(b"not allowed"), "phase8.exe")},
        content_type="multipart/form-data",
    )
    _assert_status("reject unsupported media", response, statuses=(400,))

    print("phase8 production persistence: passed")


if __name__ == "__main__":
    run()
