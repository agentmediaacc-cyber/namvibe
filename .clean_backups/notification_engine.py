from utils.supabase_client import get_supabase_admin

def notify(profile_id, title, message="", notification_type="general", target_url="/notifications/"):
    supabase = get_supabase_admin()
    try:
        supabase.table("chain_notifications").insert({
            "profile_id": profile_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "target_url": target_url,
            "is_read": False,
        }).execute()
        return True
    except Exception as exc:
        print("[NOTIFICATION ENGINE] failed:", exc)
        return False
