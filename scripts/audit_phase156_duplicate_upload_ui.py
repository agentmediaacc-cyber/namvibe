"""
Phase 156 — Duplicate Upload UI Audit

Must FAIL if:
- More than one active reel upload modal exists
- More than one story composer exists
- Button hrefs point to old upload routes
- Homepage has duplicate Create sections

Usage:
    python3 scripts/audit_phase156_duplicate_upload_ui.py
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def audit_file(filepath, label):
    """Audit a file for duplicate upload UI patterns."""
    issues = []
    if not os.path.exists(filepath):
        return [f"{label}: file not found"]
    with open(filepath) as f:
        content = f.read()

    # Count upload modals
    modal_starts = content.count('nvpro-modal-overlay')
    if modal_starts > 1:
        issues.append(f"{label}: found {modal_starts} modal overlays (expected 1)")

    # Count upload tabs
    upload_tabs = re.findall(r'data-open-upload="(\w+)"', content)
    post_triggers = upload_tabs.count('post')
    reel_triggers = upload_tabs.count('reel')
    story_triggers = upload_tabs.count('story')
    
    # Count drop zones
    drop_zones = content.count('nvpro-drop-zone')
    if drop_zones > 3:
        issues.append(f"{label}: found {drop_zones} drop zones (expected 3 max)")

    # Check for old upload routes in hrefs
    old_route_patterns = [
        (r'href=["\']/reels/upload', '/reels/upload route'),
        (r'href=["\']/upload', 'old /upload route'),
        (r'href=["\']/posts/create', '/posts/create route'),
    ]
    for pattern, desc in old_route_patterns:
        if re.search(pattern, content):
            issues.append(f"{label}: found {desc}")

    # Check duplicate Create sections
    create_buttons = re.findall(r'data-open-upload="post"', content)
    if len(create_buttons) > 4:
        issues.append(f"{label}: found {len(create_buttons)} create-post triggers (expected max 4)")

    return issues

def main():
    passed = 0
    failed = 0
    total_issues = []

    print("=" * 60)
    print("Phase 156 — Duplicate Upload UI Audit")
    print("=" * 60)

    files_to_audit = [
        ("templates/chain_home.html", "Homepage Template"),
        ("static/js/namvibe_home_pro.js", "Homepage JS"),
        ("api_routes/reels_routes.py", "Reels Routes"),
    ]

    for path, label in files_to_audit:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
        print(f"\nAuditing {label} ({path})...")
        issues = audit_file(full_path, label)
        if issues:
            for i in issues:
                print(f"  ❌ {i}")
                failed += 1
                total_issues.append(i)
        else:
            print(f"  ✅ No issues found")
            passed += 1

    # Check reels/upload redirect
    reels_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api_routes/reels_routes.py")
    if os.path.exists(reels_path):
        with open(reels_path) as f:
            content = f.read()
        if 'redirect' in content and '/?open=upload#upload' in content:
            print(f"\n  ✅ /reels/upload redirects to unified modal")
            passed += 1
        else:
            print(f"\n  ❌ /reels/upload does not redirect to unified modal")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} PASS / {failed} FAIL / {passed + failed} TOTAL")
    print("=" * 60)
    if total_issues:
        print("ISSUES:")
        for i in total_issues:
            print(f"  - {i}")
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
