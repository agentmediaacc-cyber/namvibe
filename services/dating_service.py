import os, uuid, json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query, get_pool_status
from services.profile_service import get_profile_by_id

RELATIONSHIP_GOALS = ["friendship", "casual", "relationship", "marriage", "open"]
ACTION_TYPES = ["like", "pass", "super_like"]
REPORT_REASONS = ["fake_profile", "harassment", "inappropriate", "spam", "other"]


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


def _run(query, params=None, default=None):
    if not _db_available():
        return default or []
    try:
        return fast_query(query, params or (), default=default or [])
    except Exception:
        return default or []


def _write(query, params=None):
    if not _db_available():
        return {"ok": True}
    try:
        write_query(query, params or ())
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _row_to_dict(row):
    if not row:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _rows_to_list(rows):
    return [_row_to_dict(r) for r in rows]


# ─── DATING PROFILE ──────────────────────────────────────────

def get_dating_profile(profile_id):
    pid = _uuid(profile_id)
    rows = _run("SELECT * FROM chain_dating_profiles WHERE profile_id = %s LIMIT 1", (pid,))
    return _row_to_dict(rows[0]) if rows else None


def get_or_create_dating_profile(profile_id):
    existing = get_dating_profile(profile_id)
    if existing:
        return existing
    pid = _uuid(profile_id)
    did = str(uuid.uuid4())
    _write(
        "INSERT INTO chain_dating_profiles (id, profile_id) VALUES (%s, %s)",
        (did, pid),
    )
    return get_dating_profile(pid)


def update_dating_profile(profile_id, **kwargs):
    pid = _uuid(profile_id)
    allowed = [
        "dating_mode_on", "relationship_goal", "age_range_min", "age_range_max",
        "location_preference", "bio", "interests", "photos", "verification_status",
        "trust_score", "safety_badge", "hide_from_contacts", "visible_to_verified_only",
    ]
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            if isinstance(v, (list, tuple)):
                sets.append(f"{k} = %s")
                vals.append(json.dumps(list(v)))
            elif isinstance(v, bool):
                sets.append(f"{k} = %s")
                vals.append(v)
            else:
                sets.append(f"{k} = %s")
                vals.append(v)
    if not sets:
        return {"ok": False, "error": "no_fields"}
    vals.append(pid)
    sets.append("updated_at = now()")
    _write(f"UPDATE chain_dating_profiles SET {', '.join(sets)} WHERE profile_id = %s", tuple(vals))
    return {"ok": True}


def set_dating_mode(profile_id, on):
    return update_dating_profile(profile_id, dating_mode_on=bool(on))


# ─── DISCOVER ─────────────────────────────────────────────────

def get_discover_profiles(viewer_id, limit=30, offset=0):
    viewer = _uuid(viewer_id)
    blocked = _get_blocked_ids(viewer)
    blocked_by = _get_blocker_ids(viewer)
    excluded = {viewer}
    excluded.update(blocked)
    excluded.update(blocked_by)

    liked_rows = _run(
        "SELECT target_profile_id FROM chain_dating_likes WHERE actor_profile_id = %s",
        (viewer,),
    )
    for r in liked_rows:
        excluded.add(str(r["target_profile_id"]))

    preferences = get_dating_preferences(viewer)
    dating_profile = get_or_create_dating_profile(viewer)
    dating_mode_off = not (dating_profile or {}).get("dating_mode_on", True)

    rows = _run(
        """SELECT dp.*, p.username, p.display_name, p.avatar_url, p.full_name
           FROM chain_dating_profiles dp
           JOIN chain_profiles p ON p.id = dp.profile_id
           WHERE dp.dating_mode_on = true
             AND dp.profile_id != %s
           ORDER BY dp.trust_score DESC, dp.updated_at DESC
           LIMIT %s OFFSET %s""",
        (viewer, limit, offset),
    )

    results = []
    for r in rows:
        pid = str(r["profile_id"])
        if pid in excluded:
            continue
        profile = _row_to_dict(r)
        profile["compatibility_score"] = calculate_compatibility(viewer, pid, dating_profile)
        results.append(profile)
    return _rows_to_list(results) if results else []


# ─── LIKES / PASS / SUPER LIKE ───────────────────────────────

def like_profile(actor_id, target_id):
    return _record_action(actor_id, target_id, "like")


def pass_profile(actor_id, target_id):
    return _record_action(actor_id, target_id, "pass")


def super_like_profile(actor_id, target_id):
    return _record_action(actor_id, target_id, "super_like")


def _record_action(actor_id, target_id, action_type):
    actor = _uuid(actor_id)
    target = _uuid(target_id)
    if actor == target:
        return {"ok": False, "error": "cannot_interact_with_self"}

    existing = _run(
        "SELECT id, action_type FROM chain_dating_likes WHERE actor_profile_id = %s AND target_profile_id = %s LIMIT 1",
        (actor, target),
    )
    if existing:
        return {"ok": False, "error": "already_interacted"}

    lid = str(uuid.uuid4())
    ok = _write(
        "INSERT INTO chain_dating_likes (id, actor_profile_id, target_profile_id, action_type) VALUES (%s, %s, %s, %s)",
        (lid, actor, target, action_type),
    )
    if not ok.get("ok"):
        return ok

    result = {"ok": True, "action": action_type, "is_match": False, "match": None}

    if action_type in ("like", "super_like"):
        reciprocal = _run(
            "SELECT id FROM chain_dating_likes WHERE actor_profile_id = %s AND target_profile_id = %s AND action_type IN ('like', 'super_like') LIMIT 1",
            (target, actor),
        )
        if reciprocal:
            score = calculate_compatibility(actor, target)
            mid = str(uuid.uuid4())
            _write(
                "INSERT INTO chain_dating_matches (id, profile_id_a, profile_id_b, compatibility_score) VALUES (%s, %s, %s, %s)",
                (mid, actor, target, score),
            )
            _write(
                "UPDATE chain_dating_likes SET is_mutual = true WHERE (actor_profile_id = %s AND target_profile_id = %s) OR (actor_profile_id = %s AND target_profile_id = %s)",
                (actor, target, target, actor),
            )
            result["is_match"] = True
            result["match"] = {"id": mid, "compatibility_score": score}

    return result


def undo_last_action(profile_id):
    pid = _uuid(profile_id)
    rows = _run(
        "SELECT id, target_profile_id, action_type FROM chain_dating_likes WHERE actor_profile_id = %s ORDER BY created_at DESC LIMIT 1",
        (pid,),
    )
    if not rows:
        return {"ok": False, "error": "nothing_to_undo"}
    last = rows[0]
    _write("DELETE FROM chain_dating_likes WHERE id = %s", (last["id"],))
    if last["action_type"] in ("like", "super_like"):
        _write(
            "DELETE FROM chain_dating_matches WHERE (profile_id_a = %s AND profile_id_b = %s) OR (profile_id_a = %s AND profile_id_b = %s)",
            (pid, last["target_profile_id"], last["target_profile_id"], pid),
        )
    return {"ok": True, "undone": last["action_type"]}


# ─── MATCHES ──────────────────────────────────────────────────

def get_matches(profile_id, limit=50, offset=0):
    pid = _uuid(profile_id)
    rows = _run(
        """SELECT m.*,
                  CASE WHEN m.profile_id_a = %s THEN p_b.username ELSE p_a.username END AS match_username,
                  CASE WHEN m.profile_id_a = %s THEN p_b.display_name ELSE p_a.display_name END AS match_display_name,
                  CASE WHEN m.profile_id_a = %s THEN p_b.avatar_url ELSE p_a.avatar_url END AS match_avatar_url,
                  CASE WHEN m.profile_id_a = %s THEN p_b.id ELSE p_a.id END AS match_profile_id
           FROM chain_dating_matches m
           LEFT JOIN chain_profiles p_a ON p_a.id = m.profile_id_a
           LEFT JOIN chain_profiles p_b ON p_b.id = m.profile_id_b
           WHERE (m.profile_id_a = %s OR m.profile_id_b = %s)
             AND m.is_active = true
           ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
        (pid, pid, pid, pid, pid, pid, limit, offset),
    )
    return _rows_to_list(rows)


# ─── LIKES YOU ────────────────────────────────────────────────

def get_likes_you(profile_id, limit=30, offset=0):
    pid = _uuid(profile_id)
    rows = _run(
        """SELECT l.*, p.username, p.display_name, p.avatar_url, p.full_name
           FROM chain_dating_likes l
           JOIN chain_profiles p ON p.id = l.actor_profile_id
           WHERE l.target_profile_id = %s
             AND l.action_type IN ('like', 'super_like')
             AND l.is_mutual = false
           ORDER BY l.created_at DESC LIMIT %s OFFSET %s""",
        (pid, limit, offset),
    )
    return _rows_to_list(rows)


# ─── BLOCK / REPORT ──────────────────────────────────────────

def block_user(blocker_id, blocked_id):
    blocker = _uuid(blocker_id)
    blocked = _uuid(blocked_id)
    if blocker == blocked:
        return {"ok": False, "error": "cannot_block_self"}
    existing = _run(
        "SELECT id FROM chain_dating_blocks WHERE blocker_profile_id = %s AND blocked_profile_id = %s LIMIT 1",
        (blocker, blocked),
    )
    if existing:
        return {"ok": False, "error": "already_blocked"}
    bid = str(uuid.uuid4())
    _write(
        "INSERT INTO chain_dating_blocks (id, blocker_profile_id, blocked_profile_id) VALUES (%s, %s, %s)",
        (bid, blocker, blocked),
    )
    _write(
        "DELETE FROM chain_dating_matches WHERE (profile_id_a = %s AND profile_id_b = %s) OR (profile_id_a = %s AND profile_id_b = %s)",
        (blocker, blocked, blocked, blocker),
    )
    _write(
        "DELETE FROM chain_dating_likes WHERE (actor_profile_id = %s AND target_profile_id = %s) OR (actor_profile_id = %s AND target_profile_id = %s)",
        (blocker, blocked, blocked, blocker),
    )
    return {"ok": True}


def report_user(reporter_id, reported_id, reason, details=""):
    reporter = _uuid(reporter_id)
    reported = _uuid(reported_id)
    if reporter == reported:
        return {"ok": False, "error": "cannot_report_self"}
    rid = str(uuid.uuid4())
    _write(
        "INSERT INTO chain_dating_reports (id, reporter_profile_id, reported_profile_id, reason, details) VALUES (%s, %s, %s, %s, %s)",
        (rid, reporter, reported, reason, details),
    )
    return {"ok": True, "report_id": rid}


def _get_blocked_ids(profile_id):
    pid = _uuid(profile_id)
    rows = _run(
        "SELECT blocked_profile_id FROM chain_dating_blocks WHERE blocker_profile_id = %s",
        (pid,),
    )
    return {str(r["blocked_profile_id"]) for r in rows}


def _get_blocker_ids(profile_id):
    pid = _uuid(profile_id)
    rows = _run(
        "SELECT blocker_profile_id FROM chain_dating_blocks WHERE blocked_profile_id = %s",
        (pid,),
    )
    return {str(r["blocker_profile_id"]) for r in rows}


def is_blocked(profile_id, target_id):
    pid = _uuid(profile_id)
    tid = _uuid(target_id)
    rows = _run(
        "SELECT id FROM chain_dating_blocks WHERE blocker_profile_id = %s AND blocked_profile_id = %s LIMIT 1",
        (pid, tid),
    )
    return bool(rows)


def is_blocked_by(profile_id, target_id):
    pid = _uuid(profile_id)
    tid = _uuid(target_id)
    rows = _run(
        "SELECT id FROM chain_dating_blocks WHERE blocker_profile_id = %s AND blocked_profile_id = %s LIMIT 1",
        (tid, pid),
    )
    return bool(rows)


# ─── PREFERENCES ──────────────────────────────────────────────

def get_dating_preferences(profile_id):
    pid = _uuid(profile_id)
    rows = _run("SELECT * FROM chain_dating_preferences WHERE profile_id = %s LIMIT 1", (pid,))
    if rows:
        return _row_to_dict(rows[0])
    prefs_id = str(uuid.uuid4())
    _write(
        "INSERT INTO chain_dating_preferences (id, profile_id) VALUES (%s, %s)",
        (prefs_id, pid),
    )
    rows = _run("SELECT * FROM chain_dating_preferences WHERE profile_id = %s LIMIT 1", (pid,))
    return _row_to_dict(rows[0]) if rows else None


def update_dating_preferences(profile_id, **kwargs):
    pid = _uuid(profile_id)
    get_dating_preferences(pid)
    allowed = [
        "interested_in", "min_age", "max_age", "max_distance_km",
        "show_me", "only_verified", "hide_from_contacts",
    ]
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = %s")
            vals.append(v)
    if not sets:
        return {"ok": False, "error": "no_fields"}
    vals.append(pid)
    sets.append("updated_at = now()")
    _write(f"UPDATE chain_dating_preferences SET {', '.join(sets)} WHERE profile_id = %s", tuple(vals))
    return {"ok": True}


# ─── COMPATIBILITY ────────────────────────────────────────────

def calculate_compatibility(profile_id_a, profile_id_b, a_dating_profile=None):
    if not _db_available():
        return 50
    try:
        if not a_dating_profile:
            a_dating_profile = get_dating_profile(profile_id_a)
        b_dating_profile = get_dating_profile(profile_id_b)
        if not a_dating_profile or not b_dating_profile:
            return 50

        score = 50

        a_interests = set(a_dating_profile.get("interests") or [])
        b_interests = set(b_dating_profile.get("interests") or [])
        if a_interests and b_interests:
            common = a_interests & b_interests
            total = a_interests | b_interests
            ratio = len(common) / len(total) if total else 0
            score += int(ratio * 20)

        a_goal = a_dating_profile.get("relationship_goal", "")
        b_goal = b_dating_profile.get("relationship_goal", "")
        if a_goal and b_goal and a_goal == b_goal:
            score += 10

        a_loc = (a_dating_profile.get("location_preference") or "").strip().lower()
        b_loc = (b_dating_profile.get("location_preference") or "").strip().lower()
        if a_loc and b_loc and a_loc == b_loc:
            score += 10

        a_trust = int(a_dating_profile.get("trust_score", 50))
        b_trust = int(b_dating_profile.get("trust_score", 50))
        trust_avg = (a_trust + b_trust) / 2
        score += int((trust_avg / 100) * 10)

        return min(100, max(0, score))
    except Exception:
        return 50


# ─── RESTRICT DATING VISIBILITY ──────────────────────────────

def restrict_dating_visibility(profile_id, hide_from_contacts_val=False, visible_to_verified_only_val=False):
    return update_dating_profile(
        profile_id,
        hide_from_contacts=hide_from_contacts_val,
        visible_to_verified_only=visible_to_verified_only_val,
    )


def set_dating_preferences(profile_id, **kwargs):
    return update_dating_preferences(profile_id, **kwargs)
