#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
home = (ROOT / "templates/chain_home.html").read_text()
actions = (ROOT / "static/js/home_real_actions.js").read_text()
reels = (ROOT / "static/js/reels_autoplay_engine.js").read_text()
suggestions = (ROOT / "services/smart_suggestion_service.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("home has real sections", all(s in home for s in ["Suggested Creators", "Trending Hashtags", "Live Now", "nv-reel-card"]))
check("home includes smart suggestions", "smart_suggestions" in home and "smart_suggestions.js" in home)
check("home includes recommendation cards", "smart-popout-card" in home and "data-dismiss-card" in home)
check("home includes autoplay engine", "reels_autoplay_engine.js" in home and "IntersectionObserver" in reels)
check("home action buttons are wired", all(term in actions for term in ["likeReel", "saveReel", "shareReel", "followProfile"]))
check("home no floating shortcut", "app-floating-create" not in home)
check("home no fake/test visible copy", not any(t in home.lower() for t in ["phase8", "production reel", "test reel", "original sound", "coming soon"]))
check("suggestions use real privacy filters", "is_blocked_any" in suggestions and "is_fake_content" in suggestions)
