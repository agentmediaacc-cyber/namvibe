import json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.profile_service import get_current_profile

_GC_COLS = "id, host_profile_id, thread_id, room_name, call_type, status, max_participants, participant_count, room_locked, created_at, started_at, ended_at"
_PART_COLS = "id, group_call_id, profile_id, role, status, muted, camera_enabled, hand_raised, screen_sharing, speaking, joined_at, left_at"

def _row_to_group_call(row):
    return {
        "id": str(row["id"]), "host_profile_id": str(row["host_profile_id"]),
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "room_name": row.get("room_name") or "",
        "call_type": row["call_type"], "status": row["status"],
        "max_participants": row["max_participants"], "participant_count": row["participant_count"],
        "room_locked": row.get("room_locked", False),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "ended_at": row["ended_at"].isoformat() if row.get("ended_at") else None,
    }

def _row_to_participant(row):
    return {
        "id": str(row["id"]), "group_call_id": str(row["group_call_id"]),
        "profile_id": str(row["profile_id"]), "role": row["role"],
        "status": row["status"], "muted": row.get("muted", False),
        "camera_enabled": row.get("camera_enabled", True),
        "hand_raised": row.get("hand_raised", False),
        "screen_sharing": row.get("screen_sharing", False),
        "speaking": row.get("speaking", False),
        "joined_at": row["joined_at"].isoformat() if row.get("joined_at") else None,
        "left_at": row["left_at"].isoformat() if row.get("left_at") else None,
    }


def create_group_call(host_profile_id, room_name="", call_type="audio", thread_id=None, max_participants=32):
    rows = fast_query(
        f"INSERT INTO chain_group_calls (host_profile_id, room_name, call_type, thread_id, max_participants, status) "
        f"VALUES (%s, %s, %s, %s, %s, 'waiting') RETURNING {_GC_COLS}",
        (host_profile_id, room_name, call_type, thread_id, max_participants),
        default=[],
    )
    if not rows:
        return None
    call = _row_to_group_call(rows[0])
    join_group_call(call["id"], host_profile_id, role="host")
    started = fast_query(
        f"UPDATE chain_group_calls SET status = 'active', started_at = now(), participant_count = 1 WHERE id = %s RETURNING {_GC_COLS}",
        (call["id"],), default=[],
    )
    add_group_call_event(call["id"], host_profile_id, "call:created", {"room_name": room_name})
    return _row_to_group_call(started[0]) if started else call


def get_group_call(call_id):
    rows = fast_query(f"SELECT {_GC_COLS} FROM chain_group_calls WHERE id = %s", (call_id,), default=[])
    return _row_to_group_call(rows[0]) if rows else None


def join_group_call(call_id, profile_id, role="participant"):
    call = get_group_call(call_id)
    if not call or call["status"] == "ended":
        return False
    if call.get("room_locked") and role != "host":
        existing = fast_query(
            "SELECT id FROM chain_group_call_invites WHERE group_call_id = %s AND invited_profile_id = %s AND status = 'accepted'",
            (call_id, profile_id), default=[],
        )
        if not existing:
            return False
    existing_part = fast_query(
        "SELECT id FROM chain_group_call_participants WHERE group_call_id = %s AND profile_id = %s AND status = 'joined'",
        (call_id, profile_id), default=[],
    )
    if existing_part:
        return True
    write_query(
        "INSERT INTO chain_group_call_participants (group_call_id, profile_id, role, status, muted, camera_enabled) "
        "VALUES (%s, %s, %s, 'joined', FALSE, TRUE)",
        (call_id, profile_id, role),
    )
    write_query(
        "UPDATE chain_group_calls SET participant_count = participant_count + 1 WHERE id = %s",
        (call_id,),
    )
    add_group_call_event(call_id, profile_id, "participant:joined")
    return True


def leave_group_call(call_id, profile_id):
    write_query(
        "UPDATE chain_group_call_participants SET status = 'left', left_at = now(), muted = TRUE, speaking = FALSE, camera_enabled = FALSE, screen_sharing = FALSE "
        "WHERE group_call_id = %s AND profile_id = %s AND status = 'joined'",
        (call_id, profile_id),
    )
    write_query(
        "UPDATE chain_group_calls SET participant_count = GREATEST(participant_count - 1, 0) WHERE id = %s",
        (call_id,),
    )
    add_group_call_event(call_id, profile_id, "participant:left")
    call = get_group_call(call_id)
    if call and call["host_profile_id"] == profile_id:
        remaining = get_participants(call_id)
        if remaining:
            transfer_host(call_id, remaining[0]["profile_id"])
    return True


def invite_participant(call_id, invited_profile_id, invited_by_profile_id):
    existing = fast_query(
        "SELECT id FROM chain_group_call_invites WHERE group_call_id = %s AND invited_profile_id = %s AND status = 'pending'",
        (call_id, invited_profile_id), default=[],
    )
    if existing:
        return True
    write_query(
        "INSERT INTO chain_group_call_invites (group_call_id, invited_profile_id, invited_by_profile_id, status) VALUES (%s, %s, %s, 'pending')",
        (call_id, invited_profile_id, invited_by_profile_id),
    )
    add_group_call_event(call_id, invited_by_profile_id, "invite:sent", {"invited": invited_profile_id})
    return True


def remove_participant(call_id, profile_id, removed_by_profile_id):
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != removed_by_profile_id:
        return False
    leave_group_call(call_id, profile_id)
    add_group_call_event(call_id, removed_by_profile_id, "participant:removed", {"removed": profile_id})
    return True


def mute_participant(call_id, profile_id):
    write_query(
        "UPDATE chain_group_call_participants SET muted = TRUE WHERE group_call_id = %s AND profile_id = %s",
        (call_id, profile_id),
    )
    return True


def unmute_participant(call_id, profile_id):
    write_query(
        "UPDATE chain_group_call_participants SET muted = FALSE WHERE group_call_id = %s AND profile_id = %s",
        (call_id, profile_id),
    )
    return True


def raise_hand(call_id, profile_id):
    write_query(
        "UPDATE chain_group_call_participants SET hand_raised = TRUE WHERE group_call_id = %s AND profile_id = %s",
        (call_id, profile_id),
    )
    add_group_call_event(call_id, profile_id, "hand:raised")
    return True


def lower_hand(call_id, profile_id):
    write_query(
        "UPDATE chain_group_call_participants SET hand_raised = FALSE WHERE group_call_id = %s AND profile_id = %s",
        (call_id, profile_id),
    )
    return True


def lock_room(call_id):
    write_query("UPDATE chain_group_calls SET room_locked = TRUE WHERE id = %s", (call_id,))
    add_group_call_event(call_id, None, "room:locked")
    return True


def unlock_room(call_id):
    write_query("UPDATE chain_group_calls SET room_locked = FALSE WHERE id = %s", (call_id,))
    add_group_call_event(call_id, None, "room:unlocked")
    return True


def transfer_host(call_id, new_host_profile_id):
    call = get_group_call(call_id)
    if not call:
        return False
    old_host = call["host_profile_id"]
    write_query("UPDATE chain_group_calls SET host_profile_id = %s WHERE id = %s", (new_host_profile_id, call_id))
    write_query(
        "UPDATE chain_group_call_participants SET role = 'participant' WHERE group_call_id = %s AND profile_id = %s",
        (call_id, old_host),
    )
    write_query(
        "UPDATE chain_group_call_participants SET role = 'host' WHERE group_call_id = %s AND profile_id = %s",
        (call_id, new_host_profile_id),
    )
    add_group_call_event(call_id, new_host_profile_id, "host:transferred", {"from": old_host, "to": new_host_profile_id})
    return True


def end_group_call(call_id):
    write_query(
        "UPDATE chain_group_calls SET status = 'ended', ended_at = now() WHERE id = %s",
        (call_id,),
    )
    write_query(
        "UPDATE chain_group_call_participants SET status = 'left', left_at = now() WHERE group_call_id = %s AND status = 'joined'",
        (call_id,),
    )
    add_group_call_event(call_id, None, "call:ended")
    return True


def get_group_call_history(profile_id, limit=50):
    rows = fast_query(
        "SELECT gc.id, gc.host_profile_id, gc.thread_id, gc.room_name, gc.call_type, gc.status, "
        "gc.max_participants, gc.participant_count, gc.room_locked, gc.created_at, gc.started_at, gc.ended_at "
        "FROM chain_group_calls gc "
        "JOIN chain_group_call_participants gcp ON gcp.group_call_id = gc.id "
        "WHERE gcp.profile_id = %s AND gc.status IN ('active', 'ended') "
        "ORDER BY gc.created_at DESC LIMIT %s",
        (profile_id, limit),
        default=[],
    )
    return [_row_to_group_call(r) for r in rows]


def add_group_call_event(call_id, profile_id, event_type, metadata=None):
    meta_json = json.dumps(metadata or {})
    fast_query(
        "INSERT INTO chain_group_call_events (group_call_id, profile_id, event_type, metadata) "
        "VALUES (%s, %s, %s, %s::jsonb) RETURNING id",
        (call_id, profile_id, event_type, meta_json),
        default=[],
    )


def get_participants(call_id):
    rows = fast_query(
        f"SELECT {_PART_COLS} FROM chain_group_call_participants "
        "WHERE group_call_id = %s AND status = 'joined' ORDER BY joined_at ASC",
        (call_id,), default=[],
    )
    return [_row_to_participant(r) for r in rows]


def get_participants_with_profiles(call_id):
    rows = fast_query(
        "SELECT gcp.id, gcp.group_call_id, gcp.profile_id, gcp.role, gcp.status, "
        "gcp.muted, gcp.camera_enabled, gcp.hand_raised, gcp.screen_sharing, gcp.speaking, gcp.joined_at, gcp.left_at, "
        "p.username, p.display_name, p.avatar_url "
        "FROM chain_group_call_participants gcp "
        "LEFT JOIN chain_profiles p ON p.id = gcp.profile_id "
        "WHERE gcp.group_call_id = %s AND gcp.status = 'joined' ORDER BY gcp.joined_at ASC",
        (call_id,), default=[],
    )
    result = []
    for r in rows:
        p = _row_to_participant(r)
        p["username"] = r.get("username") or ""
        p["display_name"] = r.get("display_name") or ""
        p["avatar_url"] = r.get("avatar_url")
        result.append(p)
    return result


def update_speaking_status(call_id, profile_id, speaking):
    write_query(
        "UPDATE chain_group_call_participants SET speaking = %s WHERE group_call_id = %s AND profile_id = %s",
        (speaking, call_id, profile_id),
    )
    if speaking:
        add_group_call_event(call_id, profile_id, "speaking:started")
    else:
        add_group_call_event(call_id, profile_id, "speaking:stopped")
    return True


def update_camera_status(call_id, profile_id, enabled):
    write_query(
        "UPDATE chain_group_call_participants SET camera_enabled = %s WHERE group_call_id = %s AND profile_id = %s",
        (enabled, call_id, profile_id),
    )
    add_group_call_event(call_id, profile_id, "camera:toggled", {"enabled": enabled})
    return True


def update_screen_share_status(call_id, profile_id, sharing):
    write_query(
        "UPDATE chain_group_call_participants SET screen_sharing = %s WHERE group_call_id = %s AND profile_id = %s",
        (sharing, call_id, profile_id),
    )
    add_group_call_event(call_id, profile_id, "screen:shared", {"sharing": sharing})
    return True


def get_active_group_call(profile_id):
    rows = fast_query(
        "SELECT gc.id, gc.host_profile_id, gc.thread_id, gc.room_name, gc.call_type, gc.status, "
        "gc.max_participants, gc.participant_count, gc.room_locked, gc.created_at, gc.started_at, gc.ended_at "
        "FROM chain_group_calls gc "
        "JOIN chain_group_call_participants gcp ON gcp.group_call_id = gc.id "
        "WHERE gcp.profile_id = %s AND gcp.status = 'joined' AND gc.status = 'active' "
        "ORDER BY gc.created_at DESC LIMIT 1",
        (profile_id,), default=[],
    )
    return _row_to_group_call(rows[0]) if rows else None
