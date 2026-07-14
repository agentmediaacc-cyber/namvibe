#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / "templates" / "reels.html").read_text()
js = (ROOT / "static" / "js" / "reels.js").read_text()


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


check("single active controller", "namvibe_reels_engine.js" not in tpl, "engine script still loaded")
check("viewport observer expected", "IntersectionObserver" in js or "scroll" in js, "missing observer")
check("no raw innerHTML comments", "commentList.innerHTML = comments.map" not in js, "unsafe comment rendering remains")
print("OK")
