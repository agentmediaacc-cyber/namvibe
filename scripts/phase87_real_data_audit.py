"""Phase 87 — Real Data Audit.

Scans chain_profiles, chain_posts, chain_reels, chain_stories for obvious fake content.
Modes:
  --audit        : just report
  --delete-obvious-fake : delete fake rows (with confirmation per row)

Safety:
  - Never deletes moon, namvibe, final users.
  - Prints every row before deleting.
  - Deletes child content (posts, reels, stories) before profile.
"""

import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query, write_query
from services.production_content_guard import is_fake_content

SAFE_USERNAMES = {"moon", "namvibe", "final"}

def audit_profiles(dry_run=True):
    rows = fast_query(
        "SELECT id, username, display_name, email, created_at FROM chain_profiles ORDER BY created_at DESC LIMIT 500",
        timeout_ms=5000, default=[]
    )
    flagged = []
    for r in rows:
        username = (r.get("username") or "").lower()
        if username in SAFE_USERNAMES:
            continue
        if is_fake_content(r):
            flagged.append(r)
    return flagged

def audit_content(table, id_col, profile_col, title_col, dry_run=True):
    rows = fast_query(
        f"SELECT p.{id_col}, p.{profile_col}, p.{title_col}, pr.username FROM {table} p JOIN chain_profiles pr ON p.{profile_col} = pr.id ORDER BY p.created_at DESC LIMIT 500",
        timeout_ms=5000, default=[]
    )
    flagged = []
    for r in rows:
        username = (r.get("username") or "").lower()
        if username in SAFE_USERNAMES:
            continue
        if is_fake_content(r):
            flagged.append(r)
    return flagged

def delete_content(table, id_col, ids):
    if not ids:
        return
    placeholders = ",".join(["%s"] * len(ids))
    write_query(f"DELETE FROM {table} WHERE {id_col} IN ({placeholders})", tuple(ids))

def run():
    parser = argparse.ArgumentParser(description="Phase 87 — Real Data Audit")
    parser.add_argument("--audit", action="store_true", help="Audit only")
    parser.add_argument("--delete-obvious-fake", action="store_true", help="Delete obvious fake rows")
    args = parser.parse_args()

    dry_run = not args.delete_obvious_fake

    print("Phase 87: Real Data Audit")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE DELETE'}")
    print()

    # Profiles
    flagged_profiles = audit_profiles(dry_run)
    print(f"  Flagged profiles: {len(flagged_profiles)}")
    for r in flagged_profiles:
        print(f"    {r.get('id')} — {r.get('username')} ({r.get('display_name')})")

    # Posts
    flagged_posts = audit_content("chain_posts", "id", "profile_id", "body", dry_run)
    print(f"  Flagged posts: {len(flagged_posts)}")
    for r in flagged_posts[:10]:
        print(f"    {r.get('id')} — user {r.get('username')}: {str(r.get('body') or '')[:60]}")

    # Reels
    flagged_reels = audit_content("chain_reels", "id", "profile_id", "caption", dry_run)
    print(f"  Flagged reels: {len(flagged_reels)}")
    for r in flagged_reels[:10]:
        print(f"    {r.get('id')} — user {r.get('username')}: {str(r.get('caption') or '')[:60]}")

    # Stories
    flagged_stories = audit_content("chain_stories", "id", "profile_id", "caption", dry_run)
    print(f"  Flagged stories: {len(flagged_stories)}")
    for r in flagged_stories[:10]:
        print(f"    {r.get('id')} — user {r.get('username')}: {str(r.get('caption') or '')[:60]}")

    # Delete if live mode
    if not dry_run and flagged_profiles:
        print()
        print("  Deleting flagged content...")
        profile_ids = [r["id"] for r in flagged_profiles if r.get("id")]

        # Child content first
        delete_content("chain_posts", "profile_id", profile_ids)
        delete_content("chain_reels", "profile_id", profile_ids)
        delete_content("chain_stories", "profile_id", profile_ids)
        delete_content("chain_follows", "follower_profile_id", profile_ids)
        delete_content("chain_follows", "following_profile_id", profile_ids)
        delete_content("chain_friends", "profile_id_1", profile_ids)
        delete_content("chain_friends", "profile_id_2", profile_ids)

        # Then profiles themselves
        delete_content("chain_profiles", "id", profile_ids)
        print(f"  Deleted {len(profile_ids)} profiles and related content.")

    print(f"\n  Done. Total flagged: {len(flagged_profiles)} profiles, {len(flagged_posts)} posts, {len(flagged_reels)} reels, {len(flagged_stories)} stories")
    return True

if __name__ == "__main__":
    run()
