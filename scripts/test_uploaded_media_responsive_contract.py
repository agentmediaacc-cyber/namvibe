#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    from services.reels_serialization_service import serialize_reel
    from services.media_selection_service import select_video_url, select_poster_url, select_photo_url

    posts_dir = ROOT / "static" / "uploads" / "posts"
    reel_dir = ROOT / "static" / "uploads" / "reels"
    poster_file = next((p for p in posts_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}), None)
    video_file = next((p for p in reel_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".webm"}), None)
    assert poster_file is not None, "Missing local poster fixture"
    assert video_file is not None, "Missing local video fixture"
    poster_path = "/" + poster_file.relative_to(ROOT).as_posix()
    video_path = "/" + video_file.relative_to(ROOT).as_posix()

    row = {
        "id": "reel-1",
        "profile_id": "profile-1",
        "video_720p_url": video_path,
        "video_1080p_url": video_path,
        "thumbnail_url": poster_path,
        "width": 720,
        "height": 1280,
        "duration_seconds": 12,
        "caption": "Test reel",
    }
    serialized = serialize_reel(row, viewer_id="viewer", creator={"username": "creator", "display_name": "Creator"})
    ok = True
    ok &= check("selects best video rendition", select_video_url(row) == video_path, select_video_url(row))
    ok &= check("selects poster separately", select_poster_url(row) == poster_path, select_poster_url(row))
    ok &= check("photo selection prefers full media", select_photo_url({"photo_720p_url": poster_path, "public_url": video_path}) == poster_path, "")
    ok &= check("serialized reel uses best video", serialized.get("video_url") == video_path, str(serialized))
    ok &= check("serialized reel exposes poster", serialized.get("thumbnail_url") == poster_path, str(serialized))
    print("TEST_OK uploaded media responsive contract" if ok else "TEST_FAIL uploaded media responsive contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
