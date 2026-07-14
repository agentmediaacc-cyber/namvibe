"""Social action policy engine — determines allowed actions between profiles."""

from services.neon_service import fast_query
from services.blocking_service import is_blocked_any
from services.friendship_service import are_friends
from services.relationship_cache_service import get_relationship_state
from services.relationship_privacy_service import (
    can_view_profile as rp_can_view_profile,
    can_view_posts as rp_can_view_posts,
    can_view_reels as rp_can_view_reels,
    can_view_followers as rp_can_view_followers,
    can_view_following as rp_can_view_following,
    can_follow as rp_can_follow,
    can_send_friend_request as rp_can_send_friend_request,
    can_message as rp_can_message,
    get_full_policy,
)
from services.follow_request_service import is_private_follow_required


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
    state = get_relationship_state(current_profile_id, target_id)
    if state.get("is_friend"):
        return False
    if state.get("friend_request_sent") or state.get("friend_request_received"):
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
    if is_blocked_any(current_profile_id, target_profile_id):
        return False
    # Friends can always chat
    if are_friends(current_profile_id, target_profile_id):
        return True
    # Non-friends: check if target allows public messages
    if target_profile:
        who = target_profile.get("who_can_message", "everyone")
        return who == "everyone"
    return False


def can_like_post(current_profile_id, post):
    if not current_profile_id or not post:
        return False
    owner_id = post.get("profile_id") or post.get("owner_id")
    if not owner_id:
        return False
    if is_self(current_profile_id, owner_id):
        return False
    if is_blocked_any(current_profile_id, owner_id):
        return False
    return True


def can_view_profile(current_profile_id, target_profile, viewer_profile=None):
    target_id = target_profile.get("id") if target_profile else None
    if not target_id:
        return {"can_view_full_profile": False, "reason": "no_target_profile"}

    viewer_id = current_profile_id

    if viewer_id and is_self(viewer_id, target_id):
        return {"can_view_full_profile": True, "reason": "self"}

    if viewer_id and is_blocked_any(viewer_id, target_id):
        return {"can_view_full_profile": False, "reason": "blocked"}

    if not viewer_id:
        visibility = target_profile.get("profile_visibility") or target_profile.get("visibility") or "public"
        if str(visibility).lower() == "public":
            return {"can_view_full_profile": True, "reason": "public"}
        return {"can_view_full_profile": False, "reason": "not_logged_in"}

    allowed = rp_can_view_profile(viewer_id, target_profile)
    if allowed:
        return {"can_view_full_profile": True, "reason": "privacy_allowed"}
    return {"can_view_full_profile": False, "reason": "privacy_restricted"}


def get_relationship(current_profile_id, target_id):
    if not current_profile_id or not target_id:
        return "none"
    if is_self(current_profile_id, target_id):
        return "self"
    state = get_relationship_state(current_profile_id, target_id)
    return state.get("relationship", "none")


def get_primary_action(current_profile_id, target_profile):
    if not current_profile_id or not target_profile:
        return "none"
    target_id = target_profile.get("id")
    if not target_id:
        return "none"

    if is_self(current_profile_id, target_id):
        return "self"

    state = get_relationship_state(current_profile_id, target_id)
    relationship = state.get("relationship", "none")
    if relationship == "blocked":
        return "none"
    if relationship == "friend":
        return "message"
    if relationship == "pending_sent":
        return "request_sent"
    if relationship == "pending_received":
        return "accept_request"

    if state.get("is_following"):
        return "following"
    if state.get("follow_request_sent"):
        return "requested"
    if state.get("follow_request_received"):
        return "approve_follow"

    if is_page_like_account(target_profile):
        if can_follow(current_profile_id, target_profile):
            if is_private_follow_required(current_profile_id, target_profile):
                return "request_follow"
            return "follow"
        return "none"

    # Non-friends: if target allows public messages, primary action is "message"
    who_msg = target_profile.get("who_can_message", "everyone")
    if who_msg == "everyone" and can_chat(current_profile_id, target_id, target_profile=target_profile):
        return "message"

    if can_send_friend_request(current_profile_id, target_profile):
        return "friend_request"

    if can_follow(current_profile_id, target_profile):
        if is_private_follow_required(current_profile_id, target_profile):
            return "request_follow"
        return "follow"

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
            "can_call": False,
            "can_message_self": False,
            "can_call_self": False,
            "can_like": False,
            "can_view_posts": False,
            "can_view_reels": False,
            "can_view_media": False,
            "can_view_followers": False,
            "can_view_following": False,
            "can_view_friends": False,
            "relationship": "none",
            "follow_status": "none",
            "requires_follow_approval": False,
            "primary_action": "none",
            "reason": "no_target_profile",
        }

    self_check = is_self(current_profile_id, target_id)
    kind = get_account_kind(target_profile)

    if self_check:
        return {
            "is_self": True,
            "account_kind": kind,
            "can_view_full_profile": True,
            "can_follow": False,
            "can_send_friend_request": False,
            "can_chat": False,
            "can_call": False,
            "can_message_self": False,
            "can_call_self": False,
            "can_like": False,
            "can_view_posts": True,
            "can_view_reels": True,
            "can_view_media": True,
            "can_view_followers": True,
            "can_view_following": True,
            "can_view_friends": True,
            "relationship": "self",
            "follow_status": "self",
            "requires_follow_approval": False,
            "primary_action": "self",
            "reason": "self",
        }

    full = get_full_policy(current_profile_id, target_profile) or {}
    state = get_relationship_state(current_profile_id, target_id)
    relationship = state.get("relationship", "none")
    follow_status = "following" if state.get("is_following") else ("request_pending" if state.get("follow_request_sent") else ("request_received" if state.get("follow_request_received") else "none"))
    chat_allowed = can_chat(current_profile_id, target_id, target_profile=target_profile)
    can_view_posts = full.get("can_view_posts")
    if can_view_posts is None:
        can_view_posts = rp_can_view_posts(current_profile_id, target_profile)
    can_view_reels = full.get("can_view_reels")
    if can_view_reels is None:
        can_view_reels = rp_can_view_reels(current_profile_id, target_profile)
    can_view_followers = full.get("can_view_followers")
    if can_view_followers is None:
        can_view_followers = rp_can_view_followers(current_profile_id, target_profile)
    can_view_following = full.get("can_view_following")
    if can_view_following is None:
        can_view_following = rp_can_view_following(current_profile_id, target_profile)

    return {
        "is_self": self_check,
        "account_kind": kind,
        "can_view_full_profile": can_view_profile(current_profile_id, target_profile).get("can_view_full_profile", False),
        "can_follow": can_follow(current_profile_id, target_profile),
        "can_send_friend_request": can_send_friend_request(current_profile_id, target_profile),
        "can_chat": chat_allowed,
        "can_call": are_friends(current_profile_id, target_id),
        "can_message_self": False,
        "can_call_self": False,
        "can_like": not self_check,
        "can_view_posts": bool(can_view_posts),
        "can_view_reels": bool(can_view_reels),
        "can_view_media": bool(can_view_posts or can_view_reels),
        "can_view_followers": bool(can_view_followers),
        "can_view_following": bool(can_view_following),
        "can_view_friends": relationship == "friend" or bool(can_view_followers),
        "relationship": relationship,
        "follow_status": follow_status,
        "requires_follow_approval": is_private_follow_required(current_profile_id, target_profile),
        "primary_action": get_primary_action(current_profile_id, target_profile),
        "reason": full.get("reason", "unknown"),
    }
