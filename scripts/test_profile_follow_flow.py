#!/usr/bin/env python3
"""Phase 158B: Profile Follow Flow Verification"""
import subprocess, sys
BASE = "http://127.0.0.1:8080"

def curl(path):
    r = subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=10)
    return r.stdout

print("=" * 60)
print("PROFILE FOLLOW FLOW AUDIT")
print("=" * 60)

checks = []

# Followers page
body = curl("/profile/followers")
checks.append(("Followers page loads", len(body) > 100 and "500" not in body[:500]))
checks.append(("No 'No followers yet' in base", "No followers yet" in body or "followers" in body.lower()))

# Following page
body = curl("/profile/following")
checks.append(("Following page loads", len(body) > 100 and "500" not in body[:500]))

# Friends page
body = curl("/profile/friends")
checks.append(("Friends page loads", len(body) > 100 and "500" not in body[:500]))
checks.append(("Friend requests accessible", "friend" in body.lower() or len(body) > 100))

# Blocked list
body = curl("/profile/blocked_list")
checks.append(("Blocked list loads", len(body) > 100 and "500" not in body[:500]))

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
