#!/usr/bin/env python3
"""Phase 70 audit: Homepage Premium Rebuild — 50+ checks."""

import os, sys, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0

def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))

print("="*64)
print("Phase 70 Audit — Homepage Premium Rebuild")
print("="*64)

# ── 1. Avatar helper exists ──
src = open("services/homepage_service.py").read()
check("get_profile_avatar_url exists", "def get_profile_avatar_url" in src)

# ── 2. Avatar helper checks all 7 field names ──
avatar_fields = ["avatar_url", "photo_url", "thumbnail_url", "avatar_storage_path", "avatar_path", "profile_picture", "image_url"]
idx = src.find("def get_profile_avatar_url")
if idx >= 0:
    chunk = src[idx:idx+2000]
    for f in avatar_fields:
        check(f"get_profile_avatar_url checks {f}", f'"{f}"' in chunk or f"'{f}'" in chunk)
else:
    for f in avatar_fields:
        check(f"get_profile_avatar_url checks {f}", False)

# ── 3. Avatar fallback exists (returns None for initials) ──
check("get_profile_avatar_url returns None for no match", "return None" in src[src.find("def get_profile_avatar_url"):src.find("def get_profile_avatar_url")+1500])

# ── 4. No "Avatar" visible text in template ──
tmpl = open("templates/chain_home.html").read()
# Allow "Avatar" only in comments/aria-labels
avatar_text_lines = [l for l in tmpl.split("\n") if "Avatar" in l and "aria-label" not in l and "{%" not in l]
check("No 'Avatar' visible text in template", len(avatar_text_lines) == 0, f"found {len(avatar_text_lines)} lines")

# ── 5. CSS file loaded ──
css = open("static/css/namvibe_homepage_premium.css").read()
check("NV CSS file exists", True)

# ── 6. Story modal exists in template ──
check("Story modal overlay exists", "story-modal-overlay" in tmpl)
check("Story modal max-width constrained", "max-width" in css and "520px" in css)
check("Story upload zone exists", "story-upload-zone" in tmpl)
check("Story preview exists", "story-preview" in tmpl)
check("Story caption textarea exists", "story-caption" in tmpl)
check("Story post button exists", "story-btn-post" in tmpl)
check("Story error display exists", "story-error" in tmpl)
check("Story loading state exists", "story-loading" in tmpl)

# ── 7. Story modal CSS details ──
check("Story modal CSS: overlay", ".story-modal-overlay" in css)
check("Story modal CSS: max-width 520px", "520px" in css)
check("Story modal CSS: max-height 85vh", "85vh" in css)
check("Story preview max-height", "320px" in css)
check("Story mobile bottom sheet", "align-items: flex-end" in css)
check("Story mobile max-height 90vh", "90vh" in css)

# ── 7. No duplicate comment in template ──
check("No duplicate Phase 59 comment", tmpl.count("Phase 59: Reels Preview Section") == 1)

# ── 8. Dating link in left rail ──
check("Dating link in left rail", "dating_route" in tmpl[tmpl.find("home-left-rail"):tmpl.find("home-left-rail")+2500])

# ── 9. Mobile search wrapped in form ──
check("Mobile search has form", "<form" in tmpl[tmpl.find("home-topbar"):tmpl.find("home-topbar")+200])

# ── 10. NV theme variables exist ──
nv_vars = ["--nv-bg", "--nv-surface", "--nv-text", "--nv-muted", "--nv-border", "--nv-primary", "--nv-accent", "--nv-danger", "--nv-shadow"]
for v in nv_vars:
    check(f"Theme var {v} exists", v in css)

# ── 11. Purple gradient removed from nav active state ──
nav_active = [l for l in css.split("\n") if "is-active" in l]
purple_in_nav = any("7c3aed" in l or "purple" in l.lower() or "violet" in l.lower() for l in nav_active)
check("No purple in nav active state", not purple_in_nav)

# ── 12. Purple gradient removed from JS ──
js = open("static/js/homepage_premium.js").read()
check("No purple (#7c3aed) in homepage_premium.js", "#7c3aed" not in js)
check("No purple gradient in JS renderAnnouncementItem", "linear-gradient(135deg,#7c3aed" not in js)
check("Teal (#0f766e) in announcement avatar", "#0f766e" in js)

# ── 13. Avatar error handler in JS ──
check("initAvatarFallback exists", "initAvatarFallback" in js)
check("initStoryModal exists", "initStoryModal" in js)

# ── 14. Desktop 3-column grid exists ──
check("Home layout grid-template-columns", "grid-template-columns" in css)
check("Desktop left rail width 260px", "260px" in css)
check("Desktop right rail width 320px", "320px" in css)

# ── 15. No broken image icon text ──
check("No 'broken image' in template", "broken image" not in tmpl.lower())

# ── 16. No Test User / tester_ / Phase 8 ──
for pat in ["Test User", "tester_", "Phase 8"]:
    matches = [l for l in tmpl.split("\n") if pat.lower() in l.lower() and "safe_link" not in l and "route_exists" not in l]
    check(f"No '{pat}' in template", len(matches) == 0, str(matches[:3]) if matches else "")

# ── 17. No bare href="#" without JS handler in template ──
# Allow href="#" when data-* attribute provides the handler
bare_hash = re.findall(r'href\s*=\s*"#"(?!\s*data-)', tmpl)
bare_hash += re.findall(r'href="#".*?(?:\s|>)(?!data-)', tmpl)
# Count only <a href="#"> without data-* or known safe patterns
import html.parser
class SafeHrefChecker(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.unsafe_hashes = 0
    def handle_starttag(self, tag, attrs):
        if tag != 'a': return
        has_hash = any(n == 'href' and v == '#' for n, v in attrs)
        has_handler = any(n.startswith('data-') for n, _ in attrs)
        if has_hash and not has_handler:
            self.unsafe_hashes += 1
parser = SafeHrefChecker()
parser.feed(tmpl)
safe_hrefs_ok = parser.unsafe_hashes == 0
check("No bare href='#' without JS handler", safe_hrefs_ok, f"found {parser.unsafe_hashes} unsafe href='#'")

# ── 18. Post card premium class exists ──
check("Template has post-card-premium", "post-card-premium" in tmpl)
check("CSS has post-card-premium", "post-card-premium" in css)

# ── 19. Story CSS classes exist ──
check("CSS has .story-card", ".story-card" in css)
check("CSS has .story-ring", ".story-ring" in css)
check("CSS has .story-strip", ".story-strip" in css)
check("CSS has .story-empty", ".story-empty" in css)

# ── 20. Reels CSS classes exist ──
check("CSS has .reels-preview", ".reels-preview" in css)
check("CSS has .reel-preview-card", ".reel-preview-card" in css)
check("CSS has .reel-preview-media", ".reel-preview-media" in css)

# ── 21. Right rail CSS classes exist ──
check("CSS has .rail-section", ".rail-section" in css)
check("CSS has .suggested-card", ".suggested-card" in css)
check("CSS has .suggested-follow-btn", ".suggested-follow-btn" in css)

# ── 22. Bottom nav exists ──
check("CSS has .home-bottom-nav", ".home-bottom-nav" in css)
check("CSS has mobile-bottom-nav", "mobile-bottom-nav" in tmpl)
check("Mobile bottom nav has 5 items", tmpl.count("mobile-nav-item") >= 5)

# ── 23. Avatar object-fit cover ──
check("Avatar object-fit cover in CSS", "object-fit: cover" in css)

# ── 24. 44px tap targets ──
has_tap = "44px" in css or "min-height: 44" in css or "min-width: 44" in css
check("44px tap targets on mobile", has_tap)

# ── 25. Safe-area padding ──
check("safe-area padding in CSS", "safe-area-inset-bottom" in css)

# ── 26. Python compiles ──
try:
    import py_compile
    py_compile.compile("services/homepage_service.py", doraise=True)
    check("Python compile: homepage_service.py", True)
except py_compile.PyCompileError as e:
    check("Python compile: homepage_service.py", False, str(e))

# ── 27. Import helpers ──
try:
    import importlib.util as imp
    spec = imp.spec_from_file_location("hps", "services/homepage_service.py")
    mod = imp.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("get_profile_avatar_url is callable", callable(getattr(mod, "get_profile_avatar_url", None)))
except Exception as e:
    check("Import homepage_service", False, str(e))

# ── 28. No duplicate nav blocks ──
# Check left rail exists once
left_rail_count = tmpl.count("home-left-rail")
check("Single home-left-rail", left_rail_count == 1, f"found {left_rail_count}")
drawer_count = tmpl.count("chain-home-drawer")
check("Single chain-home-drawer", drawer_count <= 2)  # id ref + drawer itself

print("-"*64)
print(f"  {passed} passed, {failed} failed")
print("="*64)
sys.exit(0 if failed == 0 else 1)
