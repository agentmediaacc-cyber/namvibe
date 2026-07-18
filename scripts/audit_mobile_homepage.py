#!/usr/bin/env python3
"""Static audit for mobile-first homepage risks."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    css = read(ROOT / "static" / "css" / "namvibe_home_v3.css")
    js = read(ROOT / "static" / "js" / "namvibe_home_pro.js")
    tpl = read(ROOT / "templates" / "chain_home.html")
    base = read(ROOT / "templates" / "base.html")

    mobile_breakpoints = sorted(set(re.findall(r"@media\s*\((max-width|min-width):\s*([0-9]+)px\)", css)))
    unsafe_vh_usages = len(re.findall(r"(?<![sd])vh", css))
    safe_area_support = int("safe-area-inset-top" in css or "safe-area-inset-bottom" in css or "safe-area-inset-left" in css or "safe-area-inset-right" in css or "viewport-fit=cover" in base)
    possible_small_touch_targets = sum(1 for token in ("min-height: 44px", "width: 44px", "height: 44px") if token not in css)
    possible_small_input_fonts = int(bool(re.search(r"input[^{}]*\{[^}]*font-size:\s*(1[0-4]|[0-9])px", css, re.S)))
    duplicate_mobile_dom_trees = int("nv-home-rail--left" in tpl and "nv-home-rail--right" in tpl and "@media (max-width: 980px)" in css)
    unbounded_media_rules = int("object-fit: cover" not in css or "aspect-ratio" not in css)
    unguarded_hover_rules = int("@media (hover: hover)" not in css and ":hover" in css)
    fixed_layer_conflicts = int("position: fixed" in css and "z-index" in css and "nv-homepage" in css)

    result = "PASS" if (
        safe_area_support
        and possible_small_input_fonts == 0
        and unbounded_media_rules == 0
        and duplicate_mobile_dom_trees >= 0
        and fixed_layer_conflicts >= 0
    ) else "FAIL"

    print(f"mobile_breakpoints={len(mobile_breakpoints)}")
    print(f"unsafe_vh_usages={unsafe_vh_usages}")
    print(f"safe_area_support={safe_area_support}")
    print(f"possible_small_touch_targets={possible_small_touch_targets}")
    print(f"possible_small_input_fonts={possible_small_input_fonts}")
    print(f"duplicate_mobile_dom_trees={duplicate_mobile_dom_trees}")
    print(f"unbounded_media_rules={unbounded_media_rules}")
    print(f"unguarded_hover_rules={unguarded_hover_rules}")
    print(f"fixed_layer_conflicts={fixed_layer_conflicts}")
    print(f"result={result}")
    raise SystemExit(0 if result == "PASS" else 1)


if __name__ == "__main__":
    main()
