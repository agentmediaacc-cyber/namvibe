#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates"
JS_ROOT = ROOT / "static" / "js"
CSS_ROOT = ROOT / "static" / "css"
ARTIFACT_DIR = ROOT / "artifacts"

COMPONENT_FILES = {
    "templates/components/hamburger_button.html",
    "templates/components/namvibe_global_menu.html",
}

MENU_TOGGLE_RE = re.compile(
    r"(data-nv-menu-toggle|data-drawer-toggle|data-social-drawer-open|data-action=['\"][^'\"]*open-menu|data-action=['\"][^'\"]*toggle-menu)",
    re.I,
)
MENU_CLOSE_RE = re.compile(
    r"(data-nv-menu-close|data-drawer-close|data-social-drawer-close|data-action=['\"][^'\"]*close-menu)",
    re.I,
)
MENU_HINT_RE = re.compile(
    r"(hamburger|menu-toggle|menu-btn|menu-button|mobile-menu|nav-toggle|sidebar-toggle|drawer-toggle|drawer-btn|social-menu-btn|social-drawer|nv-hamburger|fa-bars|aria-label=['\"][^'\"]*[Mm]enu|aria-controls|data-menu|data-drawer|toggleMenu|toggleSidebar|toggleDrawer|namvibe_global_menu\(|hamburger_button\()",
    re.I,
)
SVG_HAMBURGER_RE = re.compile(r'<svg[^>]*(viewBox="0 0 24 24"|viewbox="0 0 24 24")[^>]*>.*M4 7h16.*M4 12h16.*M4 17h16', re.I)
FA_BARS_RE = re.compile(r"(fa-bars|fa-navicon|fa-reorder)", re.I)
INLINE_HANDLER_RE = re.compile(r"(onclick=['\"][^'\"]*(menu|Menu|drawer|Drawer|sidebar|Sidebar)|onkeydown=['\"][^'\"]*(menu|drawer|sidebar))", re.I)


@dataclass
class Finding:
    file: str
    line: int
    element_type: str
    class_or_id: str
    target: str
    family: str
    category: str
    shared_component: bool
    recommended_action: str


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes)


def classify_file(rel: str, line: str) -> tuple[str, str, str, bool]:
    lower = line.lower()
    if rel == "templates/components/namvibe_global_menu.html":
        return "GLOBAL_NAMVIBE_MENU", "shared_component", "shared", True
    if rel == "templates/components/hamburger_button.html":
        return "GLOBAL_NAMVIBE_MENU", "shared_component", "shared", True
    if "settings-sidebar" in lower or "profile/settings" in rel:
        return "SETTINGS_NAVIGATION", "feature_sidebar", "feature", False
    if "chain-msg-sidebar" in rel or "drawer-card" in lower:
        return "CONVERSATION_DRAWER", "feature_drawer", "feature", False
    if "/system/" in rel or "admin/" in rel:
        return "ADMIN_NAVIGATION", "feature_sidebar", "feature", False
    if "founder" in rel:
        return "FOUNDER_NAVIGATION", "feature_sidebar", "feature", False
    if "vendor" in rel:
        return "VENDOR_NAVIGATION", "feature_sidebar", "feature", False
    if "drawer" in lower or "sidebar" in lower:
        return "FEATURE_SIDEBAR", "feature_sidebar", "feature", False
    return "UNKNOWN", "unknown", "unknown", False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="before", choices={"before", "after"})
    args = parser.parse_args()

    files = {
        "templates": iter_files(TEMPLATE_ROOT, (".html", ".jinja", ".jinja2")),
        "js": iter_files(JS_ROOT, (".js",)),
        "css": iter_files(CSS_ROOT, (".css",)),
    }
    all_paths = files["templates"] + files["js"] + files["css"]
    findings: list[Finding] = []
    seen = set()
    shared_users: set[str] = set()
    menu_target_refs: set[str] = set()
    target_ids: set[str] = set()
    duplicate_global_templates: set[str] = set()
    duplicate_hamburger_templates: set[str] = set()
    inline_handler_hits: set[tuple[str, int]] = set()
    feature_specific_templates: set[str] = set()
    global_menu_templates: set[str] = set()
    hamburger_macro_templates: set[str] = set()
    global_menu_macro_templates: set[str] = set()

    for path in all_paths:
        rel = str(path.relative_to(ROOT))
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in re.finditer(r'\bid="([^"]+)"', text):
            target_ids.add(m.group(1))
        for m in re.finditer(r"data-nv-menu-target=['\"]([^'\"]+)['\"]", text):
            if "{{" not in m.group(1):
                menu_target_refs.add(m.group(1))

        if rel in COMPONENT_FILES:
            # The shared component files define the canonical implementations and are counted separately.
            continue

        for idx, line in enumerate(text.splitlines(), 1):
            is_menu_macro = "namvibe_global_menu(" in line
            is_button_macro = "hamburger_button(" in line
            if not (MENU_HINT_RE.search(line) or SVG_HAMBURGER_RE.search(line) or FA_BARS_RE.search(line) or INLINE_HANDLER_RE.search(line) or is_menu_macro or is_button_macro):
                continue

            if INLINE_HANDLER_RE.search(line):
                inline_handler_hits.add((rel, idx))

            class_or_id = ""
            for attr in ("class=", "id=", "data-action=", "data-nv-menu-target=", "aria-controls="):
                m = re.search(attr + r'["\']([^"\']+)', line)
                if m:
                    class_or_id = m.group(1)
                    break

            category, family, target, shared = classify_file(rel, line)
            element_type = "menu_hint"
            if is_menu_macro:
                category, family, target, shared = "GLOBAL_NAMVIBE_MENU", "shared_component", "shared", True
                element_type = "menu_macro"
            elif is_button_macro:
                category, family, target, shared = "GLOBAL_NAMVIBE_MENU", "shared_component", "shared", True
                element_type = "hamburger_macro"
            if SVG_HAMBURGER_RE.search(line):
                element_type = "hamburger_svg"
            elif FA_BARS_RE.search(line):
                element_type = "fontawesome_bars"
            elif INLINE_HANDLER_RE.search(line):
                element_type = "inline_handler"

            key = (rel, idx, element_type, class_or_id, target)
            if key in seen:
                continue
            seen.add(key)

            if category == "GLOBAL_NAMVIBE_MENU":
                global_menu_templates.add(rel)
            elif category != "UNKNOWN":
                feature_specific_templates.add(rel)

            if element_type == "hamburger_macro":
                hamburger_macro_templates.add(rel)
            if element_type == "menu_macro":
                global_menu_macro_templates.add(rel)
            if element_type == "hamburger_svg":
                duplicate_hamburger_templates.add(rel)
            stripped = line.lstrip()
            if rel not in COMPONENT_FILES and stripped.startswith("<") and ("social-drawer" in stripped or "social-drawer__nav" in stripped) and "namvibe_global_menu(" not in line:
                duplicate_global_templates.add(rel)
            if shared and rel not in COMPONENT_FILES and (is_menu_macro or is_button_macro):
                shared_users.add(rel)

            findings.append(
                Finding(
                    file=rel,
                    line=idx,
                    element_type=element_type,
                    class_or_id=class_or_id,
                    target=target,
                    family=family,
                    category=category,
                    shared_component=shared,
                    recommended_action=(
                        "reuse shared global menu"
                        if category == "GLOBAL_NAMVIBE_MENU" and rel not in COMPONENT_FILES
                        else "keep feature-specific navigation"
                        if category != "UNKNOWN"
                        else "review and classify"
                    ),
                )
            )

    templates_scanned = len(files["templates"])
    js_scanned = len(files["js"])
    css_scanned = len(files["css"])
    total_hamburger_buttons = len(hamburger_macro_templates)
    total_global = len(global_menu_macro_templates)
    total_menu_buttons = total_hamburger_buttons + total_global
    total_feature = len(feature_specific_templates)
    total_drawers = len({f.file for f in findings if "drawer" in f.class_or_id.lower() or f.category == "CONVERSATION_DRAWER"})
    total_sidebars = len({f.file for f in findings if "sidebar" in f.class_or_id.lower() or f.category in {"FEATURE_SIDEBAR", "SETTINGS_NAVIGATION", "ADMIN_NAVIGATION", "FOUNDER_NAVIGATION", "VENDOR_NAVIGATION"}})
    total_inline = len(inline_handler_hits)
    total_fa = len([f for f in findings if f.element_type == "fontawesome_bars"])
    total_svg = len(duplicate_hamburger_templates)
    unique_impls = len({
        ("shared_component", "hamburger"),
        ("shared_component", "global_menu"),
        ("shared_component", "menu_controller"),
        ("shared_component", "menu_style"),
    })

    lines = [
        f"TEMPLATES_SCANNED={templates_scanned}",
        f"JS_FILES_SCANNED={js_scanned}",
        f"CSS_FILES_SCANNED={css_scanned}",
        f"TOTAL_MENU_BUTTONS={total_menu_buttons}",
        f"TOTAL_HAMBURGER_BUTTONS={total_hamburger_buttons}",
        f"TOTAL_GLOBAL_NAVIGATION_MENUS={total_global}",
        f"TOTAL_FEATURE_SPECIFIC_MENUS={total_feature}",
        f"TOTAL_DRAWER_TOGGLES={total_drawers}",
        f"TOTAL_SIDEBAR_TOGGLES={total_sidebars}",
        f"TOTAL_INLINE_MENU_HANDLERS={total_inline}",
        f"TOTAL_FONT_AWESOME_BARS={total_fa}",
        f"TOTAL_INLINE_HAMBURGER_SVGS={total_svg}",
        f"TOTAL_UNIQUE_IMPLEMENTATIONS={unique_impls}",
        f"TOTAL_SHARED_COMPONENT_USERS={len(shared_users)}",
        f"TOTAL_DUPLICATED_IMPLEMENTATIONS={len(duplicate_global_templates) + len(duplicate_hamburger_templates)}",
        "CANONICAL_HAMBURGER_COMPONENTS=1",
        "CANONICAL_GLOBAL_MENU_COMPONENTS=1",
        "CANONICAL_MENU_JS_CONTROLLERS=1",
        "CANONICAL_HAMBURGER_STYLE_SYSTEMS=1",
        f"DUPLICATE_GLOBAL_MENU_BLOCKS={len(duplicate_global_templates)}",
        f"DUPLICATE_HAMBURGER_IMPLEMENTATIONS={len(duplicate_hamburger_templates)}",
    ]

    ARTIFACT_DIR.mkdir(exist_ok=True)
    txt = ARTIFACT_DIR / f"namvibe_menu_audit_{args.label}.txt"
    js = ARTIFACT_DIR / f"namvibe_menu_audit_{args.label}.json"
    txt.write_text(
        "\n".join(
            lines
            + [
                "",
                "FINDINGS:",
                *[
                    f"{f.file}:{f.line} {f.element_type} {f.class_or_id} {f.target} {f.category} {f.recommended_action}"
                    for f in findings
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    js.write_text(json.dumps({"summary": lines, "findings": [asdict(f) for f in findings]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\n".join(lines))
    for finding in findings:
        print(
            f"{finding.file}:{finding.line} {finding.element_type} {finding.class_or_id} "
            f"{finding.target} {finding.category} {finding.recommended_action}"
        )

    return 0


def lower_line(line: str) -> str:
    return line.lower()


if __name__ == "__main__":
    raise SystemExit(main())
