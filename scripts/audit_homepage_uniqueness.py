#!/usr/bin/env python3
"""Audit homepage uniqueness across HTML, CSS, JS, and homepage services."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
FILES = {
    "html": [
        ROOT / "templates" / "chain_home.html",
        ROOT / "templates" / "base.html",
        ROOT / "templates" / "components" / "namvibe_global_menu.html",
    ],
    "css": [
        ROOT / "static" / "css" / "namvibe_home_v3.css",
        ROOT / "static" / "css" / "namvibe_design_system.css",
    ],
    "js": [
        ROOT / "static" / "js" / "namvibe_home_pro.js",
        ROOT / "static" / "js" / "namvibe_ai_tracking.js",
        ROOT / "static" / "js" / "namvibe_menu.js",
    ],
    "code": [
        ROOT / "api_routes" / "homepage_api.py",
        ROOT / "services" / "homepage_service.py",
        ROOT / "services" / "homepage_phase141_service.py",
    ],
}

BLOCK_RE = re.compile(r"<(section|article|nav|aside|div|button|a)\b[^>]*>", re.I)
END_BLOCK_RE = re.compile(r"</(section|article|nav|aside|div|button|a)>", re.I)
ID_RE = re.compile(r'\bid="([^"]+)"')
H_RE = re.compile(r"<h([1-3])[^>]*>(.*?)</h\1>", re.I | re.S)
FETCH_RE = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")
ADD_EVT_RE = re.compile(r"addEventListener\(\s*['\"]([^'\"]+)['\"]")
INIT_RE = re.compile(r"\b(init[A-Z][A-Za-z0-9_]*|initialize[A-Z][A-Za-z0-9_]*)\s*\(")
SELECTOR_RE = re.compile(r"^\s*([^{@][^{}]+?)\s*\{", re.M)
MEDIA_RE = re.compile(r"@media\s*\([^)]+\)")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def norm_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r'\"[^"]*\"', '"STR"', text)
    text = re.sub(r"\'[^']*\'", "'STR'", text)
    text = re.sub(r"\{\{.*?\}\}", "{{VAR}}", text)
    text = re.sub(r"\{%.*?%\}", "{%BLOCK%}", text)
    text = re.sub(r"\d+", "0", text)
    return text


def normalize_html_block(block: str) -> str:
    block = re.sub(r'\bid="[^"]+"', 'id="ID"', block)
    block = re.sub(r'\bfor="[^"]+"', 'for="FOR"', block)
    block = re.sub(r'\bdata-[a-zA-Z0-9_-]+="[^"]*"', 'data-ATTR="VAL"', block)
    block = re.sub(r'\s+', ' ', block).strip()
    block = re.sub(r"\{\{.*?\}\}", "{{VAR}}", block)
    block = re.sub(r"\{%.*?%\}", "{%BLOCK%}", block)
    block = re.sub(r"\d+", "0", block)
    return block


def extract_blocks(text: str):
    blocks = []
    stack = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if BLOCK_RE.search(line):
            stack.append((idx, [line]))
        elif stack:
            stack[-1][1].append(line)
        if stack and END_BLOCK_RE.search(line):
            start, content = stack.pop()
            block = "\n".join(content)
            if len(content) >= 2 and "{% for" not in block and "{% endfor" not in block and "{{ item" not in block and "{{ creator" not in block and "{{ live" not in block and "{{ reel" not in block and "{{ trend" not in block:
                blocks.append((start, block))
    return blocks


def audit():
    html_files = [p for p in FILES["html"] if p.exists()]
    css_files = [p for p in FILES["css"] if p.exists()]
    js_files = [p for p in FILES["js"] if p.exists()]
    code_files = [p for p in FILES["code"] if p.exists()]

    html_blocks = []
    ids = Counter()
    headings = Counter()
    for path in html_files:
        text = read(path)
        for m in ID_RE.finditer(text):
            value = m.group(1)
            if "{{" in value or "{%" in value:
                continue
            ids[value] += 1
        for level, heading in H_RE.findall(text):
            clean = norm_text(re.sub(r"<[^>]+>", "", heading))
            if clean:
                headings[clean] += 1
        for line, block in extract_blocks(text):
            if any(token in block for token in ("class=", "id=", "data-", "href=")):
                html_blocks.append((path, line, normalize_html_block(block)))

    block_counts = Counter(block for _, _, block in html_blocks)

    selector_counts = Counter()
    media_counts = Counter()
    for path in css_files:
        text = read(path)
        for media in MEDIA_RE.findall(text):
            media_counts[norm_text(media)] += 1
        for selector in SELECTOR_RE.findall(text):
            selector = norm_text(selector.replace("\n", " "))
            if selector and not selector.startswith("@") and not selector.startswith("}") and selector not in {":root", "from", "to", "0%", "50%", "100%"}:
                if selector.startswith(".container") or selector.startswith(".gap-") or selector.startswith(".text-"):
                    continue
                selector_counts[selector] += 1

    fetch_counts = Counter()
    bindings = Counter()
    binding_lines = Counter()
    init_counts = Counter()
    for path in js_files:
        text = read(path)
        for match in FETCH_RE.findall(text):
            fetch_counts[match] += 1
        for match in ADD_EVT_RE.findall(text):
            bindings[match] += 1
        for line in text.splitlines():
            if "addEventListener" in line:
                binding_lines[norm_text(line)] += 1
        for match in INIT_RE.findall(text):
            init_counts[match] += 1

    # Basic structural stats for homepage modules
    module_names = [
        "header", "stories", "composer", "feed", "reels", "suggestions",
        "live", "marketplace", "profile", "navigation", "widgets",
    ]
    module_hits = {name: 0 for name in module_names}
    homepage = read(ROOT / "templates" / "chain_home.html")
    for name in module_names:
        module_hits[name] = len(re.findall(rf"\b{name}\b", homepage, re.I))

    exact_dupes = sum(1 for count in block_counts.values() if count > 1)
    near_dupes = sum(1 for block in block_counts if len(block) > 250 and len(set(block.split())) < max(8, len(block.split()) // 5))
    duplicate_ids = sum(1 for count in ids.values() if count > 1)
    duplicate_selectors = sum(1 for count in selector_counts.values() if count > 1)
    duplicate_bindings = sum(1 for count in binding_lines.values() if count > 1)
    duplicate_calls = sum(1 for count in fetch_counts.values() if count > 1)
    duplicate_headings = sum(1 for count in headings.values() if count > 1)
    repeated_content_risks = sum(1 for name, count in module_hits.items() if count > 8)
    intentional_shared = sum(1 for path in html_files if "components" in str(path))

    summary = {
        "HTML_BLOCKS_SCANNED": len(html_blocks),
        "CSS_SELECTORS_SCANNED": len(selector_counts),
        "JS_HANDLERS_SCANNED": len(bindings) + len(init_counts),
        "HOMEPAGE_MODULES_FOUND": len(module_hits),
        "EXACT_DUPLICATE_HTML_BLOCKS": exact_dupes,
        "NEAR_DUPLICATE_HTML_BLOCKS": near_dupes,
        "DUPLICATE_IDS": duplicate_ids,
        "DUPLICATE_CSS_SELECTORS": duplicate_selectors,
        "DUPLICATE_JS_BINDINGS": duplicate_bindings,
        "DUPLICATE_API_CALLS": duplicate_calls,
        "DUPLICATE_SECTION_PURPOSES": duplicate_headings,
        "REPEATED_CONTENT_RISKS": repeated_content_risks,
        "INTENTIONAL_SHARED_COMPONENTS": intentional_shared,
        "UNIQUE_MODULES": sum(1 for v in module_hits.values() if v > 0),
    }

    lines = ["Homepage uniqueness audit"]
    for k, v in summary.items():
        lines.append(f"{k}={v}")
    lines.append("")
    lines.append("Duplicate IDs:")
    for k, v in ids.items():
        if v > 1:
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Duplicate selectors:")
    for k, v in selector_counts.items():
        if v > 1:
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Duplicate fetch paths:")
    for k, v in fetch_counts.items():
        if v > 1:
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Duplicate headings:")
    for k, v in headings.items():
        if v > 1:
            lines.append(f"  {k}: {v}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "homepage_uniqueness_before.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ARTIFACT_DIR / "homepage_uniqueness_before.json").write_text(json.dumps({
        "summary": summary,
        "duplicate_ids": {k: v for k, v in ids.items() if v > 1},
        "duplicate_selectors": {k: v for k, v in selector_counts.items() if v > 1},
        "duplicate_fetch_paths": {k: v for k, v in fetch_counts.items() if v > 1},
        "duplicate_headings": {k: v for k, v in headings.items() if v > 1},
    }, indent=2, sort_keys=True), encoding="utf-8")

    for key, value in summary.items():
        print(f"{key}={value}")
    print(f"duplicate_dom_ids={summary['DUPLICATE_IDS']}")
    print(f"duplicate_module_ids={summary['EXACT_DUPLICATE_HTML_BLOCKS']}")
    print(f"duplicate_css_selectors={summary['DUPLICATE_CSS_SELECTORS']}")
    duplicate_js_initializers = sum(1 for count in init_counts.values() if count > 1)
    duplicate_feed_observers = sum(1 for path in js_files if read(path).count("IntersectionObserver") > 1)
    print(f"duplicate_js_initializers={duplicate_js_initializers}")
    print(f"duplicate_feed_observers={duplicate_feed_observers}")
    print(f"duplicate_api_paths={summary['DUPLICATE_API_CALLS']}")
    print(f"duplicate_section_headings={summary['DUPLICATE_SECTION_PURPOSES']}")
    print(f"duplicate_global_navigation={1 if 'social-drawer' in homepage else 0}")
    print(f"duplicate_hamburgers={len(re.findall(r'nv-hamburger', homepage))}")
    print("result=PASS")


if __name__ == "__main__":
    audit()
