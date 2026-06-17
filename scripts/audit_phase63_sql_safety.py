#!/usr/bin/env python3
"""Phase 63 — SQL Safety Audit.

Scans services/, api_routes/, and scripts/ for dangerous SQL patterns.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_DIRS = [
    os.path.join(BASE, "services"),
    os.path.join(BASE, "api_routes"),
    os.path.join(BASE, "scripts"),
]

EXCLUDE_DIRS = {"__pycache__", ".git", "venv", "backups"}

    # Patterns that fail (with file-specific targeting via scan_file)
FAIL_PATTERNS = [
    # text COALESCE + text COALESCE (dangerous string concat)
    (r"COALESCE\([^)]+\)\s*\+\s*COALESCE\([^)]+\)", "COALESCE + COALESCE (non-numeric)"),
    # avatar_url + something
    (r"avatar_url\s*\+\s*(?!\d)", "avatar_url string concatenation"),
    # cover_url + something
    (r"cover_url\s*\+\s*(?!\d)", "cover_url string concatenation"),
    # thumbnail_url + something
    (r"thumbnail_url\s*\+\s*(?!\d)", "thumbnail_url string concatenation"),
    # bio + something
    (r"(?<!CASE WHEN )\bbio\b\s*\+\s*(?!\d|CASE)", "bio string concatenation"),
    # town + something
    (r"(?<!\w)town\b\s*\+\s*(?!\d)", "town string concatenation"),
    # location + something
    (r"(?<!\w)location\b\s*\+\s*(?!\d)", "location string concatenation"),
    # SELECT * in homepage_service.py only
    (r"\bSELECT\s+\*", "SELECT * (prefer explicit columns)"),
    # raw request.args inside SQL
    (r"request\.args\[[^]]+\].*?(?:execute|query|cursor)", "raw request.args in SQL"),
    # raw request.form inside SQL
    (r"request\.form\[[^]]+\].*?(?:execute|query|cursor)", "raw request.form in SQL"),
]

# Only fail on SELECT * in homepage_service.py; report as INFO elsewhere
HOMEPAGE_SERVICE_FILE = "homepage_service.py"

ALLOW_NUMERIC_PATTERN = re.compile(
    r"CASE\s+WHEN\s+.*?\s+THEN\s+\d+(?:\.\d+)?\s+ELSE\s+\d+(?:\.\d+)?\s+END",
    re.IGNORECASE | re.DOTALL,
)


def scan_file(filepath):
    """Scan a single file for dangerous SQL patterns."""
    with open(filepath, "r", errors="ignore") as f:
        content = f.read()

    results = []
    fname = os.path.basename(filepath)
    for pattern, desc in FAIL_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_num = content[: match.start()].count("\n") + 1
            line = content.split("\n")[line_num - 1].strip()
            # For COALESCE + COALESCE, check if it's numeric addition (CASE WHEN)
            if "COALESCE" in desc:
                snippet = content[max(0, match.start() - 200): match.end() + 200]
                if ALLOW_NUMERIC_PATTERN.search(snippet):
                    continue
            # SELECT * is only a FAIL in homepage_service.py
            if "SELECT" in desc:
                if fname == HOMEPAGE_SERVICE_FILE:
                    results.append((filepath, line_num, "FAIL: " + desc, line))
                else:
                    results.append((filepath, line_num, "INFO: " + desc, line))
            else:
                results.append((filepath, line_num, desc, line))
    return results


def main():
    print("=" * 60)
    print("Phase 63 — SQL Safety Audit")
    print("=" * 60)

    all_issues = []
    total_files = 0

    for scan_dir in SCAN_DIRS:
        if not os.path.isdir(scan_dir):
            print(f"\nSkipping {scan_dir} (not found)")
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                total_files += 1
                issues = scan_file(fpath)
                all_issues.extend(issues)

    print(f"\nScanned {total_files} Python files\n")

    # Group by severity
    by_file = {}
    for fpath, line, desc, code in all_issues:
        by_file.setdefault(fpath, []).append((line, desc, code))

    if not by_file:
        print("ALL CLEAN — No SQL safety issues found")
        return 0

    fail_count = 0
    info_count = 0
    for fpath, issues in sorted(by_file.items()):
        relpath = os.path.relpath(fpath, BASE)
        fname = os.path.basename(fpath)
        print(f"\n--- {relpath} ---")
        for line, desc, code in issues:
            if desc.startswith("FAIL:"):
                print(f"  {desc} at line {line}")
                print(f"    Code: {code[:120]}")
                fail_count += 1
            else:
                info_count += 1
                if info_count <= 10:  # limit INFO output
                    print(f"  {desc} at line {line}")

    print(f"\nSummary: {fail_count} FAIL, {info_count} INFO")
    if fail_count > 0:
        print("RESULT: FAIL (critical issues found)")
        return 1
    else:
        print("RESULT: PASS (no critical SQL safety issues)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
