#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
header = (ROOT / "templates/profile/partials/profile_header.html").read_text()
index = (ROOT / "templates/profile/index.html").read_text()
private = (ROOT / "templates/profile/private_profile.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


owner = header.split('<div class="hero-actions">', 1)[1].split("{% else %}", 1)[0]
check("owner actions are correct", "Edit Profile" in owner and "Wallet" in owner and "Privacy" in owner)
check("owner does not show chat/call", "Message" not in owner and "Audio" not in owner and "Video" not in owner)
check("other actions use policy", "action_policy" in header and "can_call" in header and "can_chat" in header)
check("privacy badge visible", "privacy-tag" in header)
check("completion card clean", "Complete Your Profile" in index and "banner DOB skills portfolio website" not in index)
check("private profile does not leak tabs", "Private Account" in private and "profile-tabs" not in private)
check("profile empty states real", "No posts yet" in index and "No reels yet" in index)
