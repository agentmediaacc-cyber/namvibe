#!/usr/bin/env python3
"""Phase 164: Audit optimistic UI patterns across all templates and JS files."""
import sys, os, re

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

files = {
    "home_pro.js": "static/js/namvibe_home_pro.js",
    "post/detail.html": "templates/posts/detail.html",
    "reel/detail.html": "templates/reels/detail.html",
    "camera_creator.js": "static/js/namvibe_camera_creator.js",
}

contents = {}
for label, path in files.items():
    if os.path.exists(path):
        contents[label] = open(path).read()
    else:
        check(f"{label} exists", False, "file not found")

print("=== Phase 164 — Optimistic UI Contract Audit ===")

# 1. Like buttons use optimistic pattern
if "home_pro.js" in contents:
    c = contents["home_pro.js"]
    check("home_pro.js: Like has optimistic toggle",
          re.search(r"btn\.classList\.toggle\(\"is-liked\"\)\)", c) is not None or
          "btn.classList.toggle" in c)
    check("home_pro.js: Like has rollback on error",
          "btn.classList.toggle(\"is-liked\", wasLiked)" in c or
          re.search(r'classList\.toggle.*wasLiked', c) is not None)
    check("home_pro.js: Like count updates optimistically",
          "span.textContent = wasLiked" in c or
          "Math.max(oldCount - 1, 0)" in c)
    # Check both API response formats handled
    check("home_pro.js: handles reels API format (data.liked)",
          "data.liked" in c)

if "post/detail.html" in contents:
    c = contents["post/detail.html"]
    check("post/detail.html: Like optimistic toggle",
          "likeBtn.classList.toggle" in c)
    check("post/detail.html: Like rollback on catch",
          "likeBtn.classList.toggle(\"is-liked\", wasLiked)" in c)
    check("post/detail.html: Comment instant DOM insert",
          "addCommentToDOM(body, tempId)" in c)
    check("post/detail.html: Comment rollback removes temp",
          "tempEl.remove()" in c)
    check("post/detail.html: Comment count update",
          "commentCountSpan.textContent = cc + 1" in c)

if "reel/detail.html" in contents:
    c = contents["reel/detail.html"]
    check("reel/detail.html: Like optimistic toggle",
          "likeBtn.classList.toggle" in c)
    check("reel/detail.html: Like rollback on catch",
          "likeBtn.classList.toggle(\"is-liked\", wasLiked)" in c)
    check("reel/detail.html: Like count from response",
          "data.count" in c)
    check("reel/detail.html: Comment instant DOM insert",
          "addCommentToDOM(body, tempId)" in c)
    check("reel/detail.html: Comment rollback removes temp",
          "tempEl.remove()" in c)

if "camera_creator.js" in contents:
    c = contents["camera_creator.js"]
    check("camera_creator.js: Duplicate upload flag",
          "_uploading" in c)
    check("camera_creator.js: Progress bar wiring",
          "progressFill.style.width" in c)
    check("camera_creator.js: Confirm button disabled",
          "confirmBtn.disabled = true" in c)

# 2. Engagement service has no old event types
engagement = open("services/engagement_service.py").read()
check("engagement_service.py: no 'post_liked' (old format)",
      '"post_liked"' not in engagement)
check("engagement_service.py: no 'reel_liked' (old format)",
      '"reel_liked"' not in engagement)
check("engagement_service.py: no 'post_commented' (old format)",
      '"post_commented"' not in engagement)
check("engagement_service.py: no 'reel_commented' (old format)",
      '"reel_commented"' not in engagement)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
