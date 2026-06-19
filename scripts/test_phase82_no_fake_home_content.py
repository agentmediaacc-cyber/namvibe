"""Phase 82: homepage excludes fake Phase/test content."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.homepage_real_data_guard import filter_content, is_test_content
from services.homepage_service import build_tiktok_home_payload

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1


def run():
    print("Phase 82: No Fake Home Content")
    fake = [
        {"username": "phase8_abcd", "caption": "real looking"},
        {"username": "creator", "caption": "Phase 8 production reel"},
        {"username": "creator", "caption": "test reel"},
        {"username": "seed_user", "caption": "hello"},
        {"username": "creator", "music_title": "Phase 8 Original Sound"},
        {"username": "real_creator", "caption": "Windhoek sunset"},
    ]
    filtered = filter_content(fake)
    check("filters phase8 username", not any(i.get("username") == "phase8_abcd" for i in filtered))
    check("filters production reel caption", not any("production reel" in (i.get("caption") or "").lower() for i in filtered))
    check("filters test reel caption", not any("test reel" in (i.get("caption") or "").lower() for i in filtered))
    check("filters seed username", not any("seed" in (i.get("username") or "").lower() for i in filtered))
    check("filters original sound", not any("original sound" in (i.get("music_title") or "").lower() for i in filtered))
    check("keeps real content", any(i.get("username") == "real_creator" for i in filtered))
    check("is_test_content catches production reel", is_test_content({"caption": "Phase 8 production reel"}))

    payload = build_tiktok_home_payload(exclude_test_content=True)
    text = str(payload.get("reels_feed", [])).lower()
    check("homepage payload has no phase8", "phase8" not in text)
    check("homepage payload has no production reel", "production reel" not in text)

    print(f"\nPhase 82 No Fake Home Content: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
