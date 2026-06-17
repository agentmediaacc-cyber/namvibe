"""
Test: Friendship Permissions
Verifies non-friends cannot message/call/video/funds/gifts and friends can pass permission guard.
After non-friend checks, makes moon+namvibe friends to test the friend path.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_ENV"] = "production"

from services.neon_service import fast_query, write_query, prime_neon_runtime
from services.friendship_service import are_friends, require_friendship_or_403


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


def get_other_non_friend(moon_id):
    rows = fast_query(
        """
        SELECT id, username FROM chain_profiles 
        WHERE id != %s 
          AND id NOT IN (
            SELECT profile_id_1 FROM chain_friends WHERE profile_id_2 = %s AND status = 'friend'
            UNION
            SELECT profile_id_2 FROM chain_friends WHERE profile_id_1 = %s AND status = 'friend'
          )
        LIMIT 1
        """,
        [moon_id, moon_id, moon_id],
        timeout_ms=30000
    )
    return rows[0] if rows else None


def main():
    global PASS, FAIL
    print("=" * 60)
    print("Test: Friendship Permissions")
    print("=" * 60)

    prime_neon_runtime()
    import time; time.sleep(1)

    moon = find_profile("moon")
    namvibe = find_profile("namvibe")

    if not moon or not namvibe:
        print("  SKIP - moon or namvibe account not found. Create them first.")
        return

    moon_id = moon["id"]
    namvibe_id = namvibe["id"]

    print(f"\nmoon: {moon_id}")
    print(f"namvibe: {namvibe_id}")

    # Clean up any existing friendship so tests start from clean state
    write_query("DELETE FROM chain_friends WHERE (profile_id_1 = %s AND profile_id_2 = %s) OR (profile_id_1 = %s AND profile_id_2 = %s)", [moon_id, namvibe_id, namvibe_id, moon_id])

    # Test 1: Non-friends cannot pass friendship guard
    print("\n[Test 1] Non-friends permission checks")
    friends_check = are_friends(moon_id, namvibe_id)

    _, allowed = require_friendship_or_403(moon_id, namvibe_id, "message")
    check("non_friends_message_blocked", not allowed, "Non-friends cannot message")

    _, allowed = require_friendship_or_403(moon_id, namvibe_id, "call")
    check("non_friends_call_blocked", not allowed, "Non-friends cannot call")

    _, allowed = require_friendship_or_403(moon_id, namvibe_id, "video_call")
    check("non_friends_video_blocked", not allowed, "Non-friends cannot video call")

    _, allowed = require_friendship_or_403(moon_id, namvibe_id, "send_funds")
    check("non_friends_funds_blocked", not allowed, "Non-friends cannot send funds")

    _, allowed = require_friendship_or_403(moon_id, namvibe_id, "send_gift")
    check("non_friends_gift_blocked", not allowed, "Non-friends cannot send gifts")

    # Test 2: Self check
    print("\n[Test 2] Self permission checks")
    _, allowed = require_friendship_or_403(moon_id, moon_id, "message")
    check("self_message", allowed, "Self can message (no friend check needed)")

    # Make them friends so Test 3 can verify friend path
    print("\n[Setup] Making moon and namvibe friends for friend checks...")
    write_query(
        "INSERT INTO chain_friends (profile_id_1, profile_id_2, status) VALUES (%s, %s, 'friend') ON CONFLICT DO NOTHING",
        [moon_id, namvibe_id]
    )
    check("friends_setup_success", are_friends(moon_id, namvibe_id), "moon and namvibe are now friends")

    # Test 3: If they are friends, should pass
    print("\n[Test 3] Friend permission checks (if friends)")
    if are_friends(moon_id, namvibe_id):
        _, allowed = require_friendship_or_403(moon_id, namvibe_id, "message")
        check("friends_message_allowed", allowed, "Friends can message")

        _, allowed = require_friendship_or_403(moon_id, namvibe_id, "call")
        check("friends_call_allowed", allowed, "Friends can call")

        _, allowed = require_friendship_or_403(moon_id, namvibe_id, "video_call")
        check("friends_video_allowed", allowed, "Friends can video call")

        _, allowed = require_friendship_or_403(moon_id, namvibe_id, "send_funds")
        check("friends_funds_allowed", allowed, "Friends can send funds")

        _, allowed = require_friendship_or_403(moon_id, namvibe_id, "send_gift")
        check("friends_gift_allowed", allowed, "Friends can send gifts")
    else:
        print("  SKIP - moon and namvibe are not friends. Run test_friendship_flow.py first.")

    # Test 4: Check random non-friend user
    print("\n[Test 4] Random non-friend checks")
    stranger = get_other_non_friend(moon_id)
    if stranger:
        stranger_id = stranger["id"]
        if not are_friends(moon_id, stranger_id):
            _, allowed = require_friendship_or_403(moon_id, stranger_id, "message")
            check("stranger_message_blocked", not allowed, f"Stranger {stranger['username']} cannot message")

            _, allowed = require_friendship_or_403(moon_id, stranger_id, "call")
            check("stranger_call_blocked", not allowed, f"Stranger {stranger['username']} cannot call")
        else:
            print(f"  SKIP - {stranger['username']} is already friends with moon, skipping stranger test")
    else:
        print("  SKIP - No other non-friend profile found")

    # Test 5: Edge cases
    print("\n[Test 5] Edge cases")
    _, allowed = require_friendship_or_403(None, namvibe_id, "message")
    check("null_current_id", not allowed, "Null current_id should not be allowed")

    _, allowed = require_friendship_or_403(moon_id, None, "message")
    check("null_other_id", not allowed, "Null other_id should not be allowed")

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
