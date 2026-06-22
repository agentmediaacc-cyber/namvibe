#!/usr/bin/env python3
"""Phase 134 disposable-auth helpers.

Passwords are loaded only from environment or ignored local secrets and are
never printed by this module.
"""

import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("NAMVIBE_LIVE_BASE_URL", "https://namvibe.com").rstrip("/")
TEST_PREFIX = "PHASE134_TEST_"
TEST_GROUP_PREFIX = "PHASE134_TEST_GROUP_"
CONTEXT_PATH = ROOT / "tmp" / "phase134_test_context.json"
CREDS_PATH = ROOT / "secrets" / "test_credentials.json"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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


def _clean_email(value):
    if not value:
        return value
    match = re.search(r"mailto:([^)\]>]+)", value)
    return match.group(1) if match else value


def _env_user(prefix):
    username = os.environ.get(f"NAMVIBE_TEST_USER_{prefix}")
    password = os.environ.get(f"NAMVIBE_TEST_PASS_{prefix}")
    email = os.environ.get(f"NAMVIBE_TEST_EMAIL_{prefix}")
    if username and password:
        return {"username": username, "email": email, "password": password}
    return None


def _file_credentials():
    if not CREDS_PATH.exists():
        return None
    try:
        data = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
        return {
            "user_a": {
                "username": data.get("user_a", {}).get("username"),
                "email": _clean_email(data.get("user_a", {}).get("email")),
                "password": data.get("user_a", {}).get("password"),
            },
            "user_b": {
                "username": data.get("user_b", {}).get("username"),
                "email": _clean_email(data.get("user_b", {}).get("email")),
                "password": data.get("user_b", {}).get("password"),
            },
        }
    except Exception:
        return None


def get_credentials():
    creds = {"user_a": _env_user("A"), "user_b": _env_user("B")}
    if not all(creds.values()):
        file_creds = _file_credentials() or {}
        creds["user_a"] = creds["user_a"] or file_creds.get("user_a")
        creds["user_b"] = creds["user_b"] or file_creds.get("user_b")
    if not creds.get("user_a") or not creds.get("user_b"):
        return None
    if not creds["user_a"].get("password") or not creds["user_b"].get("password"):
        return None
    return creds


def has_credentials():
    return get_credentials() is not None


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "NamVibe Phase134 Disposable E2E"})
    session.verify = os.environ.get("NAMVIBE_VERIFY_SSL", "0") == "1"
    return session


def full_url(path_or_url):
    if str(path_or_url).startswith("http"):
        return str(path_or_url)
    return urljoin(BASE_URL + "/", str(path_or_url).lstrip("/"))


def csrf_from_html(html):
    patterns = [
        r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)',
        r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)',
        r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "", re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def login(session, user):
    login_url = full_url("/auth/login")
    page = session.get(login_url, timeout=30, allow_redirects=True)
    token = csrf_from_html(page.text)
    identity = user.get("email") or user.get("username")
    payload = {
        "username": identity,
        "email": identity,
        "login": identity,
        "password": user.get("password"),
    }
    if token:
        payload["csrf_token"] = token
    response = session.post(login_url, data=payload, timeout=30, allow_redirects=True)
    return response


def request_json(session, method, url, data=None, files=None):
    method = method.upper()
    kwargs = {"timeout": 45, "allow_redirects": True}
    if files:
        kwargs["data"] = data or {}
        kwargs["files"] = files
    else:
        kwargs["json"] = data or {}
    response = session.request(method, full_url(url), **kwargs)
    try:
        return response, response.json()
    except Exception:
        return response, {}


def unique_test_id():
    return TEST_PREFIX + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(4)


def is_auth_redirect(response):
    location = response.headers.get("Location", "")
    url = getattr(response, "url", "")
    return response.status_code in (301, 302, 303, 307, 308) and "/auth/login" in location or "/auth/login" in url


def safe_status(response):
    return getattr(response, "status_code", -1)


def load_context():
    if CONTEXT_PATH.exists():
        try:
            return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_context(context):
    CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in context.items() if "pass" not in k.lower() and "password" not in k.lower()}
    CONTEXT_PATH.write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")


def acceptable(response, extra=(400,)):
    return safe_status(response) in (200, 201, 202, 204, 302, 400, 401, 403, *extra)


def warn_missing_credentials(results):
    results.warn(
        "test credentials missing; create phase134_alpha and phase134_beta, then store credentials in ignored secrets/test_credentials.json"
    )


def manual_account_instructions():
    return (
        "Manual setup: create two disposable accounts named phase134_alpha and phase134_beta "
        "with test-only example.com emails, then store credentials only in secrets/test_credentials.json."
    )


def main_exit(results):
    return 0
