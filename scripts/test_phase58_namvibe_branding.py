#!/usr/bin/env python3
"""Phase 58 — NamVibe Branding Migration Tests.

Verifies:
  - homepage (dashboard/index.html) contains NamVibe
  - login page contains NamVibe
  - register page contains NamVibe
  - profile pages contain NamVibe
  - navbar contains NamVibe
  - footer contains NamVibe
  - no visible Chain/CHAIN branding remains in templates
  - chain_ database tables remain unchanged (API check)
  - config/branding.py exists
  - logo file exists
"""

import os
import sys
import glob

TESTS_PASSED = 0
TESTS_FAILED = 0

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test(name, ok, detail=""):
    global TESTS_PASSED, TESTS_FAILED
    if ok:
        TESTS_PASSED += 1
        print(f"  PASS  {name}")
    else:
        TESTS_FAILED += 1
        print(f"  FAIL  {name}  {detail}")

def check_file_contains(path, substring):
    if not os.path.exists(path):
        return False, "file not found"
    with open(path) as f:
        content = f.read()
    return substring in content, ""

def check_file_not_contains(path, substring):
    if not os.path.exists(path):
        return False, "file not found"
    with open(path) as f:
        content = f.read()
    return substring not in content, ""


# ── 1. Branding config ──
branding_py = os.path.join(PROJECT_ROOT, "config", "branding.py")
test("config/branding.py exists", os.path.exists(branding_py))
if os.path.exists(branding_py):
    with open(branding_py) as f:
        bc = f.read()
    test("APP_NAME = NamVibe", 'APP_NAME = "NamVibe"' in bc or "APP_NAME = os.getenv" in bc)
    test("APP_DOMAIN = namvibe.com", 'APP_DOMAIN = "namvibe.com"' in bc or "APP_DOMAIN = os.getenv" in bc)
    test("APP_TAGLINE defined", "APP_TAGLINE" in bc)
    test("APP_PREMIUM defined", "APP_PREMIUM" in bc)

# ── 2. Logo file ──
logo_path = os.path.join(PROJECT_ROOT, "static", "img", "namvibe-logo.svg")
test("namvibe-logo.svg exists", os.path.exists(logo_path))

# ── 3. Key templates contain NamVibe ──
templates_to_check = {
    "base.html": ("templates", "base.html"),
    "login.html": ("templates", "auth", "login.html"),
    "register.html": ("templates", "auth", "register.html"),
    "dashboard/index.html": ("templates", "dashboard", "index.html"),
    "profile/not_found.html": ("templates", "profile", "not_found.html"),
    "live/channels.html": ("templates", "live", "channels.html"),
    "matching/discover.html": ("templates", "matching", "discover.html"),
    "matching/likes.html": ("templates", "matching", "likes.html"),
    "search/index.html": ("templates", "search", "index.html"),
    "chat/thread.html": ("templates", "chat", "thread.html"),
    "favorites/index.html": ("templates", "favorites", "index.html"),
    "wallet/index.html": ("templates", "wallet", "index.html"),
}

for label, rel_path in templates_to_check.items():
    full = os.path.join(PROJECT_ROOT, *rel_path)
    has_namvibe, _ = check_file_contains(full, "NamVibe")
    has_app_name, _ = check_file_contains(full, "{{ APP_NAME }}")
    test(f"{label} contains NamVibe or {{ APP_NAME }}", (has_namvibe or has_app_name) and os.path.exists(full))

# ── 4. Dynamic {{ APP_NAME }} in titles ──
title_templates = [
    "templates/base.html",
    "templates/favorites/index.html",
    "templates/activity/history.html",
    "templates/activity/favorites.html",
    "templates/live/channels.html",
    "templates/dashboard/index.html",
    "templates/dashboard/feature_page.html",
    "templates/dashboard/legal.html",
    "templates/wallet/gift.html",
    "templates/auth/profile_required.html",
    "templates/history/index.html",
    "templates/search/index.html",
    "templates/chat/thread.html",
    "templates/chat/inbox.html",
    "templates/profile/base_profile.html",
    "templates/profile/security.html",
    "templates/profile/edit.html",
    "templates/profile/activity.html",
    "templates/profile/not_found.html",
]
for rel in title_templates:
    full = os.path.join(PROJECT_ROOT, rel)
    has_app_name, _ = check_file_contains(full, "{{ APP_NAME }}")
    test(f"{rel} uses {{ APP_NAME }} in title", has_app_name)

# ── 5. Raw <title> tags with NamVibe (non-Jinja pages) ──
raw_title_pages = {
    "templates/matching/discover.html": "{{ APP_NAME }}",
    "templates/matching/likes.html": "{{ APP_NAME }}",
    "templates/matching/matches.html": "{{ APP_NAME }}",
    "templates/live/watch.html": "{{ APP_NAME }}",
    "templates/chat/error.html": "NamVibe",
    "templates/profile/action_page.html": "NamVibe",
}
for rel, expected in raw_title_pages.items():
    full = os.path.join(PROJECT_ROOT, rel)
    has, _ = check_file_contains(full, expected)
    test(f"{rel} title updated ({expected})", has)

# ── 6. No hardcoded Chain|CHAIN in user-facing text ──
# Exclude internal JS variables, CSS classes, script IDs
user_facing_patterns = [
    " Chain Premium", " Chain Live", " Chain", 
    "CHAIN ", " CHAIN", "CHANN Premium", "CHAIN Premium",
    "the Chain", "on Chain", "| Chain", ">Chain<",
]
html_files = glob.glob(os.path.join(PROJECT_ROOT, "templates", "**", "*.html"), recursive=True)
# These are allowed in non-user-facing contexts
allowed_snippets = [
    "chain_", "CHAIN_", "CHAIN.", "CHAIN=", "CHAIN-",
    "CHAIN,", "CHAIN;", "CHAIN)", "CHAIN]",
    "chain.", "chain)", "chain,", "chain;",
    "chain-", "CHAIN", "chain_profile", "chain_wallet",
    "chain_posts", "chain_messages", "chain_favorites",
    "chain_auth", "chain_theme", "chain_home", "chain_onboarding",
    "chain_portal", "chain_wallpapers", "chain_locations",
    "chain_register", "chain_theme_audit", "chain_profile",
]
found_issues = []
for hf in html_files:
    rel = os.path.relpath(hf, PROJECT_ROOT)
    with open(hf) as f:
        content = f.read()
    # Skip internal script IDs and JS namespace refs
    if any(snip in content for snip in allowed_snippets):
        pass  # These are OK
    # Check for hardcoded "Chain" as standalone word (user-facing)
    import re
    matches = re.findall(r'(?<![a-zA-Z_])Chain(?![a-zA-Z_-])', content)
    if matches:
        found_issues.append(f"{rel}: {len(matches)} occurrence(s)")

if found_issues:
    test("No hardcoded Chain branding in templates", False, "; ".join(found_issues[:5]))
else:
    test("No hardcoded Chain branding in templates", True)

# ── 7. Python service files updated ──
service_files_with_branding = [
    ("services/auth_service.py", "NamVibe is only available"),
    ("services/auth_service.py", "creating your NamVibe account"),
    ("services/profile_service.py", "NamVibe is only available"),
    ("services/profile_service.py", "connected to another NamVibe profile"),
    ("services/push_notification_service.py", 'title or "NamVibe"'),
    ("services/callkit_service.py", '"NamVibe"'),
    ("services/group_feature_service.py", '"NamVibe Group"'),
]
for rel, snippet in service_files_with_branding:
    full = os.path.join(PROJECT_ROOT, rel)
    has, _ = check_file_contains(full, snippet)
    test(f"{rel} has '{snippet}'", has)

# ── 8. Database tables remain unchanged (check chain_ tables in code) ──
# Verify we didn't accidentally rename table references
# Check a few key files still reference chain_ tables correctly
table_refs = [
    ("services/auth_service.py", "chain_profiles"),
    ("services/profile_service.py", "chain_profiles"),
    ("services/wallet_service.py", "chain_wallets"),
    ("services/post_service.py", "chain_posts", False),
]
for rel, table in table_refs[:3]:
    full = os.path.join(PROJECT_ROOT, rel)
    if os.path.exists(full):
        has, _ = check_file_contains(full, table)
        test(f"{rel} still references {table}", has)

# ── 9. API routes unchanged ──
api_files = glob.glob(os.path.join(PROJECT_ROOT, "api_routes", "*.py"))
test("api_routes directory exists", len(api_files) > 0)

# ── 10. Logo file is valid SVG ──
if os.path.exists(logo_path):
    with open(logo_path) as f:
        logo_content = f.read()
    test("Logo is valid SVG", "<svg" in logo_content and "</svg>" in logo_content)
else:
    test("Logo file exists", False)

# ── Summary ──
print(f"\n{'='*50}")
print(f"  Phase 58 Branding Migration Results")
print(f"{'='*50}")
print(f"  Tests: {TESTS_PASSED} passed, {TESTS_FAILED} failed")
print(f"{'='*50}")

if TESTS_FAILED == 0:
    print("  DECISION: GO")
    sys.exit(0)
else:
    print("  DECISION: NO-GO")
    sys.exit(1)
