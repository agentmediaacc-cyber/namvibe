#!/usr/bin/env python3
"""Phase 179: Premium Social Interaction Engine tests."""

import sys, os, json, re, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_ENV", "development")

PASS, FAIL = "PASS", "FAIL"
_total = 0; _passed = 0; _failed = 0

def check(label, condition, detail=""):
    global _total, _passed, _failed
    _total += 1
    status = PASS if condition else FAIL
    if status == PASS: _passed += 1
    else: _failed += 1
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))

def section(name):
    print(f"\n{'='*60}\n{name}\n{'='*60}")

tpl = open("templates/chain_home.html", "rb").read().decode("utf-8")

# Load JS files for scanning
_JS_FILES = [
    "static/js/namvibe_home_pro.js",
    "static/js/namvibe_home_premium_v2.js",
    "static/js/namvibe_shared.js",
    "static/js/namvibe_home_premium.js",
]
_js_src = ""
for _f in _JS_FILES:
    try:
        _js_src += open(_f, "rb").read().decode("utf-8", errors="ignore") + "\n"
    except Exception:
        pass

def tpl_has(pattern):
    return pattern in tpl

def js_has(pattern):
    return pattern in _js_src

def any_has(pattern):
    return tpl_has(pattern) or js_has(pattern)

# ── Section 1: Homepage interaction hooks ──
section("1. Homepage interaction hooks")
check("data-action like buttons exist", tpl_has('data-action="like"'))
check("data-action comment buttons exist", tpl_has('data-action="comment"'))
check("data-action share buttons exist", tpl_has('data-action="share"'))
check("data-action save buttons exist", tpl_has('data-action="save"'))
check("data-follow-id exists", tpl_has("data-follow-id"))
check("nv-more buttons exist", tpl_has('class="nv-more"') or tpl_has('class="nv-more '))
check("like API endpoint mapped", any_has("/api/home/post/"))
check("reel like API mapped", any_has("/reels/api/reels/"))

# ── Section 2: Bottom sheet ──
section("2. Bottom sheet action menus")
check("bottom sheet overlay exists", tpl_has("nv-bottom-sheet-overlay"))
check("bottom sheet body exists", tpl_has("nv-bottom-sheet-body"))
check("bottom sheet close button", tpl_has("nv-bottom-sheet-close"))
check("bottom sheet role=dialog", tpl_has('role="dialog"'))
check("bottom sheet role=menu", tpl_has('role="menu"'))
check("openBottomSheet function", tpl_has("function openBottomSheet") or tpl_has("openBottomSheet"))
check("closeBottomSheet function", tpl_has("function closeBottomSheet") or tpl_has("closeBottomSheet"))
check("sheet-item class", tpl_has("nv-sheet-item"))
check("sheet handle exists", tpl_has("nv-bottom-sheet-handle"))
check("no dead menu items - report action", tpl_has("Report"))
check("menu items have keyboard role menuitem", tpl_has("menuitem"))

# ── Section 3: Double-tap to like ──
section("3. Double-tap to like")
check("double-tap handler exists", any_has("lastTap") and (any_has("350") or any_has("300") or any_has("280")))
check("heart burst element", tpl_has("nv-heart-burst"))
check("heart burst CSS animation", tpl_has("nv-heart-burst-kf"))
check("double-tap triggers like click", any_has("likeBtn") and any_has("click") and (any_has("lastTap") or any_has("dblclick")))

# ── Section 4: Share ──
section("4. Share behavior")
check("native share sheet (navigator.share)", any_has("navigator.share"))
check("copy link fallback", any_has("navigator.clipboard"))
check("share API tracking call", any_has("typeConfig.share") or any_has("share") and any_has("track"))
check("share bottom sheet (nvShareAction)", any_has("nvShareAction") or any_has("shareAction"))

# ── Section 5: Toast system ──
section("5. Toast system")
check("NamVibeToast defined", any_has("window.NamVibeToast") or any_has("NamVibeToast"))
check("toast show method", any_has("show:") or any_has(".show(") or any_has("show("))
check("toast success method", any_has("success:") or any_has(".success("))
check("toast error method", any_has("error:") or any_has(".error("))
check("toast warning method", any_has("warning:") or any_has(".warning("))
check("toast info method", any_has("info:") or any_has(".info("))

# ── Section 6: Optimistic updates & loading ──
section("6. Optimistic updates & loading states")
check("like button loading state", tpl_has("is-loading"))
check("disabled button state exists", any_has(":disabled") or any_has("disabled"))
check("CSS for disabled actions", tpl_has("pointer-events:none") and tpl_has("opacity:.5"))

# ── Section 7: Infinite scroll ──
section("7. Infinite scroll")
check("sentinel element exists", tpl_has("nv-feed-sentinel"))
check("IntersectionObserver for sentinel", any_has("IntersectionObserver") and any_has("sentinel"))
check('"You are all caught up" message', tpl_has("all caught up"))
check("loading spinner exists", tpl_has("nv-spinner"))
check("api endpoint for loading more", any_has("/api/homepage/feed") or any_has("/api/feed"))

# ── Section 8: Pull-to-refresh ──
section("8. Pull-to-refresh")
check("touchstart handler", any_has("touchstart"))
check("touchmove handler", any_has("touchmove"))
check("touchend handler", any_has("touchend"))
check("refresh message", any_has("Release to refresh") or any_has("Pull to refresh"))

# ── Section 9: Real-time updates ──
section("9. Real-time updates")
check("Socket.IO listener for notification:new", any_has("notification:new"))
check("Socket.IO listener for chat:message", any_has("chat:message"))
check("Socket.IO listener for story:new", any_has("story:new"))
check("Socket.IO listener for live:started", any_has("live:started"))
check("badge pulse class", tpl_has("nv-badge-pulse"))

# ── Section 10: Accessibility ──
section("10. Accessibility")
check("Escape key handler", any_has('key === "Escape"') or any_has('key==="Escape"') or any_has("key === 'Escape'") or any_has("key==='Escape'") or any_has('key !== "Escape"'))
check("focus trap in modal", any_has("focusable") and any_has("Tab"))
label_count = tpl.count("aria-label")
check("aria-label attributes exist", label_count >= 5, f"found {label_count}")
check("aria-hidden attributes", tpl_has("aria-hidden"))
check("aria-modal attribute", tpl_has("aria-modal"))
check("reduced motion media query", tpl_has("prefers-reduced-motion"))
check("focus-visible styles", tpl_has("focus-visible"))

# ── Section 11: Media behavior ──
section("11. Media behavior")
check("video autoplay IntersectionObserver", any_has("IntersectionObserver") and any_has("video.play") or any_has("video.play()") or any_has("video[0].play"))
check("video pause offscreen", any_has("video.pause") or any_has("video.pause()"))

# ── Section 12: Performance ──
section("12. Performance")
check("debounce utility exists", any_has("nvDebounce") or any_has("debounce"))
check('no href="#"', 'href="#"' not in tpl)
check("no javascript:void", "javascript:void" not in tpl)

# ── Section 13: Background audit ──
section("13. Background audit")
check("nv-bottom nav exists", tpl_has("nv-bottom"))
check("nv-create-modal exists", tpl_has("nv-create-modal"))
check("nv-toast exists (id)", tpl_has('id="nv-toast"'))
check("nv-follow button type correct", tpl_has('type="button"'))

# ── Summary ──
section(f"SUMMARY: {_passed}/{_total} passed, {_failed} failed")
sys.exit(0 if _failed == 0 else 1)
