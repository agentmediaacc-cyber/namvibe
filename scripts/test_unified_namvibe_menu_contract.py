#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
STATIC_JS = ROOT / "static" / "js"
STATIC_CSS = ROOT / "static" / "css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _files(root: Path, suffix: str):
    return sorted(p for p in root.rglob(f"*{suffix}") if p.is_file())


def _search(pattern: str, paths):
    rx = re.compile(pattern, re.I | re.M)
    hits = []
    for path in paths:
        text = _read(path)
        for lineno, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append((path, lineno, line))
    return hits


def main() -> int:
    template_files = _files(TEMPLATES, ".html") + _files(TEMPLATES, ".jinja") + _files(TEMPLATES, ".jinja2")
    non_component_templates = [
        path for path in template_files
        if path.relative_to(ROOT) not in {
            Path("templates/components/hamburger_button.html"),
            Path("templates/components/namvibe_global_menu.html"),
        }
    ]
    js_files = _files(STATIC_JS, ".js")
    css_files = _files(STATIC_CSS, ".css")

    hamburger_macro = TEMPLATES / "components" / "hamburger_button.html"
    global_menu_macro = TEMPLATES / "components" / "namvibe_global_menu.html"
    menu_js = STATIC_JS / "namvibe_menu.js"
    menu_css = STATIC_CSS / "namvibe_design_system.css"

    errors = []

    for path in (hamburger_macro, global_menu_macro, menu_js, menu_css):
        if not path.exists():
            errors.append(f"missing:{path.relative_to(ROOT)}")

    template_text = "\n".join(_read(path) for path in template_files)
    js_text = "\n".join(_read(path) for path in js_files)

    copied_svg_hits = _search(
        r'<svg[^>]*viewBox="0 0 24 24"[^>]*>\s*<path d="M4 7h16M4 12h16M4 17h16"></path>\s*</svg>',
        non_component_templates,
    )
    inline_onclick_hits = _search(r'onclick=["\'].*(toggleMenu|toggleSidebar|toggleDrawer|openMenu|closeMenu|open-menu|close-menu|drawer|sidebar)', template_files)
    fa_bars_hits = _search(r'fa-(bars|navicon|reorder)', template_files)
    target_hits = _search(r'data-nv-menu-target="([^"]+)"', template_files)
    toggle_hits = _search(r'(data-nv-menu-toggle|data-drawer-toggle|data-social-drawer-open|data-action=["\'][^"\']*(open-menu|toggle-menu))', template_files)

    targets = {
        m.group(1)
        for m in re.finditer(r'data-nv-menu-target="([^"]+)"', template_text)
        if "{{" not in m.group(1)
    }
    target_ids = {
        m.group(1)
        for m in re.finditer(r'\bid="([^"]+)"', template_text)
    }
    missing_targets = sorted(targets - target_ids)

    shared_global_menu_users = [
        str(path.relative_to(ROOT))
        for path in non_component_templates
        if "namvibe_global_menu(" in _read(path)
    ]
    global_menu_instances = len(_search(r"namvibe_global_menu\(", non_component_templates))
    hamburger_macro_uses = len(_search(r"hamburger_button\(", non_component_templates))
    unique_hamburger_impls = 1 if hamburger_macro.exists() and menu_css.exists() else 0
    duplicate_global_menu_blocks = len(_search(r'^\s*<[^>]+(?:social-drawer|social-drawer__nav)', non_component_templates))
    duplicate_hamburger_implementations = len(copied_svg_hits)
    feature_specific_menus = len(_search(r"nvpro-settings-sidebar|chain-msg-sidebar|drawer-card|nv-menu-btn|nv-mobile-drawer|nvMobileMenu|nvpro-sidebar", non_component_templates + js_files))

    if not hamburger_macro.exists() or not global_menu_macro.exists():
        errors.append("shared_component_missing")
    if not menu_js.exists():
        errors.append("menu_js_missing")
    if not menu_css.exists():
        errors.append("menu_css_missing")
    if inline_onclick_hits:
        errors.append("inline_menu_handlers_present")
    if fa_bars_hits:
        errors.append("fa_bars_present")
    if missing_targets:
        errors.append("missing_targets:" + ",".join(missing_targets))
    if duplicate_global_menu_blocks != 0:
        errors.append(f"duplicate_global_menu_blocks={duplicate_global_menu_blocks}")
    if duplicate_hamburger_implementations != 0:
        errors.append(f"duplicate_hamburger_implementations={duplicate_hamburger_implementations}")

    print(f"templates_scanned={len(template_files)}")
    print(f"menu_buttons_found={hamburger_macro_uses + global_menu_instances}")
    print(f"global_menu_instances={global_menu_instances}")
    print(f"shared_global_menu_users={len(shared_global_menu_users)}")
    print(f"feature_specific_menus={feature_specific_menus}")
    print(f"unique_hamburger_implementations={unique_hamburger_impls}")
    print(f"duplicate_global_menu_blocks={duplicate_global_menu_blocks}")
    print(f"duplicate_hamburger_implementations={duplicate_hamburger_implementations}")
    print(f"missing_targets={len(missing_targets)}")

    if errors:
        print("result=FAIL")
        for err in errors:
            print(f"error={err}")
        return 1

    print("result=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
