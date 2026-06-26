#!/usr/bin/env python3
"""Phase 164: Verify optimistic like UI, correct API response handling, and notification event types."""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = 0
FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")

home_pro = open("static/js/namvibe_home_pro.js").read()
post_detail = open("templates/posts/detail.html").read()
reel_detail = open("templates/reels/detail.html").read()
engagement_service = open("services/engagement_service.py").read()

print("=== Phase 164 — Likes Optimistic UI ===")

# 1. Optimistic toggle in home_pro.js
check("home_pro.js: optimistic toggle before fetch",
      "btn.classList.toggle" in home_pro and "wasLiked" in home_pro and "oldCount" in home_pro)

# 2. Rollback on error in home_pro.js
check("home_pro.js: rollback toggles wasLiked",
      "btn.classList.toggle(\"is-liked\", wasLiked)" in home_pro,
      "must restore original state on error")

# 3. Handles both homepage_api and reels response formats
check("home_pro.js: _handleLikeResult function exists",
      "_handleLikeResult" in home_pro)

check("home_pro.js: handles data.ok + data.result pattern",
      "data.ok && data.result" in home_pro)

check("home_pro.js: handles data.liked pattern (reels API)",
      "data.liked" in home_pro)

# 4. Post detail optimistic toggle
check("post/detail.html: optimistic toggle before fetch",
      "wasLiked" in post_detail and "oldCount" in post_detail)

check("post/detail.html: rollback on catch",
      "likeBtn.classList.toggle(\"is-liked\", wasLiked)" in post_detail,
      "must restore original state on error")

# 5. Reel detail optimistic toggle
check("reel/detail.html: optimistic toggle before fetch",
      "wasLiked" in reel_detail and "oldCount" in reel_detail)

check("reel/detail.html: rollback on catch",
      "likeBtn.classList.toggle(\"is-liked\", wasLiked)" in reel_detail,
      "must restore original state on error")

# 6. Notification event types match notification_engine.py
notif_engine = open("services/notification_engine.py").read()
check("engagement_service.py: post_like event type",
      '"post_like"' in engagement_service,
      "should match notification_engine.py 'post_like'")

check("engagement_service.py: reel_like event type",
      '"reel_like"' in engagement_service,
      "should match notification_engine.py 'reel_like'")

check("engagement_service.py: comment event type",
      '"event_type": "comment"' in engagement_service,
      "should match notification_engine.py 'comment'")

check("notification_engine.py: has post_like category",
      '"post_like": "activity"' in notif_engine)

check("notification_engine.py: has reel_like category",
      '"reel_like": "activity"' in notif_engine)

check("notification_engine.py: has comment category",
      '"comment": "activity"' in notif_engine)

check("notification_engine.py: has post_like icon",
      '"post_like": "fa-heart"' in notif_engine)

check("notification_engine.py: has reel_like icon",
      '"reel_like": "fa-heart"' in notif_engine)

check("notification_engine.py: has comment icon",
      '"comment": "fa-comment"' in notif_engine)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
