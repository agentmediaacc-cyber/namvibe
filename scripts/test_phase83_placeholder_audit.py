#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.production_content_guard import clean_text_for_public, filter_fake_content, is_fake_content, should_hide_placeholder


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("phase8 usernames hidden", is_fake_content({"username": "phase8_demo"}))
check("production reels hidden", is_fake_content({"caption": "Phase 8 production reel"}))
check("seed markers hidden", is_fake_content({"title": "seed test reel"}))
check("normal production row allowed", not is_fake_content({"username": "moon", "caption": "Real update"}))
check("filter removes fake rows", len(filter_fake_content([{"username": "moon"}, {"username": "phase8_x"}])) == 1)
check("placeholder detector works", should_hide_placeholder("Coming soon"))
check("public text cleaner blanks fake copy", clean_text_for_public("lorem ipsum placeholder") == "")

public_paths = [
    ROOT / "templates/chain_home.html",
    ROOT / "templates/reels/index.html",
    ROOT / "templates/reels/upload.html",
    ROOT / "templates/profile/index.html",
]
bad_terms = ["phase8", "production reel", "test reel", "original sound", "lorem ipsum", "dummy user"]
for path in public_paths:
    text = path.read_text().lower()
    for term in bad_terms:
        check(f"{path.name} has no {term}", term not in text)
