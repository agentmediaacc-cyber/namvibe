#!/usr/bin/env python3
"""Static contract for the mobile homepage shell."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, re.I | re.S))


def main() -> None:
    tpl = read(ROOT / "templates" / "chain_home.html")
    css = read(ROOT / "static" / "css" / "namvibe_home_v3.css")
    js = read(ROOT / "static" / "js" / "namvibe_home_pro.js")
    base = read(ROOT / "templates" / "base.html")

    mobile_header_count = 1 if "nv-home-header" in tpl else 0
    hamburger_count = count(r"hamburger_button\(", tpl)
    global_menu_count = 1 if "namvibe_global_menu" in base else 0
    stories_count = 1 if "nv-home-stories" in tpl else 0
    composer_count = 1 if "nv-home-composer" in tpl else 0
    feed_count = 1 if 'id="nvpro-feed"' in tpl else 0
    visible_desktop_rail_count = 0 if ".nv-home-rail--left" in css and ".nv-home-rail--right" in css else 1
    safe_area_contract = "PASS" if "env(safe-area-inset-top" in css and "env(safe-area-inset-bottom" in css else "FAIL"
    viewport_unit_contract = "PASS" if "100dvh" in css or "100svh" in css else "FAIL"
    input_zoom_contract = "PASS" if "font-size: 16px" in css or "font-size: 15px" in css else "FAIL"
    touch_target_contract = "PASS" if "min-height: 44px" in css else "FAIL"
    media_bounds_contract = "PASS" if "aspect-ratio" in css and "object-fit: cover" in css else "FAIL"
    duplicate_mobile_dom_count = 0 if "nv-home-rail--left" in tpl and "nv-home-rail--right" in tpl else 1

    ok = all([
        mobile_header_count == 1,
        hamburger_count >= 1,
        global_menu_count == 1,
        stories_count == 1,
        composer_count == 1,
        feed_count == 1,
        visible_desktop_rail_count == 0,
        safe_area_contract == "PASS",
        viewport_unit_contract == "PASS",
        input_zoom_contract == "PASS",
        touch_target_contract == "PASS",
        media_bounds_contract == "PASS",
        duplicate_mobile_dom_count == 0,
    ])

    print(f"mobile_header_count={mobile_header_count}")
    print(f"hamburger_count={hamburger_count}")
    print(f"global_menu_count={global_menu_count}")
    print(f"stories_count={stories_count}")
    print(f"composer_count={composer_count}")
    print(f"feed_count={feed_count}")
    print(f"visible_desktop_rail_count={visible_desktop_rail_count}")
    print(f"safe_area_contract={safe_area_contract}")
    print(f"viewport_unit_contract={viewport_unit_contract}")
    print(f"input_zoom_contract={input_zoom_contract}")
    print(f"touch_target_contract={touch_target_contract}")
    print(f"media_bounds_contract={media_bounds_contract}")
    print(f"duplicate_mobile_dom_count={duplicate_mobile_dom_count}")
    print(f"result={'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
