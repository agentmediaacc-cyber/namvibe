#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label, condition):
    print(("PASS" if condition else "FAIL") + f": {label}")
    if not condition:
        raise AssertionError(label)


def main():
    thread_html = (ROOT / "templates/messages/thread.html").read_text()
    index_html = (ROOT / "templates/messages/index.html").read_text()
    css = (ROOT / "static/css/namvibe_messages_pro.css").read_text()
    js = (ROOT / "static/js/namvibe_messages_pro.js").read_text()

    check("composer exists", "chat-composer" in thread_html and "msg-input" in thread_html)
    check("textarea has 16px mobile font", "font-size: 16px" in css and "textarea" in css)
    check("safe-area inset exists", "env(safe-area-inset-bottom)" in css)
    check("reply preview exists", "reply-preview" in thread_html and "data-reply-preview" in js)
    check("voice record button exists", "data-voice-record-button" in thread_html and "MediaRecorder" in js)
    check("attachment preview exists", "attachment-preview" in thread_html and "data-attachment-preview" in js)
    check("offline queue JS exists", "localStorage" in js and "offline_queue" in js and "flushOfflineQueue" in js)
    check("typing indicator exists", "typing-indicator" in thread_html and "typing:start" in js and "typing:stop" in js)
    check("inbox includes pro assets", "namvibe_messages_pro.css" in index_html and "namvibe_messages_pro.js" in index_html)
    print("test_message_mobile_ui_ok")


if __name__ == "__main__":
    main()
