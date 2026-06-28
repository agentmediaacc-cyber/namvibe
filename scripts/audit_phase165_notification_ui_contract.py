#!/usr/bin/env python3
"""Phase 165 audit for notification UI contract."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(errors="ignore")


def check(path, label, pattern, text):
    ok = re.search(pattern, text, re.S) is not None
    print(f"{path}: {'PASS' if ok else 'FAIL'}: {label}")
    return ok


def main():
    files = {
        "templates/notifications/index.html": read("templates/notifications/index.html"),
        "static/js/namvibe_notifications.js": read("static/js/namvibe_notifications.js"),
        "api_routes/notification_routes.py": read("api_routes/notification_routes.py"),
    }
    checks = [
        ("api_routes/notification_routes.py", "all tab", r'"key": "all"'),
        ("api_routes/notification_routes.py", "unread tab", r'"key": "unread"'),
        ("api_routes/notification_routes.py", "social tab", r'"key": "social"'),
        ("api_routes/notification_routes.py", "messages tab", r'"key": "messages"'),
        ("api_routes/notification_routes.py", "system tab", r'"key": "system"'),
        ("templates/notifications/index.html", "mark all read button", r'id="nvMarkAllBtn"'),
        ("templates/notifications/index.html", "filter pills container", r'id="nvFilters"'),
        ("static/js/namvibe_notifications.js", "sender display name rendered", r"sender_display_name"),
        ("static/js/namvibe_notifications.js", "avatar rendered", r"sender_avatar_url|sender_initials"),
        ("static/js/namvibe_notifications.js", "preview rendered", r"preview_text"),
        ("static/js/namvibe_notifications.js", "open button rendered", r"Open"),
        ("static/js/namvibe_notifications.js", "mark read button rendered", r"Mark read"),
        ("static/js/namvibe_notifications.js", "mark all read route", r"/api/notifications/read-all"),
        ("static/js/namvibe_notifications.js", "unread count route", r"/api/notifications/unread-count"),
    ]
    passed = True
    for path, label, pattern in checks:
        passed = check(path, label, pattern, files[path]) and passed
    if not passed:
        return 1
    print("PASS: phase165 notification UI contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
