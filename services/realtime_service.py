from datetime import datetime, timezone
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from utils.supabase_client import get_supabase_admin

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def set_online(profile_id, status='online', room_id=None, device_type='web'):
    payload = {
        "profile_id": profile_id,
        "status": status,
        "current_room_id": room_id,
        "device_type": device_type,
        "last_seen": _utcnow_iso(),
        "updated_at": _utcnow_iso()
    }
    # upsert logic
    supabase = get_supabase_admin()
    supabase.table("chain_presence").upsert(payload).execute()
    return True

def set_offline(profile_id):
    payload = {
        "status": 'offline',
        "updated_at": _utcnow_iso()
    }
    safe_update("chain_presence", payload, eq={"profile_id": profile_id})
    return True

def track_live_reaction(room_id, profile_id, reaction_type):
    """
    Records a live reaction and increments the room's reaction counter.
    """
    payload = {
        "room_id": room_id,
        "profile_id": profile_id,
        "reaction_type": reaction_type,
        "created_at": _utcnow_iso()
    }
    safe_insert("chain_live_reactions", payload)
    
    # Increment room counter (best effort)
    try:
        supabase = get_supabase_admin()
        supabase.rpc("increment_room_reactions", {"room_id": room_id}).execute()
    except Exception:
        pass
    
    return True

def update_typing(conversation_id, profile_id, is_typing):
    payload = {
        "conversation_id": conversation_id,
        "profile_id": profile_id,
        "is_typing": bool(is_typing),
        "updated_at": _utcnow_iso()
    }
    supabase = get_supabase_admin()
    supabase.table("chain_typing_status").upsert(payload).execute()
    return True

def get_online_profiles(limit=50):
    rows = safe_select("chain_online_presence", filters={"is_online": True}, limit=limit, order_by="updated_at", desc=True)
    return rows
