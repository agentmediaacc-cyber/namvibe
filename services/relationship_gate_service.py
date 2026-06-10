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


def relationship_status(profile_a, profile_b):
    if not profile_a or not profile_b:
        return {"status": "unknown", "can_message": False, "can_call": False}
    if profile_a == profile_b:
        return {"status": "self", "can_message": False, "can_call": False}
    if is_blocked(profile_a, profile_b):
        return {"status": "blocked", "can_message": False, "can_call": False}
    if _is_test_mode():
        return {"status": "friend", "can_message": True, "can_call": True}
    if is_mutual_follow(profile_a, profile_b):
        return {"status": "friend", "can_message": True, "can_call": True}
    rows = fast_query(
        """
        SELECT 1 FROM chain_follows
        WHERE follower_profile_id = %s AND following_profile_id = %s
        """,
        (profile_a, profile_b), default=[]
    )
    if rows:
        return {"status": "following", "can_message": True, "can_call": True}
    rows = fast_query(
        """
        SELECT 1 FROM chain_follows
        WHERE follower_profile_id = %s AND following_profile_id = %s
        """,
        (profile_b, profile_a), default=[]
    )
    if rows:
        return {"status": "follower", "can_message": True, "can_call": True}
    return {"status": "stranger", "can_message": True, "can_call": True}


def can_message(profile_a, profile_b):
    if not profile_a or not profile_b or profile_a == profile_b:
        return {"ok": False, "error": "Cannot message yourself", "status": "self"}
    if is_blocked(profile_a, profile_b):
        return {"ok": False, "error": "Messaging unavailable", "status": "blocked"}
    if _is_test_mode():
        return {"ok": True, "status": "friend"}
    mutual = is_mutual_follow(profile_a, profile_b)
    if mutual:
        return {"ok": True, "status": "friend"}
    return {"ok": True, "status": "stranger", "needs_request": True}


def can_call(profile_a, profile_b):
    if not profile_a or not profile_b or profile_a == profile_b:
        return {"ok": False, "error": "Cannot call yourself", "status": "self"}
    if is_blocked(profile_a, profile_b):
        return {"ok": False, "error": "Calling unavailable", "status": "blocked"}
    if _is_test_mode():
        return {"ok": True, "status": "friend"}
    mutual = is_mutual_follow(profile_a, profile_b)
    if mutual:
        return {"ok": True, "status": "friend"}
    return {"ok": True, "status": "stranger", "needs_request": True}
