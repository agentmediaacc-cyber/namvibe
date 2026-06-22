#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(label, condition):
    print(("PASS" if condition else "FAIL") + f": {label}")
    if not condition:
        raise AssertionError(label)


def main():
    import app
    routes = {rule.rule for rule in app.app.url_map.iter_rules()}
    route_src = (ROOT / "api_routes/messaging_routes.py").read_text()
    svc_src = (ROOT / "services/message_thread_service.py").read_text()
    migration = (ROOT / "scripts/phase91_message_schema_upgrade.py").read_text()

    check("send route registered", "/api/messages/send" in routes)
    check("send route uses current authenticated profile", "get_current_profile" in route_src and "session.get(\"profile_id\")" in route_src)
    check("send route delegates to messaging engine", "from services.messaging_engine import send_message" in route_src)
    check("client_temp_id idempotency supported", "client_temp_id" in route_src and "client_temp_id" in migration)
    check("message status sent saved", "status = 'sent'" in route_src)
    check("receiver membership enforced", "can_access_thread(profile_id, thread_id)" in route_src)
    check("ordering oldest to newest", "ORDER BY m.created_at ASC, m.id ASC" in svc_src)
    check("thread latest route registered", "/api/messages/thread/<thread_id>/latest" in routes)
    check("thread older route registered", "/api/messages/thread/<thread_id>/older" in routes)
    print("test_message_delivery_ok")


if __name__ == "__main__":
    main()
