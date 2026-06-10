#!/usr/bin/env python3
"""
Seed demo notifications for Phase 60 — Premium Notification Center.
Idempotent: creates notifications for chain_star from other seeded users.
"""
import os, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.neon_service import fast_query, write_query
from services.logging_service import log_info

SEED_NOTIFICATIONS = [
    {"event_type": "follow", "title": "chain_moon started following you", "body": "chain_moon followed you", "actor_username": "chain_moon"},
    {"event_type": "post_like", "title": "chain_gold liked your post", "body": "chain_gold liked your photo", "actor_username": "chain_gold"},
    {"event_type": "new_message", "title": "New message from chain_million", "body": "chain_million sent you a message", "actor_username": "chain_million"},
    {"event_type": "live_started", "title": "chain_premium went live", "body": "chain_premium is now live", "actor_username": "chain_premium"},
    {"event_type": "wallet_received", "title": "Wallet deposit received", "body": "You received 500 CHAIN coins", "actor_username": None},
    {"event_type": "verification_approved", "title": "Verification approved", "body": "Your account has been verified", "actor_username": None},
    {"event_type": "system_announcement", "title": "Welcome to Premium", "body": "CHAIN Premium Notification Center is now live", "actor_username": None},
    {"event_type": "comment", "title": "chain_moon commented on your post", "body": "chain_moon: Amazing view!", "actor_username": "chain_moon"},
    {"event_type": "reply", "title": "chain_gold replied to your comment", "body": "chain_gold: Totally agree!", "actor_username": "chain_gold"},
    {"event_type": "mention", "title": "chain_premium mentioned you", "body": "chain_premium mentioned you in a post", "actor_username": "chain_premium"},
    {"event_type": "reel_like", "title": "chain_million liked your reel", "body": "chain_million liked your reel", "actor_username": "chain_million"},
    {"event_type": "story_reaction", "title": "chain_gold reacted to your story", "body": "chain_gold reacted with ❤️", "actor_username": "chain_gold"},
]

def main():
    print("=" * 60)
    print("Seeding Phase 60 demo notifications")
    print("=" * 60)

    # Find chain_star
    rows = fast_query(
        "SELECT id, username FROM chain_profiles WHERE username = 'chain_star' LIMIT 1",
        default=[],
    )
    if not rows:
        print("[ERROR] chain_star not found. Run seed_chain_test_users.py first.")
        sys.exit(1)
    star_id = rows[0]["id"]

    # Find actor profiles by username
    actor_cache = {}
    actor_usernames = [n["actor_username"] for n in SEED_NOTIFICATIONS if n["actor_username"]]
    if actor_usernames:
        placeholders = ",".join(["%s"] * len(actor_usernames))
        actor_rows = fast_query(
            f"SELECT id, username FROM chain_profiles WHERE username IN ({placeholders})",
            tuple(actor_usernames),
            default=[],
        )
        for r in actor_rows:
            actor_cache[r["username"]] = r["id"]

    created = 0
    skipped = 0

    for note in SEED_NOTIFICATIONS:
        actor_id = actor_cache.get(note["actor_username"]) if note["actor_username"] else None

        # Dedup check
        existing = fast_query(
            """SELECT id FROM chain_notifications
               WHERE recipient_profile_id = %s AND event_type = %s
               AND actor_profile_id IS NOT DISTINCT FROM %s
               AND is_deleted = false
               ORDER BY created_at DESC LIMIT 1""",
            (star_id, note["event_type"], actor_id),
            default=[],
        )
        if existing:
            skipped += 1
            continue

        nid = str(uuid.uuid4())
        sql = """INSERT INTO chain_notifications
                 (id, recipient_profile_id, actor_profile_id, notification_type, title, body, is_read, created_at)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, now())"""
        try:
            write_query(sql, (
                nid, star_id, actor_id, note["event_type"],
                note["title"], note["body"],
                False,
            ))
            created += 1
            print(f"  [CREATED] {note['title']}")
        except Exception as e:
            print(f"  [ERROR] {note['title']}: {e}")

    print(f"\nCreated: {created}, Skipped (already exist): {skipped}")

    # Verify
    count_rows = fast_query(
        "SELECT COUNT(*) as cnt FROM chain_notifications WHERE recipient_profile_id = %s AND is_deleted = false",
        (star_id,),
        default=[{"cnt": 0}],
    )
    total = count_rows[0]["cnt"] if count_rows else 0
    print(f"Total notifications for chain_star: {total}")
    print("Done!")

if __name__ == "__main__":
    main()
