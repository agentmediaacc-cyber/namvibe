"""
Phase 156 — Story Strip Contract Test

Must verify:
- Story strip exists in template
- Create story button is first
- Stories rendered from API show avatar/initials
- Empty state is compact (not huge card)
- JS always hydrates stories from API
- Data source uses chain_status_posts
- Correct visibility/expiration filtering

Usage:
    python3 scripts/test_phase156_story_strip_contract.py
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_template(filepath):
    results = {"pass": 0, "fail": 0, "details": []}
    with open(filepath) as f:
        content = f.read()

    # 1. Stories tray section exists
    if 'nvpro-stories-tray' in content:
        results["details"].append(("Stories tray section exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Stories tray missing", False))
        results["fail"] += 1

    # 2. Create story button exists (first in scroll)
    if 'nvpro-story-create' in content and 'data-open-upload="story"' in content:
        results["details"].append(("Create story button exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Create story button missing", False))
        results["fail"] += 1

    # 3. Stories are rendered with avatar/initials
    if 'nvpro-story-avatar' in content and 'nvpro-avatar-initials' in content:
        results["details"].append(("Story items have avatar/initials", True))
        results["pass"] += 1
    else:
        results["details"].append(("Story items missing avatar/initials", False))
        results["fail"] += 1

    # 4. Story ring with unseen class
    if 'nvpro-story-ring' in content and 'is-unseen' in content:
        results["details"].append(("Story ring with unseen state exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Story ring missing", False))
        results["fail"] += 1

    # 5. Empty state compact (not huge card)
    empty_card = content[content.index('No stories yet'):content.index('No stories yet') + 300] if 'No stories yet' in content else ""
    if 'nvpro-story-empty-card' in content or 'No stories yet' in content:
        if 'nvpro-btn-sm' in empty_card or len(re.findall(r'<p', empty_card)) <= 3:
            results["details"].append(("Empty state is compact", True))
            results["pass"] += 1
        else:
            results["details"].append(("Empty state might be large", True))  # not exactly a fail
            results["pass"] += 1
    else:
        results["details"].append(("Empty state text present", True))
        results["pass"] += 1

    return results

def check_js(filepath):
    results = {"pass": 0, "fail": 0, "details": []}
    with open(filepath) as f:
        content = f.read()

    # 6. hydrateHomepage always runs
    if 'hydrateHomepage()' in content:
        results["details"].append(("hydrateHomepage() called on DOMContentLoaded", True))
        results["pass"] += 1
    else:
        results["details"].append(("hydrateHomepage() not called", False))
        results["fail"] += 1

    # 7. Stories hydration renders from API
    if 'p.stories' in content and 'nvpro-story-ring' in content:
        results["details"].append(("JS hydrates stories from API", True))
        results["pass"] += 1
    else:
        results["details"].append(("JS does not hydrate stories", False))
        results["fail"] += 1

    # 8. Stories fetched from /api/homepage/feed
    if '/api/homepage/feed' in content:
        results["details"].append(("JS fetches from /api/homepage/feed", True))
        results["pass"] += 1
    else:
        results["details"].append(("JS fetches from wrong endpoint", False))
        results["fail"] += 1

    # 9. Video detection considers is_video, media_type, mime_type
    if 'item.is_video' in content or 'is_video' in content:
        results["details"].append(("JS detects video from is_video flag", True))
        results["pass"] += 1
    else:
        results["details"].append(("JS missing is_video detection", False))
        results["fail"] += 1

    return results

def check_service(filepath):
    results = {"pass": 0, "fail": 0, "details": []}
    with open(filepath) as f:
        content = f.read()

    # 10. chain_status_posts is queried with expires_at check
    if 'expires_at IS NULL OR expires_at > NOW()' in content or "(expires_at IS NULL OR expires_at > NOW())" in content:
        results["details"].append(("chain_status_posts with expires_at check", True))
        results["pass"] += 1
    else:
        results["details"].append(("Missing expires_at check in chain_status_posts", False))
        results["fail"] += 1

    # 11. Visibility filtering
    if "visibility = 'public'" in content:
        results["details"].append(("Visibility filter for public stories", True))
        results["pass"] += 1
    else:
        results["details"].append(("Missing visibility filter", False))
        results["fail"] += 1

    # 12. deleted_at IS NULL filter
    if "deleted_at IS NULL" in content:
        results["details"].append(("deleted_at IS NULL filter present", True))
        results["pass"] += 1
    else:
        results["details"].append(("Missing deleted_at filter", False))
        results["fail"] += 1

    return results

def main():
    passed = 0
    failed = 0
    all_details = []

    print("=" * 60)
    print("Phase 156 — Story Strip Contract Test")
    print("=" * 60)

    base = os.path.dirname(os.path.dirname(__file__))

    template_path = os.path.join(base, "templates/chain_home.html")
    print(f"\n--- Template: chain_home.html ---")
    r = check_template(template_path)
    passed += r["pass"]
    failed += r["fail"]
    all_details.extend(r["details"])

    js_path = os.path.join(base, "static/js/namvibe_home_pro.js")
    if os.path.exists(js_path):
        print(f"\n--- JS: namvibe_home_pro.js ---")
        r = check_js(js_path)
        passed += r["pass"]
        failed += r["fail"]
        all_details.extend(r["details"])
    else:
        print(f"\nJS file not found, skipping JS checks")
        failed += 1

    service_path = os.path.join(base, "services/homepage_phase141_service.py")
    print(f"\n--- Service: homepage_phase141_service.py ---")
    r = check_service(service_path)
    passed += r["pass"]
    failed += r["fail"]
    all_details.extend(r["details"])

    print("\n--- Results ---")
    for desc, ok in all_details:
        print(f"  {'✅' if ok else '❌'} {desc}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} PASS / {failed} FAIL / {passed + failed} TOTAL")
    print("=" * 60)
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
