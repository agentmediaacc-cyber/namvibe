#!/usr/bin/env python3
"""Phase 158B: Profile Media Reflection Verification"""
import subprocess, sys
BASE = "http://127.0.0.1:8080"

def curl(path):
    r = subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=10)
    return r.stdout

print("=" * 60)
print("PROFILE MEDIA REFLECTION AUDIT")
print("=" * 60)

checks = []

# Posts page
body = curl("/profile/posts")
checks.append(("Posts page loads", len(body) > 100 and "500" not in body[:500]))

# Posts manager
body = curl("/profile/posts_manager")
checks.append(("Posts manager loads", len(body) > 100 and "500" not in body[:500]))

# Reels page
body = curl("/profile/reels")
checks.append(("Reels page loads", len(body) > 100 and "500" not in body[:500]))

# Reels manager
body = curl("/profile/reels_manager")
checks.append(("Reels manager loads", len(body) > 100 and "500" not in body[:500]))

# Posts API
body = curl("/profile/api/posts")
checks.append(("Posts API responds", len(body) > 20 and "500" not in body[:500]))

# Reels API
body = curl("/profile/api/reels")
checks.append(("Reels API responds", len(body) > 20 and "500" not in body[:500]))

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
