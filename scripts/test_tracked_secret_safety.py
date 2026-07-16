#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_TOKENS = (
    "YOUR_",
    "GENERATE_A_STRONG_RANDOM_VALUE",
    "change-me",
    "placeholder",
    "example",
    "localhost",
    "127.0.0.1",
    "not-configured",
    "not_set",
    "disabled",
    "...",
    "<",
    ">",
    "unset",
)

SENSITIVE_KEYS = (
    "SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "TURN_CREDENTIAL",
    "JWT_SECRET_KEY",
    "NAMVIBE_AI_API_KEY",
)

URL_SECRET_RE = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|rediss?|redis|https?)://[^\\s/@:]+:[^\\s/@]+@[^\\s]+"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")
ASSIGNMENT_RE = re.compile(r"^\s*([A-Z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|URL))\s*=\s*(.+?)\s*$")


def _is_string_literal(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    if value[0] in {'"', "'"} and value[-1] == value[0]:
        return True
    if value.startswith(("f\"", "f'", "F\"", "F'")) and value[-1] == value[1]:
        return True
    return False


def _masked(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _is_placeholder(value: str) -> bool:
    low = value.strip().lower()
    return any(token.lower() in low for token in PLACEHOLDER_TOKENS)


def _scan_text(path: str, text: str) -> list[dict]:
    findings: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if PRIVATE_KEY_RE.search(line):
            findings.append({
                "file": path,
                "line": lineno,
                "category": "private_key_header",
                "value": "***",
            })
            continue
        if _is_placeholder(line):
            continue
        if URL_SECRET_RE.search(line):
            findings.append({
                "file": path,
                "line": lineno,
                "category": "credential_bearing_url",
                "value": "***",
            })
            continue
        m = ASSIGNMENT_RE.match(line)
        if not m:
            continue
        key, value = m.groups()
        if value.startswith(("f\"", "f'", "F\"", "F'")):
            continue
        if key not in SENSITIVE_KEYS and "PASSWORD" not in key and "TOKEN" not in key and "SECRET" not in key and "KEY" not in key:
            continue
        if _is_placeholder(value):
            continue
        if not _is_string_literal(value):
            continue
        if len(value) >= 24 or value.startswith(("postgresql://", "postgres://", "redis://", "rediss://")):
            findings.append({
                "file": path,
                "line": lineno,
                "category": f"assignment:{key.lower()}",
                "value": _masked(value),
            })
    return findings


def main() -> int:
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    findings: list[dict] = []
    for rel in tracked:
        if rel.endswith(".env.bak") or rel.endswith("/env.bak"):
            findings.append({
                "file": rel,
                "line": 1,
                "category": "tracked_env_backup",
                "value": "***",
            })
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Ignore placeholder-heavy docs/tests unless they contain a direct credential pattern.
        findings.extend(_scan_text(rel, text))

    # Filter out known safe placeholder-only examples.
    safe = []
    for item in findings:
        rel = item["file"]
        if rel.startswith("scripts/test_") or rel.startswith("docs/") or rel.endswith(".md"):
            if item["category"] in {"private_key_header", "credential_bearing_url", "tracked_env_backup"}:
                safe.append(item)
                continue
            # Allow placeholder-like examples in docs/tests.
            continue
        safe.append(item)
    findings = safe

    if findings:
        print(json.dumps({"record_type": "tracked_secret_safety", "status": "failed", "findings": findings}, ensure_ascii=True))
        return 1

    print(json.dumps({"record_type": "tracked_secret_safety", "status": "ok", "tracked_files_scanned": len(tracked)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
