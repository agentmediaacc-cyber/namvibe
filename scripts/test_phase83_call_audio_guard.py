#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = (ROOT / "templates/base.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("global NamVibeCallAudio stopAll exists", "window.NamVibeCallAudio" in base and "stopAll" in base)
check("no global test call sound button", "Test call sound" not in base and "chainTestRing" not in base)
check("incoming call requires call id", "if (!callId) return" in base)
check("incoming call passes payload to audio guard", "playIncoming(data)" in base)
check("self caller is blocked", "callerId === currentProfileId" in base)
check("dismissed or muted calls are blocked", "dismissed[callId]" in base and "muted" in base)
check("audio stops on route changes", "pagehide" in base and "popstate" in base and "hashchange" in base)
check("audio stops on logout", "/auth/logout" in base and "stopAll()" in base)
check("audio stops on disconnect", 's.on("disconnect", function(){ if(window.NamVibeCallAudio)' in base)
check("terminal call events stop audio", "call:answered" in base and "call:rejected" in base and "call:missed" in base)
check("no unlock button injected on load", "chainSoundUnlockBtn" not in base)
