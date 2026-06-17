"""Social action policy engine — determines allowed actions between profiles."""

from services.friend_service import are_friends
from services.neon_service import fast_query
from services.privacy_service import is_blocked
from services.relationship_privacy_service import (
    can_view_profile as rp_can_view_profile,
    can_follow as rp_can_follow,
    can_send_friend_request as rp_can_send_friend_request,
    can_message as rp_can_message,
    get_full_policy,
)


def get_account_kind(profile_row):
    if not profile_row:
        return "unknown"
    account_type = (profile_row.get("account_type") or "").lower()
    profile_type = (profile_row.get("profile_type") or "").lower()
    is_page = bool(profile_row.get("is_page"))
    is_creator = bool(profile_row.get("is_creator")) or profile_type in ("creator", "host")
    is_premium = bool(profile_row.get("is_premium"))
    is_business = account_type == "business" or profile_type == "seller"
    is_verified = bool(profile_row.get("is_verified")) or bool(profile_row.get("verified"))

    if is_page:
        return "page"
    if is_business:
        return "business"
    if is_creator:
        return "creator"
    if is_premium:
        return "premium"
    if is_verified:
        return "government"
    if profile_type == "member" or account_type == "personal":
        return "person"
    return "person"


def is_page_like_account(profile_row):
    kind = get_account_kind(profile_row)
    return kind in ("page", "business", "creator", "premium", "government")


def is_person_account(profile_row):
    return get_account_kind(profile_row) == "person"


def is_self(current_profile_id, target_profile_id):
    if not current_profile_id or not target_profile_id:
        return False
    return str(current_profile_id) == str(target_profile_id)


def can_send_friend_request(current_profile_id, target_profile):
    if not current_profile_id or not target_profile:
        return False
    target_id = target_profile.get("id")
    if not target_id:
        return False
    if is_self(current_profile_id, target_id):
        return False
    if is_page_like_account(target_profile):
        return False
    if are_friends(current_profile_id, target_id):
        return False
    existing = fast_query(
        """SELECT 1 FROM chain_friend_requests
           WHERE ((sender_profile_id = %s AND recipient_profile_id = %s)
              OR (sender_profile_id = %s AND recipient_profile_id = %s))
             AND status = 'pending'""",
        [current_profile_id, target_id, target_id, current_profile_id],
    )
    if existing:
        return False
    if not rp_can_send_friend_request(current_profile_id, target_profile):
        return False
    return True


def can_follow(current_profile_id, target_profile):
    if not current_profile_id or not target_profile:
        return False
    target_id = target_profile.get("id")
    if not target_id:
        return False
    if is_self(current_profile_id, target_id):
        return False
    if not rp_can_follow(current_profile_id, target_profile):
        return False
    return True


def can_chat(current_profile_id, target_profile_id, target_profile=None):
    if not current_profile_id or not target_profile_id:
        return False
    if is_self(current_profile_id, target_profile_id):
        return False
    if is_blocked(current_profile_id, target_profile_id):
        return False
    if is_blocked(target_profile_id, current_profile_id):
        return False
    if target_profile:
        if not rp_can_message(current_profile_id, target_profile):
            return False
    return are_friends(current_profile_id, target_profile_id)


def can_like_post(current_profile_id, post):
    if not current_profile_id or not post:
        return False
    owner_id = post.get("profile_id") or post.get("owner_id")
    if not owner_id:
        return False
    if is_self(current_profile_id, owner_id):
        return False
    if is_blocked(current_profile_id, owner_id):
        return False
    if is_blocked(owner_id, current_profile_id):
        return False
    return True


def can_view_profile(current_profile_id, target_profile, viewer_profile=None):
    target_id = target_profile.get("id") if target_profile else None
    if not target_id:
        return {"can_view_full_profile": False, "reason": "no_target_profile"}

    viewer_id = current_profile_id

    if viewer_id and is_self(viewer_id, target_id):
        return {"can_view_full_profile": True, "reason": "self"}

    if viewer_id and is_blocked(viewer_id, target_id):
        return {"can_view_full_profile": False, "reason": "blocked"}
    if viewer_id and is_blocked(target_id, viewer_id):
        return {"can_view_full_profile": False, "reason": "blocked_by_target"}

    if not viewer_id:
        visibility = target_profile.get("profile_visibility") or target_profile.get("visibility") or "public"
        if str(visibility).lower() == "public":
            return {"can_view_full_profile": True, "reason": "public"}
        return {"can_view_full_profile": False, "reason": "not_logged_in"}

    allowed = rp_can_view_profile(viewer_id, target_profile)
    if allowed:
        return {"can_view_full_profile": True, "reason": "privacy_allowed"}
    return {"can_view_full_profile": False, "reason": "privacy_restricted"}


def get_relationship(current_profile_id, target_profile_id):
    if not current_profile_id or not target_profile_id:
        return "none"
    if is_self(current_profile_id, target_profile_id):
        return "self"

    if is_blocked(current_profile_id, target_profile_id):
        return "blocked"
    if is_blocked(target_profile_id, current_profile_id):
        return "blocked"

    if are_friends(current_profile_id, target_profile_id):
        return "friend"

    sent = fast_query(
        "SELECT 1 FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending'",
        [current_profile_id, target_profile_id],
    )
    if sent:
        return "pending_sent"

    received = fast_query(
        "SELECT 1 FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending'",
        [target_profile_id, current_profile_id],
    )
    if received:
        return "pending_received"

    follows = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
        [current_profile_id, target_profile_id],
    )
    if follows:
        return "following"

    return "none"


def get_primary_action(current_profile_id, target_profile):
    if not current_profile_id or not target_profile:
        return "none"
    target_id = target_profile.get("id")
    if not target_id:
        return "none"

    if is_self(current_profile_id, target_id):
        return "none"

    relationship = get_relationship(current_profile_id, target_id)

    if relationship == "blocked":
        return "none"
    if relationship == "friend":
        return "message"

    if relationship == "pending_sent":
        return "request_sent"
    if relationship == "pending_received":
        return "accept_request"

    if is_page_like_account(target_profile):
        can_follow_val = can_follow(current_profile_id, target_profile)
        if can_follow_val:
            return "follow"
        return "none"
    can_fr = can_send_friend_request(current_profile_id, target_profile)
    if can_fr:
        return "friend_request"
    is_following_rows = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
        [current_profile_id, target_id],
    )
    if is_following_rows:
        return "following"
    return "none"


def get_action_policy(current_profile_id, target_profile):
    target_id = target_profile.get("id") if target_profile else None
    if not target_id:
        return {
            "is_self": False,
            "account_kind": "unknown",
            "can_view_full_profile": False,
            "can_follow": False,
            "can_send_friend_request": False,
            "can_chat": False,
            "can_like": False,
            "relationship": "none",
            "primary_action": "none",
            "reason": "no_target_profile",
        }

    self_check = is_self(current_profile_id, target_id)
    kind = get_account_kind(target_profile)
    full = get_full_policy(current_profile_id, target_profile) or {}
    relationship = get_relationship(current_profile_id, target_id)

    return {
        "is_self": self_check,
        "account_kind": kind,
        "can_view_full_profile": full.get("can_view_profile", False),
        "can_follow": full.get("can_follow", False),
        "can_send_friend_request": full.get("can_send_friend_request", False),
        "can_chat": full.get("can_message", False),
        "can_like": not self_check,
        "relationship": relationship,
        "primary_action": get_primary_action(current_profile_id, target_profile),
        "reason": full.get("reason", "unknown"),
    }
