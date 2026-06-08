#!/usr/bin/env python3
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))
os.environ["FLASK_TESTING"] = "1"

from services import message_feature_service as m  # noqa: E402


def main():
    sender = str(uuid.uuid4())
    receiver = str(uuid.uuid4())
    thread_id = m.create_direct_thread(sender, receiver)["thread_id"]
    message_id = m.send_text_message(thread_id, sender, "voice preview")["message_id"]
    waveform = [0.1, 0.3, 0.8, 0.2]
    assert m.save_voice_note_draft(thread_id, sender, audio_url="local://draft.webm", duration_seconds=4.2, waveform=waveform, mime_type="audio/webm", file_size=12000, draft_state="locked")["ok"]
    saved = m.save_voice_note(message_id, sender, audio_url="local://sent.webm", duration_seconds=4.2, waveform=waveform, mime_type="audio/webm", file_size=12000, playback_speed=1.5, draft_state="sent")
    assert saved["ok"]
    assert saved["voice_note"]["waveform"] == waveform
    assert saved["voice_note"]["playback_speed"] == 1.5
    assert m.save_voice_playback_state(message_id, receiver, playback_speed=2, played=True, position_seconds=3)["ok"]
    print("phase30 voice notes: ok")


if __name__ == "__main__":
    main()
