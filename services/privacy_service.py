from services.supabase_safe import safe_select, safe_update

def can_view_profile(viewer_profile_id, target_profile_id):
    if not target_profile_id:
        return False
    if not viewer_profile_id:
        return False
    if viewer_profile_id == target_profile_id:
        return True
    row = safe_select("chain_profiles", columns="account_privacy, blocked_profile_ids", filters={"id": target_profile_id}, limit=1)
    if not row:
        return True
    privacy = (row[0] or {}).get("account_privacy") or "public"
    if privacy == "public":
        blocked = (row[0] or {}).get("blocked_profile_ids") or []
        return str(viewer_profile_id) not in [str(b) for b in (blocked if isinstance(blocked, list) else [])]
    if privacy == "private":
        follows = safe_select("chain_follows", filters={"follower_profile_id": viewer_profile_id, "following_profile_id": target_profile_id}, limit=1)
        if follows:
            return True
        return False
    return True

def is_blocked(profile_id, target_profile_id):
    if not profile_id or not target_profile_id:
        return False
    row = safe_select("chain_profiles", columns="blocked_profile_ids", filters={"id": target_profile_id}, limit=1)
    if not row:
        return False
    blocked = (row[0] or {}).get("blocked_profile_ids") or []
    return str(profile_id) in [str(b) for b in (blocked if isinstance(blocked, list) else [])]

def can_send_message(sender_profile_id, recipient_profile_id):
    if not sender_profile_id or not recipient_profile_id:
        return False
    if sender_profile_id == recipient_profile_id:
        return False
    if is_blocked(sender_profile_id, recipient_profile_id):
        return False
    return True

def filter_private_content(items, viewer_profile_id, content_key="profile_id"):
    if not viewer_profile_id:
        return [i for i in (items or []) if i.get("visibility") in (None, "public")]
    filtered = []
    for item in (items or []):
        owner_id = item.get(content_key)
        if not owner_id:
            filtered.append(item)
            continue
        if str(owner_id) == str(viewer_profile_id):
            filtered.append(item)
            continue
        if item.get("visibility") in (None, "public"):
            if not is_blocked(viewer_profile_id, owner_id):
                filtered.append(item)
            continue
        if item.get("visibility") == "followers":
            follows = safe_select("chain_follows", filters={"follower_profile_id": viewer_profile_id, "following_profile_id": owner_id}, limit=1)
            if follows:
                filtered.append(item)
            continue
    return filtered
