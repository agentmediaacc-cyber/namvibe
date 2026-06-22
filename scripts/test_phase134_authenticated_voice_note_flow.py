#!/usr/bin/env python3
import os
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import TEST_PREFIX, get_credentials, has_credentials, load_context, login, make_session, print_header, request_json, Results, unique_test_id, warn_missing_credentials

R = Results()
print_header("PHASE 134 - AUTHENTICATED VOICE NOTE FLOW")
TMP = Path(__file__).resolve().parents[1] / "tmp"


def make_wav():
    TMP.mkdir(exist_ok=True)
    path = TMP / "phase134_voice_note.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        frames = b"".join(struct.pack("<h", 0) for _ in range(800))
        handle.writeframes(frames)
    return path


if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated voice note flow skipped")
else:
    creds, context = get_credentials(), load_context()
    thread_id = context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID")
    if not thread_id:
        R.warn("missing disposable thread id; voice note upload skipped")
    else:
        s = make_session()
        response = login(s, creds["user_a"])
        if "/auth/login" in response.url:
            R.fail("user A login failed")
        else:
            R.ok("user A login")
        wav = make_wav()
        with wav.open("rb") as handle:
            res, data = request_json(s, "POST", f"/messages/api/thread/{thread_id}/voice-note", {"seconds": "1", "body": f"{TEST_PREFIX}{unique_test_id()} voice"}, {"audio": (wav.name, handle, "audio/wav")})
        if res.status_code >= 500:
            R.fail(f"voice note upload returned {res.status_code}")
        elif res.status_code in (200, 201):
            R.ok("voice note upload endpoint works")
            if "voice" in str(data).lower() or "audio" in str(data).lower():
                R.ok("voice/audio metadata present in response")
            else:
                R.warn("voice response lacks obvious voice/audio metadata")
        elif res.status_code == 404:
            R.fail("voice note endpoint returned 404")
        else:
            R.warn(f"voice note upload returned {res.status_code}")
        R.warn("voice_note_received notification verification is async; notification flow script polls endpoints")

R.summary("PHASE 134 - AUTHENTICATED VOICE NOTE FLOW")

