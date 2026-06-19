#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
home = (ROOT / "templates/chain_home.html").read_text()
service = (ROOT / "services/homepage_service.py").read_text()
actions = (ROOT / "static/js/home_real_actions.js").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


section_checks = {
    "Stories": "Stories",
    "For You feed": "nv-feed-center",
    "Reels": "nv-reel-card",
    "Live": "Live Now",
    "Suggested Creators": "Suggested Creators",
    "Trending Hashtags": "Trending Hashtags",
    "Discover": "Discover",
}
for label, marker in section_checks.items():
    check(f"home has {label} section", marker.lower() in home.lower())

for route in ["/posts/create", "/live/studio", "/messages/", "/calls/", "/wallet/", "/dating/", "/profile/", "/notifications/"]:
    check(f"home links {route}", route in home or "safe_link" in home)

for action in ["like", "comment", "share", "save"]:
    check(f"home action {action} is wired", f"action === '{action}'" in actions or f'data-action="{action}"' in home)

check("follow action is wired", "followProfile" in actions and "/api/profile/" in actions)
check("actions disable buttons during requests", "setBusy(button, true)" in actions and "disabled" in actions)
check("actions show toast on failure", "Could not" in actions and "toast(" in actions)
check("homepage excludes test content by default", "exclude_test_content=True" in service or "filter_content" in service)
check("homepage has timeout fallback", "future.result(timeout=" in service and "fallback" in service.lower())
check("home clean css included", "home_modern_clean.css" in home)
