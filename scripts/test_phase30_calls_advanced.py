#!/usr/bin/env python3
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))
os.environ["FLASK_TESTING"] = "1"

from services import call_feature_service as c  # noqa: E402


def main():
    caller = str(uuid.uuid4())
    receiver = str(uuid.uuid4())
    audio = c.start_call(caller, receiver, "audio")
    assert audio["ok"], audio
    call_id = audio["call"]["id"]
    assert c.answer_call(call_id, receiver)["ok"]
    time.sleep(0.01)
    assert c.record_quality_event(call_id, caller, "network", 0.9, {"screen_share": False})["ok"]
    assert c.record_event(call_id, caller, "screen-share", {"enabled": True})["ok"]
    assert c.record_event(call_id, caller, "reconnect", {"state": "connected"})["ok"]
    assert c.end_call(call_id, caller)["ok"]

    video = c.start_call(caller, receiver, "video")
    assert video["ok"], video
    assert c.end_call(video["call"]["id"], caller, status="missed")["ok"]

    group = c.start_group_call(caller, [receiver, str(uuid.uuid4())], "video")
    assert group["ok"], group
    group_id = group["call"]["id"]
    assert c.add_participant(group_id, str(uuid.uuid4()), "invited")["ok"]
    assert c.record_call_waiting(group_id, receiver, str(uuid.uuid4()))["ok"]
    assert c.save_device_settings(caller, hd_enabled=True, noise_suppression=True, background_blur=True)["ok"]
    assert c.save_recording_setting(caller, allow_recording=False)["ok"]
    assert c.end_call(group_id, caller)["ok"]
    assert c.recent_calls(caller)
    print("phase30 calls advanced: ok")


if __name__ == "__main__":
    main()
