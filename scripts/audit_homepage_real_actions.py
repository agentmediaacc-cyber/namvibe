#!/usr/bin/env python3
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


class ClickableCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.clickables = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"a", "button"} or "data-action" in attrs or "onclick" in attrs:
            self.clickables.append({"tag": tag, "attrs": attrs})


def normalize_route(rule: str) -> str:
    return re.sub(r"<[^>]+>", "__param__", rule)


def is_safe_href(href: str) -> bool:
    return (
        href.startswith("http://")
        or href.startswith("https://")
        or href.startswith("mailto:")
        or href.startswith("tel:")
        or href.startswith("/static/")
        or href.startswith("#upload")
    )


def route_exists(href: str, known_routes: set[str]) -> bool:
    if not href.startswith("/"):
        return False
    path = href.split("?", 1)[0].split("#", 1)[0]
    if path in known_routes:
        return True
    parts = [segment for segment in path.split("/") if segment]
    for route in known_routes:
        route_parts = [segment for segment in route.split("/") if segment]
        if len(parts) != len(route_parts):
            continue
        matched = True
        for actual, expected in zip(parts, route_parts):
            if expected == "__param__":
                continue
            if actual != expected:
                matched = False
                break
        if matched:
            return True
    return False


def main() -> int:
    template_path = ROOT / "templates" / "chain_home.html"
    js_path = ROOT / "static" / "js" / "namvibe_home_pro.js"
    template_source = template_path.read_text()
    js_source = js_path.read_text()

    with app.test_client() as client:
        response = client.get("/")
        homepage_html = response.get_data(as_text=True)

    collector = ClickableCollector()
    collector.feed(homepage_html)

    known_routes = {normalize_route(rule.rule) for rule in app.url_map.iter_rules()}
    failures: list[str] = []
    warnings: list[str] = []

    fake_href_patterns = ("#", "", "javascript:void(0)", "javascript:;")
    banned_literals = ("/messages/groups/empty",)

    for item in collector.clickables:
        tag = item["tag"]
        attrs = item["attrs"]
        href = (attrs.get("href") or "").strip()
        onclick = (attrs.get("onclick") or "").strip()
        data_action = (attrs.get("data-action") or "").strip()

        if onclick:
            failures.append(f"inline onclick remains on {tag}: {onclick[:80]}")

        if tag == "a":
            if href in fake_href_patterns:
                failures.append(f"placeholder href on anchor: {href or '<empty>'}")
            elif href and not is_safe_href(href) and not route_exists(href, known_routes):
                failures.append(f"homepage anchor points to unknown route: {href}")

            if href in banned_literals:
                failures.append(f"placeholder or generic homepage route still rendered: {href}")

        if data_action:
            handler_token = f"action === \"{data_action}\""
            if handler_token not in template_source and f"[data-action='{data_action}']" not in template_source and f"[data-action={data_action}]" not in js_source:
                failures.append(f"data-action '{data_action}' has no matching handler")

    expected_actions = {"like", "comment", "share", "save"}
    rendered_actions = set(re.findall(r'data-action="([^"]+)"', homepage_html))
    missing_actions = sorted(expected_actions - rendered_actions)
    if missing_actions:
        warnings.append(f"expected homepage actions not rendered in current response: {', '.join(missing_actions)}")

    if "/messages/upgrade/groups/empty" in homepage_html:
        warnings.append("groups link is present; verify it is intentional because the underlying blueprint is dev-only")

    if re.search(r">\s*•••\s*<", homepage_html):
        failures.append("decorative more-menu button still rendered on homepage")

    if "onclick=" in template_source:
        failures.append("chain_home.html still contains inline onclick handlers")

    print("HOMEPAGE REAL ACTIONS AUDIT")
    print(f"Rendered homepage status: {response.status_code}")
    print(f"Collected clickables: {len(collector.clickables)}")
    print(f"Rendered data-actions: {', '.join(sorted(rendered_actions)) or 'none'}")

    if warnings:
        print("\nWARNINGS")
        for warning in warnings:
            print(f"- {warning}")

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nPASS")
    print("- No placeholder hrefs rendered on homepage")
    print("- No unknown homepage routes detected")
    print("- No inline onclick handlers remain in chain_home.html")
    print("- Homepage data-action buttons have matching handlers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
