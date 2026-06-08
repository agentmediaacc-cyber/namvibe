#!/usr/bin/env python3
"""Phase 33 — Color System Tests."""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pass_count = 0
fail_count = 0

def test(name, condition):
    global pass_count, fail_count
    if condition:
        print(f"  [PASS] {name}")
        pass_count += 1
    else:
        print(f"  [FAIL] {name}")
        fail_count += 1

print("=== Phase 33 Color System Test ===")

# 1. chain_theme.css exists
theme_css = os.path.join(BASE, "static/css/chain_theme.css")
test("chain_theme.css exists", os.path.exists(theme_css))

# 2. chain_theme.css has core variables
if os.path.exists(theme_css):
    with open(theme_css) as f:
        css = f.read()

    test("--chain-bg defined", "--chain-bg" in css)
    test("--chain-bg value is #050505", "#050505" in css)
    test("--chain-bg-soft defined", "--chain-bg-soft" in css)
    test("--chain-card defined", "--chain-card" in css)
    test("--chain-text defined", "--chain-text" in css)
    test("--chain-muted defined", "--chain-muted" in css)
    test("--chain-cyan defined", "--chain-cyan" in css)
    test("--chain-pink defined", "--chain-pink" in css)
    test("--chain-purple defined", "--chain-purple" in css)
    test("--chain-orange defined", "--chain-orange" in css)
    test("--chain-gold defined", "--chain-gold" in css)
    test("--chain-gradient defined", "--chain-gradient" in css)
    test("--chain-story-ring defined", "--chain-story-ring" in css)
    test("--chain-live-gradient defined", "--chain-live-gradient" in css)
    test("--chain-premium-gradient defined", "--chain-premium-gradient" in css)

    # Check the actual hex values
    test("TikTok cyan #00f2ea", "#00f2ea" in css)
    test("TikTok pink #ff0050", "#ff0050" in css)
    test("Instagram purple #833ab4", "#833ab4" in css)
    test("Instagram orange #fd1d1d", "#fd1d1d" in css)
    test("Instagram gold #fcb045", "#fcb045" in css)
    test("Deep black #050505", "#050505" in css)
    test("Soft black #0b0b0f", "#0b0b0f" in css)
    test("Card black #111118", "#111118" in css)
    test("Card-2 black #1a1a24", "#1a1a24" in css)
    test("White text #ffffff", "#ffffff" in css)
    test("Muted text #a1a1aa", "#a1a1aa" in css)
else:
    for i in range(20):
        test(f"variable check {i}", False)

# 3. chain_theme_audit.js exists
audit_js = os.path.join(BASE, "static/js/chain_theme_audit.js")
test("chain_theme_audit.js exists", os.path.exists(audit_js))
if os.path.exists(audit_js):
    with open(audit_js) as f:
        js = f.read()
    test("audit JS exports chainThemeAudit", "chainThemeAudit" in js)
    test("audit JS checks variables", "expected" in js)
    test("audit JS checks body background", "bodyBg" in js or "body_bg" in js)

# 4. chain_theme.css loaded in base template
base_html = os.path.join(BASE, "templates/base.html")
if os.path.exists(base_html):
    with open(base_html) as f:
        base = f.read()
    test("base.html loads chain_theme.css", "chain_theme.css" in base)
    test("base.html loads chain_theme_audit.js", "chain_theme_audit.js" in base)
    test("base.html has chain-shell--social class", "chain-shell--social" in base)
else:
    test("base.html exists", False)

# 5. Key CSS files exist
for css_file in ["style.css", "chain_home.css", "chain_theme.css", "chain_auth.css", "live.css", "calls.css", "chat.css", "platform_premium.css"]:
    test(f"static/css/{css_file} exists", os.path.exists(os.path.join(BASE, "static/css", css_file)))

print(f"\nResults: {pass_count}/{pass_count + fail_count} passed, {fail_count}/{pass_count + fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
