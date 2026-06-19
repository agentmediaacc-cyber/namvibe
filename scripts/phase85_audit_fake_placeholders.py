#!/usr/bin/env python3
"""Audit production-facing fake, placeholder, and dead-link copy."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["templates", "static", "services", "api_routes", "scripts", "sql"]
SKIP_PARTS = {"venv", "__pycache__", "backups", ".git", "node_modules"}
SKIP_FILE_PATTERNS = (
    re.compile(r"(^|/)test_", re.I),
    re.compile(r"(^|/)audit_", re.I),
    re.compile(r"phase8", re.I),
    re.compile(r"phase85_audit_fake_placeholders\.py$"),
    re.compile(r"phase85_clean_fake_rows\.py$"),
)

TERMS = [
    ("phase8", re.compile(r"\bphase\s*8\b|phase8(?!\d)", re.I)),
    ("production reel", re.compile(r"production\s+reel", re.I)),
    ("test reel", re.compile(r"test\s+reel", re.I)),
    ("seed", re.compile(r"\bseed(?:ed|ing)?\b", re.I)),
    ("dummy", re.compile(r"\bdummy\b", re.I)),
    ("fake", re.compile(r"\bfake\b", re.I)),
    ("sample", re.compile(r"\bsample\b", re.I)),
    ("lorem", re.compile(r"\blorem\b|\bipsum\b", re.I)),
    ("placeholder", re.compile(r"\bplaceholder\b", re.I)),
    ("coming soon", re.compile(r"coming\s+soon", re.I)),
    ("TODO", re.compile(r"\bTODO\b")),
    ("Original Sound", re.compile(r"Original\s+Sound", re.I)),
    ("CHAIN old branding", re.compile(r">\s*CHAIN\s*<|Chain\s*\|")),
    ("hardcoded localhost", re.compile(r"https?://(?:localhost|127\.0\.0\.1):\d+", re.I)),
    ("javascript void", re.compile(r"javascript:void\(0\)", re.I)),
    ("href hash", re.compile(r"href=[\"']#[\"']", re.I)),
]

FORM_PLACEHOLDER_RE = re.compile(r"\bplaceholder=[\"'][^\"']+[\"']", re.I)
CLASS_PLACEHOLDER_RE = re.compile(r"(class|id)=[\"'][^\"']*placeholder[^\"']*[\"']", re.I)


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if any(part in SKIP_PARTS for part in path.parts):
        return True
    if any(pattern.search(rel) for pattern in SKIP_FILE_PATTERNS):
        return True
    if path.suffix.lower() not in {".html", ".js", ".css", ".py", ".sql", ".md", ".txt"}:
        return True
    return False


def classify(path: Path, line: str, term: str) -> str:
    rel = path.relative_to(ROOT).as_posix()
    stripped = line.strip()
    if rel.startswith(("templates/admin/", "templates/dev/")):
        return "WARN"
    if rel.startswith("scripts/") or rel.startswith("services/") or rel.startswith("api_routes/") or rel.startswith("sql/"):
        return "WARN"
    if stripped.startswith(("<!--", "{#", "//", "/*", "*", "#")):
        return "WARN"
    if term == "placeholder" and (
        FORM_PLACEHOLDER_RE.search(line)
        or CLASS_PLACEHOLDER_RE.search(line)
        or "::placeholder" in line
        or re.search(r"[.#][\w-]*placeholder[\w-]*", line, re.I)
        or re.search(r"\b[\w-]*placeholder[\w-]*\b", line, re.I)
    ):
        return "WARN"
    if term == "href hash" and "onclick=" in line:
        return "WARN"
    if rel.startswith("static/js/") and term not in {"javascript void", "hardcoded localhost"}:
        return "WARN"
    if rel.startswith("static/css/"):
        return "WARN"
    if term in {"href hash", "javascript void", "hardcoded localhost", "CHAIN old branding"}:
        return "BLOCKER"
    if rel.startswith("templates/") or rel.startswith("static/"):
        return "BLOCKER"
    return "WARN"


def scan():
    findings = []
    for dirname in SCAN_DIRS:
        root = ROOT / dirname
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            try:
                lines = path.read_text(errors="ignore").splitlines()
            except Exception:
                continue
            for idx, line in enumerate(lines, start=1):
                for term, pattern in TERMS:
                    if not pattern.search(line):
                        continue
                    sev = classify(path, line, term)
                    findings.append({
                        "severity": sev,
                        "path": path.relative_to(ROOT).as_posix(),
                        "line": idx,
                        "term": term,
                        "snippet": line.strip()[:180],
                    })
    return findings


def main():
    findings = scan()
    for item in findings:
        print(f"{item['severity']} {item['path']}:{item['line']} [{item['term']}] {item['snippet']}")
    blockers = sum(1 for item in findings if item["severity"] == "BLOCKER")
    warnings = len(findings) - blockers
    print(f"phase85_fake_placeholder_audit: {blockers} blockers, {warnings} warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
