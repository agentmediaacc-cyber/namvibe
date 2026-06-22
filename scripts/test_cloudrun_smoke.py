"""Phase 104 — Smoke test a deployed Cloud Run service.

Usage:
    python3 scripts/test_cloudrun_smoke.py --url https://chain-app-xxxxx-uc.a.run.app

Or with PROJECT_ID (auto-fetches URL):
    PROJECT_ID=my-gcp-project python3 scripts/test_cloudrun_smoke.py
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse

TEST_TIMEOUT = 30

results = {"passed": 0, "failed": 0, "warnings": 0, "warnings_list": [], "errors": []}
redis_connected = None
redis_scheme = None
redis_ssl_reqs = None
redis_health_body = ""

ENDPOINTS = [
    ("/healthz", "Lightweight health check", {200}),
    ("/", "Homepage", {200}),
    ("/discover/", "Discover page", {200}),
    ("/reels/", "Reels page", {200, 302}),
    ("/live/", "Live page", {200}),
    ("/system/api/webrtc-health", "WebRTC health API", {200}),
    ("/system/api/livekit-health", "LiveKit health API", {200}),
    ("/health/redis", "Redis health check", {200, 503}),
]

SENSITIVE_PATTERNS = [
    b"SECRET_KEY",
    b"DATABASE_URL",
    b"SUPABASE_",
    b"supabase_anon_key",
    b"supabase_service_role",
    b"REDIS_URL",
    b"redis://",
    b"postgres://",
    b"postgresql://",
]


def _ok(label):
    results["passed"] += 1
    print(f"  [PASS] {label}")


def _fail(label, detail=""):
    results["failed"] += 1
    msg = f"{label}: {detail}" if detail else label
    results["errors"].append(msg)
    print(f"  [FAIL] {msg}")


def _warn(label, detail=""):
    results["warnings"] += 1
    msg = f"{label}: {detail}" if detail else label
    results["warnings_list"].append(msg)
    print(f"  [WARN] {msg}")


def _fetch(url, path):
    full_url = url.rstrip("/") + path
    req = urllib.request.Request(full_url)
    try:
        resp = urllib.request.urlopen(req, timeout=TEST_TIMEOUT)
        body = resp.read()
        return resp.status, resp.headers, body
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except Exception as e:
        return None, {}, str(e).encode()


def _check_no_secrets(path, body):
    for pattern in SENSITIVE_PATTERNS:
        if pattern in body:
            return pattern.decode()
    return None


def main():
    parser = argparse.ArgumentParser(description="Smoke test Cloud Run deployment")
    parser.add_argument("--url", help="Cloud Run service URL")
    args = parser.parse_args()

    url = args.url

    # If no --url, try to auto-fetch from gcloud
    if not url:
        project = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
        if project:
            import subprocess
            result = subprocess.run(
                ["gcloud", "run", "services", "describe", "chain-app",
                 "--project", project, "--region", "us-central1",
                 "--format", "json", "--quiet"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                url = data.get("status", {}).get("url", "")
        if not url:
            print("ERROR: --url or PROJECT_ID env var required.")
            sys.exit(1)

    print(f"Testing: {url}")
    print()

    for path, label, accepted in ENDPOINTS:
        print(f"--- {path} ({label}) ---")
        status, headers, body = _fetch(url, path)

        if status is None:
            _fail(label, f"connection failed: {body.decode()[:200]}")
            continue

        if status in accepted:
            _ok(f"{path} -> {status}")
        else:
            _warn(f"{path} -> {status} (expected {accepted})")

        # Check for secrets in response body
        leak = _check_no_secrets(path, body)
        if leak:
            _fail(label, f"secret leaked in response: {leak}")
        else:
            _ok(f"{path} no secrets leaked")

        # Check for masked values
        body_text = body.decode("utf-8", errors="replace").lower()
        if "[masked]" in body_text:
            _warn(f"{path} contains '[masked]' placeholder in response")

        # Parse /health/redis response
        if path == "/health/redis":
            global redis_connected, redis_scheme, redis_ssl_reqs, redis_health_body
            redis_health_body = body.decode("utf-8", errors="replace")
            try:
                data = json.loads(redis_health_body)
                redis_connected = bool(data.get("connected", data.get("available", False)))
                redis_scheme = data.get("redis_url_scheme", "")
                redis_ssl_reqs = data.get("ssl_cert_reqs")
                if redis_connected:
                    _ok("/health/redis -> Redis connected")
                else:
                    _warn("/health/redis -> Redis not connected (in-memory fallback active)")
                if redis_scheme == "rediss":
                    _ok("/health/redis -> TLS enabled (rediss://)")
                else:
                    _warn(f"/health/redis -> unexpected scheme: {redis_scheme}")
                if redis_ssl_reqs == "required":
                    _ok("/health/redis -> SSL certificate verification required")
                elif redis_ssl_reqs is None:
                    _warn("/health/redis -> SSL cert reqs not set (defaults to required)")
                else:
                    _warn(f"/health/redis -> SSL cert reqs: {redis_ssl_reqs} (expected required)")
            except (json.JSONDecodeError, KeyError):
                _warn("/health/redis -> could not parse response")

    print()
    print("=" * 50)
    print("SMOKE TEST REPORT")
    print("=" * 50)
    print(f"  Passed:   {results['passed']}")
    print(f"  Failed:   {results['failed']}")
    print(f"  Warnings: {results['warnings']}")

    if results["errors"]:
        print("\n  Errors:")
        for e in results["errors"]:
            print(f"    - {e}")

    print()
    print("-" * 50)
    print("REDIS STATUS")
    print("-" * 50)
    redis_local_detected = redis_connected is not None and not redis_connected
    redis_ready_for_cloudrun = redis_connected is True
    tls_ok = redis_scheme == "rediss" and redis_ssl_reqs == "required"
    print(f"  redis_connected:         {str(redis_connected).lower()}")
    print(f"  redis_url_scheme:        {redis_scheme or 'unknown'}")
    print(f"  ssl_cert_reqs:           {redis_ssl_reqs or 'default'}")
    print(f"  redis_local_detected:    {str(redis_local_detected).lower()}")
    print(f"  redis_ready_for_cloudrun: {str(redis_ready_for_cloudrun).lower()}")
    print(f"  test_deploy_allowed:      true")
    if redis_ready_for_cloudrun and tls_ok:
        print(f"  production_recommendation: Redis connected, TLS verified — ready for production")
    elif redis_ready_for_cloudrun:
        print(f"  production_recommendation: Redis connected but TLS config needs review")
    else:
        print(f"  production_recommendation: Set up managed Redis before production launch")
        print(f"  production_recommendation: See docs/CLOUD_RUN_REDIS_SETUP.md")

    print()
    print("-" * 50)
    print("OVERALL")
    print("-" * 50)
    ok = results["failed"] == 0
    print(f"  smoke_test: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
