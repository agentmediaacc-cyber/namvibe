"""Relationship Privacy Service — granular privacy rules engine.

Provides Instagram/Facebook-style privacy enforcement with separate controls
for profile, posts, reels, stories, followers, following, friend requests,
following, and messaging.
"""

from services.neon_service import fast_query
from services.friend_service import are_friends
from services.privacy_service import is_blocked

ALLOWED_VISIBILITY = {"public", "friends_only", "followers_only", "private"}
ALLOWED_INTERACTION = {"everyone", "friends", "followers", "no_one"}


def normalize_visibility(value, default="public"):
    if not value:
        return default
    v = str(value).lower().strip()
    return v if v in ALLOWED_VISIBILITY else default


def normalize_interaction(value, default="everyone"):
    if not value:
        return default
    v = str(value).lower().strip()
    return v if v in ALLOWED_INTERACTION else default


def is_friend(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    return are_friends(viewer_id, owner_id)


def is_follower(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    rows = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
        [viewer_id, owner_id], timeout_ms=1500, default=[]
    )
    return bool(rows)


def is_following(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    rows = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
        [owner_id, viewer_id], timeout_ms=1500, default=[]
    )
    return bool(rows)


def is_blocked_any(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    if is_blocked(viewer_id, owner_id):
        return True
    if is_blocked(owner_id, viewer_id):
        return True
    return False


def get_relationship(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return "none"
    if str(viewer_id) == str(owner_id):
        return "self"
    if is_blocked_any(viewer_id, owner_id):
        return "blocked"
    if are_friends(viewer_id, owner_id):
        return "friend"
    viewer_follows = is_follower(viewer_id, owner_id)
    owner_follows = is_following(viewer_id, owner_id)
    if viewer_follows and owner_follows:
        return "mutual_follow"
    if viewer_follows:
        return "follower"
    if owner_follows:
        return "following"
    return "none"


def _is_self(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    return str(viewer_id) == str(owner_id)


def is_approved_follower(viewer_id, owner_id):
    """Alias for is_follower since chain_follows now only contains approved follows."""
    return is_follower(viewer_id, owner_id)


def has_pending_follow_request(viewer_id, owner_id):
    if not viewer_id or not owner_id:
        return False
    rows = fast_query(
        "SELECT 1 FROM chain_follow_requests WHERE requester_profile_id = %s AND target_profile_id = %s AND status = 'pending' LIMIT 1",
        [viewer_id, owner_id], timeout_ms=1000, default=[]
    )
    return bool(rows)


def can_view_by_rule(viewer_id, owner_id, rule):
    if not owner_id:
        return False
    rule = normalize_visibility(rule)
    if not viewer_id:
        return rule == "public"
    if is_blocked_any(viewer_id, owner_id):
        return False
    if _is_self(viewer_id, owner_id):
        return True
    if rule == "public":
        return True
    if rule == "friends_only":
        return are_friends(viewer_id, owner_id)
    if rule == "followers_only" or rule == "private":
        return are_friends(viewer_id, owner_id) or is_approved_follower(viewer_id, owner_id)
    return True


def _profile_value(profile, key, default=None):
    if not profile:
        return default
    val = profile.get(key)
    if val is None and key == "profile_visibility":
        val = profile.get("visibility")
    if val is None:
        val = profile.get(key.replace("who_can_", "who_can_"), default)
    return val if val is not None else default


def can_view_profile(viewer_id, profile):
    if not profile:
        return False
    owner_id = profile.get("id")
    if not owner_id:
        return False
    if is_blocked_any(viewer_id, owner_id):
        return False
    if _is_self(viewer_id, owner_id):
        return True
    rule = normalize_visibility(_profile_value(profile, "profile_visibility", "public"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_view_posts(viewer_id, profile):
    if not profile:
        return False
    if not can_view_profile(viewer_id, profile):
        return False
    owner_id = profile.get("id")
    rule = normalize_visibility(_profile_value(profile, "who_can_see_posts", "public"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_view_reels(viewer_id, profile):
    if not profile:
        return False
    if not can_view_profile(viewer_id, profile):
        return False
    owner_id = profile.get("id")
    rule = normalize_visibility(_profile_value(profile, "who_can_see_reels", "public"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_view_stories(viewer_id, profile):
    if not profile:
        return False
    if not can_view_profile(viewer_id, profile):
        return False
    owner_id = profile.get("id")
    rule = normalize_visibility(_profile_value(profile, "who_can_see_stories", "friends_only"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_view_followers(viewer_id, profile):
    if not profile:
        return False
    if not can_view_profile(viewer_id, profile):
        return False
    owner_id = profile.get("id")
    rule = normalize_visibility(_profile_value(profile, "who_can_see_followers", "public"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_view_following(viewer_id, profile):
    if not profile:
        return False
    if not can_view_profile(viewer_id, profile):
        return False
    owner_id = profile.get("id")
    rule = normalize_visibility(_profile_value(profile, "who_can_see_following", "public"))
    return can_view_by_rule(viewer_id, owner_id, rule)


def can_send_friend_request(viewer_id, profile):
    if not viewer_id or not profile:
        return False
    owner_id = profile.get("id")
    if not owner_id:
        return False
    if _is_self(viewer_id, owner_id):
        return False
    if is_blocked_any(viewer_id, owner_id):
        return False
    rule = normalize_interaction(_profile_value(profile, "who_can_send_friend_requests", "everyone"))
    if rule == "no_one":
        return False
    if rule == "friends":
        return are_friends(viewer_id, owner_id)
    if rule == "followers":
        return is_follower(viewer_id, owner_id)
    return True


def can_follow(viewer_id, profile):
    if not viewer_id or not profile:
        return False
    owner_id = profile.get("id")
    if not owner_id:
        return False
    if _is_self(viewer_id, owner_id):
        return False
    if is_blocked_any(viewer_id, owner_id):
        return False
    rule = normalize_interaction(_profile_value(profile, "who_can_follow_me", "everyone"))
    if rule == "no_one":
        return False
    if rule == "friends":
        return are_friends(viewer_id, owner_id)
    if rule == "followers":
        return is_follower(viewer_id, owner_id)
    return True


def can_message(viewer_id, profile):
    if not viewer_id or not profile:
        return False
    owner_id = profile.get("id")
    if not owner_id:
        return False
    if _is_self(viewer_id, owner_id):
        return False
    if is_blocked_any(viewer_id, owner_id):
        return False
    rule = normalize_interaction(_profile_value(profile, "who_can_message_me", "friends"))
    if rule == "no_one":
        return False
    if rule == "friends":
        return are_friends(viewer_id, owner_id)
    if rule == "followers":
        return is_follower(viewer_id, owner_id)
    return True


def get_reason(result_dict, key, relationship):
    if result_dict.get(key):
        return f"{key}_allowed"
    return f"{key}_denied_{relationship}"


def get_full_policy(viewer_id, profile):
    if not profile:
        return None
    owner_id = profile.get("id")
    relationship = get_relationship(viewer_id, owner_id) if viewer_id and owner_id else "none"
    profile_visibility = normalize_visibility(_profile_value(profile, "profile_visibility", "public"))

    cvp = can_view_profile(viewer_id, profile)
    cvpo = can_view_posts(viewer_id, profile)
    cvr = can_view_reels(viewer_id, profile)
    cvs = can_view_stories(viewer_id, profile)
    cvf = can_view_followers(viewer_id, profile)
    cvfw = can_view_following(viewer_id, profile)
    csfr = can_send_friend_request(viewer_id, profile)
    cf = can_follow(viewer_id, profile)
    cm = can_message(viewer_id, profile)

    return {
        "relationship": relationship,
        "profile_visibility": profile_visibility,
        "can_view_profile": cvp,
        "can_view_posts": cvpo,
        "can_view_reels": cvr,
        "can_view_stories": cvs,
        "can_view_followers": cvf,
        "can_view_following": cvfw,
        "can_send_friend_request": csfr,
        "can_follow": cf,
        "can_message": cm,
        "reason": get_reason(locals(), "can_view_profile", relationship),
    }
