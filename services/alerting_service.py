import uuid
from copy import deepcopy
from datetime import datetime, timezone

_ALERTS = []
VALID_SEVERITIES = {"info", "warning", "high", "critical"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_alert(component, severity, title, message, metadata=None):
    severity = severity if severity in VALID_SEVERITIES else "info"
    alert = {
        "id": str(uuid.uuid4()),
        "component": component,
        "severity": severity,
        "title": title,
        "message": message,
        "resolved": False,
        "resolved_at": None,
        "metadata": metadata or {},
        "created_at": _now(),
    }
    _ALERTS.append(alert)
    return {"ok": True, "alert": deepcopy(alert)}


def resolve_alert(alert_id):
    for alert in _ALERTS:
        if alert["id"] == alert_id:
            alert["resolved"] = True
            alert["resolved_at"] = _now()
            return {"ok": True, "alert": deepcopy(alert)}
    return {"ok": False, "error": "alert_not_found"}


def get_active_alerts(component=None):
    alerts = [a for a in _ALERTS if not a.get("resolved")]
    if component:
        alerts = [a for a in alerts if a.get("component") == component]
    return deepcopy(alerts)


def get_alert_history(limit=100):
    return deepcopy(_ALERTS[-int(limit or 100):])


def check_component_health(component, status=None, metadata=None):
    status = status or "ok"
    if status in {"ok", "healthy", "fallback"}:
        return {"ok": True, "component": component, "status": status}
    severity = "critical" if status in {"down", "failed"} else "warning"
    return create_alert(component, severity, f"{component} health issue", f"{component} reported status {status}", metadata)


def generate_alert_summary():
    active = get_active_alerts()
    return {
        "ok": True,
        "active_count": len(active),
        "critical_count": len([a for a in active if a.get("severity") == "critical"]),
        "high_count": len([a for a in active if a.get("severity") == "high"]),
        "alerts": active,
    }
