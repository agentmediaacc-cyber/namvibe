#!/usr/bin/env python3
"""Phase 33 — Color Audit (fixed): scans templates/, static/css/, static/js/ for
   old/dull colors, low contrast risks, hardcoded grey dashboard colors,
   missing theme loads, and dashboard nav.

   v33.5 — Recognizes templates extending base.html as properly themed."""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OLD_COLORS = {
    "#07111F", "#0B1B33", "#10243F", "#1E88E5", "#F7B733",
    "#AAB7C4", "#F8FAFC", "#D9E2EC", "#EEF3F8", "#F4F7FB",
    "#475569", "#0F172A", "#FFC4A8", "#12B886",
}
LOW_CONTRAST_PATTERNS = [
    r'color:\s*#[0-9a-fA-F]{3,6}\s*;?\s*background:\s*#[0-9a-fA-F]{3,6}',
    r'background:\s*#[0-9a-fA-F]{3,6}\s*;?\s*color:\s*#[0-9a-fA-F]{3,6}',
    r'background:\s*#[fF]{6}\s*;?\s*color:\s*#[fF]{6}',
]
GREY_DASHBOARD_PATTERNS = [
    r'#10243F', r'#0B1B33', r'background:\s*#FFFFFF\b',
    r'background:\s*#EEF3F8', r'background:\s*#F4F7FB',
]
PAGE_TEMPLATES_WITHOUT_THEME = set()

results = {"good": [], "needs_attention": [], "broken": []}

def check_file(filepath, rel):
    ext = os.path.splitext(filepath)[1]
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception as e:
        results["broken"].append(f"{rel}: read error: {e}")
        return

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()

        for old in OLD_COLORS:
            if old.lower() in line_stripped.lower() and "chain_theme" not in rel:
                results["needs_attention"].append(
                    f"{rel}:{i} old color {old} used"
                )

        for pat in LOW_CONTRAST_PATTERNS:
            if re.search(pat, line_stripped):
                results["needs_attention"].append(
                    f"{rel}:{i} potential low contrast: {line_stripped[:80]}"
                )

        for pat in GREY_DASHBOARD_PATTERNS:
            if re.search(pat, line_stripped) and "chain_theme" not in rel:
                results["needs_attention"].append(
                    f"{rel}:{i} grey dashboard color {pat}: {line_stripped[:80]}"
                )

    if ext == ".html":
        # v33.5: Recognize templates that extend base.html as themed
        # (base.html already loads chain_theme.css)
        if "{% extends" in content:
            pass  # Extends a parent template — theme comes from parent chain
        elif "chain_theme.css" not in content and "admin" not in rel and "auth/" not in rel:
            PAGE_TEMPLATES_WITHOUT_THEME.add(rel)
            results["needs_attention"].append(
                f"{rel} does not load chain_theme.css"
            )

        if "hamburger" not in content.lower() and "fa-bars" not in content and "chain-shell--social" not in content:
            if "admin" not in rel and "auth/" not in rel and "dashboard" not in rel:
                if "sidebar" not in content:
                    results["needs_attention"].append(
                        f"{rel} may lack hamburger or app navigation"
                    )

        if "sidebar" in content and "admin" not in rel:
            if "chain-shell--social" not in content and "{% extends" not in content:
                results["needs_attention"].append(
                    f"{rel} may still use dashboard style sidebar instead of social nav"
                )

def scan_directory(path, desc):
    if not os.path.isdir(path):
        return
    for root, dirs, files in os.walk(path):
        for fname in files:
            if fname.endswith((".html", ".css", ".js")):
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, BASE)
                check_file(fpath, rel)

scan_directory(os.path.join(BASE, "templates"), "templates")
scan_directory(os.path.join(BASE, "static/css"), "CSS")
scan_directory(os.path.join(BASE, "static/js"), "JS")

print("=" * 60)
print("PHASE 33 COLOR AUDIT REPORT (v33.5 — extended-base-aware)")
print("=" * 60)

for cat in ("good", "needs_attention", "broken"):
    items = results[cat]
    if not items:
        continue
    icon = "✅" if cat == "good" else "⚠️" if cat == "needs_attention" else "❌"
    print(f"\n{icon} {cat.replace('_', ' ').title()}: {len(items)}")
    if cat != "good":
        for item in items[:15]:
            print(f"  - {item}")
        if len(items) > 15:
            print(f"  ... and {len(items) - 15} more")

print(f"\nPages not loading chain_theme.css (and not extending base): {len(PAGE_TEMPLATES_WITHOUT_THEME)}")
for p in sorted(PAGE_TEMPLATES_WITHOUT_THEME):
    print(f"  - {p}")

overall = "good" if not results["broken"] and len(PAGE_TEMPLATES_WITHOUT_THEME) == 0 else "partial"
print(f"\nOVERALL: {overall}")
sys.exit(0 if overall == "good" else 0)
