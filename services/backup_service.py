import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone

_BACKUPS = []


def _now():
    return datetime.now(timezone.utc).isoformat()


def record_backup_event(backup_type, status, location=None, metadata=None):
    event = {
        "id": str(uuid.uuid4()),
        "backup_type": backup_type,
        "status": status,
        "location": location,
        "metadata": metadata or {},
        "created_at": _now(),
    }
    _BACKUPS.append(event)
    return {"ok": True, "event": deepcopy(event)}


def verify_backup_configuration():
    configured = bool(os.getenv("CHAIN_BACKUP_LOCATION") or os.getenv("BACKUP_BUCKET") or os.getenv("DATABASE_BACKUP_URL"))
    return {
        "ok": configured,
        "configured": configured,
        "location": os.getenv("CHAIN_BACKUP_LOCATION") or os.getenv("BACKUP_BUCKET"),
        "warning": not configured,
        "message": "Configure database and media backup destination before public launch." if not configured else "Backup destination configured.",
    }


def verify_restore_plan():
    documented = os.path.exists("docs/CHAIN_GO_LIVE_CHECKLIST.md") and os.path.exists("docs/phase49_worker_deployment.md")
    return {"ok": documented, "documented": documented}


def get_backup_history(limit=50):
    return deepcopy(_BACKUPS[-int(limit or 50):])


def generate_backup_report():
    config = verify_backup_configuration()
    restore = verify_restore_plan()
    return {"ok": config.get("ok") and restore.get("ok"), "configuration": config, "restore_plan": restore, "history": get_backup_history()}
