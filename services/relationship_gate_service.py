import os

from services.neon_service import fast_query


def _is_test_mode():
    return os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1"


def is_mutual_follow(profile_a, profile_b):
    if not profile_a or not profile_b:
        return False
    rows = fast_query(
        """
        SELECT 1 FROM chain_follows f1
        JOIN chain_follows f2 ON f1.follower_profile_id = f2.following_profile_id
            AND f1.following_profile_id = f2.follower_profile_id
        WHERE f1.follower_profile_id = %s AND f1.following_profile_id = %s
        """,
        (profile_a, profile_b), default=[]
    )
    return bool(rows)


def is_blocked(profile_a, profile_b):
    if not profile_a or not profile_b:
        return False
    rows = fast_query(
        """
        SELECT 1 FROM chain_blocks
        WHERE ((blocker_profile_id = %s AND blocked_profile_id = %s)
           OR (blocker_profile_id = %s AND blocked_profile_id = %s))
        AND deleted_at IS NULL
        """,
        (profile_a, profile_b, profile_b, profile_a), default=[]
    )
    return bool(rows)


def _are_friends(a, b):
    """Check if two users are friends via chain_friends table."""
    if not a or not b:
        return False
    p1, p2 = (a, b) if str(a) < str(b) else (b, a)
    rows = fast_query(
        "SELECT 1 FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s AND status = 'friend' AND deleted_at IS NULL LIMIT 1",
        (p1, p2), default=[]
    )
    return bool(rows)


def _get_who_can_message(profile_id):
    """Get the who_can_message setting for a profile. Returns 'everyone' by default."""
    if not profile_id:
        return "everyone"
    rows = fast_query(
        "SELECT who_can_message FROM chain_profiles WHERE id = %s LIMIT 1",
        (profile_id,), default=[]
    )
    if rows and rows[0].get("who_can_message"):
        return rows[0]["who_can_message"]
    return "everyone"


def relationship_status(profile_a, profile_b):
    if not profile_a or not profile_b:
        return {"status": "unknown", "can_message": False, "can_call": False}
    if profile_a == profile_b:
        return {"status": "self", "can_message": False, "can_call": False}
    if is_blocked(profile_a, profile_b):
        return {"status": "blocked", "can_message": False, "can_call": False}
    if _is_test_mode():
        return {"status": "friend", "can_message": True, "can_call": True}
    if _are_friends(profile_a, profile_b):
        return {"status": "friend", "can_message": True, "can_call": True}
    # Not friends: can call only if friends, can message if recipient allows
    who = _get_who_can_message(profile_b)
    can_msg = who == "everyone"
    return {"status": "stranger", "can_message": can_msg, "can_call": False}


def can_message(profile_a, profile_b):
    """Check if profile_a can message profile_b.

    Rules:
    - Friends: always allowed
    - Non-friends: allowed only if profile_b has who_can_message = 'everyone'
    - Blocked: never allowed
    """
    if not profile_a or not profile_b or profile_a == profile_b:
        return {"ok": False, "error": "Cannot message yourself", "status": "self"}
    if is_blocked(profile_a, profile_b):
        return {"ok": False, "error": "Messaging unavailable", "status": "blocked"}
    if _is_test_mode():
        return {"ok": True, "status": "friend"}
    if _are_friends(profile_a, profile_b):
        return {"ok": True, "status": "friend"}
    # Non-friend: check if recipient allows public messages
    who = _get_who_can_message(profile_b)
    if who == "everyone":
        return {"ok": True, "status": "public", "needs_request": True}
    return {"ok": False, "error": "This user only accepts messages from friends", "status": "friends_only"}


def can_call(profile_a, profile_b):
    """Check if profile_a can call profile_b.

    Rules:
    - Friends: always allowed
    - Non-friends: never allowed (calling requires friendship)
    - Blocked: never allowed
    """
    if not profile_a or not profile_b or profile_a == profile_b:
        return {"ok": False, "error": "Cannot call yourself", "status": "self"}
    if is_blocked(profile_a, profile_b):
        return {"ok": False, "error": "Calling unavailable", "status": "blocked"}
    if _is_test_mode():
        return {"ok": True, "status": "friend"}
    if _are_friends(profile_a, profile_b):
        return {"ok": True, "status": "friend"}
    # Non-friends cannot call
    return {"ok": False, "error": "You must be friends before you can call", "status": "friends_only"}
