#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
header = (ROOT / "templates/profile/partials/profile_header.html").read_text()
index = (ROOT / "templates/profile/index.html").read_text()
private = (ROOT / "templates/profile/private_profile.html").read_text()
policy = (ROOT / "services/social_action_policy.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


owner_block = header.split('<div class="hero-actions">', 1)[1].split("{% else %}", 1)[0]
check("owner block has Edit Profile", "Edit Profile" in owner_block)
check("owner block has Create", "Create" in owner_block or "Create Post" in owner_block)
check("owner block has Wallet", "Wallet" in owner_block)
check("owner block has Privacy", "Privacy" in owner_block)
check("owner block has no self message", "Message" not in owner_block and "Audio" not in owner_block and "Video" not in owner_block)
check("other actions use action_policy", "action_policy" in header and "can_chat" in header and "can_call" in header)
check("self policy blocks chat/call", '"primary_action": "self"' in policy and '"can_chat": False' in policy and '"can_call": False' in policy)
check("privacy badge visible", "privacy" in header.lower() and "badge" in header.lower())
check("completion cards clean", "Complete Your Profile" in index and "next_best_action" in index)
check("raw missing list removed", "banner DOB skills portfolio website" not in index)
private_lower = private.lower()
check("private template hides content", "private account" in private_lower and "profile-tabs" not in private_lower and "nv-reel-card" not in private_lower)
