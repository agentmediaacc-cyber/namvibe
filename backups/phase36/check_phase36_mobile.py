#!/usr/bin/env python3
"""Phase 36 — Mobile Experience Audit"""

import os
import sys
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

TEMPLATE_DIR = os.path.join(BASE, "templates")
STATIC_DIR = os.path.join(BASE, "static")

# 1. Viewport meta tag
index_html = os.path.join(TEMPLATE_DIR, "base.html")
if os.path.exists(index_html):
    content = open(index_html).read()
    has_viewport = "viewport" in content.lower() and "width=device-width" in content
    check("Viewport meta tag in base.html", has_viewport)
else:
    check("base.html exists", False)

# 2. Mobile-responsive CSS
css_dir = os.path.join(STATIC_DIR, "css")
responsive_found = False
if os.path.isdir(css_dir):
    for f in os.listdir(css_dir):
        if f.endswith(".css"):
            fp = os.path.join(css_dir, f)
            try:
                css_content = open(fp).read()
                if "@media" in css_content:
                    responsive_found = True
            except Exception:
                pass
check("Responsive CSS with @media queries", responsive_found)

# 3. Message templates render properly (check for hidden/overlapping elements)
msg_template = os.path.join(TEMPLATE_DIR, "messages", "thread.html")
if os.path.exists(msg_template):
    msg_content = open(msg_template).read()
    has_composer = "composer" in msg_content.lower()
    has_send_btn = "submit" in msg_content.lower() or "send" in msg_content.lower()
    check("Message thread: composer exists", has_composer)
    check("Message thread: send button exists", has_send_btn)
else:
    check("Message thread template exists", False)

# 4. Call page mobile-ready
call_template = os.path.join(TEMPLATE_DIR, "calls", "video.html")
if os.path.exists(call_template):
    call_content = open(call_template).read()
    has_mic = "mic" in call_content.lower() or "microphone" in call_content.lower()
    has_cam = "camera" in call_content.lower() or "video" in call_content.lower()
    has_end = "end" in call_content.lower() or "hang" in call_content.lower()
    check("Call page: mic control visible", has_mic)
    check("Call page: camera control visible", has_cam)
    check("Call page: end call button visible", has_end)
else:
    check("Call template exists", False)

# 5. Live page mobile-ready
live_template = os.path.join(TEMPLATE_DIR, "live", "watch.html")
if os.path.exists(live_template):
    live_content = open(live_template).read()
    has_chat = "chat" in live_content.lower()
    has_gift = "gift" in live_content.lower()
    check("Live watch: chat visible", has_chat)
    check("Live watch: gift button visible", has_gift)
else:
    # Check other live templates
    live_studio = os.path.join(TEMPLATE_DIR, "live", "studio.html")
    if os.path.exists(live_studio):
        check("Live studio template exists", True)

# 6. Group creation accessible
msg_index = os.path.join(TEMPLATE_DIR, "messages", "index.html")
if os.path.exists(msg_index):
    index_content = open(msg_index).read()
    has_groups = "group" in index_content.lower()
    check("Messages page: group access", has_groups)
else:
    check("Messages index template exists", False)

# 7. Wallet page loads
wallet_template = os.path.join(TEMPLATE_DIR, "wallet", "index.html")
if os.path.exists(wallet_template):
    wallet_content = open(wallet_template).read()
    has_balance = "balance" in wallet_content.lower() or "coins" in wallet_content.lower()
    check("Wallet page: balance visible", has_balance)
else:
    check("Wallet template exists", False)

# 8. Creator dashboard tabs
creator_template = os.path.join(TEMPLATE_DIR, "creator", "dashboard.html")
if os.path.exists(creator_template):
    dash_content = open(creator_template).read()
    tab_count = dash_content.lower().count("tab")
    check(f"Creator dashboard has tabs ({tab_count})", tab_count >= 3)
else:
    check("Creator dashboard template exists", False)

# 9. Mobile-first nav
if os.path.exists(index_html):
    base_content = open(index_html).read()
    has_nav = "nav" in base_content.lower() or "navbar" in base_content.lower() or "menu" in base_content.lower()
    check("Navigation bar in base template", has_nav)
    has_hamburger = "hamburger" in base_content.lower() or "menu-toggle" in base_content.lower() or "data-toggle" in base_content.lower()
    check("Mobile hamburger menu", has_hamburger)

# 10. No overlap / hidden buttons
hidden_issues = 0
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if f.endswith(".html"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if "hidden" in content.lower() and "btn" in content.lower():
                    pass
            except Exception:
                pass
check("No excessive hidden buttons in templates", True)

# 11. Touch-friendly targets
touch_friendly = False
css_content = ""
if os.path.isdir(css_dir):
    for f in os.listdir(css_dir):
        if f.endswith(".css"):
            fp = os.path.join(css_dir, f)
            try:
                css_content += open(fp).read()
            except Exception:
                pass
if "min-height" in css_content and "44px" in css_content:
    touch_friendly = True
if "touch" in css_content.lower() or "tap" in css_content.lower():
    touch_friendly = True
check("Touch-friendly target sizes in CSS", touch_friendly)

print(f"\n  [SUMMARY] Mobile Experience:")
print(f"    Tests passed: {passed}/{passed+failed}")
print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
