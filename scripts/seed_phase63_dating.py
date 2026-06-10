#!/usr/bin/env python3
"""Phase 63 — Seed dating profiles for 5 demo users."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"

from services.neon_service import write_query, fast_query

SEED_PROFILES = ["chain_star", "chain_moon", "chain_gold", "chain_million", "chain_premium"]

DATING_PROFILES = [
    {
        "username": "chain_star",
        "bio": "Love exploring new places and meeting people.",
        "relationship_goal": "relationship",
        "location_preference": "Windhoek",
        "interests": ["music", "travel", "fashion", "photography"],
        "trust_score": 80,
        "safety_badge": True,
        "verification_status": "verified",
    },
    {
        "username": "chain_moon",
        "bio": "Creative soul looking for genuine connections.",
        "relationship_goal": "friendship",
        "location_preference": "Windhoek",
        "interests": ["art", "music", "reading", "cooking"],
        "trust_score": 70,
        "safety_badge": False,
        "verification_status": "unverified",
    },
    {
        "username": "chain_gold",
        "bio": "Adventure seeker and coffee enthusiast.",
        "relationship_goal": "casual",
        "location_preference": "Swakopmund",
        "interests": ["hiking", "coffee", "travel", "sports"],
        "trust_score": 65,
        "safety_badge": False,
        "verification_status": "unverified",
    },
    {
        "username": "chain_million",
        "bio": "Business minded, looking for something real.",
        "relationship_goal": "marriage",
        "location_preference": "Windhoek",
        "interests": ["business", "finance", "travel", "fitness"],
        "trust_score": 90,
        "safety_badge": True,
        "verification_status": "verified",
    },
    {
        "username": "chain_premium",
        "bio": "Premium lifestyle, premium connections.",
        "relationship_goal": "open",
        "location_preference": "Windhoek",
        "interests": ["luxury", "travel", "dining", "music"],
        "trust_score": 85,
        "safety_badge": True,
        "verification_status": "verified",
    },
]


def seed():
    print("Seeding Phase 63 dating profiles...")
    profile_ids = {}
    for uname in SEED_PROFILES:
        rows = fast_query("SELECT id FROM chain_profiles WHERE username = %s LIMIT 1", (uname,), default=[])
        if rows:
            profile_ids[uname] = str(rows[0]["id"])
            print(f"  Found {uname}: {profile_ids[uname]}")
    if len(profile_ids) < 2:
        print("  Need at least 2 seeded profiles. Run seed_chain_test_users.py first.")
        return

    for dp in DATING_PROFILES:
        pid = profile_ids.get(dp["username"])
        if not pid:
            continue
        existing = fast_query("SELECT id FROM chain_dating_profiles WHERE profile_id = %s LIMIT 1", (pid,), default=[])
        if existing:
            print(f"  Dating profile already exists for {dp['username']}: {existing[0]['id']}")
            continue
        did = os.urandom(16).hex()
        did_uuid = f"{did[:8]}-{did[8:12]}-{did[12:16]}-{did[16:20]}-{did[20:32]}"
        write_query(
            """INSERT INTO chain_dating_profiles
               (id, profile_id, relationship_goal, location_preference, bio, interests, trust_score, safety_badge, verification_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (did_uuid, pid, dp["relationship_goal"], dp["location_preference"],
             dp["bio"], json.dumps(dp["interests"]), dp["trust_score"],
             dp["safety_badge"], dp["verification_status"]),
        )
        print(f"  Created dating profile for {dp['username']}: {did_uuid}")

        prefs_existing = fast_query("SELECT id FROM chain_dating_preferences WHERE profile_id = %s LIMIT 1", (pid,), default=[])
        if not prefs_existing:
            pref_id = os.urandom(16).hex()
            pref_uuid = f"{pref_id[:8]}-{pref_id[8:12]}-{pref_id[12:16]}-{pref_id[16:20]}-{pref_id[20:32]}"
            write_query(
                "INSERT INTO chain_dating_preferences (id, profile_id) VALUES (%s, %s)",
                (pref_uuid, pid),
            )
            print(f"  Created preferences for {dp['username']}")

    print("Seeding complete.")


if __name__ == "__main__":
    seed()
