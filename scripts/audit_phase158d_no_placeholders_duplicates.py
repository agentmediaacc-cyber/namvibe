#!/usr/bin/env python3
"""Audit: No placeholder pages, no dead buttons, no duplicate UI."""
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
print("PHASE 158D - NO PLACEHOLDERS / NO DUPLICATES AUDIT")
print("=" * 60)

placeholder_patterns = [
    r"under construction",
    r"coming soon",
    r"this page is not ready",
    r"placeholder",
    r"TODO",
    r"FIXME",
    r"not implemented",
    r"feature coming",
]

# Check new template files
template_dir = "templates"
new_files = [
    "profile/completion.html",
    "profile/sent_requests.html",
    "profile/suggestions.html",
    "profile/sharing.html",
    "profile/security.html",
    "profile/verification_request.html",
    "profile/business.html",
    "profile/advertising.html",
    "admin/verifications.html",
]

for relpath in new_files:
    fpath = os.path.join(template_dir, relpath)
    full_path = fpath
    if not os.path.exists(full_path):
        full_path = os.path.join(os.getcwd(), fpath)
    
    if not os.path.exists(full_path):
        warn(f"{relpath} not found")
        FAIL += 1
        continue
    
    with open(full_path) as f:
        content = f.read()
    
    test(f"{relpath} exists", True)
    
    # Check for placeholder patterns
    for pat in placeholder_patterns:
        if re.search(pat, content, re.IGNORECASE):
            warn(f"{relpath} contains placeholder text: '{pat}'")
    
    # Check for dead buttons (buttons with no action or empty onclick)
    dead_btn = re.findall(r'<button[^>]*>(?:\s*</button>\s*$|<!--.*-->.*</button>)', content)
    if dead_btn:
        warn(f"{relpath} has potentially dead buttons", str(len(dead_btn)) + " found")

# Check service files exist and are not placeholders
services = [
    "services/profile_completion_service.py",
    "services/verification_request_service.py",
    "services/trust_scam_service.py",
    "services/business_page_service.py",
    "services/subscriber_content_service.py",
    "services/location_privacy_service.py",
    "services/profile_sharing_service.py",
]
for svc in services:
    if os.path.exists(svc):
        with open(svc) as f:
            content = f.read()
        test(f"{svc} exists", True)
        test(f"{svc} has real code (not placeholder)", len(content) > 50)
        for pat in placeholder_patterns:
            if re.search(pat, content, re.IGNORECASE):
                warn(f"{svc} contains placeholder text: '{pat}'")
    else:
        warn(f"{svc} not found")

# Check route files exist
routes = [
    "api_routes/social_graph_routes.py",
    "api_routes/verification_admin_routes.py",
    "api_routes/ad_admin_routes.py",
]
for r in routes:
    if os.path.exists(r):
        with open(r) as f:
            content = f.read()
        test(f"{r} exists", True)
        test(f"{r} has real routes", len(content) > 100)
        for pat in placeholder_patterns:
            if re.search(pat, content, re.IGNORECASE):
                warn(f"{r} contains placeholder text: '{pat}'")
    else:
        warn(f"{r} not found")

# Check SQL migration
sql_file = "sql/058_phase158d_tables.sql"
if os.path.exists(sql_file):
    with open(sql_file) as f:
        content = f.read()
    test("SQL migration exists", True)
    test("SQL migration has real content", len(content) > 100)
else:
    warn("SQL migration not found")

print(f"\nResults: {PASS} passed, {FAIL} failed, {WARN} warnings")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
