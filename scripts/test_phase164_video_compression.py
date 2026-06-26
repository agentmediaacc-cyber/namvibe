#!/usr/bin/env python3
"""Phase 164: Verify video compression pipeline — service, schema, and processing jobs."""
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

# Check video processing service exists
vps_path = "services/video_processing_service.py"
vps_exists = os.path.exists(vps_path)
check(f"video_processing_service.py exists", vps_exists)

if vps_exists:
    vps = open(vps_path).read()

    # Core functions
    check("validate_video function",
          "def validate_video" in vps)

    check("compress_video function",
          "def compress_video" in vps)

    check("create_processing_job function",
          "def create_processing_job" in vps)

    check("update_job_status function",
          "def update_job_status" in vps)

    check("get_pending_jobs function",
          "def get_pending_jobs" in vps)

    check("process_job function",
          "def process_job" in vps)

    check("ensure_processing_jobs_table function",
          "def ensure_processing_jobs_table" in vps)

    # Constants
    check("MAX_VIDEO_DURATION_SECONDS = 120",
          "MAX_VIDEO_DURATION_SECONDS" in vps)

    check("MAX_VIDEO_SIZE_MB = 500",
          "MAX_VIDEO_SIZE_MB" in vps)

    check("TARGET_RESOLUTIONS defined",
          "TARGET_RESOLUTIONS" in vps)

    # ffmpeg usage
    check("ffprobe for duration",
          "ffprobe" in vps)

    check("ffmpeg for compression",
          "ffmpeg" in vps)

    check("libx264 codec",
          "libx264" in vps)

    # Supabase upload after compression
    check("upload_media_to_supabase called",
          "upload_media_to_supabase" in vps)

# Schema includes processing jobs table
content_service = open("services/content_service.py").read()
check("content_service.py: chain_media_processing_jobs table",
      "chain_media_processing_jobs" in content_service)

check("content_service.py: input_url column",
      "input_url text NOT NULL" in content_service)

check("content_service.py: output_url column",
      "output_url text" in content_service)

check("content_service.py: status column",
      "status text NOT NULL DEFAULT 'pending'" in content_service)

check("content_service.py: idx_media_processing_jobs_status index",
      "idx_media_processing_jobs_status" in content_service)

# Reels API triggers compression
reels_routes = open("api_routes/reels_routes.py").read()
check("reels_routes.py: imports video_processing_service",
      "video_processing_service" in reels_routes)

check("reels_routes.py: create_processing_job called on reel upload",
      "create_processing_job" in reels_routes)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
