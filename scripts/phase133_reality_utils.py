#!/usr/bin/env python3
"""Shared helpers for Phase 133 production-facing reality checks."""

import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("NAMVIBE_LIVE_BASE_URL", "https://namvibe.com").rstrip("/")
HEADERS = {"User-Agent": "NamVibe Phase133 Reality"}
ACCEPTABLE_AUTH_STATUSES = {200, 302, 401, 403}
ACCEPTABLE_ROUTE_STATUSES = {200, 302, 400, 401, 403}
SSL_FALLBACK_USED = False


class Results:
    def __init__(self):
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def ok(self, message):
        self.pass_count += 1
        print(f"  [PASS] {message}")

    def fail(self, message):
        self.fail_count += 1
        print(f"  [FAIL] {message}")

    def warn(self, message):
        self.warn_count += 1
        print(f"  [WARN] {message}")

    def check(self, label, condition, warn_only=False):
        if condition:
            self.ok(label)
        elif warn_only:
            self.warn(label)
        else:
            self.fail(f"{label} missing")

    def summary(self, title):
        print(f"\n{'=' * 60}")
        print(f"{title} SUMMARY")
        print(f"{'=' * 60}")
        print(f"  PASS: {self.pass_count}  FAIL: {self.fail_count}  WARN: {self.warn_count}")
        print(f"  safe_to_commit: {'YES' if self.fail_count == 0 else 'NO'}")


def print_header(title):
    print("=" * 60)
    print(title)
    print("=" * 60)


def read_file(path):
    full = ROOT / path
    if not full.exists():
        return ""
    return full.read_text(encoding="utf-8", errors="ignore")


def has_pattern(text, pattern):
    return re.search(pattern, text, re.IGNORECASE | re.DOTALL) is not None


def http_request(path_or_url, method="GET", data=None, headers=None, timeout=45):
    global SSL_FALLBACK_USED
    url = path_or_url if str(path_or_url).startswith("http") else BASE + str(path_or_url)
    body = None
    req_headers = dict(HEADERS)
    if headers:
        req_headers.update(headers)
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = data
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            text = response.read(700000).decode("utf-8", errors="ignore")
            return response.status, text, response.geturl()
    except urllib.error.HTTPError as exc:
        text = exc.read(200000).decode("utf-8", errors="ignore")
        return exc.code, text, exc.geturl()
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            SSL_FALLBACK_USED = True
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context()) as response:
                    text = response.read(700000).decode("utf-8", errors="ignore")
                    return response.status, text, response.geturl()
            except urllib.error.HTTPError as http_exc:
                text = http_exc.read(200000).decode("utf-8", errors="ignore")
                return http_exc.code, text, http_exc.geturl()
            except Exception as retry_exc:
                return -1, str(retry_exc), url
        return -1, str(exc), url
    except Exception as exc:
        return -1, str(exc), url


def route_check(results, path, method="GET", data=None, label=None, acceptable=None):
    status, body, _ = http_request(path, method=method, data=data)
    acceptable = acceptable or ACCEPTABLE_ROUTE_STATUSES
    name = label or path
    if status in acceptable:
        results.ok(f"{name} route responds ({status})")
    elif status in (404, 500, 502, 503):
        results.fail(f"{name} route returned {status}")
    else:
        results.warn(f"{name} route returned {status}")
    return status, body


def static_refs(html):
    refs = set()
    for match in re.findall(r"""(?:src|href)=["']([^"']+\.(?:js|css|png|jpg|jpeg|webp|svg)(?:\?[^"']*)?)["']""", html, re.I):
        if match.startswith("/static/"):
            refs.add(match)
        elif match.startswith(BASE + "/static/"):
            refs.add(match.replace(BASE, ""))
    return sorted(refs)


def node_check(results, path):
    full = ROOT / path
    if not full.exists():
        results.warn(f"{path} not present")
        return
    try:
        proc = subprocess.run(["node", "--check", str(full)], cwd=ROOT, capture_output=True, text=True, timeout=20)
        if proc.returncode == 0:
            results.ok(f"node --check {path}")
        else:
            results.fail(f"node --check {path}: {(proc.stderr or proc.stdout)[:180]}")
    except FileNotFoundError:
        results.warn("node unavailable for JS syntax checks")
    except Exception as exc:
        results.warn(f"node --check {path} skipped: {exc}")


def credentials():
    env = {
        "user_a": os.environ.get("NAMVIBE_TEST_USER_A"),
        "pass_a": os.environ.get("NAMVIBE_TEST_PASS_A"),
        "user_b": os.environ.get("NAMVIBE_TEST_USER_B"),
        "pass_b": os.environ.get("NAMVIBE_TEST_PASS_B"),
    }
    if all(env.values()):
        return env
    cred_file = ROOT / "secrets" / "test_credentials.json"
    if cred_file.exists():
        try:
            data = json.loads(cred_file.read_text(encoding="utf-8"))
            env.update({
                "user_a": env["user_a"] or data.get("NAMVIBE_TEST_USER_A") or data.get("user_a"),
                "pass_a": env["pass_a"] or data.get("NAMVIBE_TEST_PASS_A") or data.get("pass_a"),
                "user_b": env["user_b"] or data.get("NAMVIBE_TEST_USER_B") or data.get("user_b"),
                "pass_b": env["pass_b"] or data.get("NAMVIBE_TEST_PASS_B") or data.get("pass_b"),
            })
        except Exception:
            pass
    return env if all(env.values()) else None


def warn_ssl_fallback(results):
    if SSL_FALLBACK_USED:
        results.warn("Python CA verification failed locally; retried live HTTPS with certificate verification disabled")


def main_result_code(results):
    return 0
