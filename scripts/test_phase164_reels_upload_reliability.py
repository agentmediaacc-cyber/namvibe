#!/usr/bin/env python3
"""Phase 164: Verify reels upload reliability — duplicate prevention, file size validation, progress bar."""
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

reels_routes = open("api_routes/reels_routes.py").read()
camera_js = open("static/js/namvibe_camera_creator.js").read()

print("=== Phase 164 — Reels Upload Reliability ===")

# 1. Dedup key for reels upload
check("reels_routes.py: dedup key with profile_id+filename+size",
      "dedup_key = f\"reel_upload:{profile_id}:{video_file.filename}:{video_file.content_length}\"" in reels_routes)

# 2. Dedup check returns 429
check("reels_routes.py: dedup check returns 429 on duplicate",
      "return jsonify({\"ok\": False, \"error\": \"Duplicate upload detected\"}), 429" in reels_routes)

# 3. File size validation (500MB limit)
check("reels_routes.py: 500MB max size check",
      "max_size = 500 * 1024 * 1024" in reels_routes)

check("reels_routes.py: size validation returns 400",
      "Video exceeds 500MB limit" in reels_routes)

# 4. Camera JS: progress bar
check("camera_creator.js: XHR upload progress handler",
      "xhr.upload.onprogress" in camera_js)

check("camera_creator.js: progress percentage computed",
      "pct = Math.round((e.loaded / e.total) * 100)" in camera_js)

check("camera_creator.js: progressFill width updated",
      "progressFill.style.width" in camera_js)

# 5. Camera JS: confirm button disabled during upload
check("camera_creator.js: confirmBtn disabled during upload",
      "confirmBtn.disabled = true" in camera_js)

# 6. Video processing job created after reel upload
check("reels_routes.py: create_processing_job called",
      "create_processing_job" in reels_routes)

# 7. Reel upload endpoint is the canonical API endpoint
check("reels_routes.py: api_create_reel exists (canonical)",
      "def api_create_reel" in reels_routes)

# 8. Rate limiting on the form upload route
check("reels_routes.py: rate limit on upload route",
      "@limiter.limit(\"20/hour\"" in reels_routes)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
