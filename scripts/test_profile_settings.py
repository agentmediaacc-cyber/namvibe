#!/usr/bin/env python3
"""Phase 158B: Profile Settings Verification"""
import subprocess, sys, os
BASE = "http://127.0.0.1:8080"

def curl(path):
    r = subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=10)
    return r.stdout

print("=" * 60)
print("PROFILE SETTINGS AUDIT")
print("=" * 60)

checks = []

# Settings page loads
body = curl("/profile/settings")
ok = len(body) > 100 and "500" not in body[:500]
checks.append(("Settings page loads", ok))
if ok:
    sections = {
        "Profile details form": "display_name" in body or "username" in body,
        "Privacy section": "show_online_status" in body or "profile_visibility" in body,
        "Call access section": "allow_video_calls" in body or "allow_audio_calls" in body,
        "Audio/video quality": "audio_quality" in body or "video_quality" in body,
        "Encryption section": "encryption" in body.lower() or "key fingerprint" in body.lower(),
        "Ringing section": "ringtone" in body or "vibration" in body,
    }
    for name, cond in sections.items():
        checks.append((name, cond))

# Privacy page
body = curl("/profile/privacy")
ok = len(body) > 100
checks.append(("Privacy page loads", ok))
if ok:
    privacy_opts = {
        "Profile visibility select": "profile_visibility" in body,
        "Who can see posts": "who_can_see_posts" in body,
        "Who can see reels": "who_can_see_reels" in body,
        "Who can see stories": "who_can_see_stories" in body,
        "Who can follow": "who_can_follow_me" in body,
        "Who can message": "who_can_message_me" in body,
        "Who can call": "who_can_call" in body,
    }
    for name, cond in privacy_opts.items():
        checks.append((name, cond))

# Security page
body = curl("/profile/security")
ok = len(body) > 100
checks.append(("Security page loads", ok))

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
