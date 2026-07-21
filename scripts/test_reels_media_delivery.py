#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
_SSL_CONTEXT = ssl._create_unverified_context()


def fetch_json(path: str) -> dict:
    req = Request(urljoin(BASE_URL + "/", path.lstrip("/")), headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_head(url: str) -> tuple[int, dict[str, str]]:
    req = Request(url, method="HEAD")
    with urlopen(req, timeout=30, context=_SSL_CONTEXT if url.startswith("https://") else None) as resp:
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}


def fetch_range(url: str) -> tuple[int, dict[str, str], bytes]:
    req = Request(url, headers={"Range": "bytes=0-1023"})
    with urlopen(req, timeout=30, context=_SSL_CONTEXT if url.startswith("https://") else None) as resp:
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()


def main() -> int:
    payload = fetch_json("/reels/api/reels/feed?limit=5")
    items = payload.get("items") or payload.get("reels") or []
    reel = next((item for item in items if item.get("video_url")), None)
    if not reel:
        raise SystemExit("No reel with a video URL was returned")

    video_url = reel["video_url"]
    parsed = urlparse(video_url)
    local_path = None
    if parsed.scheme in ("", "http", "https") and parsed.path.startswith("/static/uploads/reels/"):
        local_path = ROOT / parsed.path.lstrip("/")
        assert local_path.exists(), f"Local reel file missing: {local_path}"
        assert local_path.stat().st_size > 0, f"Local reel file empty: {local_path}"

    status, headers = fetch_head(video_url if parsed.scheme else urljoin(BASE_URL + "/", video_url.lstrip("/")))
    assert status in (200, 206), f"Unexpected HEAD status {status} for {video_url}"
    assert "content-type" in headers and "video" in headers["content-type"].lower(), headers.get("content-type")

    range_status, range_headers, body = fetch_range(video_url if parsed.scheme else urljoin(BASE_URL + "/", video_url.lstrip("/")))
    assert range_status in (200, 206), f"Expected video response for range request, got {range_status}"
    if range_status == 206:
        assert "content-range" in range_headers, "Missing Content-Range header"
    assert len(body) > 0, "Empty range response body"

    if local_path and shutil.which("ffprobe"):
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,width,height,pix_fmt",
                "-show_entries",
                "format=format_name,duration",
                "-of",
                "json",
                str(local_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(probe.stdout)
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
        assert video_stream.get("codec_name") in {"h264", "avc1", "mpeg4"}, video_stream
        if audio_stream:
            assert audio_stream.get("codec_name") in {"aac", "mp3", "opus"}, audio_stream
        assert video_stream.get("pix_fmt") in {None, "yuv420p", "yuvj420p"}, video_stream

    print(
        json.dumps(
            {
                "video_url": video_url,
                "head_status": status,
                "range_status": range_status,
                "local_path": str(local_path) if local_path else None,
            },
            ensure_ascii=True,
        )
    )
    print("TEST_OK reels media delivery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
