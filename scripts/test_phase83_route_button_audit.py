#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


templates = [
    path
    for path in (ROOT / "templates").rglob("*.html")
    if path.name != "oauth_diagnostics.html"
]
static_js = list((ROOT / "static/js").glob("*.js"))
combined = "\n".join(path.read_text(errors="ignore") for path in templates + static_js)

check("no hardcoded localhost links", "localhost:" not in combined and "127.0.0.1:" not in combined)
check("no old /chain route links", 'href="/chain' not in combined and "href='/chain" not in combined)

action_handlers = (ROOT / "static/js/home_real_actions.js").read_text() + "\n" + (ROOT / "static/js/profile_command_center.js").read_text()
surface_combined = "\n".join(
    (ROOT / path).read_text(errors="ignore")
    for path in [
        Path("templates/chain_home.html"),
        Path("templates/profile/index.html"),
        Path("templates/profile/partials/profile_header.html"),
    ]
)
for action in sorted(set(re.findall(r'data-action="([^"]+)"', surface_combined))):
    if action in {"copy-url", "profile-tab", "completion", "privacy", "qr", "more"}:
        continue
    check(f"data-action {action} has handler", action in action_handlers or f"action === '{action}'" in action_handlers)

bad_hrefs = []
for match in re.finditer(r'<a\b[^>]*href=["\']#["\'][^>]*>', surface_combined):
    tag = match.group(0)
    if any(token in tag for token in ("data-modal", "data-tab", "data-toggle", "role=\"button\"", "onclick=")):
        continue
    bad_hrefs.append(tag[:120])
check("no dead href=# links", not bad_hrefs)

from app import app

rules = {rule.rule for rule in app.url_map.iter_rules()}
check("/security route exists", "/security" in rules)
check("/calls route exists", "/calls/" in rules or "/calls" in rules)
