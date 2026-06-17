"""
Test: Friendship System Flow
Tests the complete friend request lifecycle using moon and namvibe test accounts.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_ENV"] = "production"

from services.neon_service import fast_query, write_query, prime_neon_runtime
from services.friend_service import send_friend_request, accept_friend_request, decline_friend_request, are_friends


PASS = 0
FAIL = 0


def check(test_name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS [{test_name}] {detail}")
    else:
        FAIL += 1
        print(f"  FAIL [{test_name}] {detail}")


def find_profile(username):
    rows = fast_query("SELECT id, username FROM chain_profiles WHERE username = %s LIMIT 1", [username], timeout_ms=30000)
    return rows[0] if rows else None


def cleanup_requests(sender_id, receiver_id):
    write_query("DELETE FROM chain_notifications WHERE actor_profile_id IN (%s, %s)", [sender_id, receiver_id])
    write_query("DELETE FROM chain_friend_requests WHERE sender_profile_id IN (%s, %s) OR recipient_profile_id IN (%s, %s)", [sender_id, receiver_id, sender_id, receiver_id])
    write_query("DELETE FROM chain_friends WHERE (profile_id_1 = %s AND profile_id_2 = %s) OR (profile_id_1 = %s AND profile_id_2 = %s)", [sender_id, receiver_id, receiver_id, sender_id])


def main():
    global PASS, FAIL
    print("=" * 60)
    print("Test: Friendship System Flow")
    print("=" * 60)

    prime_neon_runtime()
    import time; time.sleep(1)

    moon = find_profile("moon")
    namvibe = find_profile("namvibe")

    if not moon:
        print("  SKIP - moon account not found. Create it first.")
        return
    if not namvibe:
        print("  SKIP - namvibe account not found. Create it first.")
        return

    moon_id = moon["id"]
    namvibe_id = namvibe["id"]

    print(f"\nUsing moon: {moon_id}")
    print(f"Using namvibe: {namvibe_id}")

    cleanup_requests(moon_id, namvibe_id)

    # Step 1: Send friend request from moon to namvibe
    print("\n[Step 1] Send friend request from moon -> namvibe")
    result = send_friend_request(moon_id, namvibe_id)
    check("send_friend_request", result.get("success"), f"Request sent: {result.get('request_id')}")
    if not result.get("success"):
        print(f"  Error: {result.get('error')}")

    # Step 2: Confirm pending request exists
    print("\n[Step 2] Confirm pending request")
    req = fast_query(
        "SELECT id, sender_profile_id, recipient_profile_id, status FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending'",
        [moon_id, namvibe_id]
    )
    check("pending_request_exists", bool(req), f"Found request: {req[0]['id'] if req else 'N/A'}")

    request_id = req[0]['id'] if req else None

    # Step 3: Confirm namvibe notification exists
    print("\n[Step 3] Confirm namvibe notification")
    notifs = fast_query(
        """SELECT id, event_type, title, actor_profile_id FROM chain_notifications
           WHERE recipient_profile_id = %s AND deleted_at IS NULL
           ORDER BY created_at DESC LIMIT 10""",
        [namvibe_id], timeout_ms=15000
    )
    fr_notif = [n for n in notifs if n.get('event_type') in ('friend_request',) and str(n.get('actor_profile_id')) == moon_id]
    check("friend_request_notification", bool(fr_notif), f"Notification found: {fr_notif[0]['title'] if fr_notif else 'N/A'}")

    # Step 4: Accept as namvibe
    print("\n[Step 4] Accept request as namvibe")
    result = accept_friend_request(namvibe_id, request_id)
    check("accept_friend_request", result.get("success"), f"Accept result: {result.get('success')}")

    # Step 5: Confirm chain_friends row exists
    print("\n[Step 5] Confirm chain_friends row")
    friends_row = fast_query(
        "SELECT id FROM chain_friends WHERE (profile_id_1 = %s AND profile_id_2 = %s) OR (profile_id_1 = %s AND profile_id_2 = %s) LIMIT 1",
        [moon_id, namvibe_id, namvibe_id, moon_id]
    )
    check("friendships_row", bool(friends_row), f"Friendship row: {friends_row[0]['id'] if friends_row else 'N/A'}")

    # Step 6: Check accepted notification for moon
    print("\n[Step 6] Confirm accepted notification for moon")
    notifs_moon = fast_query(
        """SELECT id, event_type, title, actor_profile_id FROM chain_notifications
           WHERE recipient_profile_id = %s AND deleted_at IS NULL
           ORDER BY created_at DESC LIMIT 10""",
        [moon_id], timeout_ms=15000
    )
    accepted_notif = [n for n in notifs_moon if n.get('event_type') in ('friend_request_accepted', 'friend_accepted') and str(n.get('actor_profile_id')) == namvibe_id]
    check("accepted_notification", bool(accepted_notif), f"Accepted notif: {accepted_notif[0]['title'] if accepted_notif else 'N/A'}")

    # Step 7: Confirm are_friends returns true
    print("\n[Step 7] Check are_friends")
    check("are_friends_true", are_friends(moon_id, namvibe_id), "moon and namvibe are friends")
    check("are_friends_symmetric", are_friends(namvibe_id, moon_id), "namvibe and moon are friends")

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
