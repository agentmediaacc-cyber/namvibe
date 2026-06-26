#!/usr/bin/env python3
"""Phase 164: Verify multi-picture story table and upload flow."""
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

content_service = open("services/content_service.py").read()

print("=== Phase 164 — Multi-Picture Story ===")

# 1. chain_story_media_items table exists in schema
check("content_service.py: chain_story_media_items CREATE TABLE",
      "chain_story_media_items" in content_service)

# 2. Table has story_id FK
check("content_service.py: story_id FK",
      "story_id uuid REFERENCES chain_status_posts" in content_service)

# 3. Table has media_url, media_type, sort_order
check("content_service.py: media_url column",
      "media_url text NOT NULL" in content_service)

check("content_service.py: media_type column",
      "media_type text DEFAULT 'image'" in content_service)

check("content_service.py: sort_order column",
      "sort_order integer DEFAULT 0" in content_service)

# 4. Index on story_id + sort_order
check("content_service.py: idx_chain_story_media_items_story index",
      "idx_chain_story_media_items_story" in content_service)

# 5. Camera creator JS has _uploading flag
camera_js = open("static/js/namvibe_camera_creator.js").read()
check("camera_creator.js: _uploading flag for duplicate prevention",
      "var _uploading" in camera_js)

check("camera_creator.js: _uploading check at start of upload",
      "if (_uploading) return" in camera_js)

check("camera_creator.js: _uploading reset in onload",
      "_uploading = false" in camera_js)

# 6. Content service schema has alter columns for chain_status_posts
check("content_service.py: background_color column",
      "background_color" in content_service)

check("content_service.py: text_content column",
      "text_content" in content_service)

check("content_service.py: owner_id column",
      "owner_id" in content_service)

check("content_service.py: duration_seconds column",
      "duration_seconds" in content_service)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
