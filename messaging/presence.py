from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone


ONLINE_TTL_SECONDS = 180
RECENT_WINDOW = timedelta(minutes=15)


def _online_key(user_id):
    return f"presence:online:{user_id}"


def _last_seen_key(user_id):
    return f"presence:last_seen:{user_id}"


def mark_user_online(user_id):
    if not user_id:
        return
    stamp = timezone.now().isoformat()
    cache.set(_online_key(user_id), stamp, timeout=ONLINE_TTL_SECONDS)
    cache.set(_last_seen_key(user_id), stamp, timeout=60 * 60 * 24 * 7)


def mark_user_offline(user_id):
    if not user_id:
        return
    cache.delete(_online_key(user_id))
    cache.set(_last_seen_key(user_id), timezone.now().isoformat(), timeout=60 * 60 * 24 * 7)


def presence_snapshot(user):
    user_id = getattr(user, "id", user)
    if not user_id:
        return {"is_online": False, "last_seen": None, "label": "Offline"}

    online_stamp = cache.get(_online_key(user_id))
    if online_stamp:
        return {"is_online": True, "last_seen": online_stamp, "label": "Online"}

    last_seen = cache.get(_last_seen_key(user_id))
    if not last_seen:
        return {"is_online": False, "last_seen": None, "label": "Active recently"}

    try:
        last_seen_dt = datetime.fromisoformat(last_seen)
        if timezone.is_naive(last_seen_dt):
            last_seen_dt = timezone.make_aware(last_seen_dt, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return {"is_online": False, "last_seen": None, "label": "Active recently"}

    if timezone.now() - last_seen_dt <= RECENT_WINDOW:
        label = "Active recently"
    else:
        label = f"Active {timezone.localtime(last_seen_dt).strftime('%b %d, %H:%M')}"
    return {"is_online": False, "last_seen": last_seen_dt.isoformat(), "label": label}
