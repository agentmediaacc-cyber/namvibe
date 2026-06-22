#!/usr/bin/env python3
"""Tests mobile UI elements: incoming modal, accept/reject, 44px, safe-area."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    call_overlay = read("templates/calls/call_overlay.html")
    css = read("static/css/namvibe_calls_pro.css")
    js = read("static/js/namvibe_calls_pro.js")
    history_html = read("templates/calls/history.html")
    index_html = read("templates/calls/index.html")

    checks = []

    # Incoming call modal
    checks.append(check("incoming call modal exists", "call-overlay-incoming" in call_overlay))

    # Accept/reject buttons
    checks.append(check("accept button exists", "data-call-accept" in call_overlay))
    checks.append(check("reject button exists", "data-call-reject" in call_overlay))

    # Minimum tap target 44px
    checks.append(check("min tap target 44px", "min-width: 44px" in css or "min-height: 44px" in css))
    checks.append(check("tap target on control buttons", "min-width: 44px" in css))

    # Safe-area inset
    checks.append(check("safe-area inset exists", "safe-area-inset-bottom" in css))
    checks.append(check("safe-area top exists", "safe-area-inset-top" in css))

    # Video container
    checks.append(check("video container exists", "call-video-container" in call_overlay))
    checks.append(check("local video element exists", "call-local-video" in call_overlay))
    checks.append(check("remote video element exists", "call-remote-video" in call_overlay))

    # Call timer
    checks.append(check("call timer exists", "call-timer" in call_overlay))

    # Mute button
    checks.append(check("mute button exists", "call-mute-btn" in call_overlay))

    # Speaker button
    checks.append(check("speaker button exists", "call-speaker-btn" in call_overlay))

    # Camera switch button
    checks.append(check("camera switch button exists", "call-switch-camera-btn" in call_overlay))

    # Camera toggle
    checks.append(check("camera toggle button exists", "call-camera-btn" in call_overlay))

    # Reconnecting state
    checks.append(check("reconnecting state exists", "call-overlay-reconnecting" in call_overlay))

    # Ringtone unlock prompt
    checks.append(check("ringtone unlock prompt exists", "call-ringtone-unlock" in call_overlay))
    checks.append(check("ringtone unlock button exists", "call-ringtone-unlock-btn" in call_overlay))

    # Restart ringing function
    checks.append(check("startRinging function exists", "startRinging" in js))
    checks.append(check("stopRinging function exists", "stopRinging" in js))

    # cleanup functions
    checks.append(check("cleanupMedia function exists", "cleanupMedia" in js))
    checks.append(check("cleanupCall function exists", "cleanupCall" in js))

    # History page elements
    checks.append(check("history filter buttons exist", "call-filter-btn" in history_html))
    checks.append(check("history list exists", "call-history-list" in history_html))
    checks.append(check("callback button exists", "call-callback-btn" in history_html))
    checks.append(check("delete button exists", "call-delete-btn" in history_html))

    # Index page
    checks.append(check("calls index page exists", "calls-index-container" in index_html))

    if not all(checks):
        raise SystemExit(1)
    print("test_call_mobile_ui_ok")


if __name__ == "__main__":
    main()
