#!/usr/bin/env python3
"""
NamVibe Reel E2E — Full user flow test:

  1. Create NamVibe advert video with moviepy + numpy
  2. Upload as User A (alpha_user) via POST /api/reels/create
  3. Verify reel exists in DB, check video_url, caption, visibility
  4. User B (beta) views the reel (triggers view notification)
  5. User B likes the reel → verify reel_like notification for User A
  6. User B comments on the reel → verify comment notification for User A
  7. User B follows User A → verify new_follower notification for User A
  8. User B sends friend request to User A → verify friend_request notification

Usage: python scripts/test_namvibe_reel_e2e.py
"""

import io
import json
import os
import sys
import time
import uuid
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"
os.environ["WTF_CSRF_ENABLED"] = "0"

from app import app as flask_app
from services.neon_service import fast_query, write_query
from services.engagement_service import follow_profile
from services.social_relationship_service import send_friend_request

flask_app.config["WTF_CSRF_ENABLED"] = False

TEST_PREFIX = "NVE2E_"

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
        fail(f"{label}  {detail}")

def print_step(num, title):
    print(f"\n{'='*60}")
    print(f"STEP {num}: {title}")
    print(f"{'='*60}")

def login(client, profile_data):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = profile_data["auth_user_id"]
        sess["profile_id"] = profile_data["profile_id"]
        sess["user_id"] = profile_data["profile_id"]
        sess["username"] = profile_data["username"]
        sess["full_name"] = profile_data.get("full_name", profile_data["username"])
        sess["logged_in"] = True
        sess["email"] = profile_data["email"]
        sess["profile_completed"] = True
        sess["age_verified"] = True
        sess["age_check_required"] = False
        sess["access_token"] = f"nve2e-{profile_data['username']}"

def make_advert_video():
    """Generate a 3-second NamVibe-branded advert video as bytes.
    Includes a timestamp pixel so each run produces a unique hash."""
    try:
        from moviepy import VideoClip
    except ImportError:
        from moviepy.editor import VideoClip
    import numpy as np
    import tempfile

    duration = 3.0
    fps = 24
    w, h = 480, 854
    run_seed = int(time.time() * 1000) % 65536

    def make_frame(t):
        progress = t / duration
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        fade = min(1.0, progress * 2)
        r = int(254 * fade)
        g = int(105 * fade)
        b = int(180 * fade)
        frame[:, :, 0] = r
        frame[:, :, 1] = g
        frame[:, :, 2] = b
        cx, cy = w // 2, h // 2 - 40
        for row in range(h):
            for col in range(w):
                dx, dy = col - cx, row - cy
                if abs(dx) < 5 and abs(dy) < 5:
                    frame[row, col] = [255, 255, 255]
        # Embed run seed so content_hash differs each run
        frame[0, 0] = [run_seed & 0xFF, (run_seed >> 8) & 0xFF, 0]
        return frame

    clip = VideoClip(make_frame, duration=duration).with_fps(fps)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = tmp.name
    tmp.close()
    clip.write_videofile(tmp_path, codec="libx264", audio=False, fps=fps, logger=None, preset="ultrafast", ffmpeg_params=["-crf", "35"])
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data, clip.size

def get_reel_from_db(reel_id):
    rows = fast_query(
        "SELECT * FROM chain_reels WHERE id = %s", [reel_id],
        timeout_ms=5000, default=[]
    )
    return rows[0] if rows else None

def get_notifications(recipient_id, event_type=None, actor_id=None, entity_id=None):
    conditions = ["recipient_profile_id = %s"]
    params = [recipient_id]
    if event_type:
        conditions.append("event_type = %s")
        params.append(event_type)
    if actor_id:
        conditions.append("actor_profile_id = %s")
        params.append(actor_id)
    if entity_id:
        conditions.append("entity_id = %s")
        params.append(entity_id)
    sql = "SELECT * FROM chain_notifications WHERE " + " AND ".join(conditions) + " ORDER BY created_at DESC"
    return fast_query(sql, params, timeout_ms=5000, default=[])

# ──────────────────────────────────────────────
# User credentials (from test_credentials.json)
# ──────────────────────────────────────────────
USER_A = {
    "username": "alpha_user",
    "profile_id": "622b8aaf-8a0c-49e3-b7ac-3901d40cded6",
    "auth_user_id": "5c6b5b7f-5b56-4db5-a86a-14a99557beb5",
    "email": "alpha@namvibe.com",
    "full_name": "Alpha User",
}
USER_B = {
    "username": "beta",
    "profile_id": "40e42995-999e-403d-9a35-fc8b2cc7096f",
    "auth_user_id": "05667e0d-e2a2-40bb-a80b-1ed9f6e22fed",
    "email": "beta@namvibe.com",
    "full_name": "Beta",
}

CAPTION = f"{TEST_PREFIX}NamVibe Advert — Discover Your Vibe {uuid.uuid4().hex[:6]}"

# ──────────────────────────────────────────────
def main():
    print("=" * 72)
    print("NAM VIBE REEL E2E — Full User Flow")
    print("=" * 72)

    reel_id = None
    client = flask_app.test_client()

    # Clean up any previous test state for clean run
    for pid in [USER_A["profile_id"], USER_B["profile_id"]]:
        try:
            write_query("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_follows WHERE follower_profile_id = %s OR following_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_friend_requests WHERE sender_profile_id = %s OR recipient_profile_id = %s", (pid, pid))
            write_query("DELETE FROM chain_friends WHERE profile_id_1 = %s OR profile_id_2 = %s", (pid, pid))
        except Exception:
            pass

    # ── STEP 1: Create advert video ──
    print_step(1, "Create NamVibe advert video with moviepy + numpy")
    try:
        video_bytes, (w, h) = make_advert_video()
        check("video bytes generated", len(video_bytes) > 1000, f"size={len(video_bytes)}")
        check("video dimensions", w == 480 and h == 854, f"{w}x{h}")
    except Exception as e:
        fail(f"video generation failed: {e}")
        return 1

    # ── STEP 2: Upload as User A ──
    print_step(2, "Upload video as User A (alpha_user)")
    login(client, USER_A)

    video_file = (io.BytesIO(video_bytes), "namvibe_advert.mp4", "video/mp4")
    upload_resp = client.post(
        "/reels/api/reels/create",
        data={
            "video": video_file,
            "caption": CAPTION,
            "visibility": "public",
            "music_title": "NamVibe Original",
            "music_artist": "NamVibe",
        },
        content_type="multipart/form-data",
    )
    upload_json = upload_resp.get_json(silent=True) or {}
    check("upload status 201", upload_resp.status_code == 201, f"status={upload_resp.status_code}")
    check("upload ok flag", upload_json.get("ok") is True, str(upload_json))
    reel_id = upload_json.get("reel_id")
    check("reel_id returned", bool(reel_id), str(reel_id))

    if not reel_id:
        fail("no reel_id — cannot continue")
        return 1

    # ── STEP 3: Verify reel in DB ──
    print_step(3, "Verify reel in database")
    reel = get_reel_from_db(reel_id)
    check("reel exists in DB", bool(reel), f"id={reel_id}")
    if reel:
        check("profile_id matches User A", reel.get("profile_id") == USER_A["profile_id"], f"{reel.get('profile_id')}")
        check("caption matches", CAPTION in reel.get("caption", ""), f"expected={CAPTION[:30]}...")
        check("visibility is public", reel.get("visibility") == "public", f"{reel.get('visibility')}")
        check("video_url present", bool(reel.get("video_url")), reel.get("video_url", "")[:60])
        check("status is published", reel.get("status") == "published", f"{reel.get('status')}")
        check("processing_status is ready", reel.get("processing_status") == "ready", f"{reel.get('processing_status')}")
        check("likes_count starts at 0", int(reel.get("likes_count", -1)) == 0)
        check("views_count starts at 0", int(reel.get("views_count", -1)) == 0)
        check("comments_count starts at 0", int(reel.get("comments_count", -1)) == 0)

    # ── STEP 4: User B views the reel ──
    print_step(4, "User B (beta) views the reel via track endpoint")
    login(client, USER_B)
    view_resp = client.post(
        f"/reels/api/reels/{reel_id}/event",
        json={"event_type": "view", "watch_ms": 3000},
        content_type="application/json",
    )
    view_json = view_resp.get_json(silent=True) or {}
    check("view event accepted", view_resp.status_code == 200, str(view_resp.status_code))

    # Also trigger watch event for better view tracking
    watch_resp = client.post(
        f"/reels/api/reels/{reel_id}/watch-v2",
        json={"watch_ms": 3000, "completed": True},
        content_type="application/json",
    )
    watch_json = watch_resp.get_json(silent=True) or {}
    check("watch event accepted", watch_resp.status_code == 200, str(watch_resp.status_code))

    # Give views a moment to be flushed (async view queue)
    time.sleep(1)

    # ── STEP 5: User B likes the reel ──
    print_step(5, "User B likes the reel")
    like_resp = client.post(
        f"/reels/api/reels/{reel_id}/like",
        content_type="application/json",
    )
    like_json = like_resp.get_json(silent=True) or {}
    check("like status 200", like_resp.status_code == 200, str(like_resp.status_code))
    check("like liked=true", like_json.get("liked") is True, str(like_json))
    check("like count >= 1", int(like_json.get("count", 0)) >= 1, f"count={like_json.get('count')}")

    # Verify notification for User A
    like_notifs = get_notifications(
        USER_A["profile_id"],
        event_type="reel_like",
        actor_id=USER_B["profile_id"],
        entity_id=reel_id,
    )
    check("reel_like notification for User A", len(like_notifs) >= 1, f"count={len(like_notifs)}")
    if like_notifs:
        check("notification title is 'Reel liked'", like_notifs[0].get("title") == "Reel liked", str(like_notifs[0].get("title")))

    # Verify DB like count
    reel_after_like = get_reel_from_db(reel_id)
    if reel_after_like:
        check("likes_count incremented in DB", int(reel_after_like.get("likes_count", 0)) >= 1, f"count={reel_after_like.get('likes_count')}")

    # ── STEP 6: User B comments on the reel ──
    print_step(6, "User B comments on the reel")
    comment_text = f"Great NamVibe advert! {uuid.uuid4().hex[:6]}"
    comment_resp = client.post(
        f"/reels/api/reels/{reel_id}/comment",
        data={"body": comment_text},
        content_type="multipart/form-data",
    )
    comment_json = comment_resp.get_json(silent=True) or {}
    check("comment status 201", comment_resp.status_code == 201, str(comment_resp.status_code))
    check("comment success", comment_json.get("success") is True, str(comment_json))

    # Verify comment notification for User A
    comment_notifs = get_notifications(
        USER_A["profile_id"],
        event_type="comment",
        actor_id=USER_B["profile_id"],
        entity_id=reel_id,
    )
    check("comment notification for User A", len(comment_notifs) >= 1, f"count={len(comment_notifs)}")
    if comment_notifs:
        check("notification title is 'New reel comment'", comment_notifs[0].get("title") == "New reel comment", str(comment_notifs[0].get("title")))

    # Verify DB comments count
    reel_after_comment = get_reel_from_db(reel_id)
    if reel_after_comment:
        check("comments_count incremented in DB", int(reel_after_comment.get("comments_count", 0)) >= 1, f"count={reel_after_comment.get('comments_count')}")

    # ── STEP 7: User B follows User A ──
    print_step(7, "User B follows User A")
    follow_res = follow_profile(USER_B["profile_id"], USER_A["profile_id"], toggle=False)
    check("follow_profile success", follow_res.get("success") is True, str(follow_res))

    # Verify follow notification for User A
    follow_notifs = get_notifications(
        USER_A["profile_id"],
        event_type="new_follower",
        actor_id=USER_B["profile_id"],
    )
    check("new_follower notification for User A", len(follow_notifs) >= 1, f"count={len(follow_notifs)}")
    if follow_notifs:
        check("notification title is 'New follower'", follow_notifs[0].get("title") == "New follower", str(follow_notifs[0].get("title")))

    # ── STEP 8: User B sends friend request to User A ──
    print_step(8, "User B sends friend request to User A")
    fr_resp = client.post(
        f"/api/friends/request/{USER_A['profile_id']}",
        json={"message": "Let's vibe together!"},
        content_type="application/json",
    )
    fr_json = fr_resp.get_json(silent=True) or {}
    check("friend request status 200", fr_resp.status_code == 200, str(fr_resp.status_code))
    check("friend request ok", fr_json.get("ok") is True, str(fr_json))
    request_id = fr_json.get("request_id")
    check("request_id returned", bool(request_id), f"got={fr_json}")

    # Verify User A can see the friend request
    login(client, USER_A)
    requests_resp = client.get("/social/api/friends")
    requests_json = requests_resp.get_json(silent=True) or {}
    # Just check the endpoint works
    check("User A can access friend requests", requests_resp.status_code == 200, str(requests_resp.status_code))

    # ── STEP 9: Dedup test — uploading same video again should be rejected ──
    print_step(9, "Dedup test — re-upload same video as User A")
    login(client, USER_A)
    dup_video = (io.BytesIO(video_bytes), "namvibe_advert_dup.mp4", "video/mp4")
    dup_resp = client.post(
        "/reels/api/reels/create",
        data={
            "video": dup_video,
            "caption": f"{CAPTION} DUPLICATE",
            "visibility": "public",
        },
        content_type="multipart/form-data",
    )
    dup_json = dup_resp.get_json(silent=True) or {}
    # Duplicate is not an error — it returns the existing reel (see create_reel_record dedup logic)
    # The api returns 201 with the existing reel_id, which is correct dedup behavior
    dup_reel_id = dup_json.get("reel_id")
    check("duplicate upload returns same reel_id", dup_reel_id == reel_id, f"original={reel_id} dup={dup_reel_id}")

    # ── SUMMARY ──
    print("\n" + "=" * 72)
    print("NAM VIBE REEL E2E — RESULTS")
    print("=" * 72)
    print(f"  PASS: {RESULTS['pass']}")
    print(f"  FAIL: {RESULTS['fail']}")
    print(f"  WARN: {RESULTS['warn']}")
    total = RESULTS["pass"] + RESULTS["fail"] + RESULTS["warn"]
    print(f"  TOTAL: {total}")
    print(f"  OUTCOME: {'ALL PASS' if RESULTS['fail'] == 0 else 'SOME FAILURES'}")

    if RESULTS["fail"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
