#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / "static/css/home_feed_mobile.css").read_text()
js = (ROOT / "static/js/home_feed_mobile.js").read_text()
home = (ROOT / "templates/chain_home.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("mobile css included", "home_feed_mobile.css" in home)
check("mobile js included", "home_feed_mobile.js" in home)
check("safe area padding", "env(safe-area-inset-bottom)" in css)
check("snap scrolling optional", "scroll-snap-type" in css and "proximity" in css)
check("thumb friendly buttons", "min-width: 44px" in css and "min-height: 44px" in css)
check("media fallback", "nv-video-fallback" in css and "nv-video-fallback" in js)
check("stable viewport var", "--nv-vh" in js)
