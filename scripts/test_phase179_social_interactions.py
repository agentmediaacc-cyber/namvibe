#!/usr/bin/env python3
"""Phase 179: Premium Social Interaction Engine tests."""

import sys, os, json, re

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
js_src = ""
m = re.search(r'<script>\s*(\(function\(\)\{.*?\}\(\)\);\s*)?\s*</script>', tpl, re.DOTALL)
if m:
    js_src = m.group(0) if m.lastindex else ""

# ── Section 1: Homepage interaction hooks ──
section("1. Homepage interaction hooks")
check("data-action like buttons exist", "data-action=\"like\"" in tpl)
check("data-action comment buttons exist", "data-action=\"comment\"" in tpl)
check("data-action share buttons exist", "data-action=\"share\"" in tpl)
check("data-action save buttons exist", "data-action=\"save\"" in tpl)
check("data-follow-id exists", "data-follow-id" in tpl)
check("nv-more buttons exist", "class=\"nv-more\"" in tpl)
check("like API endpoint mapped", "/api/home/post/" in tpl)
check("reel like API mapped", "/reels/api/reels/" in tpl)

# ── Section 2: Bottom sheet ──
section("2. Bottom sheet action menus")
check("bottom sheet overlay exists", "nv-bottom-sheet-overlay" in tpl)
check("bottom sheet body exists", "nv-bottom-sheet-body" in tpl)
check("bottom sheet close button", "nv-bottom-sheet-close" in tpl)
check("bottom sheet role=dialog", 'role="dialog"' in tpl)
check("bottom sheet role=menu", 'role="menu"' in tpl)
check("openBottomSheet function", "function openBottomSheet" in tpl)
check("closeBottomSheet function", "function closeBottomSheet" in tpl)
check("sheet-item class", "nv-sheet-item" in tpl)
check("sheet handle exists", "nv-bottom-sheet-handle" in tpl)
check("no dead menu items - report action", "Report" in tpl)
check("menu items have keyboard role menuitem", "menuitem" in tpl and "setAttribute" in tpl)

# ── Section 3: Double-tap to like ──
section("3. Double-tap to like")
check("double-tap handler exists", "lastTap" in tpl and "350" in tpl)
check("heart burst element", "nv-heart-burst" in tpl)
check("heart burst CSS animation", "nv-heart-burst-kf" in tpl)
check("double-tap triggers like click", "likeBtn.click" in tpl)

# ── Section 4: Share ──
section("4. Share behavior")
check("native share sheet (navigator.share)", "navigator.share" in tpl)
check("copy link fallback", "navigator.clipboard" in tpl)
check("share API tracking call", "typeConfig.share" in tpl)
check("share bottom sheet (nvShareAction)", "nvShareAction" in tpl)

# ── Section 5: Toast system ──
section("5. Toast system")
check("NamVibeToast defined", "window.NamVibeToast" in tpl)
check("toast show method", "show:" in tpl or "NamVibeToast.show" in tpl)
check("toast success method", "success:" in tpl)
check("toast error method", "error:" in tpl)
check("toast warning method", "warning:" in tpl)
check("toast info method", "info:" in tpl)

# ── Section 6: Optimistic updates & loading ──
section("6. Optimistic updates & loading states")
check("like button loading state", "is-loading" in tpl)
check("disabled button state exists", ".nv-action:disabled" in tpl or "button:disabled" in tpl)
check("CSS for disabled actions", "pointer-events:none" in tpl and "opacity:.5" in tpl)

# ── Section 7: Infinite scroll ──
section("7. Infinite scroll")
check("sentinel element exists", "nv-feed-sentinel" in tpl)
check("IntersectionObserver for sentinel", "IntersectionObserver" in tpl and "nv-feed-sentinel" in tpl)
check("\"You are all caught up\" message", "all caught up" in tpl)
check("loading spinner exists", "nv-spinner" in tpl)
check("api endpoint for loading more", "/api/homepage/feed" in tpl or "/api/feed" in tpl)

# ── Section 8: Pull-to-refresh ──
section("8. Pull-to-refresh")
check("touchstart handler", "touchstart" in tpl and "ptrStartY" in tpl)
check("touchmove handler", "touchmove" in tpl and "ptrStartY" in tpl)
check("touchend handler", "touchend" in tpl and "ptrPulling" in tpl)
check("refresh message", "Release to refresh" in tpl)

# ── Section 9: Real-time updates ──
section("9. Real-time updates")
check("Socket.IO listener for notification:new", "notification:new" in tpl)
check("Socket.IO listener for chat:message", "chat:message" in tpl)
check("Socket.IO listener for story:new", "story:new" in tpl)
check("Socket.IO listener for live:started", "live:started" in tpl)
check("badge pulse class", "nv-badge-pulse" in tpl)

# ── Section 10: Accessibility ──
section("10. Accessibility")
check("Escape key handler", 'key === "Escape"' in tpl or 'key==="Escape"' in tpl)
check("focus trap in modal", "focusable" in tpl and "Tab" in tpl)
label_count = tpl.count("aria-label")
check("aria-label attributes exist", label_count >= 5, f"found {label_count}")
check("aria-hidden attributes", "aria-hidden" in tpl)
check("aria-modal attribute", "aria-modal" in tpl)
check("reduced motion media query", "prefers-reduced-motion" in tpl)
check("focus-visible styles", "focus-visible" in tpl)

# ── Section 11: Media behavior ──
section("11. Media behavior")
check("video autoplay IntersectionObserver", "IntersectionObserver" in tpl and "video.play" in tpl)
check("video pause offscreen", "video.pause" in tpl)

# ── Section 12: Performance ──
section("12. Performance")
check("debounce utility exists", "nvDebounce" in tpl)
check("no href=\"#\"", 'href="#"' not in tpl)
check("no javascript:void", "javascript:void" not in tpl)

# ── Section 13: Background audit ──
section("13. Background audit")
check("nv-bottom nav exists", "nv-bottom" in tpl)
check("nv-create-modal exists", "nv-create-modal" in tpl)
check("nv-toast exists (id)", 'id="nv-toast"' in tpl or 'id="nv-toast"' in tpl)
check("nv-follow button type correct", 'type="button"' in tpl or 'type=\\"button\\"' in tpl)

# ── Summary ──
section(f"SUMMARY: {_passed}/{_total} passed, {_failed} failed")
sys.exit(0 if _failed == 0 else 1)
