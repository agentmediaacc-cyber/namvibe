"""Redis-only hot path for presence operations.

Avoids Neon queries on the hot path by caching conversation peers in Redis.
Syncs to Neon via background jobs (presence_engine.sync_presence_to_neon).
"""

from datetime import datetime, timezone
from services.redis_service import (
    get_redis, get_json, set_json, delete_key,
    presence_key, typing_key,
)

PRESENCE_TTL = 60
PEER_CACHE_TTL = 3600


def _get_cached_peers(profile_id):
    """Returns cached conversation peer IDs for a profile (Redis-only)."""
    r = get_redis()
    if not r:
        return []
    key = f"presence:peers:{profile_id}"
    cached = r.smembers(key)
    if cached:
        return [pid.decode() if isinstance(pid, bytes) else pid for pid in cached]
    return []


def _cache_conversation_peers(profile_id):
    """Warms the peer cache from Neon (called outside hot path)."""
    from services.neon_service import fast_query
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
    r = get_redis()
    if r and peers:
        key = f"presence:peers:{profile_id}"
        r.delete(key)
        r.sadd(key, *[p['profile_id'] for p in peers])
        r.expire(key, PEER_CACHE_TTL)
    return peers


def emit_presence_update(profile_id, status):
    """Notifies active conversation peers via Redis-only peer cache."""
    from services.socketio_service import emit_to_profile
    peers = _get_cached_peers(profile_id)
    if not peers:
        _cache_conversation_peers(profile_id)
        peers = _get_cached_peers(profile_id)
    for peer_id in peers:
        emit_to_profile(peer_id, "presence:update", {
            "profile_id": profile_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


def set_online(profile_id):
    """Redis-only set online. Enqueues Neon sync as background job."""
    r = get_redis()
    now_iso = datetime.now(timezone.utc).isoformat()
    result = False
    if r:
        r.setex(presence_key("online", profile_id), PRESENCE_TTL, "1")
        set_json(f"presence:state:{profile_id}", {"status": "online", "last_seen_at": now_iso}, ttl=PRESENCE_TTL)
        if not r.get(presence_key("synced", profile_id)):
            from services.queue_service import enqueue_job
            enqueue_job("services.presence_engine.sync_presence_to_neon", profile_id, "online")
            r.setex(presence_key("synced", profile_id), 300, "1")
        result = True
    emit_presence_update(profile_id, "online")
    return result


def set_offline(profile_id):
    """Redis-only set offline. Enqueues Neon sync as background job."""
    r = get_redis()
    now_iso = datetime.now(timezone.utc).isoformat()
    if r:
        r.delete(presence_key("online", profile_id))
        set_json(f"presence:state:{profile_id}", {"status": "offline", "last_seen_at": now_iso}, ttl=3600)
    emit_presence_update(profile_id, "offline")
    from services.queue_service import enqueue_job
    enqueue_job("services.presence_engine.sync_presence_to_neon", profile_id, "offline")
    return True


def heartbeat(profile_id):
    """Updates presence TTL in Redis."""
    return set_online(profile_id)


def set_typing(profile_id, thread_id):
    """Sets typing indicator in Redis."""
    r = get_redis()
    if r:
        r.setex(typing_key(thread_id, profile_id), 10, "1")
    return True


def get_presence(profile_ids):
    """Gets presence info from Redis first, falls back to Neon."""
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
        from services.neon_service import fast_query
        sql = "SELECT profile_id, status, last_seen_at FROM chain_presence WHERE profile_id = ANY(%s::uuid[])"
        db_results = fast_query(sql, (missing_ids,))
        for row in db_results:
            if isinstance(row.get('last_seen_at'), datetime):
                row['last_seen_at'] = row['last_seen_at'].isoformat()
        results.extend(db_results)
    return results
