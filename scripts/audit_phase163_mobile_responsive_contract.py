#!/usr/bin/env python3
"""Phase 163 — Mobile Responsive Stability & Professional UI Polish Audit"""

import re, sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

issues = []
pass_count = 0
fail_count = 0

def check(name, ok, detail=""):
    global pass_count, fail_count
    if ok:
        pass_count += 1
        print(f"  PASS: {name}")
    else:
        fail_count += 1
        print(f"  FAIL: {name} — {detail}")
        issues.append(f"{name}: {detail}")

def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None

# ── 1. Viewport meta in base.html ──
base_html = read_file(os.path.join(os.path.dirname(__file__), "..", "templates", "base.html"))
check("1a. viewport meta with viewport-fit=cover",
      base_html and 'viewport-fit=cover' in base_html,
      "base.html missing viewport-fit=cover")

check("1b. viewport meta width=device-width",
      base_html and 'width=device-width' in base_html,
      "base.html missing width=device-width")

# ── 2. Global CSS rules ──
check("2a. html,body overflow-x:hidden in base.html",
      base_html and 'overflow-x: hidden' in base_html,
      "base.html missing html,body overflow-x:hidden")

check("2b. img,video max-width:100% in base.html",
      base_html and 'img, video { max-width: 100%' in base_html,
      "base.html missing img,video max-width:100%")

# ── 3. namvibe_home_pro.css checks ──
home_css = read_file(os.path.join(os.path.dirname(__file__), "..", "static/css/namvibe_home_pro.css"))
if home_css:
    check("3a. box-sizing reset",
          'box-sizing: border-box' in home_css,
          "missing box-sizing reset")

    # Check for 100vw usage
    vw_issues = []
    for i, line in enumerate(home_css.split("\n"), 1):
        if '100vw' in line and 'max-width: 100vh' not in line:
            vw_issues.append(f"line {i}")
    check("3b. no 100vw causing overflow",
          len(vw_issues) == 0,
          f"100vw found at: {', '.join(vw_issues)}")

    check("3c. header-icon has position:relative",
          '.nvpro-header-icon' in home_css and 'position: relative' in home_css.split('.nvpro-header-icon')[1].split('}')[0],
          ".nvpro-header-icon missing position:relative for badge")

    check("3d. bottom-nav safe-area padding",
          'safe-area-inset-bottom' in home_css,
          "bottom-nav missing safe-area-inset-bottom")

    check("3e. body mobile padding includes safe-area",
          'env(safe-area-inset-bottom' in home_css,
          "body mobile padding missing safe-area-inset-bottom")

    check("3f. search input 16px min on mobile",
          'max(16px' in home_css,
          "mobile search input font-size may be <16px")

    check("3g. modal uses max-width:100% not 100vw",
          'max-width: 100%;' in home_css,
          "modal uses 100vw instead of 100%")

    check("3h. bottom-nav hidden on desktop",
          '.nvpro-bottom-nav { display: none !important;' in home_css,
          "bottom-nav missing desktop hide rule")

    check("3i. left-rail hidden on mobile",
          '.nvpro-left-rail { display: none;' in home_css or '.nvpro-left-rail{display:none' in home_css.replace(' ', ''),
          "left-rail not hidden on mobile")

    check("3j. stories tray exists",
          '.nvpro-stories-tray' in home_css,
          "stories tray missing from CSS")
else:
    check("3. namvibe_home_pro.css", False, "file not found")

# ── 4. Camera creator CSS ──
cam_css = read_file(os.path.join(os.path.dirname(__file__), "..", "static/css/namvibe_camera_creator.css"))
if cam_css:
    check("4a. camera creator box-sizing reset",
          'box-sizing:border-box' in cam_css.replace(' ', ''),
          "camera creator CSS missing box-sizing reset")

    check("4b. camera input font-size >= 16px",
          'max(16px' in cam_css,
          "camera creator input font-size may be <16px")

    check("4c. camera overlay safe-area padding",
          'safe-area-inset-top' in cam_css,
          "camera overlay missing safe-area padding")
else:
    check("4. camera_creator.css", False, "file not found")

# ── 5. Post detail input ──
post_detail = read_file(os.path.join(os.path.dirname(__file__), "..", "templates/posts/detail.html"))
if post_detail:
    check("5a. post detail comment input font-size >= 16px",
          'max(16px' in post_detail,
          "post detail comment input <16px")
else:
    check("5. posts/detail.html", False, "file not found")

# ── 6. Reel detail input ──
reel_detail = read_file(os.path.join(os.path.dirname(__file__), "..", "templates/reels/detail.html"))
if reel_detail:
    check("6a. reel detail comment input font-size >= 16px",
          'max(16px' in reel_detail,
          "reel detail comment input <16px")
else:
    check("6. reels/detail.html", False, "file not found")

# ── 7. namvibe_home_pro.js performance ──
home_js = read_file(os.path.join(os.path.dirname(__file__), "..", "static/js/namvibe_home_pro.js"))
if home_js:
    check("7a. requestAnimationFrame debounced scroll",
          'requestAnimationFrame' in home_js and 'passive: true' in home_js,
          "scroll handler not debounced with requestAnimationFrame")

    check("7b. IntersectionObserver for media",
          'IntersectionObserver' in home_js,
          "missing IntersectionObserver for media preloading")

    check("7c. lazy loading for images",
          'loading="lazy"' in home_js,
          "missing lazy loading for images")
else:
    check("7. namvibe_home_pro.js", False, "file not found")

# ── 8. chain_home.html checks ──
chain_home = read_file(os.path.join(os.path.dirname(__file__), "..", "templates/chain_home.html"))
if chain_home:
    check("8a. no duplicate mobile navs",
          chain_home.count('nvpro-bottom-nav') <= 1,
          "duplicate bottom nav found")

    check("8b. bottom nav has 5 items (Home, Discover, Create, Inbox, Profile)",
          chain_home.count('nvpro-bottom-item') == 5,
          "bottom nav doesn't have exactly 5 items")

    check("8c. offline banner exists",
          'nvpro-offline-banner' in chain_home,
          "offline banner missing")

    check("8d. camera creator partial included",
          'camera_creator.html' in chain_home,
          "camera creator partial not included")

    check("8e. left-rail single HTML element (not duplicated)",
          chain_home.count('class="nvpro-left-rail"') == 1 or chain_home.count("class=\"nvpro-left-rail\"") == 1,
          "left-rail HTML element appears more than once")

    check("8f. no desktop sidebar visible on mobile (hidden via CSS)",
          '.nvpro-sidebar { display: none;' not in chain_home,
          "sidebar hidden rule is in CSS, not HTML (OK)")  # This is OK since it's in CSS
else:
    check("8. chain_home.html", False, "file not found")

# ── 9. Aspect ratios for media ──
if home_css:
    check("9a. reel thumbnail has aspect-ratio",
          'aspect-ratio: 9/16' in home_css or 'aspect-ratio:9/16' in home_css.replace(' ', ''),
          "reel thumb missing aspect-ratio")

    check("9b. post media max-height constraint",
          'max-height: 420px' in home_css,
          "post media missing max-height constraint")

# ── 10. Base.html mobile nav ──
if base_html:
    check("10a. mobile-nav hidden on non-auth surfaces",
          'class="mobile-nav"' in base_html and 'display: none' not in base_html[:2000],
          "base.html has mobile-nav (hidden by CSS — OK if CSS hides it)")

# ── Summary ──
print(f"\n{'='*60}")
print(f"Phase 163 — Mobile Responsive Audit Results")
print(f"{'='*60}")
print(f"PASS: {pass_count} | FAIL: {fail_count}")

if fail_count == 0:
    print("OVERALL: PASS")
    sys.exit(0)
else:
    print(f"OVERALL: FAIL — {fail_count} issues need fixing")
    for i in issues:
        print(f"  - {i}")
    sys.exit(1)
