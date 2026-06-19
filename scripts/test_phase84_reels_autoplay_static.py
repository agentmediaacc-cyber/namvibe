#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "static/js/reels_autoplay_engine.js").read_text()
home = (ROOT / "templates/chain_home.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("reels autoplay script exists", "IntersectionObserver" in js)
check("plays only mostly visible", "intersectionRatio >= 0.72" in js)
check("pauses outside viewport", "intersectionRatio < 0.35" in js and "pause(" in js)
check("muted by default", "video.muted = true" in js)
check("tap to unmute", "unmuted = !unmuted" in js)
check("double tap like", "lastTap" in js and "[data-action=\"like\"]" in js)
check("progress bar", "nv-video-progress" in home and "timeupdate" in js)
check("preloads next", "preloadNext" in js and "preload = 'auto'" in js)
check("stops on hidden/route change", "visibilitychange" in js and "pagehide" in js and "popstate" in js)
check("tracks video events", "/api/video-events" in js)
check("template includes script", "reels_autoplay_engine.js" in home)
