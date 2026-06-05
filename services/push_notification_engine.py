import json
import requests
import os
from services.neon_service import write_query, fast_query
from services.queue_service import enqueue_job

FCM_API_URL = "https://fcm.googleapis.com/fcm/send"
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY")

def register_device(profile_id, device_token, platform, app_version):
    """Registers a mobile device for push notifications."""
    sql = """
        INSERT INTO chain_push_devices (profile_id, device_token, platform, app_version, last_seen_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (profile_id, device_token) DO UPDATE 
        SET app_version = %s, last_seen_at = now(), deleted_at = NULL
    """
    return write_query(sql, (profile_id, device_token, platform, app_version, app_version))

def send_push_notification(profile_id, title, body, data=None):
    """Enqueues a push notification to be sent."""
    sql = "SELECT device_token, platform FROM chain_push_devices WHERE profile_id = %s AND deleted_at IS NULL"
    devices = fast_query(sql, (profile_id,))
    
    if not devices:
        return False
        
    for device in devices:
        payload = {
            "token": device['device_token'],
            "platform": device['platform'],
            "title": title,
            "body": body,
            "data": data or {}
        }
        enqueue_job("process_push_job", payload, queue_name='notifications', max_attempts=3)
        
    return True

def process_push_job(payload):
    """Worker job to actually send push via FCM."""
    if not FCM_SERVER_KEY:
        print("[push] FCM_SERVER_KEY not configured, skipping send.")
        return True

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={FCM_SERVER_KEY}'
    }
    
    fcm_payload = {
        'to': payload['token'],
        'notification': {
            'title': payload['title'],
            'body': payload['body'],
            'sound': 'default'
        },
        'data': payload['data'],
        'priority': 'high'
    }

    try:
        resp = requests.post(FCM_API_URL, headers=headers, data=json.dumps(fcm_payload), timeout=10)
        result = resp.json()
        
        if resp.status_code == 200:
            if result.get('failure') == 1:
                error = result['results'][0].get('error')
                if error in ['NotRegistered', 'InvalidRegistration']:
                    # Token is invalid, deactivate device
                    write_query("UPDATE chain_push_devices SET deleted_at = now() WHERE device_token = %s", (payload['token'],))
            return True
        else:
            print(f"[push] FCM error: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"[push] Failed to send FCM: {e}")
        return False
