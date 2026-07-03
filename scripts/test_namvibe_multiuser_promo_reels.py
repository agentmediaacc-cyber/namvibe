#!/usr/bin/env python3
"""Generate 5 NamVibe promo reels and verify multi-user visibility/interactions."""

import io
import json
import os
import sys
import time
import uuid
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("ALLOW_LOCAL_AUTH_FALLBACK", "true")
os.environ.setdefault("WTF_CSRF_ENABLED", "0")

from app import app as flask_app
from services.neon_service import fast_query, write_query

flask_app.config["WTF_CSRF_ENABLED"] = False

CREDS_PATH = ROOT / "secrets" / "test_credentials.json"
OUTPUT_DIR = ROOT / "static" / "media" / "samples" / "promos"
TEST_PREFIX = "PROMO_MULTI_"

UPLOAD_USER = "chain_star"
VIEWER_USERS = ["chain_moon", "chain_gold", "chain_million", "chain_premium"]

RESULTS = {"pass": 0, "fail": 0, "warn": 0}


def ok(msg):
    RESULTS["pass"] += 1
    print(f"  PASS  {msg}")


def fail(msg):
    RESULTS["fail"] += 1
    print(f"  FAIL  {msg}")


def warn(msg):
    RESULTS["warn"] += 1
    print(f"  WARN  {msg}")


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(f"{label} {detail}".rstrip())


def print_step(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def load_credentials():
    if not CREDS_PATH.exists():
        raise SystemExit("Missing secrets/test_credentials.json. Run seed_chain_test_users.py first.")
    data = json.loads(CREDS_PATH.read_text())
    resolved = {}
    for username in [UPLOAD_USER] + VIEWER_USERS:
        cred = data.get(username) or {}
        if not cred.get("profile_id"):
            raise SystemExit(f"Missing profile_id for {username} in secrets/test_credentials.json")
        resolved[username] = {
            "username": cred.get("username") or username,
            "profile_id": cred["profile_id"],
            "auth_user_id": cred.get("auth_user_id"),
            "email": cred.get("email"),
            "full_name": cred.get("full_name") or username,
        }
    return resolved


def login(client, identity):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = identity["auth_user_id"]
        sess["profile_id"] = identity["profile_id"]
        sess["user_id"] = identity["profile_id"]
        sess["username"] = identity["username"]
        sess["full_name"] = identity["full_name"]
        sess["auth_email"] = identity["email"]
        sess["email"] = identity["email"]
        sess["logged_in"] = True
        sess["profile_completed"] = True
        sess["age_verified"] = True
        sess["age_check_required"] = False
        sess["access_token"] = f"promo-{identity['username']}"


def generate_video_bytes(index):
    import numpy as np
    try:
        from moviepy import VideoClip
    except ImportError:
        from moviepy.editor import VideoClip

    duration = 1.4
    fps = 12
    width, height = 240, 426
    seed = 35 * (index + 1)

    def make_frame(t):
        progress = t / duration
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 0] = (30 + seed + int(progress * 110)) % 255
        frame[:, :, 1] = (90 + seed + int(progress * 70)) % 255
        frame[:, :, 2] = (170 + seed + int(progress * 40)) % 255

        orb_x = 30 + int(progress * (width - 60))
        orb_y = 70 + ((index * 40) % 180)
        frame[max(0, orb_y - 22):min(height, orb_y + 22), max(0, orb_x - 22):min(width, orb_x + 22), :] = [255, 255, 255]
        frame[height - 70:height - 40, 24:width - 24, :] = [20 + seed, 20 + seed, 20 + seed]
        frame[height - 64:height - 46, 30:30 + int((width - 60) * progress), :] = [255, 255, 255]
        frame[0, 0, :] = [index + 1, seed % 255, (seed * 2) % 255]
        return frame

    clip = VideoClip(make_frame, duration=duration).with_fps(fps)
    tmp = tempfile.NamedTemporaryFile(suffix=f"_{index}.mp4", delete=False)
    tmp_path = tmp.name
    tmp.close()
    clip.write_videofile(
        tmp_path,
        codec="libx264",
        audio=False,
        fps=fps,
        logger=None,
        preset="ultrafast",
        ffmpeg_params=["-crf", "36"],
    )
    data = Path(tmp_path).read_bytes()
    os.unlink(tmp_path)
    return data


def generate_local_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for index in range(5):
        video_bytes = generate_video_bytes(index)
        out_path = OUTPUT_DIR / f"namvibe_promo_{index + 1}.mp4"
        out_path.write_bytes(video_bytes)
        files.append((out_path, video_bytes))
    return files


def find_reel(reel_id):
    rows = fast_query(
        "SELECT id, profile_id, caption, video_url, visibility, likes_count, comments_count, shares_count, views_count, status, processing_status FROM chain_reels WHERE id = %s",
        (reel_id,),
        timeout_ms=8000,
        default=[],
    )
    return rows[0] if rows else None


def list_follow_row(follower_id, following_id):
    return fast_query(
        "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
        (follower_id, following_id),
        timeout_ms=5000,
        default=[],
    )


def cleanup_relationships(uploader_id, viewer_ids):
    for viewer_id in viewer_ids:
        write_query(
            "DELETE FROM chain_follows WHERE (follower_profile_id = %s AND following_profile_id = %s) OR (follower_profile_id = %s AND following_profile_id = %s)",
            (viewer_id, uploader_id, uploader_id, viewer_id),
            timeout_ms=8000,
        )


def cleanup_prior_test_reels(uploader_id):
    write_query(
        "DELETE FROM chain_reels WHERE profile_id = %s AND caption LIKE %s",
        (uploader_id, f"{TEST_PREFIX}%"),
        timeout_ms=8000,
    )


def reel_visible_in_payload(payload, reel_id):
    reels = (((payload or {}).get("payload") or {}).get("reels")) or []
    return any(str(item.get("id")) == str(reel_id) for item in reels)


def main():
    identities = load_credentials()
    uploader = identities[UPLOAD_USER]
    viewers = [identities[name] for name in VIEWER_USERS]
    viewer_ids = [viewer["profile_id"] for viewer in viewers]

    print_step("STEP 1: Generate 5 local NamVibe promo videos with moviepy + numpy")
    promo_files = generate_local_files()
    check("generated 5 promo files", len(promo_files) == 5, f"count={len(promo_files)}")
    for path, data in promo_files:
        check(f"{path.name} created", path.exists() and len(data) > 1000, f"size={len(data)}")

    cleanup_prior_test_reels(uploader["profile_id"])
    cleanup_relationships(uploader["profile_id"], viewer_ids)

    client = flask_app.test_client()

    print_step("STEP 2: Upload all 5 promo reels as chain_star")
    login(client, uploader)
    uploaded = []
    run_tag = uuid.uuid4().hex[:8]
    for index, (path, data) in enumerate(promo_files, start=1):
        caption = f"{TEST_PREFIX}{run_tag}_{index} NamVibe promo reel"
        response = client.post(
            "/reels/api/reels/create",
            data={
                "video": (io.BytesIO(data), path.name, "video/mp4"),
                "caption": caption,
                "visibility": "public",
                "music_title": "NamVibe Promo",
                "music_artist": "NamVibe",
            },
            content_type="multipart/form-data",
        )
        payload = response.get_json(silent=True) or {}
        reel_id = payload.get("reel_id")
        check(f"upload {index} returned 201", response.status_code == 201, f"status={response.status_code} payload={payload}")
        check(f"upload {index} returned reel_id", bool(reel_id), str(payload))
        if reel_id:
            uploaded.append({"id": reel_id, "caption": caption, "filename": path.name})

    check("5 reels uploaded", len(uploaded) == 5, f"count={len(uploaded)}")

    print_step("STEP 3: Verify uploaded reels exist and are published")
    for item in uploaded:
        reel = find_reel(item["id"])
        check(f"{item['filename']} exists in DB", bool(reel), item["id"])
        if reel:
            check(f"{item['filename']} visibility public", reel.get("visibility") == "public", str(reel.get("visibility")))
            check(f"{item['filename']} published", reel.get("status") == "published", str(reel.get("status")))
            check(f"{item['filename']} ready", reel.get("processing_status") == "ready", str(reel.get("processing_status")))
            check(f"{item['filename']} has video_url", bool(reel.get("video_url")), str(reel.get("video_url")))

    print_step("STEP 4: Verify viewers can see uploaded reels in reels feed and homepage feed")
    for viewer in viewers:
        login(client, viewer)
        reels_feed = client.get("/reels/api/reels/feed?limit=20")
        reels_payload = reels_feed.get_json(silent=True) or {}
        visible_ids = {str(item.get("id")) for item in reels_payload.get("reels", [])}
        check(f"{viewer['username']} reels feed loaded", reels_feed.status_code == 200, f"status={reels_feed.status_code}")
        check(
            f"{viewer['username']} sees uploaded reels in reels feed",
            all(str(item["id"]) in visible_ids for item in uploaded),
            f"visible={sorted(visible_ids)[:5]}",
        )

        homepage_feed = client.get("/api/homepage/feed?limit=20")
        homepage_payload = homepage_feed.get_json(silent=True) or {}
        check(f"{viewer['username']} homepage feed loaded", homepage_feed.status_code == 200, f"status={homepage_feed.status_code}")
        visible_homepage = sum(1 for item in uploaded if reel_visible_in_payload(homepage_payload, item["id"]))
        check(
            f"{viewer['username']} sees uploaded reels in homepage payload",
            visible_homepage >= 1,
            f"homepage_visible={visible_homepage}",
        )

    print_step("STEP 5: Verify viewers can view, like, comment, share, and follow uploader")
    like_comment_targets = uploaded[:4]
    for viewer, target in zip(viewers, like_comment_targets):
        login(client, viewer)

        before = find_reel(target["id"]) or {}

        view_resp = client.post(
            f"/reels/api/reels/{target['id']}/watch-v2",
            json={"watch_ms": 2200, "completed": True},
            content_type="application/json",
        )
        check(f"{viewer['username']} watch accepted", view_resp.status_code == 200, str(view_resp.status_code))

        like_resp = client.post(f"/reels/api/reels/{target['id']}/like", content_type="application/json")
        like_payload = like_resp.get_json(silent=True) or {}
        check(f"{viewer['username']} like accepted", like_resp.status_code == 200, str(like_payload))
        check(f"{viewer['username']} like success", bool(like_payload.get("success")), str(like_payload))

        comment_resp = client.post(
            f"/reels/api/reels/{target['id']}/comment",
            data={"body": f"Promo looks good from {viewer['username']}"},
            content_type="multipart/form-data",
        )
        comment_payload = comment_resp.get_json(silent=True) or {}
        check(f"{viewer['username']} comment accepted", comment_resp.status_code == 201, str(comment_payload))
        check(f"{viewer['username']} comment success", bool(comment_payload.get("success")), str(comment_payload))

        share_resp = client.post(
            f"/reels/api/reels/{target['id']}/share-v2",
            json={"target": "copy_link"},
            content_type="application/json",
        )
        share_payload = share_resp.get_json(silent=True) or {}
        check(f"{viewer['username']} share accepted", share_resp.status_code == 200, str(share_payload))
        check(f"{viewer['username']} share success", bool(share_payload.get("success")), str(share_payload))

        follow_resp = client.post(f"/api/social/follow/{uploader['profile_id']}", content_type="application/json")
        follow_payload = follow_resp.get_json(silent=True) or {}
        check(f"{viewer['username']} follow accepted", follow_resp.status_code == 200, str(follow_payload))
        check(
            f"{viewer['username']} now follows uploader",
            bool(follow_payload.get("ok")) and (
                bool(follow_payload.get("following")) or follow_payload.get("state") == "following"
            ),
            str(follow_payload),
        )

        after = find_reel(target["id"]) or {}
        check(
            f"{viewer['username']} increased like count",
            int(after.get("likes_count") or 0) >= int(before.get("likes_count") or 0) + 1,
            f"before={before.get('likes_count')} after={after.get('likes_count')}",
        )
        check(
            f"{viewer['username']} increased comment count",
            int(after.get("comments_count") or 0) >= int(before.get("comments_count") or 0) + 1,
            f"before={before.get('comments_count')} after={after.get('comments_count')}",
        )
        check(
            f"{viewer['username']} increased share count",
            int(after.get("shares_count") or 0) >= int(before.get("shares_count") or 0) + 1,
            f"before={before.get('shares_count')} after={after.get('shares_count')}",
        )
        check(
            f"{viewer['username']} follow row exists",
            bool(list_follow_row(viewer["profile_id"], uploader["profile_id"])),
            f"viewer={viewer['profile_id']}",
        )

    print_step("SUMMARY")
    print(f"PASS: {RESULTS['pass']}")
    print(f"FAIL: {RESULTS['fail']}")
    print(f"WARN: {RESULTS['warn']}")
    print(f"Promo output folder: {OUTPUT_DIR}")
    if RESULTS["fail"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
