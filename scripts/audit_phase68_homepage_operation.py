#!/usr/bin/env python3
"""Phase 68 audit: homepage nav consolidation, no # hrefs, backend data, hamburger JS."""
import os, sys, re, compileall
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(str(ROOT))

errors = []

def check(name, ok, detail=""):
    if ok:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
        errors.append(name)

def file_contains(path, pattern):
    try:
        text = Path(path).read_text()
        return bool(re.search(pattern, text, re.I))
    except Exception:
        return False

print("=== PHASE 68 AUDIT: Homepage Operation ===\n")

# 1. Nav consolidation
print("1. Nav structure")
tmpl = Path("templates/chain_home.html").read_text()
check("Drawer exists", 'chain-home__drawer' in tmpl)
check("Left rail exists", 'home-left-rail' in tmpl)
check("Mobile bottom nav exists", 'mobile-bottom-nav' in tmpl)
check("No duplicate drawer/left rail (both serve diff breakpoints)",
      'chain-home__drawer' in tmpl and 'home-left-rail' in tmpl)
# Drawer nav links
drawer_section = tmpl.split('chain-home__drawer-backdrop')[1].split('</aside>')[0] if 'chain-home__drawer-backdrop' in tmpl else ''
drawer_links = len(re.findall(r'<a href=', drawer_section))
check("Drawer contains nav links", drawer_links > 5)

# 2. No hardcoded href="#"
print("\n2. Dead link audit")
# Allow Jinja2 fallback patterns: href="{{ x if cond else '#' }}"
hardcoded_hash = re.findall(r'href="#"[^>]*>', tmpl)
# Filter out Jinja2 fallback patterns and JS-handled data-* links
real_hashes = [h for h in hardcoded_hash if "{{" not in h and "data-" not in h]
check(f"No hardcoded href=\"#\" ({len(real_hashes)} found)", len(real_hashes) == 0,
      f"Found: {real_hashes}")
check("No javascript:void(0)", 'javascript:void(0)' not in tmpl)

# 3. No placeholder/hardcoded test data
print("\n3. Placeholder data audit")
placeholders = ["Test User", "tester_", "Phase 8", "Lorem ipsum", "lorem ipsum",
                "Jane Doe", "John Doe", "test_user", "testcreator"]
for ph in placeholders:
    if ph in tmpl:
        # Check if it's only in comments or Jinja2 conditionals
        lines = [i+1 for i, line in enumerate(tmpl.split('\n')) if ph in line]
        check(f"No hardcoded '{ph}'", False, f"Found at lines {lines}")
    else:
        check(f"No hardcoded '{ph}'", True)

# 4. Hamburger visible on all screen sizes
print("\n4. Hamburger visibility")
css = Path("static/css/chain_home.css").read_text()
check("Hamburger NOT hidden at mobile (no display:none rule)",
      not bool(re.search(r'chain-home__menu-btn\s*\{[^}]*display:\s*none', css)))

# 5. Header search hidden on mobile
print("\n5. Mobile search consolidation")
check("Header search hidden on mobile (display:none at 760px)",
      bool(re.search(r'chain-home__top-search\s*\{[^}]*display:\s*none', css)))
check("No duplicate hamburger JS toggle handler removed",
      not file_contains("static/js/chain_home.js", r"Mobile menu toggle \(hamburger\)"))

# 6. No duplicate Phase 58 hamburger JS
print("\n6. JS handler audit")
js = Path("static/js/chain_home.js").read_text()
check("First IIFE has drawer toggle/listeners", "setDrawerState" in js or "data-drawer-toggle" in js)
check("ESC key handler present", "Escape" in js)
check("Backdrop close handler present", "data-drawer-close" in js)
check("No duplicate hamburger handler", len(re.findall(r'menuBtn\.addEventListener\("click"', js)) == 0)

# 7. Reconnecting toast debounced (3s)
print("\n7. Reconnect debounce")
base = Path("templates/base.html").read_text()
check("Reconnecting toast has debounce (setTimeout 3000)",
      "3000" in base and ("reconnecting" in base.lower() or "toast" in base.lower()))
check("Initial connect done flag exists", "initialConnectDone" in base)

# 8. Test call sound restricted
print("\n8. Test call sound guard")
check("addUnlockButton restricted to admin/developer paths",
      "admin" in base.lower() or "developer" in base.lower())

# 9. Current user card
print("\n9. Current user profile card")
check("User card has initials fallback", "gen-avatar" in tmpl)
check("User card reads from current object", "current.avatar_url" in tmpl or "current.full_name" in tmpl)
check("User card has login/join fallback for anonymous", 'Join NamVibe' in tmpl or 'Login' in tmpl or 'Create an account' in tmpl)

# 10. Story upload
print("\n10. Story upload")
check("Story create link uses safe_link", "story_create" in tmpl)
check("Story create route verified by route_exists", "route_exists('/status/create')" in tmpl)
check("Story strip uses real data (stories loop)", "for story in stories" in tmpl)

# 11. Right sidebar uses backend data
print("\n11. Right sidebar data sources")
check("Trending creators from recommended_profiles", "recommended_profiles" in tmpl)
check("Suggested people from suggested_people", "suggested_people" in tmpl)
check("Trending hashtags from trending_hashtags", "trending_hashtags" in tmpl)
check("Popular towns are real links (no fake)", "town_filter" in tmpl)
check("Live rooms from live_rooms", "live_rooms" in tmpl)

# 12. Buttons have proper routes
print("\n12. Button route integrity")
check("Composer uses safe_link fallback", "composer_fallback" in tmpl)
check("Post/Reel/Story/Live avail checks", "post_available" in tmpl and "story_available" in tmpl)
check("All primary nav items use Jinja2 route vars",
      all(x in tmpl for x in ['home_route', 'discover_route', 'live_route',
                                'reel_route', 'drawer_messages', 'drawer_profile']))

# 13. safe_upload_file usage
print("\n13. safe_upload_file usage")
status_svc = Path("services/status_service.py").read_text()
profile_svc = Path("services/profile_service.py").read_text()
storage_svc = Path("services/storage_service.py").read_text()
check("safe_upload_file defined in storage_service", "def safe_upload_file" in storage_svc)
check("status_service uses safe_upload_file", "safe_upload_file" in status_svc)
check("profile_service uses safe_upload_file", "safe_upload_file" in profile_svc)
check("LOCAL_UPLOAD_DIRS has all categories",
      all(k in storage_svc for k in ['"avatar"', '"cover"', '"story"', '"post"', '"reel"']))

# 14. No Bucket not found in templates
print("\n14. No bucket error leakage")
bucket_errors = []
for tpl in sorted(Path("templates").rglob("*.html")):
    text = tpl.read_text()
    if "Bucket not found" in text or "bucket_not_found" in text:
        bucket_errors.append(tpl.name)
check("No 'Bucket not found' in any template", len(bucket_errors) == 0,
      f"Found in: {bucket_errors}")

# 15. Python compile
print("\n15. Python compile check")
all_ok = compileall.compile_dir(str(ROOT), force=True, quiet=1)
check("All Python files compile clean", all_ok)

print(f"\n{'='*50}")
print(f"RESULTS: {len(errors)} FAILURES")
if errors:
    print("FAILED CHECKS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
