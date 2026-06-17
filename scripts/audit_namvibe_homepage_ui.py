#!/usr/bin/env python3
"""Audit script for NamVibe Homepage UI quality checks."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS = 0
FAIL = 0
WARN = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1


def warn(label, detail=""):
    global WARN
    print(f"  [WARN] {label}" + (f" — {detail}" if detail else ""))
    WARN += 1


def read(path):
    full = ROOT / path
    if not full.exists():
        return None
    return full.read_text(encoding="utf-8", errors="replace")


def main():
    os.chdir(ROOT)

    print("=" * 60)
    print("NamVibe Homepage UI Audit")
    print("=" * 60)

    # --- 1. Check no duplicate nav blocks on homepage template ---
    home = read("templates/chain_home.html")
    check("chain_home.html exists", home is not None)
    if home is None:
        return 1

    # Check for duplicate mobile navs (exact class match, not nested elements)
    mobile_nav_count = len(re.findall(r'class="mobile-bottom-nav"', home))
    check("At most 1 mobile bottom nav", mobile_nav_count <= 1,
          f"found {mobile_nav_count}")

    # Check left-rail appears once
    left_rail_count = len(re.findall(r'home-left-rail', home))
    check("At most 1 desktop left rail", left_rail_count <= 1,
          f"found {left_rail_count}")

    # Check the base nav blocks are overridden
    check("top_header block overridden", "{% block top_header %}{% endblock %}" in home)
    check("mobile_nav block overridden", "{% block mobile_nav %}{% endblock %}" in home)

    # --- 2. No visible CHAIN branding on homepage ---
    branding_patterns = [
        r'[Cc][Hh][Aa][Ii][Nn]\s*[Pp][Rr][Ee][Mm][Ii][Uu][Mm]',
        r'[Cc]hain\s*[Uu]ser',
        r'[Cc]hain\s*[Mm]ember',
        r'[Cc]hain\s*[Hh]ost',
        r'[Oo]n\s*[Cc]hain[.\s]',
        r'[Jj]oin\s*the\s*[Cc]hain',
    ]
    branding_issues = []
    for line_num, line in enumerate(home.splitlines(), 1):
        for pat in branding_patterns:
            if re.search(pat, line) and "chain_home" not in line and "chain-home" not in line:
                branding_issues.append((line_num, line.strip()))
    check("No visible CHAIN branding in homepage template",
          len(branding_issues) == 0,
          f"found {len(branding_issues)} issue(s): {branding_issues[:3]}")
    if branding_issues:
        for ln, txt in branding_issues[:3]:
            warn(f"Branding at line {ln}: {txt[:80]}")

    # Check NamVibe appears as brand
    check("NamVibe brand in homepage", "NamVibe" in home)

    # Check no 'chain' username fallback remains
    check("No 'chain' username fallback",
          "'chain' " not in home and "or 'chain'" not in home)

    # --- 3. No phase8 test posts shown in homepage rendering ---
    check("No 'Phase 8 Persistence' display name",
          "Phase 8 Persistence" not in home)
    check("No 'phase8_' in server-rendered section",
          "phase8_" not in home)

    # Check the real_data_guard filters Phase 8 by content
    guard = read("services/homepage_real_data_guard.py")
    check("real_data_guard.py exists", guard is not None)
    if guard:
        check("Phase 8 display pattern filter exists",
              "PHASE8_DISPLAY_PATTERN" in guard)
        check("Phase 8 content pattern filter exists",
              "PHASE8_CONTENT_PATTERN" in guard)

    # --- 4. Mobile CSS media queries exist ---
    css_home = read("static/css/chain_home.css")
    css_premium = read("static/css/homepage_premium.css")
    combined_css = (css_home or "") + (css_premium or "")

    check("Mobile media query (max-width: 768px) in CSS",
          "@media (max-width: 768px)" in combined_css or
          "@media (max-width: 760px)" in combined_css or
          "@media (max-width: 480px)" in combined_css)
    check("Min-width desktop media query",
          "@media (min-width: 1024px)" in combined_css or
          "@media (min-width: 761px)" in combined_css)

    # --- 5. Bottom nav exists for mobile ---
    check("mobile-bottom-nav exists in template",
          "mobile-bottom-nav" in home)
    check("mobile-nav-item exists",
          "mobile-nav-item" in home)

    # --- 6. Desktop layout exists ---
    check("home-left-rail (desktop sidebar) exists",
          "home-left-rail" in home)
    check("home-right-rail exists",
          "home-right-rail" in home)
    check("home-feed center column exists",
          "home-feed" in home)
    check("3-column layout CSS in homepage_premium",
          "grid-template-columns" in (css_premium or ""))

    # --- 7. Reconnecting banner toast class exists ---
    base = read("templates/base.html")
    check("base.html exists", base is not None)
    if base:
        check("reconnect-banner class in base.html",
              "reconnect-banner" in base)
        check("reconnect-banner.show in base.html",
              "reconnect-banner.show" in base or 'reconnect-banner.show' in base)
        check("Reconnect banner uses toast style (border-radius)",
              "border-radius" in base[base.find("reconnect-banner"):base.find("reconnect-banner")+300] if "reconnect-banner" in base else False)

    # --- 8. Feed card structure ---
    check("Post card premium class exists", "post-card-premium" in home)
    check("Post header with avatar", "post-avatar" in home)
    check("Post author info section", "post-author-info" in home)
    check("Post action buttons (like/comment/share/save)",
          "post-action-btn" in home)
    check("Composer card exists", "composer-card" in home)
    check("Feed tabs exist", "feed-tabs" in home)
    check("Story strip exists", "story-strip" in home)

    # --- 9. Composer card sections ---
    for action in ["Post", "Reel", "Story", "Live"]:
        check(f"Composer has {action} button",
              f">{action}<" in home)

    # --- 10. Right rail sections ---
    for section in ["Trending Creators", "Live Rooms", "Nearby"]:
        if section in home:
            check(f"Right rail has '{section}' section", True)
        else:
            warn(f"Right rail missing '{section}' section - possibly hidden by conditional")

    # --- 11. FontAwesome loaded ---
    if base:
        check("FontAwesome CSS loaded",
              "font-awesome" in base or "fontawesome" in base)

    # --- 12. Mobile font-size >= 16px on inputs ---
    if combined_css:
        has_min_font = False
        for line in combined_css.splitlines():
            if "font-size" in line and "16px" in line and "@media" in combined_css[:combined_css.find(line)]:
                has_min_font = True
                break
        if has_min_font:
            check("Mobile font-size 16px set", True)
        else:
            warn("Mobile font-size 16px set — check media queries",
                 "not explicitly found, but browser default may apply")

    print()
    total = PASS + FAIL
    all_pass = FAIL == 0
    print(f"Results: {PASS}/{total} passed, {FAIL} failed, {WARN} warnings")
    print("DECISION: GO" if all_pass else "DECISION: NO-GO")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
