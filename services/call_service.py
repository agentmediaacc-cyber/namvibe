from datetime import datetime, timezone, timedelta
import uuid
from services.neon_service import fast_query, write_query
from services.socketio_service import emit_to_profile

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def start_call(conversation_id, caller_profile_id, receiver_profile_id, call_type='video'):
    call_id = str(uuid.uuid4())
    room_id = f"call-{uuid.uuid4()}"
    started_at = _utcnow_iso()
    
    sql = """
        INSERT INTO chain_call_sessions (id, conversation_id, caller_profile_id, receiver_profile_id, call_type, call_status, room_id, started_at)
        VALUES (%s, %s, %s, %s, %s, 'ringing', %s, %s)
    """
    try:
        write_query(sql, (call_id, conversation_id, caller_profile_id, receiver_profile_id, call_type, room_id, started_at))
        
        call = {
            "id": call_id,
            "conversation_id": conversation_id,
            "caller_profile_id": caller_profile_id,
            "receiver_profile_id": receiver_profile_id,
            "call_type": call_type,
            "call_status": 'ringing',
            "room_id": room_id,
            "started_at": started_at
        }
        
        # Add participants
        add_participant(call_id, caller_profile_id, status='accepted', joined_at=started_at)
        if receiver_profile_id:
            add_participant(call_id, receiver_profile_id, status='ringing')
            
            # Notify receiver via socket
            emit_to_profile(receiver_profile_id, "call:incoming", {
                "call_id": call_id,
                "caller_id": caller_profile_id,
                "call_type": call_type,
                "room_id": room_id
            })
            
            # Create persistent notification
            from services.notification_engine import create_notification
            create_notification(
                recipient_profile_id=receiver_profile_id,
                actor_profile_id=caller_profile_id,
                event_type="incoming_call",
                title=f"Incoming {call_type} call",
                body="Tap to answer",
                action_url=f"/calls/{call_id}/answer"
            )

        return call
    except Exception as e:
        print(f"[call_service] Error starting call: {e}")
        return None

def add_participant(call_id, profile_id, status='invited', joined_at=None):
    sql = "INSERT INTO chain_call_participants (call_session_id, profile_id, status, joined_at) VALUES (%s, %s, %s, %s)"
    return write_query(sql, (call_id, profile_id, status, joined_at))

def update_participant_status(call_id, profile_id, status):
    joined_at = None
    left_at = None
    if status == 'accepted':
        joined_at = _utcnow_iso()
        sql = "UPDATE chain_call_participants SET status = %s, joined_at = %s WHERE call_session_id = %s AND profile_id = %s"
        return write_query(sql, (status, joined_at, call_id, profile_id))
    elif status in ('left', 'declined', 'missed'):
        left_at = _utcnow_iso()
        sql = "UPDATE chain_call_participants SET status = %s, left_at = %s WHERE call_session_id = %s AND profile_id = %s"
        return write_query(sql, (status, left_at, call_id, profile_id))
    else:
        sql = "UPDATE chain_call_participants SET status = %s WHERE call_session_id = %s AND profile_id = %s"
        return write_query(sql, (status, call_id, profile_id))

def record_call_event(call_id, profile_id, event_type, payload=None):
    import json
    sql = "INSERT INTO chain_call_events (call_session_id, profile_id, event_type, payload) VALUES (%s, %s, %s, %s)"
    return write_query(sql, (call_id, profile_id, event_type, json.dumps(payload or {})))

def answer_call(call_id, profile_id):
    # Verify receiver
    rows = fast_query("SELECT * FROM chain_call_sessions WHERE id = %s", (call_id,))
    if not rows:
        return None, "Call not found."
    
    call = rows[0]
    if call['receiver_profile_id'] and str(call['receiver_profile_id']) != str(profile_id):
        return None, "Unauthorized."
    
    answered_at = _utcnow_iso()
    write_query("UPDATE chain_call_sessions SET call_status = 'answered', answered_at = %s WHERE id = %s", (answered_at, call_id))
    update_participant_status(call_id, profile_id, 'accepted')
    
    # Notify caller
    emit_to_profile(call['caller_profile_id'], "call:answered", {"call_id": call_id, "profile_id": profile_id})
    
    call['call_status'] = 'answered'
    call['answered_at'] = answered_at
    return call, None

def end_call(call_id, profile_id):
    rows = fast_query("SELECT * FROM chain_call_sessions WHERE id = %s", (call_id,))
    if not rows:
        return None, "Call not found."
    
    call = rows[0]
    ended_at = datetime.now(timezone.utc)
    
    # Check if it was missed
    if call['call_status'] == 'ringing' and str(profile_id) == str(call['caller_profile_id']):
        write_query("UPDATE chain_call_sessions SET call_status = 'missed' WHERE id = %s", (call_id,))
        update_participant_status(call_id, call['receiver_profile_id'], 'missed')
        
        # Notify missed call
        from services.notification_engine import create_notification
        create_notification(
            recipient_profile_id=call['receiver_profile_id'],
            actor_profile_id=call['caller_profile_id'],
            event_type="missed_call",
            title="Missed call",
            body=f"You missed a {call['call_type']} call",
            action_url="/calls/recent"
        )
        return None, None

    started_at = call.get('answered_at') or call.get('started_at')
    
    duration = 0
    if started_at:
        try:
            if isinstance(started_at, str):
                start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            else:
                start_dt = started_at
            duration = int((ended_at - start_dt).total_seconds())
        except Exception as e:
            print(f"Duration calc error: {e}")
            
    sql = "UPDATE chain_call_sessions SET call_status = 'ended', ended_at = %s, duration_seconds = %s WHERE id = %s"
    write_query(sql, (ended_at.isoformat(), max(duration, 0), call_id))
    update_participant_status(call_id, profile_id, 'left')
    
    # Notify other participants
    p_rows = fast_query("SELECT profile_id FROM chain_call_participants WHERE call_session_id = %s", (call_id,))
    for p in p_rows:
        if str(p['profile_id']) != str(profile_id):
            emit_to_profile(p['profile_id'], "call:ended", {"call_id": call_id, "by": profile_id})

    rows_updated = fast_query("SELECT * FROM chain_call_sessions WHERE id = %s", (call_id,))
    return rows_updated[0] if rows_updated else None, None

def reject_call(call_id, profile_id):
    rows = fast_query("SELECT * FROM chain_call_sessions WHERE id = %s", (call_id,))
    if not rows:
        return None, "Call not found."
    
    call = rows[0]
    write_query("UPDATE chain_call_sessions SET call_status = 'rejected' WHERE id = %s", (call_id,))
    update_participant_status(call_id, profile_id, 'declined')
    
    # Notify caller
    emit_to_profile(call['caller_profile_id'], "call:rejected", {"call_id": call_id, "by": profile_id})
    return True, None

def check_call_timeouts():
    """Identifies 'ringing' calls older than 30s and marks them as missed."""
    timeout_limit = datetime.now(timezone.utc) - timedelta(seconds=30)
    sql = """
        SELECT id, caller_profile_id, receiver_profile_id, call_type 
        FROM chain_call_sessions 
        WHERE call_status = 'ringing' AND started_at < %s
    """
    stale_calls = fast_query(sql, (timeout_limit.isoformat(),))
    
    for call in stale_calls:
        call_id = call['id']
        write_query("UPDATE chain_call_sessions SET call_status = 'missed' WHERE id = %s", (call_id,))
        update_participant_status(call_id, call['receiver_profile_id'], 'missed')
        
        # Notify missed call
        from services.notification_engine import create_notification
        create_notification(
            recipient_profile_id=call['receiver_profile_id'],
            actor_profile_id=call['caller_profile_id'],
            event_type="missed_call",
            title="Missed call",
            body=f"You missed a {call['call_type']} call",
            action_url="/calls/recent"
        )
        # Notify via socket
        emit_to_profile(call['receiver_profile_id'], "call:missed", {"call_id": call_id})
        emit_to_profile(call['caller_profile_id'], "call:no-answer", {"call_id": call_id})
        
    return len(stale_calls)

def list_recent_calls(profile_id):
    sql = """
        SELECT c.*, 
               caller.username as caller_username, caller.avatar_url as caller_avatar,
               receiver.username as receiver_username, receiver.avatar_url as receiver_avatar
        FROM chain_call_sessions c
        LEFT JOIN chain_profiles caller ON c.caller_profile_id = caller.id
        LEFT JOIN chain_profiles receiver ON c.receiver_profile_id = receiver.id
        WHERE c.caller_profile_id = %s OR c.receiver_profile_id = %s
        ORDER BY c.started_at DESC
        LIMIT 50
    """
    return fast_query(sql, (profile_id, profile_id))
