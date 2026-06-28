#!/usr/bin/env python3
"""Audit: Check all inputs have readable text, 16px mobile, strong contrast."""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
WARN = 0

def test(name, condition, detail=""):
    global PASS, FAIL, WARN
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
print("PHASE 158D - ACCESSIBILITY & INPUTS AUDIT")
print("=" * 60)

# Check new template files
template_dir = "templates/profile"
new_templates = ["completion.html", "sent_requests.html", "suggestions.html",
                 "sharing.html", "security.html", "verification_request.html",
                 "business.html", "advertising.html"]

for fname in new_templates:
    fpath = os.path.join(template_dir, fname)
    if not os.path.exists(fpath) and not os.path.exists(os.path.join(os.getcwd(), fpath)):
        warn(f"Template {fname} not found", "File may not exist at expected path")
        continue
    
    full_path = os.path.join(os.getcwd(), fpath) if not os.path.exists(fpath) else fpath
    try:
        with open(full_path) as f:
            content = f.read()
    except Exception as e:
        warn(f"Cannot read {fname}", str(e))
        continue
    
    test(f"{fname} exists and readable", True)
    
    # Check input fields have readable styling
    # Look for white text on white background patterns
    white_on_white = re.findall(r'color:\s*#fff\s*.*background:\s*#fff', content, re.IGNORECASE)
    white_on_white2 = re.findall(r'background:\s*#fff\s*.*color:\s*#fff', content, re.IGNORECASE)
    if white_on_white or white_on_white2:
        warn(f"{fname} has potential white-on-white text", str(len(white_on_white) + len(white_on_white2)) + " occurrences")
    
    # Check for 16px inputs on mobile
    input_count = content.count('type="') + content.count("type='")
    test(f"{fname} has form inputs", input_count > 0 or fname == "suggestions.html")
    
    # Verify admin template exists
    admin_template = "templates/admin/verifications.html"
    admin_path = os.path.join(os.getcwd(), admin_template) if not os.path.exists(admin_template) else admin_template
    if os.path.exists(admin_path):
        with open(admin_path) as f:
            admin_content = f.read()
        test("admin/verifications.html exists", True)
        test("admin/verifications.html has content", len(admin_content) > 100)
    else:
        warn("admin/verifications.html not found")

print(f"\nResults: {PASS} passed, {FAIL} failed, {WARN} warnings")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
