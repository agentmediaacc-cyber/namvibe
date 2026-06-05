import json
from datetime import datetime, timezone
from services.neon_service import write_query
from services.queue_service import enqueue_job

def track_event(event_type, profile_id=None, entity_type=None, entity_id=None, metadata=None, request=None):
    """Tracks a structured analytics event asynchronously."""
    ip = None
    ua = None
    if request:
        ip = request.remote_addr
        ua = request.user_agent.string

    payload = {
        "profile_id": profile_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "ip_address": ip,
        "user_agent": ua,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Use RQ for async tracking if available
    enqueue_job("services.analytics_engine.process_analytics_job", payload, queue_name='cleanup')
    return True

def track_reel_view(reel_id, profile_id=None, request=None):
    return track_event("reel_view", profile_id=profile_id, entity_type="reel", entity_id=reel_id, request=request)

def track_profile_view(target_profile_id, viewer_profile_id=None, request=None):
    return track_event("profile_view", profile_id=viewer_profile_id, entity_type="profile", entity_id=target_profile_id, request=request)

def track_live_join(room_id, profile_id=None, request=None):
    return track_event("live_join", profile_id=profile_id, entity_type="live_room", entity_id=room_id, request=request)

def track_feed_impression(entity_type, entity_id, profile_id=None):
    return track_event("feed_impression", profile_id=profile_id, entity_type=entity_type, entity_id=entity_id)

def process_analytics_job(payload):
    """Worker job to persist analytics to Neon."""
    sql = """
        INSERT INTO chain_analytics_events (
            profile_id, event_type, entity_type, entity_id, metadata, ip_address, user_agent, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        payload['profile_id'], payload['event_type'], payload['entity_type'], payload['entity_id'],
        json.dumps(payload['metadata']), payload['ip_address'], payload['user_agent'], payload['created_at']
    )
    return write_query(sql, params)
