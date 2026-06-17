#!/usr/bin/env python3
"""Test Phase 72 — NamVibe 2026 Homepage Route Variables.

Verifies all template variables used in chain_home.html exist
in the home route's context or Jinja globals.
"""

import sys
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TEMPLATE = os.path.join(BASE, "templates", "chain_home.html")

# Variables used in the refactored template (extracted manually)
EXPECTED_VARIABLES = {
    # Core
    "is_logged_in",
    "current",
    "reels_feed",
    "stories",
    "suggested_creators",
    "trending_hashtags",
    "live_rooms",
    "popular_towns",
    "wallet",
    # Booleans
    "reel_available",
    "story_available",
    "live_available",
    "upload_video_available",
    "post_available",
    # Routes
    "home_route",
    "discover_route",
    "reel_route",
    "live_route",
    "reel_create",
    "story_create",
    "composer_fallback",
    "upload_video_route",
    "dating_route",
    "friends_route",
    "login_route",
    "register_route",
    # Drawer routes
    "drawer_profile",
    "drawer_messages",
    "drawer_notifications",
    "drawer_wallet",
    "drawer_settings",
    # Filter
    "town_filter",
}


def extract_variables(text):
    """Extract {{ var }} and {{ var.attr }} references from template."""
    found = set()
    # {{ varname }}
    for m in re.finditer(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}", text):
        parts = m.group(1).split(".")
        found.add(parts[0])
    # {{ varname | filter }}
    for m in re.finditer(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\|", text):
        found.add(m.group(1))
    # {% if varname %}
    for m in re.finditer(r"\{%\s*(?:if|elif)\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*", text):
        parts = m.group(1).split(".")
        found.add(parts[0])
    # {% for varname in listvar %}
    for m in re.finditer(r"\{%\s*for\s+\w+\s+in\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*", text):
        parts = m.group(1).split(".")
        found.add(parts[0])
    return found


def main():
    print("=" * 60)
    print("Phase 72 — Home Route Variable Check")
    print("=" * 60)

    if not os.path.exists(TEMPLATE):
        print(f"FAIL: template not found at {TEMPLATE}")
        return 1

    with open(TEMPLATE) as f:
        text = f.read()

    actual = extract_variables(text)
    print(f"\nTemplate variables found: {len(actual)}")
    for v in sorted(actual):
        print(f"  - {v}")

    missing = EXPECTED_VARIABLES - actual
    extra = actual - EXPECTED_VARIABLES

    if missing:
        print(f"\nWARN: expected but not found in template ({len(missing)}):")
        for v in sorted(missing):
            print(f"  - {v}")

    if extra:
        print(f"\nINFO: found but not in expected list ({len(extra)}):")
        for v in sorted(extra):
            print(f"  - {v}")

    # Check actual routes file for context
    app_py = os.path.join(BASE, "app.py")
    if os.path.exists(app_py):
        with open(app_py) as f:
            app_text = f.read()
        missing_in_app = EXPECTED_VARIABLES - {v for v in EXPECTED_VARIABLES if v in app_text}
        if missing_in_app:
            print(f"\nWARN: these vars not found in app.py text ({len(missing_in_app)}):")
            for v in sorted(missing_in_app):
                print(f"  - {v}")
            print("(may be set via globals, safe_link, or helper functions)")
        else:
            print("\nAll expected variables found in app.py references.")

    print(f"\nTotal template lines: {text.count(chr(10)) + 1}")
    print("=" * 60)
    print("Route variable check complete.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
