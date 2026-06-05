import json
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, write_query
from services.redis_service import delete_key, get_json, get_redis, presence_key, set_json, typing_key

PRESENCE_TTL = 60
TYPING_TTL = 10

from services.socketio_service import emit_to_profile

def emit_presence_update(profile_id, status):
    """Notifies active conversation peers that a profile has changed status."""
    # Throttle: Only emit every 30s per status type
    throttle_key = f"presence_throttle:{profile_id}:{status}"
    r = get_redis()
    if r and r.get(throttle_key):
        return
    if r:
        r.setex(throttle_key, 30, "1")

    # Find active conversation peers (updated in last 24h)
    sql = """
        SELECT DISTINCT tm2.profile_id 
        FROM chain_thread_members tm1
        JOIN chain_thread_members tm2 ON tm1.thread_id = tm2.thread_id
        JOIN chain_message_threads t ON tm1.thread_id = t.id
        WHERE tm1.profile_id = %s 
          AND tm2.profile_id != %s
          AND t.updated_at > now() - interval '24 hours'
    """
    peers = fast_query(sql, (profile_id, profile_id), default=[])
    for peer in peers:
        emit_to_profile(peer['profile_id'], "presence:update", {
            "profile_id": profile_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

def set_online(profile_id):
    """Sets a profile as online in Redis and enqueues Neon sync."""
    r = get_redis()
    now_iso = datetime.now(timezone.utc).isoformat()
    if r:
        r.setex(presence_key("online", profile_id), PRESENCE_TTL, "1")
        set_json(f"presence:state:{profile_id}", {"status": "online", "last_seen_at": now_iso}, ttl=PRESENCE_TTL)
        # Enqueue job to sync to Neon if not recently synced
        if not r.get(presence_key("synced", profile_id)):
            from services.queue_service import enqueue_job
            enqueue_job("services.presence_engine.sync_presence_to_neon", profile_id, "online")
            r.setex(presence_key("synced", profile_id), 300, "1")
    
    emit_presence_update(profile_id, "online")
    return True

def set_offline(profile_id):
    """Sets a profile as offline in Redis and Neon."""
    r = get_redis()
    now_iso = datetime.now(timezone.utc).isoformat()
    if r:
        r.delete(presence_key("online", profile_id))
        set_json(f"presence:state:{profile_id}", {"status": "offline", "last_seen_at": now_iso}, ttl=3600)
    
    emit_presence_update(profile_id, "offline")
    
    # Update Neon with UPSERT
    sql = """
        INSERT INTO chain_presence (profile_id, status, last_seen_at, updated_at)
        VALUES (%s, 'offline', now(), now())
        ON CONFLICT (profile_id) DO UPDATE 
        SET status = 'offline', last_seen_at = now(), updated_at = now()
    """
    return write_query(sql, (profile_id,))

def heartbeat(profile_id):
    """Updates presence TTL in Redis."""
    return set_online(profile_id)

def set_typing(profile_id, thread_id):
    """Sets the typing status for a profile in Redis."""
    r = get_redis()
    if r:
        r.setex(typing_key(thread_id, profile_id), TYPING_TTL, "1")
    return True

def get_presence(profile_ids):
    """Gets presence info for a list of profile IDs from Redis first."""
    if not profile_ids:
        return []
    
    r = get_redis()
    results = []
    
    missing_ids = []
    for pid in profile_ids:
        is_online = False
        if r:
            cached = get_json(f"presence:state:{pid}")
            is_online = bool(r.get(presence_key("online", pid))) or bool(cached and cached.get("status") == "online")
            if is_online:
                results.append({
                    "profile_id": pid, 
                    "status": "online", 
                    "last_seen_at": (cached.get("last_seen_at") if cached else datetime.now(timezone.utc).isoformat())
                })
                continue
        
        missing_ids.append(pid)
            
    if missing_ids:
        sql = "SELECT profile_id, status, last_seen_at FROM chain_presence WHERE profile_id = ANY(%s::uuid[])"
        db_results = fast_query(sql, (missing_ids,))
        # Convert datetime to isoformat if needed
        for row in db_results:
            if isinstance(row.get('last_seen_at'), datetime):
                row['last_seen_at'] = row['last_seen_at'].isoformat()
        results.extend(db_results)
        
    return results

def sync_presence_to_neon(profile_id, status="online"):
    """Syncs presence state from Redis/app to Neon (Job)."""
    sql = """
        INSERT INTO chain_presence (profile_id, status, last_seen_at, updated_at)
        VALUES (%s, %s, now(), now())
        ON CONFLICT (profile_id) DO UPDATE 
        SET status = EXCLUDED.status, last_seen_at = now(), updated_at = now()
    """
    return write_query(sql, (profile_id, status))
