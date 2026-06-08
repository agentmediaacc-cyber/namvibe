#!/usr/bin/env python3
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))
os.environ["FLASK_TESTING"] = "1"

from services import message_feature_service as m  # noqa: E402


def assert_ok(result):
    assert result.get("ok"), result
    return result


def main():
    sender = str(uuid.uuid4())
    receiver = str(uuid.uuid4())
    thread = assert_ok(m.create_direct_thread(sender, receiver))["thread_id"]
    msg = assert_ok(m.send_text_message(thread, sender, "hello phase30"))["message"]
    message_id = msg["id"]

    assert m.get_thread_messages(thread, receiver)
    assert_ok(m.mark_delivered(thread, receiver))
    assert_ok(m.mark_seen(thread, receiver))
    assert m.unread_count(receiver) == 0
    assert_ok(m.add_reaction(message_id, receiver, "heart"))
    assert_ok(m.edit_message(message_id, sender, "hello edited"))
    assert_ok(m.delete_message(message_id, receiver, for_everyone=False))
    assert_ok(m.star_message(message_id, receiver, True))
    assert_ok(m.pin_message(message_id, receiver, True))

    target = assert_ok(m.create_direct_thread(sender, str(uuid.uuid4())))["thread_id"]
    assert_ok(m.forward_messages(sender, [message_id], [target]))
    assert_ok(m.multi_select_action(receiver, [message_id], "delete_for_everyone"))
    assert_ok(m.save_draft(thread, sender, "draft body"))
    scheduled_for = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    assert_ok(m.schedule_message(thread, sender, "later", scheduled_for))
    assert_ok(m.save_shared_item(thread, message_id, sender, "media", title="photo", url="https://cdn.local/photo.jpg", mime_type="image/jpeg"))
    assert_ok(m.save_shared_item(thread, message_id, sender, "document", title="doc", url="https://cdn.local/doc.pdf", mime_type="application/pdf"))
    assert_ok(m.save_shared_item(thread, message_id, sender, "link", title="link", url="https://example.com"))
    assert len(m.list_shared_items(thread, "media")) == 1
    assert len(m.list_shared_items(thread, "document")) == 1
    assert len(m.list_shared_items(thread, "link")) == 1
    assert_ok(m.save_wallpaper(thread, sender, "neon-night"))
    assert_ok(m.save_autodownload_settings(sender, mobile_photos=True))
    assert_ok(m.save_encryption_status(thread, sender, "transport_protected"))
    print("phase30 messaging whatsapp: ok")


if __name__ == "__main__":
    main()
