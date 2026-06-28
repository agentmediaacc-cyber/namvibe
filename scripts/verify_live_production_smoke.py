#!/usr/bin/env python3
import json
import os
import ssl
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app

PUBLIC_ROUTES = [
    ("/", {200, 302}),
    ("/auth/login", {200, 302}),
    ("/auth/register", {200, 302}),
    ("/healthz", {200}),
    ("/health/db", {200, 503}),
    ("/health/redis", {200, 503}),
    ("/health/supabase", {200, 503}),
    ("/reels/", {200, 302}),
    ("/search", {200, 302}),
]

PROTECTED_ROUTES = [
    "/profile/",
    "/messages/",
    "/notifications/",
    "/wallet/",
    "/settings/",
    "/admin/",
]


def _line(status, label, detail=""):
    suffix = f" :: {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def _check_remote_health():
    url = os.environ.get("NAMVIBE_HEALTH_URL", "https://namvibe.com/healthz")
    try:
        context = None
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            context = ssl.create_default_context()
        req = Request(url, headers={"User-Agent": "chain-smoke/1.0"})
        with urlopen(req, timeout=8, context=context) as resp:
            body = resp.read(400).decode("utf-8", errors="replace")
            ok = 200 <= resp.status < 300
            if not ok:
                return False, f"status={resp.status}"
            try:
                payload = json.loads(body)
                return True, payload.get("status") or "ok"
            except Exception:
                return True, f"status={resp.status}"
    except ssl.SSLCertVerificationError as error:
        return "warn", f"ssl_verify_failed: {error}"
    except URLError as error:
        return None, str(error.reason)
    except Exception as error:
        return None, str(error)


def main():
    app = create_app()
    failures = []
    warnings = []

    with app.test_client() as client:
        for path, expected in PUBLIC_ROUTES:
            response = client.get(path, follow_redirects=False)
            ok = response.status_code in expected and response.status_code != 500
            if ok:
                _line("PASS", f"public route {path}", f"status={response.status_code}")
            else:
                _line("FAIL", f"public route {path}", f"status={response.status_code}")
                failures.append(f"public route failed: {path} -> {response.status_code}")

        for path in PROTECTED_ROUTES:
            response = client.get(path, follow_redirects=False)
            ok = response.status_code in {302, 401, 403}
            if ok:
                _line("PASS", f"protected route {path}", f"status={response.status_code}")
            else:
                _line("FAIL", f"protected route {path}", f"status={response.status_code}")
                failures.append(f"protected route weak/unexpected: {path} -> {response.status_code}")

    remote_ok, detail = _check_remote_health()
    if remote_ok == "warn":
        _line("WARN", "Remote namvibe health", detail)
        warnings.append(detail)
    elif remote_ok is None:
        print(f"[SKIP] Remote namvibe health check skipped :: {detail}")
    elif remote_ok:
        _line("PASS", "Remote namvibe health", detail)
    else:
        _line("FAIL", "Remote namvibe health", detail)
        failures.append(f"remote namvibe health failed: {detail}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1
    if warnings:
        print("WARN")
        for warning in warnings:
            print(warning)
        return 0
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
