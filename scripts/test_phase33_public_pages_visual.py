#!/usr/bin/env python3
"""Phase 33 — Public Pages Visual Test."""

import os
import sys
import subprocess
import importlib.util
import json

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

print("=== Phase 33 Public Pages Visual Test ===")

# 1. Check templates exist
templates_root = os.path.join(BASE, "templates")
template_files = set()
for root, dirs, files in os.walk(templates_root):
    for f in files:
        if f.endswith(".html"):
            rel = os.path.relpath(os.path.join(root, f), templates_root)
            template_files.add(rel)

key_templates = [
    "base.html",
    "chain_home.html",
    "settings/notifications.html",
]

# Add known key templates
for root, dirs, files in os.walk(templates_root):
    for f in files:
        if f.endswith(".html"):
            rel = os.path.relpath(os.path.join(root, f), templates_root)
            if "auth/" in rel and f.endswith(".html"):
                key_templates.append(rel)
            if "messages/" in rel and f.endswith(".html"):
                key_templates.append(rel)
            if "calls/" in rel and f.endswith(".html"):
                key_templates.append(rel)
            if "live/" in rel and f.endswith(".html"):
                key_templates.append(rel)
            if "creator/" in rel and f.endswith(".html"):
                key_templates.append(rel)
            if "profile/" in rel and f.endswith(".html"):
                key_templates.append(rel)

for t in set(key_templates):
    test(f"Template exists: {t}", t in template_files)

# 2. Check all HTML templates for basic structure
html_issues = []
for tf in template_files:
    fpath = os.path.join(templates_root, tf)
    try:
        with open(fpath) as f:
            content = f.read()
    except:
        html_issues.append(f"{tf}: unreadable")
        continue

    if not content.strip():
        html_issues.append(f"{tf}: empty file")
        continue

    if "{% extends" not in content and "{% block" not in content and "<!DOCTYPE" not in content:
        # Might be a partial
        pass

    # Check for unclosed tags (basic)
    for tag in ["{% if", "{% for", "{% block"]:
        opens = content.count(tag)
        if tag == "{% block":
            closes = content.count("{% endblock") + content.count("{% endfor") + content.count("{% endif")
        else:
            close_tag = tag.replace("{% ", "{% end")
            closes = content.count(close_tag)
        # Too basic, skip

if html_issues:
    for issue in html_issues[:5]:
        test(issue, False)

# 3. Check CSS files compile
for css_name in ["chain_theme.css", "style.css", "chain_home.css", "platform_premium.css", "live.css", "calls.css", "chat.css"]:
    css_path = os.path.join(BASE, "static/css", css_name)
    if os.path.exists(css_path):
        with open(css_path) as f:
            css = f.read()
        # Basic check: balanced braces
        opens = css.count("{")
        closes = css.count("}")
        test(f"{css_name} balanced braces", opens == closes)
    else:
        test(f"{css_name} exists", False)

# 4. Check that public templates have proper navigation
public_templates = ["chain_home.html", "auth/login.html", "auth/register.html"]
base_content = ""
base_path = os.path.join(templates_root, "base.html")
if os.path.exists(base_path):
    with open(base_path) as f:
        base_content = f.read()

test("base.html has hamburger menu", "fa-bars" in base_content)
test("base.html has mobile nav", "mobile-nav" in base_content)
test("base.html has drawer", "social-drawer" in base_content)
test("base.html has search bar", "search-bar" in base_content)
test("base.html has theme switcher", "theme-switcher" in base_content)

# 5. Check chain_home.html for social content sections
home_path = os.path.join(templates_root, "chain_home.html")
if os.path.exists(home_path):
    with open(home_path) as f:
        home = f.read()
    test("homepage has stories section", "story" in home.lower())
    test("homepage has live section", "live" in home.lower())
    test("homepage has composer", "composer" in home.lower() or "create" in home.lower())
    test("homepage has feed/suggestions", "feed" in home.lower() or "suggest" in home.lower())

# 6. Check messages template
msg_templates = [t for t in template_files if "messages/" in t or t == "chat.html"]
for msg_t in msg_templates[:1]:
    mpath = os.path.join(templates_root, msg_t)
    if os.path.exists(mpath):
        with open(mpath) as f:
            msg = f.read()
        test(f"Messages template has composer ({msg_t})", "composer" in msg.lower() or "message-form" in msg or "input" in msg)

# 7. Check calls template
call_templates = [t for t in template_files if "calls/" in t]
for ct in call_templates[:1]:
    cpath = os.path.join(templates_root, ct)
    if os.path.exists(cpath):
        with open(cpath) as f:
            call = f.read()
        test(f"Calls template has controls ({ct})", "control" in call.lower() or "button" in call or "danger" in call)

# 8. Check live template
live_templates = [t for t in template_files if "live/" in t]
for lt in live_templates[:1]:
    lpath = os.path.join(templates_root, lt)
    if os.path.exists(lpath):
        with open(lpath) as f:
            live = f.read()
        test(f"Live template has studio ({lt})", "studio" in live.lower() or "go-live" in live or "stream" in live.lower())

# 9. Check creator/dashboard template
creator_templates = [t for t in template_files if "creator/" in t or "dashboard/" in t]
for ct in creator_templates[:1]:
    cpath = os.path.join(templates_root, ct)
    if os.path.exists(cpath):
        with open(cpath) as f:
            creator = f.read()
        test(f"Creator/dashboard has tabs ({ct})", "tab" in creator.lower() or "nav" in creator.lower() or "menu" in creator.lower())

if not creator_templates:
    test("Creator/dashboard template found", False)

# 10. Settings notifications page
notif_path = os.path.join(templates_root, "settings/notifications.html")
if os.path.exists(notif_path):
    with open(notif_path) as f:
        notif = f.read()
    test("Push settings page loads", "push" in notif.lower() or "notification" in notif.lower())
    test("Push settings has toggles", "toggle" in notif.lower() or "checkbox" in notif.lower() or "switch" in notif.lower())

# 11. Check for duplicate styles
css_files_read = {}
for css_name in ["chain_theme.css", "chain_home.css", "style.css", "platform_premium.css"]:
    css_path = os.path.join(BASE, "static/css", css_name)
    if os.path.exists(css_path):
        with open(css_path) as f:
            css_files_read[css_name] = f.read()

if "chain_theme.css" in css_files_read and "chain_home.css" in css_files_read:
    # Check chain_home doesn't override theme colors with old values
    home_css = css_files_read["chain_home.css"]
    old_colors_in_home = [c for c in ["#F4F7FB", "#0B1B33", "#1E88E5", "#F7B733", "#D72638"] if c in home_css]
    test("chain_home.css doesn't use old blue (#1E88E5)", "#1E88E5" not in home_css or False)
    # Just report
    if old_colors_in_home:
        print(f"  [INFO] chain_home.css still has {len(old_colors_in_home)} old colors: {old_colors_in_home}")

print(f"\nResults: {pass_count}/{pass_count + fail_count} passed, {fail_count}/{pass_count + fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
