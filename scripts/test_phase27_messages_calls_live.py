import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_project_python():
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        venv_python = ROOT / "venv" / "bin" / "python3"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise


_ensure_project_python()

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")

from app import app


def _login(client):
    auth_user_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    with client.session_transaction() as sess:
        sess["auth_user_id"] = auth_user_id
        sess["profile_id"] = profile_id
        sess["auth_email"] = "phase27@example.com"
        sess["username"] = "phase27"
        sess["full_name"] = "Phase 27"
        sess["profile_warning"] = True
    return {"auth_user_id": auth_user_id, "profile_id": profile_id}


def main():
    app.config["TESTING"] = True
    client = app.test_client()
    ids = _login(client)
    thread_id = str(uuid.uuid4())
    peer_id = str(uuid.uuid4())

    unread = client.get("/messages/api/unread-count")
    if unread.status_code not in {200, 302}:
        raise AssertionError(f"unread count returned {unread.status_code}")

    send = client.post("/messages/api/messages/send", json={"thread_id": thread_id, "body": "Phase 27 smoke message", "client_message_id": str(uuid.uuid4())})
    if send.status_code not in {200, 400, 401, 404, 500}:
        raise AssertionError(f"message send returned unexpected status {send.status_code}")

    call = client.post("/calls/start", data={"conversation_id": thread_id, "receiver_id": peer_id, "call_type": "audio"})
    if call.status_code not in {200, 302, 400, 500}:
        raise AssertionError(f"call start returned unexpected status {call.status_code}")

    live = client.get("/live/")
    if live.status_code != 200:
        raise AssertionError(f"live page returned {live.status_code}")

    print("phase27 messages/calls/live: ok")


if __name__ == "__main__":
    main()
