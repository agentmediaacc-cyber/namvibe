#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "chain_home.html"
CSS = ROOT / "static" / "css" / "namvibe_home_v3.css"
JS = ROOT / "static" / "js" / "namvibe_home_pro.js"
BASE = ROOT / "templates" / "base.html"
MENU_JS = ROOT / "static" / "js" / "namvibe_menu.js"
MENU_COMPONENT = ROOT / "templates" / "components" / "namvibe_global_menu.html"
HAMBURGER_COMPONENT = ROOT / "templates" / "components" / "hamburger_button.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    if detail:
        print(f"{label}={status} {detail}")
    else:
        print(f"{label}={status}")
    return ok


def main() -> int:
    failures = 0

    tpl = read(TEMPLATE)
    css = read(CSS)
    js = read(JS)
    base = read(BASE)
    menu_js = read(MENU_JS)
    menu_component = read(MENU_COMPONENT)
    hamburger_component = read(HAMBURGER_COMPONENT)

    template_extends_base = "{% extends \"base.html\" %}" in tpl
    shared_navigation = 'namvibe_global_menu' in base and 'namvibe_menu.js' in base and 'hamburger_button' in base
    stylesheet_contract = tpl.count("/static/css/namvibe_home_v3.css") == 1 and "nv-homepage-v3" in css
    controller_contract = tpl.count("/static/js/namvibe_home_pro.js") == 1 and "nvpro-feed" in js and "window.__NAMVIBE_HOME_PRO_INITIALIZED__" in js
    real_data_contract = all(token in tpl for token in ("stories", "feed_items", "reels", "live_rooms", "suggested_people")) and "placeholder" not in tpl.lower()
    responsive_contract = all(token in css for token in (
        "@media (max-width: 1240px)",
        "@media (max-width: 980px)",
        "@media (max-width: 640px)",
        "@media (max-width: 520px)",
        "grid-template-columns: minmax(240px, 272px) minmax(0, 1fr) minmax(296px, 340px)",
        "grid-template-columns: minmax(0, 1fr)",
    ))
    duplicate_controller_count = tpl.count("/static/js/namvibe_home_pro.js") - 1
    hardcoded_fake_content_count = sum(
        count(pattern, tpl)
        for pattern in (r"\bfake\b", r"\bdemo\b", r"\bplaceholder\b", r"\btest user\b")
    )
    global_menu_instances = count(r"namvibe_global_menu", base + tpl)
    shared_global_menu_users = count(r"hamburger_button\(", base + tpl)
    feature_specific_menus = count(r"nv-rail-nav|nv-home-bottom-nav|nv-home-composer", tpl)
    unique_hamburger_implementations = 1 if "hamburger_button" in hamburger_component and "data-nv-menu-toggle" in hamburger_component else 0
    duplicate_global_menu_blocks = max(0, count(r"nav class=\"nv-rail-nav\"", tpl) - 1)
    duplicate_hamburger_implementations = count(r"fa-bars|fa-navicon|fa-reorder|<svg[^>]*viewBox=\"0 0 24 24\"[^>]*>\s*<path d=\"M4 7h16M4 12h16M4 17h16\"/>", tpl + css + js)
    missing_targets = 0
    targets = re.findall(r'data-nv-menu-target="([^"]+)"', base + tpl)
    for target in targets:
        if target and target not in (base + tpl):
            missing_targets += 1

    failures += 0 if check("homepage_template", template_extends_base, "extends base.html") else 1
    failures += 0 if check("shared_navigation", shared_navigation, "shared menu and drawer wiring present") else 1
    failures += 0 if check("stylesheet_contract", stylesheet_contract, "premium stylesheet loaded once") else 1
    failures += 0 if check("controller_contract", controller_contract, "one active homepage controller") else 1
    failures += 0 if check("real_data_contract", real_data_contract, "real feed/stories/reels data referenced") else 1
    failures += 0 if check("responsive_contract", responsive_contract, "desktop and mobile layout rules present") else 1

    print(f"duplicate_controller_count={duplicate_controller_count}")
    print(f"hardcoded_fake_content_count={hardcoded_fake_content_count}")
    print(f"global_menu_instances={global_menu_instances}")
    print(f"shared_global_menu_users={shared_global_menu_users}")
    print(f"feature_specific_menus={feature_specific_menus}")
    print(f"unique_hamburger_implementations={unique_hamburger_implementations}")
    print(f"duplicate_global_menu_blocks={duplicate_global_menu_blocks}")
    print(f"duplicate_hamburger_implementations={duplicate_hamburger_implementations}")
    print(f"missing_targets={missing_targets}")

    result_ok = (
        unique_hamburger_implementations == 1
        and duplicate_global_menu_blocks == 0
        and duplicate_hamburger_implementations == 0
        and missing_targets == 0
        and duplicate_controller_count == 0
        and hardcoded_fake_content_count == 0
        and failures == 0
    )
    print(f"result={'PASS' if result_ok else 'FAIL'}")
    return 0 if result_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
