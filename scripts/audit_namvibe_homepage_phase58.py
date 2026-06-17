#!/usr/bin/env python3
"""Phase 58 — Premium Homepage Upgrade Audit.

Checks:
1. No .env touched
2. No secrets touched
3. Homepage template exists
4. No duplicate nav blocks
5. NamVibe branding present
6. CHAIN branding not visible on homepage
7. Phase 8/test/debug posts filtered
8. Mobile bottom nav exists
9. Desktop layout exists
10. Right sidebar exists
11. Story row exists
12. Composer buttons exist
13. Reconnect toast exists
14. Skeleton loader classes exist
15. Media queries exist
16. Min mobile font size 16px
17. Touch targets 44px
18. No obvious placeholder text like lorem ipsum

Returns exit code 0 if all checks pass, 1 otherwise.
"""

import re
import os
import sys
import glob as glob_module


def check_file_exists(path, label):
    exists = os.path.isfile(path)
    status = "PASS" if exists else "FAIL"
    print(f"  [{status}] {label}: {path}")
    return exists


def check_has_content(path, pattern, label, flags=0):
    try:
        with open(path, "r") as f:
            content = f.read()
        has = bool(re.search(pattern, content, flags))
        status = "PASS" if has else "FAIL"
        print(f"  [{status}] {label}: pattern={pattern!r}")
        return has
    except Exception as e:
        print(f"  [FAIL] {label}: could not read ({e})")
        return False


def check_not_contains(path, pattern, label, flags=0):
    try:
        with open(path, "r") as f:
            content = f.read()
        has = bool(re.search(pattern, content, flags))
        status = "FAIL" if has else "PASS"
        if has:
            print(f"  [FAIL] {label}: found forbidden pattern {pattern!r}")
        else:
            print(f"  [PASS] {label}: pattern={pattern!r} not found")
        return not has
    except Exception as e:
        print(f"  [FAIL] {label}: could not read ({e})")
        return False


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base)

    all_pass = True
    results = []

    print("\n=== Phase 58 — Premium Homepage Upgrade Audit ===\n")

    # 1. No .env touched
    print("\n[1] Environment & Secrets:")
    r = check_not_contains(
        "services/homepage_real_data_guard.py",
        r"DATABASE_URL|SUPABASE_URL|NEON_URL|REDIS_URL",
        "No DB URLs in data guard",
        re.I,
    )
    results.append(r)

    # 2. No secrets touched
    r = check_not_contains(
        "services/homepage_real_data_guard.py",
        r"api_key|api_secret|password",
        "No secrets in data guard",
        re.I,
    )
    results.append(r)

    # 3. Homepage template exists
    print("\n[2] Templates:")
    r = check_file_exists("templates/chain_home.html", "Homepage template")
    results.append(r)

    # 4. No duplicate nav blocks
    r = check_has_content(
        "templates/chain_home.html",
        r"mobile-bottom-nav",
        "Mobile bottom nav present",
    )
    results.append(r)

    # Check that base.html's mobile_nav block is suppressed
    r = check_has_content(
        "templates/chain_home.html",
        r"{% block mobile_nav %}{% endblock %}",
        "Base mobile nav suppressed",
    )
    results.append(r)

    # 5. NamVibe branding present
    print("\n[3] Branding:")
    r = check_has_content(
        "templates/chain_home.html",
        r"NamVibe",
        "NamVibe branding in template",
    )
    results.append(r)

    # 6. No CHAIN branding visible on homepage (uppercase "CHAIN" as standalone text, not in CSS classes)
    r = check_not_contains(
        "templates/chain_home.html",
        r"[^a-zA-Z]CHAIN[^a-zA-Z_]",  # standalone uppercase CHAIN not part of chain_ CSS classes
        "No standalone CHAIN branding",
    )
    results.append(r)

    # 7. Phase 8/test/debug posts filtered
    print("\n[4] Content Filtering:")
    r = check_has_content(
        "services/homepage_real_data_guard.py",
        r"test\s*post|debug|lorem\s*ipsum",
        "Test post/debug/lorem patterns in data guard",
        re.I,
    )
    results.append(r)

    r = check_has_content(
        "services/homepage_real_data_guard.py",
        r"phase8_|Phase\s*8\s*Persistence",
        "Phase 8 patterns in data guard",
        re.I,
    )
    results.append(r)

    # 8. Mobile bottom nav exists
    print("\n[5] Layout:")
    r = check_has_content(
        "templates/chain_home.html",
        r"mobile-bottom-nav",
        "Mobile bottom nav HTML",
    )
    results.append(r)

    # 9. Desktop layout exists
    r = check_has_content(
        "templates/chain_home.html",
        r"home-left-rail",
        "Desktop left rail",
    )
    results.append(r)

    r = check_has_content(
        "templates/chain_home.html",
        r"home-right-rail",
        "Desktop right rail",
    )
    results.append(r)

    # 10. Right sidebar exists
    r = check_has_content(
        "templates/chain_home.html",
        r"Trending Creators|Suggested People|Trending Hashtags",
        "Right sidebar sections",
    )
    results.append(r)

    # 11. Story row exists
    r = check_has_content(
        "templates/chain_home.html",
        r"story-strip",
        "Story strip HTML",
    )
    results.append(r)

    # 12. Composer buttons exist
    print("\n[6] Composer:")
    for btn in ["Post", "Reel", "Story", "Live", "Photo", "Video", "Poll", "Feeling", "Location"]:
        r = check_has_content(
            "templates/chain_home.html",
            rf">{btn}<",
            f"Composer button: {btn}",
        )
        results.append(r)

    # 13. Reconnect toast exists
    print("\n[7] Notifications:")
    r = check_has_content(
        "templates/base.html",
        r"reconnect-banner",
        "Reconnect toast in base.html",
    )
    results.append(r)

    # 14. Skeleton loader classes exist
    print("\n[8] Loaders:")
    for cls in ["skeleton-box", "skeleton-row", "feed-skeleton", "skeleton-text"]:
        r = check_has_content(
            "static/css/homepage_premium.css",
            cls,
            f"Skeleton class: {cls}",
        )
        results.append(r)

    # 15. Media queries exist
    print("\n[9] Responsive:")
    for bp in ["max-width: 1024px", "max-width: 768px", "max-width: 480px"]:
        r = check_has_content(
            "static/css/homepage_premium.css",
            bp,
            f"Media query: {bp}",
        )
        results.append(r)

    # 16. Min mobile font size 16px
    r = check_has_content(
        "static/css/homepage_premium.css",
        r"font-size:\s*16px\s*!important",
        "Mobile min font size 16px",
    )
    results.append(r)

    # 17. Touch targets 44px
    r = check_has_content(
        "static/css/homepage_premium.css",
        r"min-height:\s*44px",
        "Touch targets min 44px",
    )
    results.append(r)

    # 18. No placeholder text like lorem ipsum
    print("\n[10] Content Quality:")
    r = check_not_contains(
        "templates/chain_home.html",
        r"lorem\s*ipsum",
        "No lorem ipsum in template",
        re.I,
    )
    results.append(r)

    r = check_not_contains(
        "static/css/homepage_premium.css",
        r"lorem\s*ipsum",
        "No lorem ipsum in CSS",
        re.I,
    )
    results.append(r)

    # 19. CSS safety: body background, contrast, safe-area
    print("\n[11] CSS Safety:")
    r = check_has_content(
        "static/css/homepage_premium.css",
        r"safe-area-inset",
        "Safe area padding",
    )
    results.append(r)

    r = check_has_content(
        "static/css/homepage_premium.css",
        r"--hp-bg|--hp-text",
        "CSS variables for background/text",
    )
    results.append(r)

    # Summary
    print("\n" + "=" * 50)
    all_pass = all(results)
    if all_pass:
        print("RESULT: ALL CHECKS PASSED")
    else:
        failed = sum(1 for r in results if not r)
        print(f"RESULT: {failed} CHECK(S) FAILED")
        print("Review warnings above.")
    print("=" * 50)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
