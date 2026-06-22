#!/usr/bin/env python3
"""
Phase 129 — Secrets Safety Audit.
Scans the repository for committed secrets, sensitive files, and .gitignore protection.
Never prints secret values — only file paths and pattern types.
"""

import os
import sys
import re
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def read_file(path):
    full = os.path.join(ROOT, path) if not path.startswith("/") else path
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


def git_ls_files(pattern):
    try:
        r = subprocess.run(
            ["git", "ls-files", pattern],
            capture_output=True, text=True, timeout=5,
            cwd=ROOT,
        )
        return r.stdout.strip().splitlines() if r.stdout.strip() else []
    except Exception:
        return []


GITIGNORE_PATH = os.path.join(ROOT, ".gitignore")
IGNORE_PATTERNS = [
    ".env", ".env.*", "!.env.example",
    "secrets/", "logs/", "tmp/",
    "*.pem", "*.key", "*.crt", "*.p12",
    "*.sqlite", "*.db", "*.bak",
    "*.pid", "*.log",
    "*.json.bak",
    ".cloudflared/*.json",
]

SENSITIVE_PATTERNS = {
    "SUPABASE_SERVICE_ROLE_KEY": r'(?:SUPABASE_SERVICE_ROLE|SERVICE_ROLE_KEY)\s*=\s*["\']?[A-Za-z0-9._-]{20,}',
    "DATABASE_URL": r'DATABASE_URL\s*=\s*postgres(?:ql)?://\S+',
    "UPSTASH_REDIS_PASSWORD": r'(?:UPSTASH_REDIS|REDIS_PASSWORD)\s*=\s*["\']?\S+',
    "PRIVATE_KEY": r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
}


print("=" * 60)
print("PHASE 129 — SECRETS SAFETY AUDIT")
print("=" * 60)

# ── 1. .gitignore exists ──
print("\n--- 1. .gitignore ---")
if os.path.exists(GITIGNORE_PATH):
    ok(".gitignore exists")
else:
    fail(".gitignore missing")

gitignore_text = read_file(GITIGNORE_PATH) or ""

# ── 2. .env not tracked ──
print("\n--- 2. .env Tracking ---")
tracked_env = git_ls_files(".env")
tracked_dotenv = [f for f in git_ls_files(".env.*") if f != ".env.example"]
if not tracked_env and not tracked_dotenv:
    ok("No .env files tracked by git (excluding intentional .env.example)")
else:
    for f in tracked_env + tracked_dotenv:
        fail(f"{f} is tracked by git — remove with git rm --cached")

# ── 3. secrets/ not tracked ──
print("\n--- 3. secrets/ Tracking ---")
tracked_secrets = git_ls_files("secrets/")
if not tracked_secrets:
    ok("secrets/ directory not tracked")
else:
    for f in tracked_secrets:
        fail(f"{f} is tracked by git")

# ── 4. logs/ not tracked ──
print("\n--- 4. logs/ Tracking ---")
tracked_logs = git_ls_files("logs/")
if not tracked_logs:
    ok("logs/ directory not tracked")
else:
    for f in tracked_logs:
        fail(f"{f} is tracked by git")

# ── 5. tmp/ not tracked ──
print("\n--- 5. tmp/ Tracking ---")
tracked_tmp = git_ls_files("tmp/")
if not tracked_tmp:
    ok("tmp/ directory not tracked")
else:
    for f in tracked_tmp:
        fail(f"{f} is tracked by git")

# ── 6. .gitignore protects sensitive files ──
print("\n--- 6. .gitignore Protection ---")
for pattern in IGNORE_PATTERNS:
    if pattern in gitignore_text:
        ok(f".gitignore protects: {pattern}")
    else:
        fail(f".gitignore missing: {pattern}")

# ── 7. No private keys tracked ──
print("\n--- 7. Private Keys ---")
tracked_keys = git_ls_files("*.pem") + git_ls_files("*.key") + git_ls_files("*.crt") + git_ls_files("*.p12")
if not tracked_keys:
    ok("No private key files tracked")
else:
    for f in tracked_keys:
        fail(f"Private key file tracked: {f}")

# ── 8. No credentials JSON tracked ──
print("\n--- 8. Credential JSON ---")
tracked_creds = git_ls_files("*.json")
creds_found = False
for f in tracked_creds:
    content = read_file(f)
    if content and ("\"account_tag\"" in content or "\"credentials_file\"" in content or "cloudflared" in content):
        fail(f"Cloudflare credential file tracked: {f}")
        creds_found = True
if not creds_found:
    ok("No cloudflared credential JSON tracked")

# ── 9. Scan source files for secret patterns ──
print("\n--- 9. Secret Pattern Scan ---")
source_dirs = ["scripts/", "services/", "api_routes/", "templates/", "static/js/", "docs/"]
found_secrets = False
for sdir in source_dirs:
    full_dir = os.path.join(ROOT, sdir)
    if not os.path.isdir(full_dir):
        continue
    for root, _dirs, files in os.walk(full_dir):
        for fname in files:
            if not fname.endswith((".py", ".js", ".html", ".md", ".yml", ".yaml", ".txt")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue
            for label, pattern in SENSITIVE_PATTERNS.items():
                if re.search(pattern, content):
                    rel = os.path.relpath(fpath, ROOT)
                    warn(f"Possible {label} in {rel}")
                    found_secrets = True
if not found_secrets:
    ok("No secret patterns found in source files")

# ── 10. No .env.example with real secrets ──
print("\n--- 10. .env.example Safety ---")
env_example = read_file(".env.example")
if env_example:
    secrets_in_example = False
    for label, pattern in SENSITIVE_PATTERNS.items():
        if re.search(pattern, env_example):
            warn(f"{label} found in .env.example — should use placeholders")
            secrets_in_example = True
    if not secrets_in_example:
        ok(".env.example contains no real secrets")
else:
    ok(".env.example not present (no risk)")

# ── 11. Scripts don't print secrets ──
print("\n--- 11. Script Print Safety ---")
script_dir = os.path.join(ROOT, "scripts")
unsafe_print = False
for root, _dirs, files in os.walk(script_dir):
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        text = read_file(fpath)
        if not text:
            continue
        # Check for common unsafe patterns
        if re.search(r'print\(.*\.env', text) or re.search(r'print\(.*os\.environ\[', text):
            warn(f"{fname} may print env vars — review")
            unsafe_print = True
if not unsafe_print:
    ok("Scripts do not appear to print environment secrets")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 129 — SECRETS SAFETY AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  RESULT: {'SECURE' if FAIL == 0 else 'LEAKS DETECTED'}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
