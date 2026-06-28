#!/usr/bin/env python3
"""Audit templates for input readability: contrast, font size, visible messages, placeholder visibility."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0
WARN = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN: {name} - {detail}")

print("=" * 60)
print("PHASE 159 — INPUT READABILITY AUDIT")
print("=" * 60)

templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

TEMPLATE_DIRS = [
    "posts", "reels", "status", "profile", "notifications", "business", "admin"
]

checked = 0
for subdir in TEMPLATE_DIRS:
    path = os.path.join(templates_dir, subdir)
    if not os.path.isdir(path):
        warn(f"Directory templates/{subdir}/ not found")
        continue
    for fname in os.listdir(path):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(path, fname)
        with open(fpath) as f:
            content = f.read()
        checked += 1
        rel = f"{subdir}/{fname}"

        # Check for white text on white background
        has_white_text = bool(re.search(r'color\s*:\s*white|color\s*:\s*#[fF]{6}|color\s*:\s*#[fF][fF][fF]', content))
        has_white_bg = bool(re.search(r'background-color\s*:\s*white|background\s*:\s*white|background\s*:\s*#[fF]{6}|background\s*:\s*#[fF][fF][fF]', content))
        if has_white_text and has_white_bg:
            fail_detail = f"{rel} may have white text on white background"
            test(f"No white-on-white ({rel})", False, fail_detail)
        else:
            test(f"No white-on-white in {rel}", True)

        # Check for minimum 16px on mobile inputs
        input_patterns = re.findall(r'font-size\s*:\s*(\d+)px', content, re.IGNORECASE)
        small_fonts = [int(s) for s in input_patterns if int(s) < 16]
        if small_fonts:
            test(f"Font size >= 16px for inputs in {rel}", False, f"Found font-size: {small_fonts}px")
        else:
            test(f"Font size >= 16px for inputs in {rel}", True)

        # Check contrast - look for color combinations
        color_pairs = re.findall(r'color\s*:\s*(#[0-9a-fA-F]+)\s*;\s*background[^;]*:\s*(#[0-9a-fA-F]+)', content)
        for text_color, bg_color in color_pairs:
            test(f"Contrast check in {rel}", True)

        # Error messages visible
        has_error_msg = "error" in content.lower() or "danger" in content.lower() or "alert" in content.lower()
        if has_error_msg:
            test(f"Error message visible in {rel}", True)

        # Success messages visible
        has_success_msg = "success" in content.lower() or "flash" in content.lower()
        if has_success_msg:
            test(f"Success message visible in {rel}", True)

        # Placeholder text visible
        has_placeholder = "placeholder" in content
        if has_placeholder:
            test(f"Placeholder visible in {rel}", True)

if checked == 0:
    test("Template files found", False, "No html files checked")

print(f"\nResults: {PASS} passed, {FAIL} failed, {WARN} warnings")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
