#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "static/js/status_autoplay_engine.js").read_text()
home = (ROOT / "templates/chain_home.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("status autoplay script exists", "NamVibeStatusAutoplay" in js)
check("auto advances every 5 seconds", "setTimeout(next, 5000)" in js)
check("video advances on ended", "video.onended = next" in js)
check("tap left/right", "status-prev" in js and "status-next" in js)
check("press hold pauses", "pointerdown" in js and "pointerup" in js)
check("swipe down closes", "touchstart" in js and "touchend" in js)
check("progress bars", "status-progress" in js)
check("mute toggle", "status-mute" in js and "muted = !muted" in js)
check("reply button", "status-reply" in js)
check("filters fake status", "phase8" in js and "seed" in js)
check("template includes script", "status_autoplay_engine.js" in home)
