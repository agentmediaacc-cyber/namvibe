#!/usr/bin/env python3
"""Test music metadata fields exist and audio playback is wired."""

import re, sys

issues = []

# 1. Check backend music fields in content_service.py
with open("services/content_service.py") as f:
    cs = f.read()
    for field in ["music_url", "music_title", "music_artist", "music_start_seconds", "music_duration_seconds"]:
        if field not in cs:
            issues.append(f"content_service.py: missing field '{field}'")
        # check it appears in create_post_record
        if field not in cs.split("def create_post_record")[1].split("def create_reel_record")[0]:
            issues.append(f"content_service.py: '{field}' missing from create_post_record")
        # check in create_reel_record
        if field not in cs.split("def create_reel_record")[1].split("def create_story_record")[0]:
            issues.append(f"content_service.py: '{field}' missing from create_reel_record")
        # check in create_story_record
        if field not in cs.split("def create_story_record")[1].split("def create_poll_record")[0]:
            issues.append(f"content_service.py: '{field}' missing from create_story_record")

# 2. Check supabase_storage_service accepts audio
with open("services/supabase_storage_service.py") as f:
    ss = f.read()
    if "ALLOWED_AUDIO_EXTENSIONS" not in ss:
        issues.append("supabase_storage_service: missing ALLOWED_AUDIO_EXTENSIONS")
    if "mp3" not in ss:
        issues.append("supabase_storage_service: missing mp3 support")
    if "audio" not in ss.split("def upload_media_to_supabase")[1].split("def check_bucket_exists")[0]:
        issues.append("supabase_storage_service: upload_media not handling audio")

# 3. Check API routes accept music fields
for fp, endpoint in [("api_routes/post_routes.py", "api_create"), ("api_routes/status_routes.py", "api_create"), ("api_routes/reels_routes.py", "api_create_reel")]:
    with open(fp) as f:
        content = f.read()
        if "music_url" not in content:
            issues.append(f"{fp}: {endpoint} missing music_url param")
        if "music_file" not in content:
            issues.append(f"{fp}: {endpoint} missing music_file handling")

# 4. Check camera creator has music button
with open("templates/partials/camera_creator.html") as f:
    cc = f.read()
    if "music" not in cc.lower():
        issues.append("camera_creator.html: missing music editor tool")

with open("static/js/namvibe_camera_creator.js") as f:
    cjs = f.read()
    if "music" not in cjs:
        issues.append("namvibe_camera_creator.js: missing music handling")

# 5. Check detail templates have music player
for fp in ["templates/posts/detail.html", "templates/reels/detail.html"]:
    with open(fp) as f:
        content = f.read()
        if "data-music-url" not in content:
            issues.append(f"{fp}: missing music player (data-music-url)")
        if "music_title" not in content:
            issues.append(f"{fp}: missing music_title display")

if issues:
    for i in issues:
        print(f"MUSIC FAIL: {i}")
    sys.exit(1)
else:
    print("PART A OK: Music metadata fields, upload, and playback are properly wired")