#!/usr/bin/env python3
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


class HomepageCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"a", "button"} or any(
            key in attrs for key in ("data-action", "data-follow-id", "data-nv-open-create")
        ):
            self.nodes.append({"tag": tag, "attrs": attrs})


def normalize_route(rule: str) -> str:
    return re.sub(r"<[^>]+>", "__param__", rule)


def route_exists(path: str, known_routes: set[str]) -> bool:
    clean = path.split("?", 1)[0].split("#", 1)[0]
    if clean in known_routes:
        return True
    parts = [part for part in clean.split("/") if part]
    for route in known_routes:
        route_parts = [part for part in route.split("/") if part]
        if len(parts) != len(route_parts):
            continue
        if all(expected == "__param__" or actual == expected for actual, expected in zip(parts, route_parts)):
            return True
    return False


def is_safe_href(href: str) -> bool:
    return href.startswith(("http://", "https://", "mailto:", "tel:", "/static/"))


def main() -> int:
    template_path = ROOT / "templates" / "chain_home.html"
    template_source = template_path.read_text()

    with app.test_client() as client:
      response = client.get("/")
      html = response.get_data(as_text=True)

    known_routes = {normalize_route(rule.rule) for rule in app.url_map.iter_rules()}
    collector = HomepageCollector()
    collector.feed(html)

    failures: list[str] = []
    rendered_actions = set(re.findall(r'data-action="([^"]+)"', html))
    create_types = re.findall(r'data-nv-create-type="([^"]+)"', html)

    if response.status_code >= 500:
        failures.append(f"homepage returned {response.status_code}")

    if 'href="#"' in html or 'href=""' in html or "javascript:void(0)" in html or "javascript:;" in html:
        failures.append("homepage still renders placeholder hrefs")

    if "data-action=" in template_source and "safeHandler(\"delegated-click\"" not in template_source:
        failures.append("homepage data-action buttons are missing delegated click handler wiring")

    if "[data-nv-open-create]" not in template_source:
        failures.append("create buttons are missing JS wiring")

    if "reportHomepageError" not in template_source:
        failures.append("homepage runtime guard was not found in template script")

    for expected in ("post", "story", "reel"):
        if expected not in create_types:
            failures.append(f"missing create trigger for {expected}")

    template_actions = set(re.findall(r'data-action="([^"]+)"', template_source))
    for action in ("like", "comment", "share", "save"):
        if action not in template_actions:
            failures.append(f"missing homepage action template: {action}")

    for node in collector.nodes:
        tag = node["tag"]
        attrs = node["attrs"]
        href = (attrs.get("href") or "").strip()
        data_action = attrs.get("data-action")
        classes = attrs.get("class", "")

        if tag == "a" and href and not is_safe_href(href) and not route_exists(href, known_routes):
            failures.append(f"unknown route rendered on homepage: {href}")

        if tag == "button" and not any(
            key in attrs for key in ("data-action", "data-follow-id", "data-nv-open-create", "data-nv-close-create", "data-upload-tab")
        ):
            if not any(
                token in classes
                for token in ("nv-tab", "nv-primary", "social-icon-btn", "nvcc-", "nv-close")
            ):
                failures.append(f"button missing handler hook: class={attrs.get('class', '<none>')}")

        if data_action:
            if data_action in {"like", "comment", "save"} and not attrs.get("data-id"):
                failures.append(f"{data_action} button missing data-id")
            if data_action == "share" and not (attrs.get("data-id") or attrs.get("data-detail-url")):
                failures.append("share button missing share target")

        if attrs.get("data-follow-id") and not attrs.get("data-following"):
            failures.append("follow button missing data-following state")

        if attrs.get("data-nv-open-create") is not None and not attrs.get("aria-label") and "nv-create-btn" in classes:
            failures.append("top create button missing aria-label")

    print("HOMEPAGE CLICK HOOK AUDIT")
    print(f"Homepage status: {response.status_code}")
    print(f"Collected nodes: {len(collector.nodes)}")
    print(f"Rendered actions: {', '.join(sorted(rendered_actions)) or 'none'}")
    print(f"Template actions: {', '.join(sorted(template_actions)) or 'none'}")
    print(f"Create types: {', '.join(sorted(set(create_types))) or 'none'}")

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nPASS")
    print("- No dead placeholder links rendered")
    print("- Homepage create, follow, and post-action hooks are present")
    print("- Rendered homepage links resolve to known routes or safe external/static URLs")
    print("- Runtime guard is present for homepage bootstrap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
