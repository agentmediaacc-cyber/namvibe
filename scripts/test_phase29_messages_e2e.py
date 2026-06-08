import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ensure_project_python():
    try:
        import dotenv  # noqa: F401
    except ModuleNotFoundError:
        venv_python = ROOT / "venv" / "bin" / "python3"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise

_ensure_project_python()

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from services import message_feature_service as messages


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main():
    sender = str(uuid.uuid4())
    receiver = str(uuid.uuid4())
    thread = messages.create_direct_thread(sender, receiver)
    assert_true(thread["ok"], "direct thread not created")
    thread_id = thread["thread_id"]

    sent = messages.send_text_message(thread_id, sender, "hello phase29")
    assert_true(sent["ok"], "message not sent")
    message_id = sent["message_id"]

    refreshed = messages.get_thread_messages(thread_id, receiver)
    assert_true(any(row["id"] == message_id for row in refreshed), "message missing after refresh")
    assert_true(messages.unread_count(receiver) >= 1, "unread count did not increase")

    assert_true(messages.mark_delivered(thread_id, receiver)["ok"], "delivered failed")
    assert_true(messages.mark_seen(thread_id, receiver)["ok"], "seen failed")
    assert_true(messages.unread_count(receiver) == 0, "unread count did not clear")
    assert_true(messages.add_reaction(message_id, receiver, "heart")["ok"], "reaction failed")
    assert_true(messages.edit_message(message_id, sender, "hello edited")["ok"], "edit failed")
    assert_true(messages.star_message(message_id, receiver, True)["ok"], "star failed")
    assert_true(messages.save_voice_note(message_id, sender, audio_url="/media/test.webm", duration_seconds=3.2, waveform=[1, 3, 2])["ok"], "voice note failed")
    assert_true(messages.save_attachment(message_id, sender, attachment_type="document", file_name="test.pdf", media_url="/media/test.pdf")["ok"], "attachment failed")
    assert_true(messages.search_messages(receiver, "edited"), "search did not find edited message")
    assert_true(messages.delete_message(message_id, sender, for_everyone=True)["ok"], "delete everyone failed")
    assert_true(not any(row["id"] == message_id for row in messages.get_thread_messages(thread_id, receiver)), "deleted message still visible")

    print("phase29 messages e2e: ok")


if __name__ == "__main__":
    main()
