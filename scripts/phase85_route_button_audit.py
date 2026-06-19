#!/usr/bin/env python3
"""Audit production-facing links, buttons, and data-action handlers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SKIP_PARTS = {"venv", "__pycache__", "backups", ".git", "node_modules"}
SKIP_FILES = {"oauth_diagnostics.html"}
SURFACE_TEMPLATES = [
    "templates/chain_home.html",
    "templates/profile/index.html",
    "templates/profile/partials/profile_header.html",
    "templates/profile/private_profile.html",
    "templates/messages/index.html",
    "templates/calls/recent.html",
    "templates/reels/index.html",
    "templates/reels/upload.html",
    "templates/live/index.html",
    "templates/live/studio.html",
    "templates/dating/index.html",
    "templates/wallet/index.html",
]
HANDLER_FILES = [
    "static/js/home_real_actions.js",
    "static/js/smart_suggestions.js",
    "static/js/profile_command_center.js",
    "static/js/friendship_controls.js",
    "static/js/namvibe_2026_home.js",
    "static/js/home_feed_mobile.js",
]
REQUIRED_ROUTES = {
    "Post": ["/posts/create", "/features/create-post"],
    "Story": ["/stories/create", "/status/create"],
    "Reel": ["/reels/upload", "/features/upload-reel"],
    "Live": ["/live/studio"],
    "Messages": ["/messages/"],
    "Calls": ["/calls/", "/calls/recent"],
    "Wallet": ["/wallet/"],
    "Dating": ["/dating/", "/dating/discover"],
    "Profile": ["/profile/"],
    "Settings": ["/settings", "/profile/settings"],
    "Security": ["/security", "/security/privacy"],
    "Notifications": ["/notifications/", "/notifications/center"],
}


def read(path):
    return (ROOT / path).read_text(errors="ignore") if (ROOT / path).exists() else ""


def route_rules():
    from app import app

    return {rule.rule for rule in app.url_map.iter_rules()}


def handler_source():
    return "\n".join(read(path) for path in HANDLER_FILES)


def audit():
    findings = []
    handlers = handler_source()
    combined = "\n".join(read(path) for path in SURFACE_TEMPLATES)

    for path in SURFACE_TEMPLATES:
        text = read(path)
        for idx, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "href=\"#\"" in stripped and not any(token in stripped for token in ("data-tab", "data-modal", "data-drawer", "onclick=")):
                findings.append(("BLOCKER", path, idx, "dead href=#", stripped[:180]))
            if "javascript:void(0)" in stripped:
                findings.append(("BLOCKER", path, idx, "javascript:void(0)", stripped[:180]))
            if re.search(r"href=[\"'][\"']", stripped):
                findings.append(("BLOCKER", path, idx, "empty href", stripped[:180]))
            if "localhost:" in stripped or "127.0.0.1:" in stripped:
                findings.append(("BLOCKER", path, idx, "hardcoded localhost", stripped[:180]))
            if re.search(r"<button\b(?![^>]*\btype=)", stripped) and "<form" in text[max(0, text.find(line) - 500):text.find(line) + 500]:
                findings.append(("WARN", path, idx, "button missing type near form", stripped[:180]))

    for action in sorted(set(re.findall(r'data-action=["\']([^"\']+)["\']', combined))):
        if action in {"copy-url", "profile-tab", "completion", "privacy", "qr", "more"}:
            continue
        if action not in handlers and f"action === '{action}'" not in handlers and f'action === "{action}"' not in handlers:
            findings.append(("BLOCKER", "templates/static", 0, f"data-action without handler: {action}", ""))

    rules = route_rules()
    for label, candidates in REQUIRED_ROUTES.items():
        if not any(route in rules for route in candidates):
            findings.append(("BLOCKER", "app.url_map", 0, f"missing route for {label}", ", ".join(candidates)))

    if 'href="/chain' in combined or "href='/chain" in combined:
        findings.append(("BLOCKER", "templates", 0, "old /chain route", ""))

    return findings


def main():
    findings = audit()
    for severity, path, line, issue, snippet in findings:
        suffix = f":{line}" if line else ""
        print(f"{severity} {path}{suffix} [{issue}] {snippet}")
    blockers = sum(1 for f in findings if f[0] == "BLOCKER")
    warnings = len(findings) - blockers
    print(f"phase85_route_button_audit: {blockers} blockers, {warnings} warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
