#!/usr/bin/env python3
"""Phase 164: Verify story music trim validation (max 90s)."""
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

status_service = open("services/status_service.py").read()
camera_creator_js = open("static/js/namvibe_camera_creator.js").read()

print("=== Phase 164 — Story Music Trim Validation ===")

# 1. Music duration capped at 90s in create_status
check("status_service.py: music_duration_seconds capped at 90",
      "music_duration_seconds > 90" in status_service and "music_duration_seconds = 90" in status_service)

# 2. Music start_seconds clamped to >= 0
check("status_service.py: music_start_seconds clamped to >=0",
      "music_start_seconds < 0" in status_service and "music_start_seconds = 0" in status_service)

# 3. music_duration_seconds is int-cast
check("status_service.py: music_duration_seconds int-converted",
      "int(music_duration_seconds or 0)" in status_service)

# 4. Camera creator JS has music URL field
check("camera_creator.js: music URL input created",
      "nvcct-music-url" in camera_creator_js)

# 5. Camera creator JS has music title field
check("camera_creator.js: music title input created",
      "nvcct-music-title" in camera_creator_js)

# 6. Camera creator music fields appended to upload
check("camera_creator.js: music_url appended to FormData",
      "music_url" in camera_creator_js)

check("camera_creator.js: music_title appended to FormData",
      "music_title" in camera_creator_js)

check("camera_creator.js: music_artist appended to FormData",
      "music_artist" in camera_creator_js)

# 7. Status routes accept music fields
api_routes = open("api_routes/status_routes.py").read()
check("status_routes.py: music_url param accepted",
      "music_url" in api_routes)

check("status_routes.py: music_start_seconds param accepted",
      "music_start_seconds" in api_routes)

check("status_routes.py: music_duration_seconds param accepted",
      "music_duration_seconds" in api_routes)

# 8. DB stores music duration
content_service = open("services/content_service.py").read()
check("content_service.py: music_duration_seconds column in schema",
      "music_duration_seconds" in content_service)

check("content_service.py: music_start_seconds column in schema",
      "music_start_seconds" in content_service)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
