import os
import json
from services.redis_service import publish
from services.logging_service import log_info, log_error

def send_push_notification(profile_id, title, body, data=None):
    """
    Abstractions for Push Notifications (FCM / APNS).
    For now, enqueues an intent for a worker to process.
    """
    payload = {
        "profile_id": profile_id,
        "title": title,
        "body": body,
        "data": data or {},
        "timestamp": os.getlogin() if os.name == 'posix' else 'unknown' # dummy
    }
    
    # Enqueue push intent via Redis
    publish(f"push:intents:{profile_id}", payload)
    log_info("push_notification_intent_created", profile_id=profile_id)
    return True

def register_device_token(profile_id, token, platform='fcm'):
    """Registers a push token for a user."""
    # In a real app, store this in a 'chain_device_tokens' table
    log_info("push_token_registered", profile_id=profile_id, platform=platform)
    return True
