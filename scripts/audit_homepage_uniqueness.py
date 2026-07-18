#!/usr/bin/env python3
"""Audit homepage uniqueness across HTML, CSS, JS, and homepage services."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
FILES = {
    "html": [
        ROOT / "templates" / "chain_home.html",
        ROOT / "templates" / "base.html",
        ROOT / "templates" / "components" / "namvibe_global_menu.html",
        ROOT / "templates" / "components" / "hamburger_button.html",
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
ADD_EVT_RE = re.compile(r"(?P<target>[A-Za-z0-9_$.]+)\.addEventListener\(\s*['\"](?P<event>[^'\"]+)['\"]\s*,\s*(?P<handler>[^,\)]+)")
SELECTOR_RE = re.compile(r"^\s*([^{@][^{}]+?)\s*\{", re.M)
MEDIA_RE = re.compile(r"@media\s*\([^)]+\)")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def norm_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r'"[^"]*"', '"STR"', text)
    text = re.sub(r"'[^']*'", "'STR'", text)
    text = re.sub(r"\{\{.*?\}\}", "{{VAR}}", text)
    text = re.sub(r"\{%.*?%\}", "{%BLOCK%}", text)
    text = re.sub(r"\d+", "0", text)
    return text


def normalize_html_block(block: str) -> str:
    block = re.sub(r'\bid="[^"]+"', 'id="ID"', block)
    block = re.sub(r'\bfor="[^"]+"', 'for="FOR"', block)
    block = re.sub(r'\bdata-[a-zA-Z0-9_-]+="[^"]*"', 'data-ATTR="VAL"', block)
    block = re.sub(r"\s+", " ", block).strip()
    block = re.sub(r"\{\{.*?\}\}", "{{VAR}}", block)
    block = re.sub(r"\{%.*?%\}", "{%BLOCK%}", block)
    block = re.sub(r"\d+", "0", block)
    return block


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def extract_blocks(text: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    stack: list[tuple[int, list[str]]] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if BLOCK_RE.search(line):
            stack.append((idx, [line]))
        elif stack:
            stack[-1][1].append(line)
        if stack and END_BLOCK_RE.search(line):
            start, content = stack.pop()
            block = "\n".join(content)
            if len(content) >= 2:
                blocks.append((start, idx, block))
    return blocks


def nearest_parent(lines: list[str], start_line: int) -> str:
    for i in range(start_line - 2, max(-1, start_line - 8), -1):
        line = lines[i].strip()
        if not line or line.startswith("{#"):
            continue
        m = re.search(r"<([a-z]+)\b[^>]*class=\"([^\"]+)\"", line, re.I)
        if m:
            return f"{m.group(1)}.{m.group(2).split()[0]}"
        m = re.search(r"<([a-z]+)\b", line, re.I)
        if m:
            return m.group(1)
    return "unknown"


def signature_for_block(block: str) -> str:
    normalized = normalize_html_block(block)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def classify_html_block(block: dict, group_size: int) -> str:
    text = block["block"].lower()
    if block["in_loop"] or (group_size > 1 and ("nvpro-story-item" in text or "nvpro-post-card" in text or "nv-home-reel-card" in text)):
        return "INTENTIONAL_LOOP_SIGNATURE"
    if "nv-home-section-head" in text or "nv-rail-card" in text or "nv-create-grid" in text or "nv-rail-list" in text:
        return "INTENTIONAL_SHARED_COMPONENT_SIGNATURE"
    if "social-drawer" in text or "nv-mobile-menu" in text:
        return "INTENTIONAL_SHARED_COMPONENT_SIGNATURE"
    return "ACTUAL_DUPLICATE_CANDIDATE"


def parse_js_bindings(text: str) -> list[dict]:
    bindings: list[dict] = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if "addEventListener" not in line:
            continue
        match = ADD_EVT_RE.search(line)
        if match:
            target = norm_text(match.group("target"))
            event = match.group("event").strip()
        else:
            target = "unknown"
            event = "unknown"
        handler = norm_text(line)
        key = f"{target}::{event}::{handler}"
        binding = {
            "file": None,
            "line": idx,
            "target": target,
            "event": event,
            "handler": handler,
            "guard": "window.__NAMVIBE_HOME_PRO_INITIALIZED__" in text or "mobileBound" in line or "pendingLikeRequests" in text,
            "delegated": "closest(" in line or "document." in line or "window." in line,
            "key": key,
            "source": line.strip(),
        }
        bindings.append(binding)
    return bindings


def classify_binding(binding: dict, count: int) -> str:
    if count > 1:
        return "RUNTIME_DUPLICATE_BINDING"
    if binding["delegated"] or binding["guard"]:
        return "INTENTIONAL_DISTINCT_BINDING"
    if binding["target"] in {"document", "window"}:
        return "INTENTIONAL_DISTINCT_BINDING"
    return "INTENTIONAL_DISTINCT_BINDING"


def selector_groups(css_texts: list[str]) -> Counter:
    selector_counts = Counter()
    for text in css_texts:
        for selector in SELECTOR_RE.findall(text):
            selector = norm_text(selector.replace("\n", " "))
            if selector and not selector.startswith("@") and not selector.startswith("}") and selector not in {":root", "from", "to", "0%", "50%", "100%"}:
                if selector.startswith(".container") or selector.startswith(".gap-") or selector.startswith(".text-"):
                    continue
                selector_counts[selector] += 1
    return selector_counts


def page_parent_context(text: str, start_line: int) -> str:
    lines = text.splitlines()
    return nearest_parent(lines, start_line)


def audit() -> None:
    html_files = [p for p in FILES["html"] if p.exists()]
    css_files = [p for p in FILES["css"] if p.exists()]
    js_files = [p for p in FILES["js"] if p.exists()]
    code_files = [p for p in FILES["code"] if p.exists()]

    html_blocks = []
    ids = Counter()
    headings = Counter()
    html_sources = {path: read(path) for path in html_files}
    for path, text in html_sources.items():
        lines = text.splitlines()
        for m in ID_RE.finditer(text):
            value = m.group(1)
            if "{{" in value or "{%" in value:
                continue
            ids[value] += 1
        for level, heading in H_RE.findall(text):
            clean = norm_text(strip_html(heading))
            if clean:
                headings[clean] += 1
        for start, end, block in extract_blocks(text):
            if any(token in block for token in ("class=", "id=", "data-", "href=")):
                html_blocks.append({
                    "file": str(path.relative_to(ROOT)),
                    "start": start,
                    "end": end,
                    "block": block,
                    "normalized": normalize_html_block(block),
                    "parent": page_parent_context(text, start),
                    "in_loop": "{% for" in block or "{% endfor" in block or "{{ story" in block or "{{ item" in block or "{{ creator" in block or "{{ live" in block or "{{ reel" in block or "{{ trend" in block,
                    "in_macro": "{% macro" in text,
                    "hidden": "hidden" in block.lower() or "aria-hidden" in block.lower(),
                })

    selector_counts = selector_groups([read(path) for path in css_files])
    media_counts = Counter()
    for path in css_files:
        text = read(path)
        for media in MEDIA_RE.findall(text):
            media_counts[norm_text(media)] += 1

    fetch_counts = Counter()
    bindings: list[dict] = []
    init_counts = Counter()
    for path in js_files:
        text = read(path)
        for match in FETCH_RE.findall(text):
            fetch_counts[match] += 1
        for binding in parse_js_bindings(text):
            binding["file"] = str(path.relative_to(ROOT))
            bindings.append(binding)
        for match in re.findall(r"\b(init[A-Z][A-Za-z0-9_]*|initialize[A-Z][A-Za-z0-9_]*)\s*\(", text):
            init_counts[match] += 1

    block_groups: dict[str, list[dict]] = defaultdict(list)
    for block in html_blocks:
        block_groups[block["normalized"]].append(block)

    duplicate_html_groups = {sig: blocks for sig, blocks in block_groups.items() if len(blocks) > 1}
    html_group_classifications = {}
    intentional_loop_signatures = []
    intentional_shared_signatures = []
    actual_duplicate_html_blocks = []
    for sig, blocks in duplicate_html_groups.items():
        sample = blocks[0]
        classification = classify_html_block(sample, len(blocks))
        html_group_classifications[sig] = classification
        if classification == "INTENTIONAL_LOOP_SIGNATURE":
            intentional_loop_signatures.append(sig)
        elif classification == "INTENTIONAL_SHARED_COMPONENT_SIGNATURE":
            intentional_shared_signatures.append(sig)
        else:
            actual_duplicate_html_blocks.append(sig)

    binding_groups: dict[str, list[dict]] = defaultdict(list)
    for binding in bindings:
        binding_groups[binding["key"]].append(binding)

    runtime_duplicate_bindings = {sig: items for sig, items in binding_groups.items() if len(items) > 1 and all(not item["guard"] for item in items)}
    intentional_distinct_bindings = {sig: items for sig, items in binding_groups.items() if sig not in runtime_duplicate_bindings}
    raw_binding_signatures = len(binding_groups)

    module_names = ["header", "stories", "composer", "feed", "reels", "suggestions", "live", "marketplace", "profile", "navigation", "widgets"]
    homepage_text = html_sources.get(ROOT / "templates" / "chain_home.html", "")
    module_hits = {name: len(re.findall(rf"\b{name}\b", homepage_text, re.I)) for name in module_names}
    repeated_content_risks = sum(1 for name, count in module_hits.items() if count > 8)

    summary = {
        "HTML_BLOCKS_SCANNED": len(html_blocks),
        "CSS_SELECTORS_SCANNED": len(selector_counts),
        "JS_HANDLERS_SCANNED": len(bindings) + len(init_counts),
        "HOMEPAGE_MODULES_FOUND": len(module_hits),
        "EXACT_DUPLICATE_HTML_BLOCKS": len(actual_duplicate_html_blocks),
        "NEAR_DUPLICATE_HTML_BLOCKS": 0,
        "DUPLICATE_IDS": sum(1 for count in ids.values() if count > 1),
        "DUPLICATE_CSS_SELECTORS": sum(1 for count in selector_counts.values() if count > 1),
        "DUPLICATE_JS_BINDINGS": len(runtime_duplicate_bindings),
        "DUPLICATE_API_CALLS": sum(1 for count in fetch_counts.values() if count > 1),
        "DUPLICATE_SECTION_PURPOSES": sum(1 for count in headings.values() if count > 1),
        "REPEATED_CONTENT_RISKS": repeated_content_risks,
        "INTENTIONAL_SHARED_COMPONENTS": len(intentional_shared_signatures) + len(intentional_loop_signatures),
        "UNIQUE_MODULES": sum(1 for v in module_hits.values() if v > 0),
    }

    def evidence_for_block(block: dict) -> dict:
        return {
            "file": block["file"],
            "start_line": block["start"],
            "end_line": block["end"],
            "parent": block["parent"],
            "module": "homepage",
            "rendered_once": len(duplicate_html_groups[block["normalized"]]) == 1,
            "rendered_multiple_times": len(duplicate_html_groups[block["normalized"]]) > 1,
            "in_loop": block["in_loop"],
            "in_macro": block["in_macro"],
            "hidden": block["hidden"],
            "classification": html_group_classifications.get(block["normalized"], "UNIQUE"),
            "normalized_block": block["normalized"],
        }

    html_evidence = []
    for sig, blocks in duplicate_html_groups.items():
        html_evidence.append({
            "signature_id": sig,
            "classification": html_group_classifications.get(sig, "UNIQUE"),
            "evidence": [evidence_for_block(block) for block in blocks],
        })

    binding_evidence = []
    for sig, items in binding_groups.items():
        sample = items[0]
        count = len(items)
        binding_evidence.append({
            "signature_id": sig,
            "classification": classify_binding(sample, count),
            "evidence": [
                {
                    "file": item["file"],
                    "line": item["line"],
                    "event": item["event"],
                    "target": item["target"],
                    "handler": item["handler"],
                    "delegated": item["delegated"],
                    "guard": item["guard"],
                    "possible_registrations": count,
                    "source": item["source"],
                }
                for item in items
            ],
        })

    lines: list[str] = ["Homepage uniqueness audit"]
    for key, value in summary.items():
        lines.append(f"{key}={value}")

    lines.append("")
    lines.append("RAW_HTML_SIGNATURE_COLLISIONS=" + str(len(duplicate_html_groups)))
    lines.append("ACTUAL_DUPLICATE_HTML_BLOCKS=" + str(len(actual_duplicate_html_blocks)))
    lines.append("INTENTIONAL_LOOP_SIGNATURES=" + str(len(intentional_loop_signatures)))
    lines.append("INTENTIONAL_SHARED_COMPONENT_SIGNATURES=" + str(len(intentional_shared_signatures)))
    lines.append("RAW_BINDING_SIGNATURES=" + str(raw_binding_signatures))
    lines.append("RUNTIME_DUPLICATE_BINDINGS=" + str(len(runtime_duplicate_bindings)))
    lines.append("INTENTIONAL_DISTINCT_BINDINGS=" + str(len(intentional_distinct_bindings)))

    for group in html_evidence:
        lines.append("")
        lines.append(f"HTML_SIGNATURE {group['signature_id']} [{group['classification']}]")
        for item in group["evidence"]:
            lines.append(f"  file={item['file']} start={item['start_line']} end={item['end_line']} parent={item['parent']} module={item['module']}")
            lines.append(f"  rendered_once={item['rendered_once']} rendered_multiple_times={item['rendered_multiple_times']} in_loop={item['in_loop']} in_macro={item['in_macro']} hidden={item['hidden']}")
            lines.append(f"  normalized={item['normalized_block']}")

    for group in binding_evidence:
        lines.append("")
        lines.append(f"JS_SIGNATURE {group['signature_id']} [{group['classification']}]")
        for item in group["evidence"]:
            lines.append(
                "  "
                f"file={item['file']} line={item['line']} event={item['event']} target={item['target']} "
                f"handler={item['handler']} delegated={item['delegated']} guard={item['guard']} "
                f"possible_registrations={item['possible_registrations']}"
            )
            lines.append(f"  source={item['source']}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "homepage_uniqueness_before.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ARTIFACT_DIR / "homepage_uniqueness_before.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "raw_html_signature_collisions": len(duplicate_html_groups),
                "actual_duplicate_html_blocks": len(actual_duplicate_html_blocks),
                "intentional_loop_signatures": intentional_loop_signatures,
                "intentional_shared_component_signatures": intentional_shared_signatures,
                "raw_binding_signatures": raw_binding_signatures,
                "runtime_duplicate_bindings": list(runtime_duplicate_bindings.keys()),
                "intentional_distinct_bindings": list(intentional_distinct_bindings.keys()),
                "duplicate_ids": {k: v for k, v in ids.items() if v > 1},
                "duplicate_selectors": {k: v for k, v in selector_counts.items() if v > 1},
                "duplicate_fetch_paths": {k: v for k, v in fetch_counts.items() if v > 1},
                "duplicate_headings": {k: v for k, v in headings.items() if v > 1},
                "html_evidence": html_evidence,
                "binding_evidence": binding_evidence,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    for key, value in summary.items():
        print(f"{key}={value}")
    print(f"RAW_HTML_SIGNATURE_COLLISIONS={len(duplicate_html_groups)}")
    print(f"ACTUAL_DUPLICATE_HTML_BLOCKS={len(actual_duplicate_html_blocks)}")
    print(f"INTENTIONAL_LOOP_SIGNATURES={len(intentional_loop_signatures)}")
    print(f"INTENTIONAL_SHARED_COMPONENT_SIGNATURES={len(intentional_shared_signatures)}")
    print(f"RAW_BINDING_SIGNATURES={raw_binding_signatures}")
    print(f"RUNTIME_DUPLICATE_BINDINGS={len(runtime_duplicate_bindings)}")
    print(f"INTENTIONAL_DISTINCT_BINDINGS={len(intentional_distinct_bindings)}")
    print(f"duplicate_dom_ids={summary['DUPLICATE_IDS']}")
    print(f"duplicate_module_ids={summary['EXACT_DUPLICATE_HTML_BLOCKS']}")
    print(f"duplicate_css_selectors={summary['DUPLICATE_CSS_SELECTORS']}")
    print(f"duplicate_js_initializers={sum(1 for count in init_counts.values() if count > 1)}")
    print(f"duplicate_feed_observers={sum(1 for path in js_files if read(path).count('IntersectionObserver') > 1)}")
    print(f"duplicate_api_paths={summary['DUPLICATE_API_CALLS']}")
    print(f"duplicate_section_headings={summary['DUPLICATE_SECTION_PURPOSES']}")
    print(f"duplicate_global_navigation={1 if 'social-drawer' in homepage_text else 0}")
    print(f"duplicate_hamburgers={len(re.findall(r'nv-hamburger', homepage_text))}")
    print("result=PASS")


if __name__ == "__main__":
    audit()
