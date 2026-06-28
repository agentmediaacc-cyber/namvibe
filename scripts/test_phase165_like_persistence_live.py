#!/usr/bin/env python3
"""Phase 165 live proof for like persistence."""

import io
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
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
        sess["access_token"] = f"phase165-like-{profile['username']}"


def create_profile(username_prefix, display_name):
    profile_id = str(uuid.uuid4())
    auth_user_id = str(uuid.uuid4())
    username = f"{username_prefix}_{suffix()}"
    email = f"{username}@test.local"
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, username, display_name, email,
            profile_visibility, followers_count, following_count, created_at
        ) VALUES (%s, %s, %s, %s, %s, 'public', 0, 0, now())
        """,
        (profile_id, auth_user_id, username, display_name, email),
    )
    return {
        "id": profile_id,
        "auth_user_id": auth_user_id,
        "username": username,
        "display_name": display_name,
        "email": email,
    }


def db_one(sql, params):
    rows = fast_query(sql, params, default=[])
    return rows[0] if rows else {}


def post_multipart(client, path, data):
    return client.post(path, data=data, content_type="multipart/form-data")


def make_photo_file():
    return (io.BytesIO(PNG_BYTES), "phase165_like.png")


def cleanup(profile_ids):
    for profile_id in profile_ids:
        try:
            write_query("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (profile_id, profile_id))
            write_query("DELETE FROM chain_post_reactions WHERE profile_id = %s", (profile_id,))
            write_query("DELETE FROM chain_posts WHERE profile_id = %s", (profile_id,))
            write_query("DELETE FROM chain_profiles WHERE id = %s", (profile_id,))
        except Exception:
            pass


def main():
    print("=" * 80)
    print("PHASE 165 LIKE PERSISTENCE LIVE")
    print("=" * 80)

    profiles = []
    try:
        with flask_app.app_context():
            owner = create_profile("phase165_owner", "Phase165 Owner")
            viewer = create_profile("phase165_viewer", "Phase165 Viewer")
            profiles.extend([owner["id"], viewer["id"]])

            client_owner = flask_app.test_client()
            client_viewer = flask_app.test_client()
            login(client_owner, owner)
            login(client_viewer, viewer)

            create_resp = post_multipart(
                client_owner,
                "/api/posts/create",
                {
                    "caption": f"phase165 like post {suffix()}",
                    "visibility": "public",
                    "media": make_photo_file(),
                },
            )
            create_json = create_resp.get_json(silent=True) or {}
            post_id = ((create_json.get("post") or {}).get("id")) if create_json.get("ok") else None
            post_row = db_one(
                "SELECT id, profile_id, likes_count, caption, media_url FROM chain_posts WHERE id = %s",
                (post_id,),
            ) if post_id else {}
            print_step(
                1,
                "create owner + viewer and owner creates post",
                "POST /api/posts/create",
                create_resp.status_code,
                create_json,
                post_row,
                create_resp.status_code == 201 and bool(post_row.get("id")),
            )

            like_resp = client_viewer.post(f"/api/social/post/{post_id}/like")
            like_json = like_resp.get_json(silent=True) or {}
            like_db = {
                "reaction_row": db_one(
                    """
                    SELECT profile_id, post_id, reaction_type, created_at
                    FROM chain_post_reactions
                    WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like'
                    """,
                    (viewer["id"], post_id),
                ),
                "post_counts": db_one(
                    "SELECT likes_count FROM chain_posts WHERE id = %s",
                    (post_id,),
                ),
            }
            print_step(
                2,
                "viewer likes the post",
                f"POST /api/social/post/{post_id}/like",
                like_resp.status_code,
                like_json,
                like_db,
                like_resp.status_code == 200 and like_json.get("success") is True and like_json.get("liked") is True,
            )

            refreshed_home = client_owner.get("/api/homepage/feed?tab=for_you&limit=20")
            refreshed_home_json = refreshed_home.get_json(silent=True) or {}
            refreshed_detail = client_owner.get(f"/post/{post_id}")
            feed_items = ((refreshed_home_json.get("payload") or {}).get("feed_items")) or []
            feed_post = next((item for item in feed_items if item.get("id") == post_id), {})
            notif_rows = fast_query(
                """
                SELECT event_type, actor_profile_id, recipient_profile_id, entity_type, entity_id, action_url
                FROM chain_notifications
                WHERE recipient_profile_id = %s AND entity_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (owner["id"], post_id),
                default=[],
            )
            persistence_db = {
                "post_row": db_one(
                    "SELECT likes_count FROM chain_posts WHERE id = %s",
                    (post_id,),
                ),
                "feed_post": feed_post,
                "detail_contains_count": str(like_json.get("count")) in refreshed_detail.data.decode("utf-8", "ignore"),
                "notifications": notif_rows,
            }
            print_step(
                3,
                "verify API success + DB row + persisted count after refresh + notification",
                f"GET /api/homepage/feed?tab=for_you&limit=20 and GET /post/{post_id}",
                {"feed": refreshed_home.status_code, "detail": refreshed_detail.status_code},
                {
                    "feed_post": feed_post,
                    "detail_snippet": refreshed_detail.data.decode("utf-8", "ignore")[:500],
                },
                persistence_db,
                refreshed_home.status_code == 200
                and refreshed_detail.status_code == 200
                and int((persistence_db["post_row"] or {}).get("likes_count") or 0) >= 1
                and int((feed_post or {}).get("likes_count") or 0) >= 1
                and any(row.get("event_type") == "post_like" for row in notif_rows),
            )
    finally:
        cleanup(profiles)

    print("\nPASS: phase165 like persistence live proof completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
