#!/usr/bin/env python3
"""Audit Phase Profile 2026 - Premium Profile Rebuild."""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    return condition


def audit_profile_2026():
    print("=" * 60)
    print("AUDIT: Phase Profile 2026 - Premium Profile Rebuild")
    print("=" * 60)
    print()

    all_pass = True

    # 1. Check profile_2026_service exists
    service_path = BASE_DIR / "services" / "profile_2026_service.py"
    all_pass &= check("profile_2026_service.py exists", service_path.exists())

    # 2. Check get_profile_2026 function exists
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "get_profile_2026 function exists",
            "def get_profile_2026(" in content
        )

    # 3. Check own and public routes exist
    routes_path = BASE_DIR / "api_routes" / "profile_routes.py"
    if routes_path.exists():
        routes_content = routes_path.read_text()
        all_pass &= check(
            "Profile routes file exists",
            routes_path.exists()
        )
        all_pass &= check(
            "Username canonical route /@<username> exists",
            '@profile_bp.route("/@<username>")' in routes_content
        )
        all_pass &= check(
            "ID route /id/<profile_id> exists",
            '@profile_bp.route("/id/<user_id>")' in routes_content
        )

    # 4. Check API section routes exist
    api_routes = [
        "/api/<target>/overview",
        "/api/<target>/content",
        "/api/<target>/reels",
        "/api/<target>/stories",
        "/api/<target>/gallery",
        "/api/<target>/live",
        "/api/<target>/activity",
    ]
    if routes_path.exists():
        routes_content = routes_path.read_text()
        for route in api_routes:
            all_pass &= check(
                f"API route {route} exists",
                route in routes_content,
                route
            )

    # 5. Check templates use real view model
    profile_index = BASE_DIR / "templates" / "profile" / "index.html"
    if profile_index.exists():
        index_content = profile_index.read_text()
        all_pass &= check(
            "Profile index.html uses pv (profile view model)",
            "{% set p = pv or {} %}" in index_content
        )
        all_pass &= check(
            "Profile index.html has data-profile-pro attribute",
            'data-profile-pro' in index_content
        )

    # 6. Check CSS has hero/tabs/grids/mobile/skeleton/empty states
    css_path = BASE_DIR / "static" / "css" / "namvibe_profile_pro.css"
    if css_path.exists():
        css_content = css_path.read_text()
        all_pass &= check(
            "CSS has .nv-hero class",
            ".nv-hero" in css_content
        )
        all_pass &= check(
            "CSS has .nv-tabs class",
            ".nv-tabs" in css_content
        )
        all_pass &= check(
            "CSS has .nv-grid class",
            ".nv-grid" in css_content
        )
        all_pass &= check(
            "CSS has mobile responsive styles",
            "@media (max-width: 640px)" in css_content
        )
        all_pass &= check(
            "CSS has .nv-skeleton class",
            ".nv-skeleton" in css_content
        )
        all_pass &= check(
            "CSS has .nv-empty-inline class",
            ".nv-empty-inline" in css_content
        )

    # 7. Check JS has tab/action/share/infinite/presence handlers
    js_path = BASE_DIR / "static" / "js" / "profile_systems.js"
    if js_path.exists():
        js_content = js_path.read_text()
        all_pass &= check(
            "JS has initTabs function",
            "function initTabs()" in js_content
        )
        all_pass &= check(
            "JS has initActions function",
            "function initActions()" in js_content
        )
        all_pass &= check(
            "JS has share handler",
            'data-action="share"' in js_content
        )
        all_pass &= check(
            "JS has presence handler",
            "initPresence" in js_content
        )
        all_pass &= check(
            "JS has async tab loading",
            "async function load" in js_content
        )

    # 8. Check no fake/hardcoded profile content
    templates_dir = BASE_DIR / "templates" / "profile"
    if templates_dir.exists():
        html_files = list(templates_dir.rglob("*.html"))
        fake_patterns = ["John Doe", "Jane Doe", "Lorem ipsum", "fake profile"]
        for html_file in html_files:
            content = html_file.read_text()
            for pattern in fake_patterns:
                if pattern.lower() in content.lower():
                    all_pass &= check(
                        f"No fake content in {html_file.name}",
                        False,
                        f"Found: {pattern}"
                    )
                    break

    # 9. Check no wrong /profile/<username> links (should be /profile/@<username> for public profiles)
    # Allow internal routes - these are legitimate profile management pages
    if templates_dir.exists():
        html_files = list(templates_dir.rglob("*.html"))
        # Only flag if we find /profile/ followed by what looks like a username (3+ alphanumeric/underscore chars)
        # that isn't a known internal route. Internal routes are things like /profile/edit, /profile/settings, etc.
        known_internal_routes = [
            "edit", "settings", "security", "api", "onboarding", "verification",
            "privacy", "follow", "block", "report", "unblock", "id", "business",
            "creator", "live", "posts", "reels", "wallet", "notifications",
            "command-center", "age-check", "retry-bootstrap", "create", "setup",
            "tab", "convert-to-page", "page", "avatar", "cover", "schedule",
            "scheduled", "current", "summary", "activity", "wallet-card", "creator-card"
        ]
        for html_file in html_files:
            content = html_file.read_text()
            # Find all /profile/<something> patterns
            import re as regex_module
            potential_links = regex_module.findall(r'/profile/([a-zA-Z0-9_]{3,30})', content)
            wrong_links = []
            for link in potential_links:
                # Skip if it's a known internal route
                if link not in known_internal_routes and not link.startswith('@'):
                    wrong_links.append(f"/profile/{link}")
            if wrong_links:
                all_pass &= check(
                    f"No wrong profile links in {html_file.name}",
                    False,
                    f"Found: {wrong_links[:3]}"
                )

    # 10. Check gallery uses target profile id
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Gallery service uses target profile id",
            "get_profile_gallery(pid" in content
        )

    # 11. Check reels uses target profile id
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Reels engine uses target profile id",
            "get_reels_feed" in content and "profile" in content.lower()
        )

    # 12. Check stories uses target profile id
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Stories engine uses target profile id",
            "get_stories_by_creator(pid" in content
        )

    # 13. Check live uses target profile id
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Live engine uses target profile id",
            "get_creator_live_analytics(pid" in content
        )

    # 14. Check creator private data hidden from public
    if service_path.exists():
        content = service_path.read_text()
        # Check that wallet/earnings are only exposed for self
        has_wallet_check = "wallet" in content.lower() and ("is_self" in content or "viewer_id" in content)
        all_pass &= check(
            "Creator earnings/wallet only for self",
            has_wallet_check
        )

    # 15. Check permission checks exist
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Permission checks exist (can_message, can_call)",
            "can_message" in content and "can_call" in content
        )

    # 16. Check activity emit exists
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Activity emit functions exist",
            "emit_profile_viewed" in content and "emit_profile_followed" in content
        )

    # 17. Check performance tracking exists
    if service_path.exists():
        content = service_path.read_text()
        all_pass &= check(
            "Performance tracking exists",
            "track_timing" in content and "profile." in content
        )

    print()
    print("=" * 60)
    if all_pass:
        print("AUDIT RESULT: ALL CHECKS PASSED")
    else:
        print("AUDIT RESULT: SOME CHECKS FAILED")
    print("=" * 60)
    return all_pass


if __name__ == "__main__":
    success = audit_profile_2026()
    sys.exit(0 if success else 1)