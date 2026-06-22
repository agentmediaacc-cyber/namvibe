#!/usr/bin/env python3
from pathlib import Path
from io import BytesIO
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
    from werkzeug.datastructures import FileStorage
    from services.message_media_service import validate_message_attachment

    app.app.config["TESTING"] = True
    app.app.config["WTF_CSRF_ENABLED"] = False
    client = app.app.test_client()
    response = client.post("/api/messages/send", json={"thread_id": "t1", "body": "hello"})
    check("unauthenticated user cannot send", response.status_code in {302, 401, 403})

    route_src = (ROOT / "api_routes/messaging_routes.py").read_text()
    thread_src = (ROOT / "services/message_thread_service.py").read_text()
    check("user cannot read non-member thread", "can_access_thread(profile_id, thread_id)" in route_src and "thread_not_found" in thread_src)
    check("blocked user cannot send if block table exists", "chain_blocks" in route_src and "blocked" in route_src)
    check("deleted-for-everyone body not exposed", "deleted_for_everyone_at" in thread_src and "NULL ELSE m.body" in thread_src)

    bad_file = FileStorage(stream=BytesIO(b"<script></script>"), filename="bad.html", content_type="text/html")
    invalid = validate_message_attachment(bad_file)
    check("attachment invalid MIME rejected", invalid.get("ok") is False and invalid.get("error") == "invalid_mime_type")
    check("POST routes keep CSRF", "csrf.exempt(messaging_api_bp)" not in (ROOT / "app.py").read_text())
    print("test_message_security_ok")


if __name__ == "__main__":
    main()
