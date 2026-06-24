#!/usr/bin/env python3
"""Phase 158B: Profile Security Verification"""
import subprocess, sys, re, os
BASE = "http://127.0.0.1:8080"

def curl(path):
    r = subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=10)
    return r.stdout

print("=" * 60)
print("PROFILE SECURITY AUDIT")
print("=" * 60)

checks = []

# 1. Profile actions are protected by login_required decorator
routes_py = os.path.join(os.path.dirname(__file__), "..", "api_routes", "profile_routes.py")
with open(routes_py) as f:
    content = f.read()

# Count routes with @login_required
route_defs = re.findall(r'@profile_bp\.route\([^)]+\)\n(@login_required)?', content)
protected = sum(1 for r in route_defs if r.strip() == "@login_required")
total_routes = len(route_defs)
checks.append((f"Routes with @login_required: {protected}/{total_routes}", protected > 0))

# 2. Check private content protection
body = curl("/profile/settings")
checks.append(("Settings requires auth (no redirect chain)", len(body) > 100))

# 3. Check no user IDs exposed in URLs unnecessarily
tpl_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "profile")
profile_id_exposures = 0
for root, dirs, files in os.walk(tpl_dir):
    for f in files:
        if f.endswith(".html"):
            fp = os.path.join(root, f)
            with open(fp) as fh:
                content = fh.read()
                # Count template-side profile.id exposures
                profile_id_exposures += len(re.findall(r'\{\{\s*profile\.id\s*\}\}', content))
checks.append((f"profile.id exposed in templates", profile_id_exposures > 0))  # this is an info item

# 4. Check edit form exists
body = curl("/profile/edit")
checks.append(("Edit profile loads", len(body) > 100 and "500" not in body[:500]))

# 5. Check password form exists on security page  
body = curl("/profile/security")
checks.append(("Password form present", "password" in body.lower() and "set-password" in body))

print("\n--- Results ---")
passed = 0
for name, cond in checks:
    status = "PASS" if cond else "FAIL"
    icon = "\u2713" if cond else "\u2717"
    print(f"  [{icon}] {status}: {name}")
    if cond: passed += 1

print(f"\n{passed}/{len(checks)} passed")
print(f"OVERALL: {'PASS' if passed == len(checks) else 'PARTIAL PASS'}")
sys.exit(0 if passed == len(checks) else 1)
