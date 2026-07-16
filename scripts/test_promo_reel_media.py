#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_namvibe_promo_video.py"


def _ffprobe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "promo"
        dry = subprocess.run(["python3", str(SCRIPT), "--dry-run", "--output-dir", str(out)], capture_output=True, text=True)
        assert dry.returncode == 0, dry.stderr
        render = subprocess.run(["python3", str(SCRIPT), "--render", "--output-dir", str(out), "--skip-browser-capture"], capture_output=True, text=True)
        assert render.returncode == 0, render.stderr
        manifest = json.loads((out / "namvibe_promo_manifest.json").read_text())
        assert manifest["width"] == 1080
        assert manifest["height"] == 1920
        assert 45 <= manifest["duration_seconds"] <= 75
        assert manifest["video_codec"] == "h264"
        assert manifest["audio_codec"] == "aac"
        for key in ("master_path", "web_path", "thumbnail_path", "poster_path", "captions_path"):
            assert Path(manifest[key]).exists()
        for name in ("namvibe_promo_master.mp4", "namvibe_promo_web.mp4"):
            data = _ffprobe(out / name)
            streams = data["streams"]
            vstream = next(s for s in streams if s["codec_type"] == "video")
            assert vstream["codec_name"] == "h264"
            assert int(vstream["width"]) == 1080
            assert int(vstream["height"]) == 1920
            assert vstream.get("pix_fmt") == "yuv420p"
            assert float(data["format"]["duration"]) >= 45
            assert float(data["format"]["duration"]) <= 75
        with Image.open(out / "namvibe_promo_thumbnail.jpg") as thumb:
            assert thumb.format == "JPEG"
        with Image.open(out / "namvibe_promo_poster.jpg") as poster:
            assert poster.format == "JPEG"
        assert "WEBVTT" in (out / "namvibe_promo_captions.vtt").read_text()
        assert not any(p.suffix.lower() == ".svg" for p in out.iterdir())
        print("TEST_OK promo reel media")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
