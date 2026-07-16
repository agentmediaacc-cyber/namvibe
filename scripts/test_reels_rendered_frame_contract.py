#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "static" / "js" / "reels.js").read_text(encoding="utf-8")
    assert "requestVideoFrameCallback" in source, "Missing rendered-frame callback logic"
    assert "markRenderedFrame" in source, "Missing rendered-frame marker logic"
    assert "has-rendered-frame" in source, "Missing rendered-frame CSS hook"
    assert "video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA" in source, "Missing readyState guard"
    print("TEST_OK reels rendered frame contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
