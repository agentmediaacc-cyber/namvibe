import os, uuid, json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query, get_pool_status
from services.homepage_real_data_guard import public_profile_sql
from services.profile_service import get_profile_by_id
from services.blocking_service import is_blocked_any
from services.relationship_privacy_service import can_view_profile
from services.dating_compatibility_service import build_compatibility_profile, score_compatibility

RELATIONSHIP_GOALS = ["friendship", "casual", "relationship", "marriage", "open"]
ACTION_TYPES = ["like", "pass", "super_like"]
REPORT_REASONS = ["fake_profile", "harassment", "inappropriate", "spam", "other"]
DEFAULT_LIMIT = 30
MAX_LIMIT = 60


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


def _may_see_phone(viewer_profile, dating_profile):
    """Phone is only visible if viewer is premium AND dating profile has show_phone_publicly=true."""
    if not viewer_profile or not dating_profile:
        return False
    is_premium = bool(viewer_profile.get("is_premium") or viewer_profile.get("premium_tier") not in (None, "", "free"))
    show_phone = bool(dating_profile.get("show_phone_publicly", False))
    return is_premium and show_phone


def _strip_sensitive(dating_row):
    """Remove sensitive fields (phone) from a dating profile row."""
    if not dating_row:
        return dating_row
    if isinstance(dating_row, dict):
        dating_row.pop("phone", None)
    return dating_row


def _clean_limit(value, default=DEFAULT_LIMIT, maximum=MAX_LIMIT):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(maximum, limit))


def _clean_offset(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _parse_json_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            loaded = json.loads(value)
            if isinstance(loaded, list):
                return [str(v).strip() for v in loaded if str(v).strip()]
        except Exception:
            pass
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(value).strip()]


def _profile_age(row):
    if not row:
        return None
    for key in ("age",):
        val = row.get(key)
        if val not in (None, ""):
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    dob = row.get("date_of_birth")
    if not dob:
        return None
    try:
        if isinstance(dob, str):
            dob_dt = datetime.fromisoformat(dob.replace("Z", "+00:00"))
        else:
            dob_dt = dob
        today = datetime.now(timezone.utc)
        years = today.year - dob_dt.year - ((today.month, today.day) < (dob_dt.month, dob_dt.day))
        return years
    except Exception:
        return None


def _eligible_for_discovery(viewer, profile_row, prefs, blocked_ids, blocker_ids, dating_profile):
    if not viewer or not profile_row or not dating_profile:
        return False
    pid = str(profile_row.get("id") or profile_row.get("profile_id") or "")
    if not pid or pid == str(viewer):
        return False
    if pid in blocked_ids or pid in blocker_ids:
        return False
    if profile_row.get("deleted_at"):
        return False
    if profile_row.get("is_public") is False:
        return False
    if profile_row.get("dating_mode_enabled") is False:
        return False
    if profile_row.get("profile_visibility") in {"private", "hidden"}:
        return False
    if dating_profile.get("dating_mode_on") is False or dating_profile.get("is_enabled") is False:
        return False
    if dating_profile.get("hide_from_contacts") and profile_row.get("username") == viewer.get("username"):
        return False
    if prefs:
        min_age = prefs.get("min_age")
        max_age = prefs.get("max_age")
        age = _profile_age(profile_row)
        if age is None:
            return False
        if min_age not in (None, "") and age < int(min_age):
            return False
        if max_age not in (None, "") and age > int(max_age):
            return False
        interested_in = str(prefs.get("interested_in") or "everyone").lower()
        gender = str(profile_row.get("gender") or "").lower()
        if interested_in not in {"everyone", "all", ""} and gender:
            if interested_in == "women" and gender not in {"female", "woman", "f"}:
                return False
            if interested_in == "men" and gender not in {"male", "man", "m"}:
                return False
    return True


def _prefetch_candidate_ids(viewer_id):
    rows = _run(
        """
        SELECT dp.profile_id
        FROM chain_dating_profiles dp
        JOIN chain_profiles p ON p.id = dp.profile_id
        WHERE dp.dating_mode_on = true
          AND dp.is_enabled = true
          AND dp.profile_id != %s
          AND COALESCE(p.deleted_at, NULL) IS NULL
        ORDER BY dp.updated_at DESC, dp.created_at DESC, dp.profile_id DESC
        LIMIT 500
        """,
        (_uuid(viewer_id),),
    )
    return [str(r["profile_id"]) for r in rows or []]


def _emit_dating_match_notification(recipient_id, actor_id):
    payload_event = (
        str(uuid.uuid4()),
        recipient_id,
        actor_id,
        "match",
        "💘 It's a match!",
        "You matched on NamVibe Dating.",
        "/dating/matches",
        datetime.now(timezone.utc),
    )
    payload_legacy = (
        str(uuid.uuid4()),
        recipient_id,
        actor_id,
        "match",
        "💘 It's a match!",
        "You matched on NamVibe Dating.",
        "dating",
        None,
        "/dating/matches",
        False,
        datetime.now(timezone.utc),
        None,
        None,
    )
    try:
        _write(
            "INSERT INTO chain_notification_events (id, profile_id, actor_profile_id, event_type, title, body, target_url, is_read, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s)",
            payload_event,
        )
        return True
    except Exception:
        pass
    try:
        _write(
            "INSERT INTO chain_notifications (id, recipient_profile_id, actor_profile_id, event_type, title, body, entity_type, entity_id, action_url, is_read, created_at, read_at, deleted_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            payload_legacy,
        )
        return True
    except Exception:
        return False


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
        "show_phone_publicly",
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
    limit = _clean_limit(limit)
    offset = _clean_offset(offset)
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

    preferences = get_dating_preferences(viewer) or {}
    dating_profile = get_or_create_dating_profile(viewer) or {}

    candidate_ids = _prefetch_candidate_ids(viewer)
    if not candidate_ids:
        return []
    rows = _run(
        f"""SELECT dp.*, p.username, p.display_name, p.avatar_url, p.full_name, p.gender, p.date_of_birth,
                  p.deleted_at, p.is_public, p.profile_visibility, p.dating_mode_enabled, p.town, p.city, p.location, p.region
           FROM chain_dating_profiles dp
           JOIN chain_profiles p ON p.id = dp.profile_id
           WHERE dp.profile_id::text = ANY(%s)
             AND {public_profile_sql("p")}
           ORDER BY dp.trust_score DESC, dp.updated_at DESC, dp.profile_id DESC""",
        (candidate_ids,),
    )

    seen = set()
    results = []
    for r in rows:
        pid = str(r["profile_id"])
        if pid in excluded or pid in seen:
            continue
        seen.add(pid)
        profile = _row_to_dict(r)
        if not _eligible_for_discovery(viewer, profile, preferences, blocked, blocked_by, dating_profile):
            continue
        compatibility = score_compatibility(
            build_compatibility_profile(viewer=viewer, viewer_profile=dating_profile, target_profile=profile, preferences=preferences)
        )
        profile["compatibility_score"] = compatibility["score"]
        profile["compatibility_reasons"] = compatibility["reasons"]
        profile["compatibility_confidence"] = compatibility["confidence"]
        results.append(profile)
    results.sort(key=lambda x: (-int(x.get("compatibility_score") or 0), str(x.get("updated_at") or ""), str(x.get("profile_id") or "")))
    page = results[offset:offset + limit] if results else []
    return _rows_to_list(page)


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
    if is_blocked_any(actor, target):
        return {"ok": False, "error": "blocked_relationship"}

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
            score_payload = score_compatibility(
                build_compatibility_profile(viewer=actor, viewer_profile=get_dating_profile(actor), target_profile=get_dating_profile(target))
            )
            score = int(score_payload["score"])
            existing_match = _run(
                "SELECT id FROM chain_dating_matches WHERE ((profile_id_a = %s AND profile_id_b = %s) OR (profile_id_a = %s AND profile_id_b = %s)) AND is_active = true LIMIT 1",
                (actor, target, target, actor),
            )
            mid = str(existing_match[0]["id"]) if existing_match else str(uuid.uuid4())
            if not existing_match:
                _write(
                    "INSERT INTO chain_dating_matches (id, profile_id_a, profile_id_b, compatibility_score) VALUES (%s, %s, %s, %s)",
                    (mid, actor, target, score),
                )
            _write(
                "UPDATE chain_dating_likes SET is_mutual = true WHERE (actor_profile_id = %s AND target_profile_id = %s) OR (actor_profile_id = %s AND target_profile_id = %s)",
                (actor, target, target, actor),
            )
            result["is_match"] = True
            result["match"] = {"id": mid, "compatibility_score": score, "reasons": score_payload["reasons"], "confidence": score_payload["confidence"]}
            _emit_dating_match_notification(actor, target)
            _emit_dating_match_notification(target, actor)

            thread = _run(
                """
                SELECT t.id
                FROM chain_message_threads t
                JOIN chain_thread_members tm1 ON tm1.thread_id = t.id AND tm1.profile_id = %s
                JOIN chain_thread_members tm2 ON tm2.thread_id = t.id AND tm2.profile_id = %s
                WHERE COALESCE(t.folder_type, '') = 'dating'
                LIMIT 1
                """,
                (actor, target),
            )
            if not thread:
                tid = str(uuid.uuid4())
                _write(
                    "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at) VALUES (%s, %s, 'direct', 'dating', now(), now())",
                    (tid, actor),
                )
                _write(
                    "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s) ON CONFLICT DO NOTHING",
                    (tid, actor, tid, target),
                )

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


def unmatch_users(profile_id, target_id):
    actor = _uuid(profile_id)
    target = _uuid(target_id)
    if actor == target:
        return {"ok": False, "error": "cannot_unmatch_self"}
    rows = _run(
        """
        SELECT id, profile_id_a, profile_id_b, is_active
        FROM chain_dating_matches
        WHERE ((profile_id_a = %s AND profile_id_b = %s) OR (profile_id_a = %s AND profile_id_b = %s))
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (actor, target, target, actor),
    )
    if not rows:
        return {"ok": False, "error": "match_not_found"}
    match = rows[0]
    if not match.get("is_active", True):
        return {"ok": True, "status": "already_inactive", "match_id": str(match["id"])}
    _write(
        "UPDATE chain_dating_matches SET is_active = false WHERE id = %s",
        (match["id"],),
    )
    return {"ok": True, "status": "unmatched", "match_id": str(match["id"])}


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
    if reason not in REPORT_REASONS:
        return {"ok": False, "error": "invalid_reason"}
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
        profile = build_compatibility_profile(
            viewer=profile_id_a,
            viewer_profile=a_dating_profile or get_dating_profile(profile_id_a),
            target_profile=get_dating_profile(profile_id_b),
            preferences=get_dating_preferences(profile_id_a),
        )
        return score_compatibility(profile)["score"]
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


# ─── BECOME FRIENDS ──────────────────────────────────────────

def become_friends(profile_id, match_id):
    """Convert a dating match to normal friends. Closes the dating chat and makes them real friends."""
    pid = _uuid(profile_id)
    rows = _run(
        "SELECT * FROM chain_dating_matches WHERE id = %s AND (profile_id_a = %s OR profile_id_b = %s) AND is_active = true LIMIT 1",
        (match_id, pid, pid),
    )
    if not rows:
        return {"ok": False, "error": "match_not_found"}
    match = rows[0]
    other_id = str(match["profile_id_a"]) if str(match["profile_id_b"]) == pid else str(match["profile_id_b"])

    # Mark match as inactive
    _write("UPDATE chain_dating_matches SET is_active = false WHERE id = %s", (match_id,))

    # Create a real friend relationship
    from services.friend_service import send_friend_request, accept_friend_request
    req = send_friend_request(pid, other_id, message="We matched on NamVibe Dating ❤️")
    if req.get("ok"):
        accept_friend_request(other_id, pid)

    # Close the dating thread (move to primary)
    thread_rows = _run(
        "SELECT id FROM chain_message_threads WHERE folder_type = 'dating' AND deleted_at IS NULL AND id IN ("
        "SELECT thread_id FROM chain_thread_members WHERE profile_id = %s "
        "INTERSECT SELECT thread_id FROM chain_thread_members WHERE profile_id = %s"
        ") LIMIT 1",
        (pid, other_id),
    )
    if thread_rows:
        from services.messaging_engine import move_thread
        move_thread(str(thread_rows[0]["id"]), "primary")

    return {"ok": True, "new_friend_id": other_id}


# ─── SOS / EMERGENCY ─────────────────────────────────────────

def sos_alert(profile_id, lat=None, lng=None):
    """Send emergency alert with live location to trusted contacts."""
    pid = _uuid(profile_id)
    profile = get_profile_by_id(pid)
    if not profile:
        return {"ok": False, "error": "profile_not_found"}
    name = profile.get("display_name") or profile.get("full_name") or "A NamVibe user"
    loc_str = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else "Location unavailable"
    from services.notification_engine import send_notification
    send_notification(
        recipient_profile_id=pid,
        type_="sos_alert",
        title="🚨 SOS Alert Sent",
        body=f"Your emergency contacts have been notified. Location: {loc_str}",
    )
    return {"ok": True, "location_url": loc_str}
