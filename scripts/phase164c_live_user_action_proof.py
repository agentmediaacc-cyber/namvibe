#!/usr/bin/env python3
"""Phase 164C live user-action proof."""

import io
import json
import os
import sys
import uuid
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"
os.environ["WTF_CSRF_ENABLED"] = "0"

from app import app as flask_app
from services.engagement_service import follow_profile
from services.neon_service import fast_query, write_query

flask_app.config["WTF_CSRF_ENABLED"] = False


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xdd\xb8\x0b\x00\x00\x00\x00IEND\xaeB`\x82"
)
MP4_BYTES = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08free\x00\x00\x00\x08mdat"
)


def new_suffix():
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
        sess["access_token"] = f"phase164c-{profile['username']}"


def create_profile(username_prefix, display_name, visibility="public"):
    profile_id = str(uuid.uuid4())
    auth_user_id = str(uuid.uuid4())
    username = f"{username_prefix}_{new_suffix()}"
    email = f"{username}@test.local"
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, username, display_name, email,
            profile_visibility, followers_count, following_count, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, 0, 0, now())
        """,
        (profile_id, auth_user_id, username, display_name, email, visibility),
    )
    return {
        "id": profile_id,
        "auth_user_id": auth_user_id,
        "username": username,
        "display_name": display_name,
        "email": email,
        "visibility": visibility,
    }


def db_one(sql, params, default=None):
    rows = fast_query(sql, params, default=[])
    if rows:
        return rows[0]
    return default or {}


def post_multipart(client, path, data):
    return client.post(path, data=data, content_type="multipart/form-data")


def make_photo_file():
    return (io.BytesIO(PNG_BYTES), "phase164c_photo.png")


def make_video_file():
    return (io.BytesIO(MP4_BYTES), "phase164c_reel.mp4")


def cleanup(profile_ids):
    try:
        for profile_id in profile_ids:
            write_query("UPDATE chain_status_posts SET deleted_at = now() WHERE profile_id = %s AND deleted_at IS NULL", (profile_id,))
            write_query("UPDATE chain_reels SET deleted_at = now() WHERE profile_id = %s AND deleted_at IS NULL", (profile_id,))
            write_query("UPDATE chain_posts SET deleted_at = now() WHERE profile_id = %s AND deleted_at IS NULL", (profile_id,))
            write_query("UPDATE chain_profiles SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL", (profile_id,))
    except Exception:
        pass


@contextmanager
def test_clients():
    yield flask_app.test_client(), flask_app.test_client(), flask_app.test_client()


def main():
    print("=" * 80)
    print("PHASE 164C LIVE USER ACTION PROOF")
    print("=" * 80)

    profiles = []
    try:
        with flask_app.app_context():
            user_a = create_profile("phase164c_a", "Phase164C User A", visibility="public")
            user_b = create_profile("phase164c_b", "Phase164C User B", visibility="public")
            user_c = create_profile("phase164c_c", "Phase164C User C", visibility="public")
            profiles.extend([user_a["id"], user_b["id"], user_c["id"]])

            with test_clients() as (client_a, client_b, client_c):
                login(client_a, user_a)
                login(client_b, user_b)
                login(client_c, user_c)

                follow_result = follow_profile(user_b["id"], user_a["id"], toggle=False)
                follow_db = db_one(
                    """
                    SELECT follower_profile_id, following_profile_id
                    FROM chain_follows
                    WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL
                    """,
                    (user_b["id"], user_a["id"]),
                )
                print_step(
                    1,
                    "Login/create User A and User B",
                    "DB create profiles A/B/C + session login + follow_profile(B -> A)",
                    "N/A",
                    {
                        "user_a": user_a["username"],
                        "user_b": user_b["username"],
                        "user_c": user_c["username"],
                        "follow_result": follow_result,
                    },
                    {"follow_row": follow_db},
                    bool(follow_db),
                )

                post_caption = f"phase164c photo post {new_suffix()}"
                resp = post_multipart(
                    client_a,
                    "/api/posts/create",
                    {
                        "caption": post_caption,
                        "visibility": "public",
                        "media": make_photo_file(),
                    },
                )
                post_json = resp.get_json(silent=True) or {}
                post_id = ((post_json.get("post") or {}).get("id")) if post_json.get("ok") else None
                post_db = db_one(
                    """
                    SELECT id, profile_id, caption, media_url, visibility, likes_count, comments_count
                    FROM chain_posts WHERE id = %s
                    """,
                    (post_id,),
                ) if post_id else {}
                print_step(
                    2,
                    "User A creates a photo post",
                    "POST /api/posts/create",
                    resp.status_code,
                    post_json,
                    post_db,
                    resp.status_code == 201 and bool(post_db.get("media_url")),
                )

                resp = client_b.post(f"/api/social/post/{post_id}/like")
                like_json = resp.get_json(silent=True) or {}
                like_db = {
                    "reaction_row": db_one(
                        """
                        SELECT profile_id, post_id, reaction_type
                        FROM chain_post_reactions
                        WHERE profile_id = %s AND post_id = %s AND reaction_type = 'like'
                        """,
                        (user_b["id"], post_id),
                    ),
                    "post_row": db_one(
                        "SELECT likes_count FROM chain_posts WHERE id = %s",
                        (post_id,),
                    ),
                }
                print_step(
                    3,
                    "User B likes the post",
                    f"POST /api/social/post/{post_id}/like",
                    resp.status_code,
                    like_json,
                    like_db,
                    resp.status_code == 200 and like_json.get("liked") is True,
                )

                verified_like_db = {
                    "reaction_count": db_one(
                        "SELECT COUNT(*) AS count FROM chain_post_reactions WHERE post_id = %s AND reaction_type = 'like'",
                        (post_id,),
                    ),
                    "post_counts": db_one(
                        "SELECT likes_count FROM chain_posts WHERE id = %s",
                        (post_id,),
                    ),
                }
                like_count_ok = (
                    verified_like_db["reaction_count"].get("count", 0) >= 1
                    and verified_like_db["post_counts"].get("likes_count", 0) >= 1
                )
                print_step(
                    4,
                    "Verify like count + DB row",
                    "SELECT chain_post_reactions + chain_posts.likes_count",
                    "N/A",
                    {"verified_like_count": verified_like_db["post_counts"].get("likes_count", 0)},
                    verified_like_db,
                    like_count_ok,
                )

                comment_body = f"phase164c comment {new_suffix()}"
                resp = client_b.post(
                    f"/api/social/post/{post_id}/comments",
                    json={"body": comment_body},
                )
                comment_json = resp.get_json(silent=True) or {}
                comment_id = ((comment_json.get("comment") or {}).get("id")) if comment_json.get("success") else None
                comment_db = {
                    "comment_row": db_one(
                        """
                        SELECT id, profile_id, post_id, body
                        FROM chain_post_comments
                        WHERE post_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (post_id,),
                    ),
                    "post_row": db_one(
                        "SELECT comments_count FROM chain_posts WHERE id = %s",
                        (post_id,),
                    ),
                }
                print_step(
                    5,
                    "User B comments",
                    f"POST /api/social/post/{post_id}/comments",
                    resp.status_code,
                    comment_json,
                    comment_db,
                    resp.status_code == 201 and bool(comment_db["comment_row"]),
                )

                verified_comment_db = {
                    "comment_count": db_one(
                        "SELECT COUNT(*) AS count FROM chain_post_comments WHERE post_id = %s",
                        (post_id,),
                    ),
                    "post_counts": db_one(
                        "SELECT comments_count FROM chain_posts WHERE id = %s",
                        (post_id,),
                    ),
                }
                comment_count_ok = (
                    verified_comment_db["comment_count"].get("count", 0) >= 1
                    and verified_comment_db["post_counts"].get("comments_count", 0) >= 1
                )
                print_step(
                    6,
                    "Verify comment count + DB row",
                    "SELECT chain_post_comments + chain_posts.comments_count",
                    "N/A",
                    {"verified_comment_count": verified_comment_db["post_counts"].get("comments_count", 0)},
                    verified_comment_db,
                    comment_count_ok,
                )

                resp = client_a.get("/api/notifications?grouped=0&limit=20")
                notif_json = resp.get_json(silent=True) or {}
                notif_db = fast_query(
                    """
                    SELECT event_type, actor_profile_id, entity_type, entity_id
                    FROM chain_notifications
                    WHERE recipient_profile_id = %s AND entity_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (user_a["id"], post_id),
                    default=[],
                )
                notif_types = {row.get("event_type") for row in notif_db}
                print_step(
                    7,
                    "Verify User A notification",
                    "GET /api/notifications?grouped=0&limit=20",
                    resp.status_code,
                    notif_json,
                    {"notifications": notif_db},
                    resp.status_code == 200
                    and ("post_like" in notif_types or "post_liked" in notif_types)
                    and ("comment" in notif_types or "post_comment" in notif_types or "post_commented" in notif_types),
                )

                story_caption = f"phase164c story {new_suffix()}"
                resp = client_a.post(
                    "/status/api/status/create",
                    data={
                        "caption": story_caption,
                        "visibility": "followers",
                        "media_type": "text",
                        "text_content": story_caption,
                        "music_title": "Phase164C",
                        "music_artist": "Proof",
                        "music_duration_seconds": "90",
                        "music_start_seconds": "0",
                    },
                )
                story_json = resp.get_json(silent=True) or {}
                story_id = ((story_json.get("story") or {}).get("id")) if story_json.get("ok") else None
                story_db = db_one(
                    """
                    SELECT id, profile_id, visibility, text_content, music_title, music_artist, music_duration_seconds
                    FROM chain_status_posts WHERE id = %s
                    """,
                    (story_id,),
                ) if story_id else {}
                print_step(
                    8,
                    "User A creates story with music_duration_seconds <= 90",
                    "POST /status/api/status/create",
                    resp.status_code,
                    story_json,
                    story_db,
                    resp.status_code == 201 and int(story_db.get("music_duration_seconds", 0) or 0) <= 90,
                )

                resp = client_a.get("/api/stories/feed")
                own_story_feed_json = resp.get_json(silent=True) or {}
                own_story_feed = own_story_feed_json.get("stories") or []
                own_story_db = db_one(
                    "SELECT id, profile_id FROM chain_status_posts WHERE id = %s",
                    (story_id,),
                )
                print_step(
                    9,
                    "Verify User A sees story",
                    "GET /api/stories/feed",
                    resp.status_code,
                    own_story_feed_json,
                    own_story_db,
                    resp.status_code == 200 and any(item.get("id") == story_id for item in own_story_feed),
                )

                resp = client_b.get(f"/api/stories/{story_id}")
                follower_story_json = resp.get_json(silent=True) or {}
                follower_story_db = db_one(
                    """
                    SELECT follower_profile_id, following_profile_id
                    FROM chain_follows
                    WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL
                    """,
                    (user_b["id"], user_a["id"]),
                )
                print_step(
                    10,
                    "Verify follower User B sees story",
                    f"GET /api/stories/{story_id}",
                    resp.status_code,
                    follower_story_json,
                    follower_story_db,
                    resp.status_code == 200 and (follower_story_json.get("story") or {}).get("id") == story_id,
                )

                resp = client_c.get(f"/api/stories/{story_id}")
                non_follower_json = resp.get_json(silent=True) or {}
                non_follower_feed = client_c.get("/api/stories/feed").get_json(silent=True) or {}
                non_follower_db = {
                    "follow_row": db_one(
                        """
                        SELECT follower_profile_id, following_profile_id
                        FROM chain_follows
                        WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL
                        """,
                        (user_c["id"], user_a["id"]),
                    ),
                    "feed_count": len(non_follower_feed.get("stories") or []),
                }
                print_step(
                    11,
                    "Verify non-follower does not",
                    f"GET /api/stories/{story_id} and GET /api/stories/feed",
                    {"detail": resp.status_code, "feed": 200},
                    {"detail": non_follower_json, "feed": non_follower_feed},
                    non_follower_db,
                    resp.status_code == 403 and not any(item.get("id") == story_id for item in (non_follower_feed.get("stories") or [])),
                )

                reel_caption = f"phase164c reel {new_suffix()}"
                resp = post_multipart(
                    client_a,
                    "/api/reels/create",
                    {
                        "caption": reel_caption,
                        "visibility": "public",
                        "video": make_video_file(),
                    },
                )
                reel_json = resp.get_json(silent=True) or {}
                reel_id = reel_json.get("reel_id") if reel_json.get("ok") else None
                reel_db = db_one(
                    """
                    SELECT id, profile_id, caption, media_url, video_url, visibility, processing_status
                    FROM chain_reels WHERE id = %s
                    """,
                    (reel_id,),
                ) if reel_id else {}
                print_step(
                    12,
                    "User A creates reel",
                    "POST /api/reels/create",
                    resp.status_code,
                    reel_json,
                    reel_db,
                    resp.status_code == 201 and bool(reel_db.get("video_url") or reel_db.get("media_url")),
                )

                homepage_resp = client_a.get("/api/homepage/feed?tab=for_you&limit=20")
                homepage_json = homepage_resp.get_json(silent=True) or {}
                reels_feed = ((homepage_json.get("payload") or {}).get("reels")) or []
                detail_resp = client_a.get(f"/reels/{reel_id}")
                profile_resp = client_a.get("/reels/profile/reels")
                reel_proof = {
                    "homepage_has_reel": any(item.get("id") == reel_id for item in reels_feed),
                    "detail_status": detail_resp.status_code,
                    "profile_status": profile_resp.status_code,
                    "profile_contains_reel": reel_caption in (profile_resp.data.decode("utf-8", "ignore")) or reel_id in (profile_resp.data.decode("utf-8", "ignore")),
                    "db_row": db_one(
                        "SELECT id, caption, profile_id FROM chain_reels WHERE id = %s",
                        (reel_id,),
                    ),
                }
                print_step(
                    13,
                    "Verify reel appears in homepage feed, /reels detail, and profile reels",
                    f"GET /api/homepage/feed + GET /reels/{reel_id} + GET /reels/profile/reels",
                    {
                        "homepage": homepage_resp.status_code,
                        "detail": detail_resp.status_code,
                        "profile_reels": profile_resp.status_code,
                    },
                    {
                        "homepage": {"reels_found": reel_proof["homepage_has_reel"], "reel_count": len(reels_feed)},
                        "detail_snippet": detail_resp.data.decode("utf-8", "ignore")[:300],
                        "profile_snippet": profile_resp.data.decode("utf-8", "ignore")[:300],
                    },
                    reel_proof,
                    reel_proof["homepage_has_reel"] and detail_resp.status_code == 200 and profile_resp.status_code == 200 and reel_proof["profile_contains_reel"],
                )

    finally:
        cleanup(profiles)

    print("\nPASS: phase164c live user action proof completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
