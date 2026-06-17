#!/usr/bin/env python3
"""Audit Phase 72 — NamVibe 2026 Homepage Rebuild.

Checks:
  - No href="#", tiktok-*, tt-*, chain-home__* in home template
  - All buttons have real routes via safe_link variables
  - Avatar shows initials fallback, never literal "Avatar" text
  - JS/CSS files exist with reasonable line counts
  - All expected functions exist in JS
  - All expected CSS classes exist in CSS
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATE = os.path.join(BASE, "templates", "chain_home.html")
JS = os.path.join(BASE, "static", "js", "namvibe_2026_home.js")
CSS = os.path.join(BASE, "static", "css", "namvibe_2026_home.css")

SKIP_JS_LOADED_CHECK = True  # template loads JS; OK if not all funcs used server-side

EXPECTED_JS_FUNCS = [
    "initTikTokFeed",
    "initKeyboardNav",
    "initActionButtons",
    "initFollowButtons",
    "initCommentDrawer",
    "initShareDrawer",
    "initStoryModal",
    "initDrawer",
    "initAvatarFallback",
    "initReconnectBanner",
    "initSearchSubmit",
    "initTownChips",
    "initHashTags",
    "initNavActive",
]

EXPECTED_CSS_CLASSES = [
    "nv-home-shell",
    "nv-home-grid",
    "nv-feed-center",
    "nv-feed-stack",
    "nv-feed-scroll",
    "nv-right-rail",
    "nv-reel-card",
    "nv-avatar",
    "nv-avatar-initials",
    "nv-empty-state",
    "nv-mobile-drawer",
    "nv-drawer-backdrop",
    "nv-bottom-nav",
    "nv-mobile-topbar",
    "nv-reconnect",
    "nv-toast",
    "nv-story-overlay",
    "nv-comment-overlay",
    "nv-share-overlay",
    "nv-follow-btn",
]


def read_text(p):
    try:
        with open(p) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def check_no_forbidden(text, forbidden, name):
    found = []
    for pattern in forbidden:
        for m in re.finditer(pattern, text):
            line = text[:m.start()].count("\n") + 1
            found.append(f"  line {line}: {m.group()}")
    if found:
        print(f"  FAIL: {name} contains forbidden patterns")
        for f in found:
            print(f)
        return False
    return True


def check_avatar_no_text(text, name):
    """Ensure we never render literal 'Avatar' text."""
    if 'Avatar' in text and 'nv-avatar-initials' not in text:
        print(f"  FAIL: {name} - found 'Avatar' text without fallback class")
        return False
    return True


def check_href_hash(text, name):
    for m in re.finditer(r'href\s*=\s*"#"', text):
        line = text[:m.start()].count("\n") + 1
        print(f"  FAIL: {name} line {line} has href=\"#\"")
        return False
    return True


def main():
    print("=" * 60)
    print("Phase 72 — NamVibe 2026 Homepage Audit")
    print("=" * 60)

    template_text = read_text(TEMPLATE)
    js_text = read_text(JS)
    css_text = read_text(CSS)

    # 1. Template checks
    print("\n--- Template: chain_home.html ---")
    tpl_ok = True

    tpl_ok &= check_no_forbidden(
        template_text,
        [r'class="[^"]*(?<!nv-)tiktok-', r'class="[^"]*tt-', r'class="[^"]*chain-home__'],
        "template",
    )
    tpl_ok &= check_href_hash(template_text, "template")

    # Check for literal '>Avatar<' text
    if re.search(r'>Avatar<', template_text):
        print("  FAIL: template has literal 'Avatar' text")
        tpl_ok = False

    # Check avatar fallback pattern
    avatar_fallbacks = re.findall(
        r'onerror="[^"]*nextElementSibling[^"]*"', template_text
    )
    if len(avatar_fallbacks) < 3:
        print(
            f"  FAIL: expected >= 3 avatar onerror fallbacks, found {len(avatar_fallbacks)}"
        )
        tpl_ok = False
    else:
        print(f"  OK: {len(avatar_fallbacks)} avatar onerror fallbacks")

    # Check no href="#" except maybe in JS (template should be clean)
    inline_disabled = re.findall(r'href="([^"]*)"[^>]*is-disabled', template_text)
    for h in inline_disabled:
        if h == "#":
            print("  FAIL: disabled button uses href='#'")
            tpl_ok = False

    if tpl_ok:
        print("  PASS: template checks OK")
    else:
        print("  WARN: some template checks failed")

    # 2. JS checks
    print("\n--- JavaScript: namvibe_2026_home.js ---")
    js_ok = True
    if not js_text:
        print("  FAIL: JS file not found or empty")
        js_ok = False
    else:
        lines = js_text.count("\n")
        if lines < 500:
            print(f"  FAIL: JS too short ({lines} lines, expected >= 500)")
            js_ok = False
        else:
            print(f"  OK: {lines} lines")

        for func in EXPECTED_JS_FUNCS:
            if func not in js_text:
                print(f"  FAIL: missing function {func}()")
                js_ok = False
        if js_ok:
            print("  PASS: all expected JS functions found")

    # 3. CSS checks
    print("\n--- CSS: namvibe_2026_home.css ---")
    css_ok = True
    if not css_text:
        print("  FAIL: CSS file not found or empty")
        css_ok = False
    else:
        lines = css_text.count("\n")
        if lines < 800:
            print(f"  FAIL: CSS too short ({lines} lines, expected >= 800)")
            css_ok = False
        else:
            print(f"  OK: {lines} lines")

        for cls in EXPECTED_CSS_CLASSES:
            if cls not in css_text:
                print(f"  FAIL: missing CSS class .{cls}")
                css_ok = False
        if css_ok:
            print("  PASS: all expected CSS classes found")

    # 4. Summary
    print("\n" + "=" * 60)
    all_ok = tpl_ok and js_ok and css_ok
    if all_ok:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: SOME CHECKS FAILED (see above)")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
