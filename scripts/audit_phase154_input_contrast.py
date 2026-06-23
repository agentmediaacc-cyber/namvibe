#!/usr/bin/env python3
"""
Phase 154 — Input Contrast Audit.

Scans CSS files for potential contrast issues:
- Look for color: with white-like colors (#fff, white, #ffffff, etc.)
- Check if paired with background: that is also white-like or transparent
- Check input, textarea, .form-control, placeholder styling
- Flag potential white-on-white or low-contrast issues
- Report PASS/WARN/FAIL per file
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
WARN = "WARN"

WHITE_RE = re.compile(r"#(?:fff|ffffff|fafafa|f5f5f5|f0f0f0|f8f9fa|f1f5f9|f8fafc)", re.IGNORECASE)
WHITE_KEYWORDS = {"white", "#fff", "#ffffff", "#fffffe", "#fafafa", "#f5f5f5"}
LIGHT_VALUES = {"transparent", "inherit", "initial", "unset", "none"}

def report(check_name, status, detail=""):
    results.append((check_name, status, detail))
    marker_map = {PASS: "\u2705", FAIL: "\u274c", SKIP: "\u23f8", WARN: "\u26a0\ufe0f"}
    marker = marker_map.get(status, "\u2753")
    print(f"  {marker} {check_name}: {status} {detail}")

def is_white_like(value):
    val = value.strip().lower()
    if val in WHITE_KEYWORDS:
        return True
    if val in LIGHT_VALUES:
        return True
    if WHITE_RE.match(val):
        return True
    return False

def is_transparent_or_missing(value):
    val = value.strip().lower()
    return val in LIGHT_VALUES or val == "" or val.startswith("rgba(0, 0, 0, 0") or val == "rgba(0,0,0,0)"

def scan_css_for_contrast(filepath, filename):
    """Scan a CSS file for potential white-on-white / low-contrast issues."""
    file_issues = []
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception as e:
        return [], f"Read error: {e}"

    total_lines = len(content.splitlines())

    input_rules = re.finditer(
        r"(input|textarea|select|\.form-control|\.search-bar\s+input|\.nvpro-search-input|\.nvpro-form-input|::placeholder|::-webkit-input-placeholder|::moz-placeholder)[^{]*\{([^}]*)\}",
        content, re.IGNORECASE | re.DOTALL
    )

    for match in input_rules:
        selector = match.group(1)
        block = match.group(2)
        has_color = "color:" in block
        has_bg = "background:" in block or "background-color:" in block
        color_val = None
        bg_val = None

        c_match = re.search(r"color:\s*([^;}]+)", block)
        if c_match:
            color_val = c_match.group(1).strip()

        bg_match = re.search(r"(?:background|background-color):\s*([^;}]+)", block)
        if bg_match:
            bg_val = bg_match.group(1).strip()

        if color_val and bg_val:
            if is_white_like(color_val):
                if is_white_like(bg_val):
                    file_issues.append(f"{selector}: white-on-white (color={color_val}, bg={bg_val})")
                elif is_transparent_or_missing(bg_val):
                    file_issues.append(f"{selector}: white-on-transparent (color={color_val}, bg={bg_val})")
        elif color_val and not bg_val:
            if is_white_like(color_val):
                file_issues.append(f"{selector}: white color without explicit background")

        placeholder_match = re.search(r"::?placeholder[^{]*\{([^}]*)\}", content, re.IGNORECASE)
        if placeholder_match:
            pb = placeholder_match.group(1)
            pc = re.search(r"color:\s*([^;}]+)", pb)
            if pc:
                pcv = pc.group(1).strip()
                if is_white_like(pcv):
                    file_issues.append(f"::placeholder white-ish color: {pcv}")

    bg_color_decls = re.findall(r"(?:background|background-color):\s*([^;}]+)", content)
    color_decls = re.findall(r"(?:^|\s)color:\s*([^;}]+)", content)

    for bg_val in bg_color_decls:
        bg_stripped = bg_val.strip().lower()
        if is_white_like(bg_stripped) and bg_stripped not in LIGHT_VALUES:
            nearby_color = None
            bg_pos = content.find(bg_val)
            chunk = content[max(0, bg_pos - 200):bg_pos + 200]
            nc = re.search(r"color:\s*([^;}]+)", chunk)
            if nc:
                nearby_color = nc.group(1).strip()
            if nearby_color and is_white_like(nearby_color):
                file_issues.append(f"Nearby color white-on-white (bg={bg_stripped}, color={nearby_color})")

    file_issues = list(dict.fromkeys(file_issues))
    return file_issues, None

def main():
    print("=" * 60)
    print("Phase 154 — Input Contrast Audit (CSS)")
    print("=" * 60)
    print()

    css_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "css")
    target_files = [
        "chain_theme.css",
        "namvibe_home_pro.css",
        "namvibe_profile_pro.css",
        "profile.css",
    ]

    total_issues = 0

    for filename in target_files:
        filepath = os.path.join(css_dir, filename)
        print(f"--- {filename} ---")

        if not os.path.exists(filepath):
            report(filename, SKIP, "File not found")
            continue

        issues, error = scan_css_for_contrast(filepath, filename)
        if error:
            report(filename, FAIL, error)
            continue

        if issues:
            total_issues += len(issues)
            report(filename, WARN if len(issues) < 5 else FAIL,
                   f"{len(issues)} potential contrast issue(s)")
            for issue in issues[:5]:
                print(f"       \u26a0 {issue}")
            if len(issues) > 5:
                print(f"       ... and {len(issues) - 5} more")
        else:
            report(filename, PASS, "No contrast issues detected")

        print()

    print("=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == PASS)
    warned = sum(1 for _, s, _ in results if s == WARN)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    print(f"Total: {len(results)} | PASS: {passed} | WARN: {warned} | FAIL: {failed} | SKIP: {skipped}")
    if total_issues > 0:
        print(f"\nTotal potential contrast issues: {total_issues}")
    print()

    if warned > 0:
        print("  WARN: Minor contrast concerns found — review recommended.")
    if failed > 0:
        print("  FAIL: Critical issues found.")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    - {name}: {detail}")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
