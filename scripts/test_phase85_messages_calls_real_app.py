#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
messages = (ROOT / "templates/messages/index.html").read_text()
calls = (ROOT / "templates/calls/recent.html").read_text()
base = (ROOT / "templates/base.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("messages empty state is real", "No conversations yet" in messages and "No messages yet" in messages)
check("messages has requests/friends surface", "friend" in messages.lower() and "request" in messages.lower())
check("messages no fake conversations", "dummy" not in messages.lower() and "phase8" not in messages.lower())
check("calls empty/search state exists", "Search contacts to call" in calls or "No calls" in calls)
check("no global test call sound", "Test call sound" not in base and "chainSoundUnlockBtn" not in base)
check("call audio guarded", "NamVibeCallAudio" in base and "playIncoming(data)" in base)
check("call audio stops on disconnect", "disconnect" in base and "stopAll" in base)
