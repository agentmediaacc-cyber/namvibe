#!/usr/bin/env python3
"""Phase 165 live proof for notification payloads."""

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
        sess["access_token"] = f"phase165-notif-{profile['username']}"


def create_profile(prefix, display_name):
    profile_id = str(uuid.uuid4())
    auth_user_id = str(uuid.uuid4())
    username = f"{prefix}_{suffix()}"
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


def make_photo_file():
    return (io.BytesIO(PNG_BYTES), "phase165_notif.png")


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
    print("PHASE 165 NOTIFICATION PAYLOAD LIVE")
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
                {"caption": f"phase165 notif post {suffix()}", "visibility": "public", "media": make_photo_file()},
            )
            create_json = create_resp.get_json(silent=True) or {}
            post_id = ((create_json.get("post") or {}).get("id")) if create_json.get("ok") else None
            print_step(1, "owner creates post", "POST /api/posts/create", create_resp.status_code, create_json, {"post_id": post_id}, create_resp.status_code == 201 and bool(post_id))

            like_resp = client_viewer.post(f"/api/social/post/{post_id}/like")
            like_json = like_resp.get_json(silent=True) or {}
            print_step(2, "viewer likes post", f"POST /api/social/post/{post_id}/like", like_resp.status_code, like_json, {"post_reaction": db_one("SELECT post_id FROM chain_post_reactions WHERE post_id = %s LIMIT 1", (post_id,))}, like_resp.status_code == 200 and like_json.get("success") is True)

            comment_body = f"phase165 notification comment {suffix()}"
            comment_resp = client_viewer.post(f"/api/social/post/{post_id}/comments", json={"body": comment_body})
            comment_json = comment_resp.get_json(silent=True) or {}
            print_step(3, "viewer comments on post", f"POST /api/social/post/{post_id}/comments", comment_resp.status_code, comment_json, {"post_comment": db_one("SELECT body FROM chain_post_comments WHERE post_id = %s ORDER BY created_at DESC LIMIT 1", (post_id,))}, comment_resp.status_code == 201 and comment_json.get("success") is True)

            unread_before_resp = client_owner.get("/api/notifications/unread-count")
            unread_before_json = unread_before_resp.get_json(silent=True) or {}
            notif_resp = client_owner.get("/api/notifications?grouped=0&limit=20")
            notif_json = notif_resp.get_json(silent=True) or {}
            items = notif_json.get("items") or []
            like_item = next((item for item in items if item.get("event_type") == "post_like" and item.get("entity_id") == post_id), {})
            comment_item = next((item for item in items if item.get("event_type") == "comment" and item.get("entity_id") == post_id), {})
            payload_db = fast_query(
                """
                SELECT event_type, actor_profile_id, entity_type, entity_id, action_url, is_read
                FROM chain_notifications
                WHERE recipient_profile_id = %s AND entity_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (owner["id"], post_id),
                default=[],
            )
            print_step(
                4,
                "fetch owner notifications and verify payload",
                "GET /api/notifications/unread-count and GET /api/notifications?grouped=0&limit=20",
                {"unread": unread_before_resp.status_code, "list": notif_resp.status_code},
                {"unread": unread_before_json, "items": items[:5]},
                {"notifications": payload_db},
                notif_resp.status_code == 200
                and unread_before_resp.status_code == 200
                and int(unread_before_json.get("count") or 0) >= 2
                and like_item.get("sender_display_name")
                and ("sender_avatar_url" in like_item or like_item.get("sender_initials"))
                and like_item.get("action_text") == "liked your post"
                and like_item.get("open_url") == f"/post/{post_id}"
                and comment_item.get("action_text") == "commented on your post"
                and comment_item.get("preview_text") == comment_body
                and comment_item.get("open_url") == f"/post/{post_id}#comments",
            )

            first_notif_id = (items[0] or {}).get("id") if items else None
            mark_read_resp = client_owner.post(f"/api/notifications/{first_notif_id}/read")
            mark_read_json = mark_read_resp.get_json(silent=True) or {}
            mark_read_db = db_one("SELECT is_read FROM chain_notifications WHERE id = %s", (first_notif_id,))
            print_step(
                5,
                "verify mark read works",
                f"POST /api/notifications/{first_notif_id}/read",
                mark_read_resp.status_code,
                mark_read_json,
                mark_read_db,
                mark_read_resp.status_code == 200 and mark_read_json.get("ok") is True and mark_read_db.get("is_read") is True,
            )

            mark_all_resp = client_owner.post("/api/notifications/read-all")
            mark_all_json = mark_all_resp.get_json(silent=True) or {}
            mark_all_db = db_one(
                "SELECT COUNT(*) AS unread_count FROM chain_notifications WHERE recipient_profile_id = %s AND is_read = FALSE AND deleted_at IS NULL",
                (owner["id"],),
            )
            print_step(
                6,
                "verify mark all read works",
                "POST /api/notifications/read-all",
                mark_all_resp.status_code,
                mark_all_json,
                mark_all_db,
                mark_all_resp.status_code == 200 and mark_all_json.get("ok") is True and int(mark_all_db.get("unread_count") or 0) == 0,
            )
    finally:
        cleanup(profiles)
    print("\nPASS: phase165 notification payload live proof completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
