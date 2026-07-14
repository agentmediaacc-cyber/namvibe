#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
svc = (ROOT / "services" / "media_pipeline.py").read_text()
stor = (ROOT / "services" / "media_storage_service.py").read_text()


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


check("ffmpeg path", "ffmpeg_available" in svc, "missing ffmpeg helper")
check("storage bucket", "chain-reels" in stor, "missing reels bucket")
check("upload metadata", "record_media_upload_metadata" in stor, "missing metadata record")
print("OK")
