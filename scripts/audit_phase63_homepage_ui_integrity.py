#!/usr/bin/env python3
"""Phase 63 — Homepage UI Integrity Audit.

Checks templates/chain_home.html, static/css/namvibe_2026_home.css,
and static/js/namvibe_2026_home.js for correctness.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TPL = os.path.join(BASE, "templates", "chain_home.html")
CSS = os.path.join(BASE, "static", "css", "namvibe_2026_home.css")
JS = os.path.join(BASE, "static", "js", "namvibe_2026_home.js")


def read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def test_template():
    """Check chain_home.html integrity."""
    print("--- Template: chain_home.html ---")
    text = read_text(TPL)
    if not text:
        print("  FAIL: File not found or empty")
        return False

    # Positive checks: these things MUST exist
    positive_checks = {
        "nv-home-shell exists": "nv-home-shell",
        "nv-left-rail exists": "nv-left-rail",
        "nv-feed-center exists": "nv-feed-center",
        "nv-right-rail exists": "nv-right-rail",
        "nv-mobile-drawer exists": "nv-mobile-drawer",
        "nv-bottom-nav exists": "nv-bottom-nav",
        "nv-story-modal exists": "nv-story-modal",
        "nv-comment-drawer exists": "nv-comment-drawer",
        "nv-share-drawer exists": "nv-share-drawer",
    }

    # Negative checks: these things must NOT exist
    negative_checks = {
        "no href='#'": r'href\s*=\s*"#"',
        "no javascript:void(0) without data-action": r'href\s*=\s*"javascript:void\(0\)"',
        "no Test User text": "Test User",
        "no tester_ text": "tester_",
        "no Phase 8 text": "Phase 8",
        "no lorem ipsum": "lorem ipsum",
        "no visible 'Avatar'": r'>\s*Avatar\s*<',
    }

    all_ok = True
    for name, search in positive_checks.items():
        found = search in text
        if found:
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")
            all_ok = False

    for name, pattern in negative_checks.items():
        found = bool(re.search(pattern, text))
        if found:
            print(f"  FAIL: {name}")
            all_ok = False
        else:
            print(f"  PASS: {name}")

    return all_ok


def test_css():
    """Check namvibe_2026_home.css integrity."""
    print("\n--- CSS: namvibe_2026_home.css ---")
    text = read_text(CSS)
    if not text:
        print("  FAIL: File not found or empty")
        return False

    checks = {
        "theme variables exist": "--nv-bg:" in text,
        "mobile media query": "@media (max-width" in text,
        "desktop 3-column grid": "grid-template-columns: var(--nv-left-rail)" in text,
        "story modal max-width 520px": "max-width: 520px" in text,
        "mobile bottom sheet exists": "align-items: flex-end" in text,
    }

    fail_patterns = {
        "no pink hardcoded": r"#[fF][0-9a-fA-F]{2}[0-9a-fA-F]*[pP]ink|#ff69b4|#ff1493",
        "no purple hardcoded": r"#[8-9a-fA-F][0-9a-fA-F]{2}[0-9a-fA-F]*[pP]urple|#800080|#9400d3",
        "no old blue theme": r"#[0-3][0-9a-fA-F]{2}[0-9a-fA-F]{3}[bB]lue|#0000ff|#1e90ff",
    }

    all_ok = True
    for name, ok in checks.items():
        if ok:
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")
            all_ok = False

    for name, pattern in fail_patterns.items():
        if re.search(pattern, text):
            print(f"  FAIL: {name}")
            all_ok = False
        else:
            print(f"  PASS: {name}")

    return all_ok


def test_js():
    """Check namvibe_2026_home.js integrity."""
    print("\n--- JS: namvibe_2026_home.js ---")
    text = read_text(JS)
    if not text:
        print("  FAIL: File not found or empty")
        return False

    checks = {
        "initTikTokFeed exists": "function initTikTokFeed" in text,
        "double tap like exists": "handleDoubleTap" in text or "dblclick" in text or "lastTap" in text,
        "follow handler exists": "toggleFollow" in text or "initFollowButtons" in text,
        "save handler exists": "saveReel" in text or "initSaveButtons" in text,
        "comment drawer exists": "initCommentDrawer" in text or "openCommentDrawer" in text,
        "share drawer exists": "initShareDrawer" in text or "openShareDrawer" in text,
        "story upload exists": "initStoryModal" in text,
        "reconnect debounce exists": "initReconnectBanner" in text and "online" in text and "offline" in text,
        "avatar fallback exists": "initAvatarFallback" in text,
    }

    missing_element_risks = []

    # Check for risky element lookups (querySelector with data-attribute containing dynamic values)
    # Find patterns like querySelector('...[data-reel-id="' + x + '"]')
    risky_patterns = [
        r"querySelector\([^)]*\+\s*[a-zA-Z]",
        r"querySelector\([^)]*reelId",
    ]
    for pattern in risky_patterns:
        for m in re.finditer(pattern, text):
            line = text[:m.start()].count("\n") + 1
            missing_element_risks.append(f"  WARN: Risky dynamic selector at line {line}")

    all_ok = True
    for name, ok in checks.items():
        if ok:
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")
            all_ok = False

    if missing_element_risks:
        for risk in missing_element_risks:
            print(risk)

    return all_ok


def main():
    print("=" * 60)
    print("Phase 63 — Homepage UI Integrity Audit")
    print("=" * 60)

    results = [
        ("Template integrity", test_template()),
        ("CSS integrity", test_css()),
        ("JS integrity", test_js()),
    ]

    print("\n" + "=" * 60)
    all_pass = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            all_pass = False

    print(f"\nOVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
