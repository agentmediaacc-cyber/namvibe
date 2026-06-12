#!/usr/bin/env python3
"""
Phase 58B — NamVibe visible branding cleanup test.

Verifies that specific user-facing CHAIN/Chain branding has been
replaced with NamVibe in production files.

Allows internal technical identifiers (CSS vars, class names,
JS globals, env vars, localStorage keys, DB table names, etc.)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1

# ------------------------------------------------------------------
# 1. Verify specific replacements were applied
# ------------------------------------------------------------------

def verify_replacement(path, substring, should_contain=True):
    """Check that a file does (or does not) contain a substring."""
    full = ROOT / path
    if not full.exists():
        check(f"{path} exists", False)
        return False
    text = full.read_text(encoding="utf-8", errors="replace")
    ok = (substring in text) if should_contain else (substring not in text)
    return ok

def test_specific_replacements():
    """Verify every required branding replacement was applied."""
    ok = True

    # 1. manifest.json
    r = verify_replacement("static/manifest.json", '"name": "NamVibe Premium"')
    check("manifest.json name is NamVibe Premium", r); ok &= r
    r = verify_replacement("static/manifest.json", '"short_name": "NamVibe"')
    check("manifest.json short_name is NamVibe", r); ok &= r
    r = verify_replacement("static/manifest.json", "CHAIN", should_contain=False)
    check("manifest.json has no CHAIN branding", r); ok &= r

    # 2. static/js/auth.js
    r = verify_replacement("static/js/auth.js", "NamVibe Auth System")
    check("auth.js uses NamVibe branding", r); ok &= r

    # 3. templates/profile/creator_tools.html
    r = verify_replacement("templates/profile/creator_tools.html", "#NamVibePremium")
    check("creator_tools.html uses #NamVibePremium", r); ok &= r

    # 4. api_routes/profile_routes.py
    r = verify_replacement("api_routes/profile_routes.py", "NamVibe is only available")
    check("profile_routes.py 'NamVibe is only available'", r); ok &= r
    r = verify_replacement("api_routes/profile_routes.py", "CHAIN is only available", should_contain=False)
    check("profile_routes.py no 'CHAIN is only available'", r); ok &= r

    # 5. api_routes/message_upgrade_routes.py
    r = verify_replacement("api_routes/message_upgrade_routes.py", '"NamVibe User"')
    check("message_upgrade_routes.py 'NamVibe User'", r); ok &= r

    # 6. services/auth_service.py
    r = verify_replacement("services/auth_service.py", '"NamVibe User"')
    check("auth_service.py 'NamVibe User'", r); ok &= r
    r = verify_replacement("services/auth_service.py", '"Chain User"', should_contain=False)
    check("auth_service.py no 'Chain User'", r); ok &= r

    # 7. services/chat_service.py
    r = verify_replacement("services/chat_service.py", '"NamVibe Member"')
    check("chat_service.py 'NamVibe Member'", r); ok &= r

    # 8. services/live_service.py
    for phrase in ['"NamVibe Host"', '"My NamVibe Live Room"', '"Welcome to my NamVibe live room."']:
        r = verify_replacement("services/live_service.py", phrase)
        check(f"live_service.py has {phrase}", r); ok &= r
    for phrase in ['"Chain Host"', '"My Chain Live Room"', '"Welcome to my Chain live room."']:
        r = verify_replacement("services/live_service.py", phrase, should_contain=False)
        check(f"live_service.py no {phrase}", r); ok &= r

    # 9. services/matching_service.py
    r = verify_replacement("services/matching_service.py", '"You matched with someone on NamVibe."')
    check("matching_service.py 'on NamVibe'", r); ok &= r

    # 10. services/activity_service.py
    r = verify_replacement("services/activity_service.py", '"Post from NamVibe feed"')
    check("activity_service.py 'NamVibe feed'", r); ok &= r
    r = verify_replacement("services/activity_service.py", '"Saved from your NamVibe activity."')
    check("activity_service.py 'NamVibe activity'", r); ok &= r

    # 11. services/creator_ai_service.py
    for tag in ["#NamVibe", "#NamVibePremium", "#NamVibeCreators"]:
        r = verify_replacement("services/creator_ai_service.py", tag)
        check(f"creator_ai_service.py has {tag}", r); ok &= r
    for tag in ["#Chain", "#ChainPremium", "#ChainCreators"]:
        r = verify_replacement("services/creator_ai_service.py", tag, should_contain=False)
        check(f"creator_ai_service.py no {tag}", r); ok &= r
    r = verify_replacement("services/creator_ai_service.py", "Join NamVibe!")
    check("creator_ai_service.py 'Join NamVibe!'", r); ok &= r
    r = verify_replacement("services/creator_ai_service.py", "Join the Chain!", should_contain=False)
    check("creator_ai_service.py no 'Join the Chain!'", r); ok &= r

    # 12. scripts/seed_phase60_notifications.py
    r = verify_replacement("scripts/seed_phase60_notifications.py", "500 NamVibe coins")
    check("seed_phase60_notifications.py 'NamVibe coins'", r); ok &= r
    r = verify_replacement("scripts/seed_phase60_notifications.py", "NamVibe Premium Notification Center")
    check("seed_phase60_notifications.py 'NamVibe Premium'", r); ok &= r

    # 13. services/wallet_action_service.py
    r = verify_replacement("services/wallet_action_service.py", "NAMVIBE-TOPUP-")
    check("wallet_action_service.py NAMVIBE-TOPUP", r); ok &= r

    return ok


# ------------------------------------------------------------------
# 2. Spot-check for remaining visible branding in user-facing files
# ------------------------------------------------------------------

USER_FACING_FILES = [
    "services/auth_service.py",
    "services/chat_service.py",
    "services/live_service.py",
    "services/matching_service.py",
    "services/activity_service.py",
    "services/creator_ai_service.py",
    "services/wallet_action_service.py",
    "api_routes/profile_routes.py",
    "api_routes/message_upgrade_routes.py",
    "static/js/auth.js",
    "static/manifest.json",
    "templates/profile/creator_tools.html",
]

# Substrings that represent remaining CHAIN/Chain branding (not internal code)
BAD_BRANDING = [
    '"CHAIN Premium"',
    '"Chain Premium"',
    '"Chain User"',
    '"Chain Member"',
    '"Chain Host"',
    '"My Chain Live Room"',
    '"Welcome to my Chain live room"',
    '"on Chain."',
    '"Join the Chain"',
    '"CHAIN is only available"',
    '"Post from Chain feed"',
    '"Saved from your Chain activity"',
    '"You matched with someone on Chain."',
    '"You received 500 CHAIN coins"',
    '"CHAIN Premium Notification Center"',
    '"CHAIN-TOPUP-"',
    '"#ChainPremium"',
    '"#ChainCreators"',
    '"#Chain"',
    '"CHAIN coins"',
    '"CHAIN User"',
]

def test_remaining_branding():
    """Check no user-facing files contain leftover CHAIN branding strings."""
    found = 0
    for rel in USER_FACING_FILES:
        full = ROOT / rel
        if not full.exists():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        for bad in BAD_BRANDING:
            stripped = bad.strip('"')
            idx = text.find(stripped)
            if idx != -1:
                lineno = text[:idx].count("\n") + 1
                line = text.splitlines()[lineno - 1].strip()
                print(f"  BRANDING: {rel}:{lineno}: {line}")
                found += 1

    check("No leftover CHAIN/Chain visible branding in key files", found == 0,
          f"found {found} leftover branding string(s)")
    return found == 0


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    os.chdir(ROOT)
    print("=" * 60)
    print("Phase 58B: NamVibe Branding Cleanup Verification")
    print("=" * 60)

    replaces_ok = test_specific_replacements()
    print()
    branding_ok = test_remaining_branding()
    print()

    total = PASS + FAIL
    all_pass = FAIL == 0
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print("DECISION: GO" if all_pass else "DECISION: NO-GO")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
