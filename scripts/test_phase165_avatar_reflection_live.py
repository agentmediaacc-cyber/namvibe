#!/usr/bin/env python3
"""Phase 165 live proof for avatar reflection."""

import io
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_ENV"] = "production"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"
os.environ["WTF_CSRF_ENABLED"] = "0"

from app import app as flask_app
from services.neon_service import fast_query, write_query

flask_app.config["WTF_CSRF_ENABLED"] = False

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xdd\xb8\x0b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def suffix():
    return uuid.uuid4().hex[:10]


def print_step(step_no, title, command, http_status, json_response, db_proof, passed):
    print(f"\nSTEP {step_no}: {title}")
    print(f"COMMAND: {command}")
    print(f"HTTP STATUS: {http_status}")
    print("JSON RESPONSE:")
    print(json.dumps(json_response, indent=2, default=str)[:4000])
    print("DB PROOF:")
    print(json.dumps(db_proof, indent=2, default=str)[:4000])
    print("PASS" if passed else "FAIL")
    if not passed:
        raise SystemExit(1)


def login(client, profile):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = profile["auth_user_id"]
        sess["profile_id"] = profile["id"]
        sess["user_id"] = profile["id"]
        sess["username"] = profile["username"]
        sess["full_name"] = profile["display_name"]
        sess["logged_in"] = True
        sess["email"] = profile["email"]
        sess["profile_completed"] = True
        sess["age_verified"] = True
        sess["age_check_required"] = False
        sess["access_token"] = f"phase165-avatar-{profile['username']}"


def create_profile(prefix, display_name, profile_photo):
    profile_id = str(uuid.uuid4())
    auth_user_id = str(uuid.uuid4())
    username = f"{prefix}_{suffix()}"
    email = f"{username}@test.local"
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, username, display_name, email,
            avatar_url, profile_photo, profile_visibility,
            followers_count, following_count, created_at
        ) VALUES (%s, %s, %s, %s, %s, NULL, %s, 'public', 0, 0, now())
        """,
        (profile_id, auth_user_id, username, display_name, email, profile_photo),
    )
    return {
        "id": profile_id,
        "auth_user_id": auth_user_id,
        "username": username,
        "display_name": display_name,
        "email": email,
        "profile_photo": profile_photo,
    }


def db_one(sql, params):
    rows = fast_query(sql, params, default=[])
    return rows[0] if rows else {}


def make_photo_file():
    return (io.BytesIO(PNG_BYTES), "phase165_avatar.png")


def post_multipart(client, path, data):
    return client.post(path, data=data, content_type="multipart/form-data")


def cleanup(profile_ids):
    for profile_id in profile_ids:
        try:
            write_query("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (profile_id, profile_id))
            write_query("DELETE FROM chain_post_reactions WHERE profile_id = %s", (profile_id,))
            write_query("DELETE FROM chain_post_comments WHERE profile_id = %s", (profile_id,))
            write_query("DELETE FROM chain_posts WHERE profile_id = %s", (profile_id,))
            write_query("DELETE FROM chain_profiles WHERE id = %s", (profile_id,))
        except Exception:
            pass


def main():
    print("=" * 80)
    print("PHASE 165 AVATAR REFLECTION LIVE")
    print("=" * 80)
    profiles = []
    try:
        with flask_app.app_context():
            owner = create_profile(
                "phase165_avatar_owner",
                "Phase165 Avatar Owner",
                f"https://example.com/{suffix()}-owner.png",
            )
            viewer = create_profile(
                "phase165_avatar_viewer",
                "Phase165 Avatar Viewer",
                f"https://example.com/{suffix()}-viewer.png",
            )
            profiles.extend([owner["id"], viewer["id"]])

            client_owner = flask_app.test_client()
            client_viewer = flask_app.test_client()
            login(client_owner, owner)
            login(client_viewer, viewer)

            create_resp = post_multipart(
                client_owner,
                "/api/posts/create",
                {
                    "caption": f"phase165 avatar post {suffix()}",
                    "visibility": "public",
                    "media": make_photo_file(),
                },
            )
            create_json = create_resp.get_json(silent=True) or {}
            post_id = ((create_json.get("post") or {}).get("id")) if create_json.get("ok") else None
            print_step(
                1,
                "create user with profile picture and create post",
                "POST /api/posts/create",
                create_resp.status_code,
                create_json,
                {
                    "owner_profile": db_one(
                        "SELECT id, avatar_url, profile_photo FROM chain_profiles WHERE id = %s",
                        (owner["id"],),
                    ),
                    "post": db_one(
                        "SELECT id, profile_id FROM chain_posts WHERE id = %s",
                        (post_id,),
                    ) if post_id else {},
                },
                create_resp.status_code == 201 and bool(post_id),
            )

            feed_resp = client_viewer.get("/api/homepage/feed?limit=20")
            feed_json = feed_resp.get_json(silent=True) or {}
            feed_items = ((feed_json.get("payload") or {}).get("feed_items")) or []
            feed_post = next((item for item in feed_items if item.get("id") == post_id), {})
            print_step(
                2,
                "verify homepage feed payload includes avatar_url",
                "GET /api/homepage/feed?limit=20",
                feed_resp.status_code,
                {"feed_post": feed_post},
                {
                    "owner_profile": db_one(
                        "SELECT id, avatar_url, profile_photo FROM chain_profiles WHERE id = %s",
                        (owner["id"],),
                    ),
                },
                feed_resp.status_code == 200
                and bool(feed_post)
                and feed_post.get("avatar_url") == owner["profile_photo"],
            )

            comment_body = f"phase165 avatar comment {suffix()}"
            comment_resp = client_viewer.post(
                f"/api/social/post/{post_id}/comments",
                json={"body": comment_body},
            )
            comment_json = comment_resp.get_json(silent=True) or {}
            comments_resp = client_owner.get(f"/api/social/post/{post_id}/comments")
            comments_json = comments_resp.get_json(silent=True) or {}
            comment_item = ((comments_json.get("comments") or [])[-1: ] or [{}])[0]
            print_step(
                3,
                "verify comment payload includes avatar_url",
                f"POST /api/social/post/{post_id}/comments and GET /api/social/post/{post_id}/comments",
                {"post": comment_resp.status_code, "list": comments_resp.status_code},
                {"comment_create": comment_json, "comment_item": comment_item},
                {
                    "viewer_profile": db_one(
                        "SELECT id, avatar_url, profile_photo FROM chain_profiles WHERE id = %s",
                        (viewer["id"],),
                    ),
                    "comment_row": db_one(
                        """
                        SELECT id, profile_id, post_id, body
                        FROM chain_post_comments
                        WHERE profile_id = %s AND post_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (viewer["id"], post_id),
                    ),
                },
                comment_resp.status_code == 201
                and comment_json.get("success") is True
                and comments_resp.status_code == 200
                and comment_item.get("avatar_url") == viewer["profile_photo"],
            )

            like_resp = client_viewer.post(f"/api/social/post/{post_id}/like")
            like_json = like_resp.get_json(silent=True) or {}
            notif_resp = client_owner.get("/api/notifications?grouped=0&limit=20")
            notif_json = notif_resp.get_json(silent=True) or {}
            items = notif_json.get("items") or []
            notif_item = next((item for item in items if item.get("actor_profile_id") == viewer["id"] and item.get("entity_id") == post_id), {})
            print_step(
                4,
                "verify notification payload includes sender avatar",
                f"POST /api/social/post/{post_id}/like and GET /api/notifications?grouped=0&limit=20",
                {"like": like_resp.status_code, "notifications": notif_resp.status_code},
                {"like": like_json, "notification": notif_item},
                {
                    "viewer_profile": db_one(
                        "SELECT id, avatar_url, profile_photo FROM chain_profiles WHERE id = %s",
                        (viewer["id"],),
                    ),
                    "notification_row": db_one(
                        """
                        SELECT event_type, actor_profile_id, recipient_profile_id, entity_id
                        FROM chain_notifications
                        WHERE recipient_profile_id = %s AND actor_profile_id = %s AND entity_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (owner["id"], viewer["id"], post_id),
                    ),
                },
                like_resp.status_code == 200
                and like_json.get("success") is True
                and notif_resp.status_code == 200
                and notif_item.get("sender_avatar_url") == viewer["profile_photo"],
            )

            profile_resp = client_viewer.get(f"/profile/@{owner['username']}")
            profile_html = profile_resp.data.decode("utf-8", "ignore")
            home_resp = client_viewer.get("/")
            home_html = home_resp.data.decode("utf-8", "ignore")
            print_step(
                5,
                "verify profile page and homepage preview render avatar or initials",
                f"GET /profile/@{owner['username']} and GET /",
                {"profile": profile_resp.status_code, "home": home_resp.status_code},
                {
                    "profile_contains_avatar": owner["profile_photo"] in profile_html,
                    "home_contains_avatar": owner["profile_photo"] in home_html,
                },
                {
                    "owner_profile": db_one(
                        "SELECT id, avatar_url, profile_photo FROM chain_profiles WHERE id = %s",
                        (owner["id"],),
                    ),
                },
                profile_resp.status_code == 200
                and home_resp.status_code == 200
                and owner["profile_photo"] in profile_html
                and owner["profile_photo"] in home_html,
            )
    finally:
        cleanup(profiles)

    print("\nPASS: phase165 avatar reflection live proof completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
