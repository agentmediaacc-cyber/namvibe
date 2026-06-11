from services.profile_service import get_current_profile, get_public_profiles
from engines.matching_engine import calculate_profile_score
from utils.supabase_client import get_supabase_admin
from services.notification_service import create_notification
from services.homepage_real_data_guard import is_test_profile


def get_discover_profiles(limit=24):
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return [], None

    try:
        passed = supabase.table("chain_profile_passes").select("target_profile_id").eq("actor_profile_id", current["id"]).execute().data or []
        liked = supabase.table("chain_profile_likes").select("profile_id").eq("liker_key", current["id"]).execute().data or []
        super_liked = supabase.table("chain_super_likes").select("target_profile_id").eq("actor_profile_id", current["id"]).execute().data or []

        excluded = {current["id"]}
        excluded.update([x["target_profile_id"] for x in passed])
        excluded.update([x["profile_id"] for x in liked])
        excluded.update([x["target_profile_id"] for x in super_liked])

        res = (
            supabase.table("chain_profiles")
            .select("*")
            .eq("is_public", True)
            .order("created_at", desc=True)
            .limit(80)
            .execute()
        )

        profiles = []
        for p in res.data or []:
            if is_test_profile(p):
                continue
            if p["id"] not in excluded:
                p["match_score"] = calculate_profile_score(current, p)
                profiles.append(p)

        profiles.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return profiles[:limit], current

    except Exception as exc:
        print("[MATCHING] discover failed:", exc)
        return [], current


def calculate_match_score(a, b):
    score = 45

    if a.get("country_origin") and b.get("country_origin") and a.get("country_origin") == b.get("country_origin"):
        score += 10

    if a.get("current_location") and b.get("current_location") and a.get("current_location") == b.get("current_location"):
        score += 15

    if a.get("relationship_goal") and b.get("relationship_goal") and a.get("relationship_goal") == b.get("relationship_goal"):
        score += 15

    a_interests = set(a.get("interests") or [])
    b_interests = set(b.get("interests") or [])
    shared = a_interests.intersection(b_interests)
    score += min(len(shared) * 5, 20)

    if b.get("is_verified"):
        score += 5

    return min(score, 99)


def _notify(profile_id, title, message, target_url):
    supabase = get_supabase_admin()
    try:
        supabase.table("chain_notifications").insert({
            "profile_id": profile_id,
            "title": title,
            "message": message,
            "target_url": target_url,
            "notification_type": "general",
            "notification_type": "general",
        }).execute()
    except Exception as exc:
        print("[MATCHING] notification failed:", exc)


def like_target(target_id):
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return False, "Create your profile first."

    if current["id"] == target_id:
        return False, "You cannot like your own profile."

    try:
        supabase.table("chain_profile_likes").insert({
            "profile_id": target_id,
            "liker_key": current["id"],
        }).execute()
    except Exception:
        pass

    reverse_like = (
        supabase.table("chain_profile_likes")
        .select("id")
        .eq("profile_id", current["id"])
        .eq("liker_key", target_id)
        .limit(1)
        .execute()
        .data
    )

    if reverse_like:
        existing = (
            supabase.table("chain_matches")
            .select("id")
            .or_(f"and(profile_one_id.eq.{current['id']},profile_two_id.eq.{target_id}),and(profile_one_id.eq.{target_id},profile_two_id.eq.{current['id']})")
            .limit(1)
            .execute()
            .data
        )

        if not existing:
            supabase.table("chain_matches").insert({
                "profile_one_id": current["id"],
                "profile_two_id": target_id,
                "match_reason": "Mutual like",
            }).execute()

            create_notification(current["id"], "💘 New Match", "You matched with someone on Chain.", "match", "/matching/matches")
            create_notification(target_id, "💘 New Match", "You matched with someone on Chain.", "match", "/matching/matches")

        return True, "match"

    create_notification(target_id, "💘 New Like", f"{current.get('full_name')} liked your profile.", "like", "/matching/likes")
    return True, "liked"


def pass_target(target_id):
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return False

    try:
        supabase.table("chain_profile_passes").insert({
            "actor_profile_id": current["id"],
            "target_profile_id": target_id,
        }).execute()
    except Exception:
        pass

    return True


def super_like_target(target_id):
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return False, "Create your profile first."

    try:
        supabase.table("chain_super_likes").insert({
            "actor_profile_id": current["id"],
            "target_profile_id": target_id,
        }).execute()
    except Exception:
        pass

    create_notification(target_id, "⭐ Super Like", f"{current.get('full_name')} sent you a Super Like.", "like", "/matching/likes")
    return True, "super_liked"


def get_matches():
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return [], None

    try:
        matches = (
            supabase.table("chain_matches")
            .select("*")
            .or_(f"profile_one_id.eq.{current['id']},profile_two_id.eq.{current['id']}")
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

        other_ids = []
        for m in matches:
            other_ids.append(m["profile_two_id"] if m["profile_one_id"] == current["id"] else m["profile_one_id"])

        if not other_ids:
            return [], current

        profiles = (
            supabase.table("chain_profiles")
            .select("*")
            .in_("id", other_ids)
            .execute()
            .data or []
        )

        return profiles, current

    except Exception as exc:
        print("[MATCHING] matches failed:", exc)
        return [], current


def get_liked_me():
    supabase = get_supabase_admin()
    current = get_current_profile()

    if not current:
        return [], None

    try:
        likes = (
            supabase.table("chain_profile_likes")
            .select("liker_key")
            .eq("profile_id", current["id"])
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

        ids = [x["liker_key"] for x in likes if x.get("liker_key")]

        if not ids:
            return [], current

        profiles = (
            supabase.table("chain_profiles")
            .select("*")
            .in_("id", ids)
            .execute()
            .data or []
        )

        return profiles, current

    except Exception as exc:
        print("[MATCHING] liked me failed:", exc)
        return [], current
