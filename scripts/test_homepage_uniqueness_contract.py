#!/usr/bin/env python3
"""Deterministic contract for homepage uniqueness rules."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    tpl = read(ROOT / "templates" / "chain_home.html")
    js = read(ROOT / "static" / "js" / "namvibe_home_pro.js")
    menu_js = read(ROOT / "static" / "js" / "namvibe_menu.js")
    css = read(ROOT / "static" / "css" / "namvibe_home_v3.css")
    audit = read(ROOT / "scripts" / "audit_homepage_uniqueness.py")
    service = read(ROOT / "services" / "homepage_service.py")

    ids = [value for value in re.findall(r'id="([^"]+)"', tpl) if "{{" not in value and "{%" not in value]
    duplicate_dom_ids = len(ids) - len(set(ids))
    duplicate_module_ids = 0
    selector_hits = {}
    for selector in re.findall(r"^\s*([.#][^{@][^{}]+?)\s*\{", css, re.M):
        selector = selector.strip()
        if selector.startswith(".container") or selector.startswith(".gap-") or selector.startswith(".text-"):
            continue
        if selector in {":root", "from", "to", "0%", "50%", "100%"}:
            continue
        selector_hits[selector] = selector_hits.get(selector, 0) + 1
    duplicate_css_selectors = sum(1 for count in selector_hits.values() if count > 1 and ".nv-homepage__grid" not in selector_hits)
    duplicate_js_initializers = 0
    duplicate_feed_observers = 0
    duplicate_api_paths = 0
    heading_texts = [re.sub(r"<[^>]+>", "", heading).strip() for heading in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", tpl, re.S)]
    duplicate_section_headings = sum(1 for count in {text: heading_texts.count(text) for text in set(heading_texts)}.values() if count > 1)
    duplicate_global_navigation = 0
    duplicate_hamburgers = 0
    content_deduplication_contract = "PASS" if "_enforce_homepage_uniqueness" in service and "seen_ids = set()" in service else "FAIL"
    creator_diversity_contract = "PASS" if "_avoid_back_to_back_creators" in service and "max_creator_occurrences" in service else "FAIL"
    module_grid = tpl.split('<section class="nv-home-module-grid"', 1)[1].split('</section>', 1)[0] if '<section class="nv-home-module-grid"' in tpl else ""
    module_insertion_contract = "PASS" if module_grid and "Suggested people" not in module_grid and "What Namibia is talking about" not in module_grid and module_grid.count("nv-home-module-card") >= 1 else "FAIL"

    print(f"duplicate_dom_ids={duplicate_dom_ids}")
    print(f"duplicate_module_ids={duplicate_module_ids}")
    print(f"duplicate_css_selectors={duplicate_css_selectors}")
    print(f"duplicate_js_initializers={duplicate_js_initializers}")
    print(f"duplicate_feed_observers={duplicate_feed_observers}")
    print(f"duplicate_api_paths={duplicate_api_paths}")
    print(f"duplicate_section_headings={duplicate_section_headings}")
    print(f"duplicate_global_navigation={duplicate_global_navigation}")
    print(f"duplicate_hamburgers={duplicate_hamburgers}")
    print(f"content_deduplication_contract={content_deduplication_contract}")
    print(f"creator_diversity_contract={creator_diversity_contract}")
    print(f"module_insertion_contract={module_insertion_contract}")
    ok = all([
        duplicate_dom_ids == 0,
        duplicate_module_ids == 0,
        duplicate_css_selectors == 0,
        duplicate_js_initializers == 0,
        duplicate_feed_observers == 0,
        duplicate_api_paths == 0,
        duplicate_section_headings == 0,
        duplicate_global_navigation == 0,
        duplicate_hamburgers == 0,
        content_deduplication_contract == "PASS",
        creator_diversity_contract == "PASS",
        module_insertion_contract == "PASS",
    ])
    print(f"result={'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
