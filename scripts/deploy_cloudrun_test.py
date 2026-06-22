"""Phase 104 — Build & deploy to Cloud Run test service.

Usage:
    PROJECT_ID=my-gcp-project python3 scripts/deploy_cloudrun_test.py

Requires:
    - gcloud CLI authenticated
    - Docker or Cloud Build enabled
    - Secrets already uploaded (run setup_gcloud_secrets_from_env.py first)
"""

import os
import subprocess
import sys
import time
import json
from datetime import datetime
from pathlib import Path

PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
if not PROJECT_ID:
    print("ERROR: PROJECT_ID env var is required.")
    sys.exit(1)

REGION = "us-central1"
SERVICE = "chain-app"
TAG = f"test-{datetime.now().strftime('%Y%m%d-%H%M')}"
IMAGE = f"gcr.io/{PROJECT_ID}/{SERVICE}:{TAG}"

SECRETS = [
    "SECRET_KEY=chain-secret-key:latest",
    "DATABASE_URL=chain-database-url:latest",
    "REDIS_URL=chain-redis-url:latest",
    "SUPABASE_URL=chain-supabase-url:latest",
    "SUPABASE_ANON_KEY=chain-supabase-anon-key:latest",
    "SUPABASE_SERVICE_ROLE_KEY=chain-supabase-service-role-key:latest",
    "APP_BASE_URL=chain-app-base-url:latest",
]


def _run(cmd, capture=True, check=True, desc=""):
    if desc:
        print(f"  {desc}...")
    result = subprocess.run(cmd, capture_output=capture, text=True, timeout=600)
    if check and result.returncode != 0:
        err = result.stderr.strip()[:300] if result.stderr else "unknown error"
        print(f"  FAILED: {err}")
        sys.exit(1)
    return result


def _ensure_secret(secret_name, placeholder):
    """Create secret with placeholder if it doesn't exist yet (non-fatal)."""
    cmd = ["gcloud", "secrets", "create", secret_name,
           "--project", PROJECT_ID, "--quiet",
           "--replication-policy", "automatic"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if proc.returncode == 0:
        print(f"    Created {secret_name} with placeholder")
        subprocess.run(
            ["gcloud", "secrets", "versions", "add", secret_name,
             "--project", PROJECT_ID, "--data-file=-", "--quiet"],
            input=placeholder, capture_output=True, text=True, timeout=15,
        )


def _check_localhost_redis():
    """Read .env and warn if REDIS_URL points to localhost. Never prints value."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("REDIS_URL="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            after_proto = val.split("://", 1)[1] if "://" in val else val
            host = after_proto.split("@")[-1].split(":")[0] if "@" in after_proto else after_proto.split(":")[0]
            if host in ("localhost", "127.0.0.1"):
                print("  [WARN] Local Redis URL detected in .env")
                print("  [WARN] Cloud Run real-time features will be degraded (in-memory fallback)")
                print("  [WARN] See docs/CLOUD_RUN_REDIS_SETUP.md to set up managed Redis")
            break


def main():
    print(f"Project: {PROJECT_ID}")
    print(f"Region:  {REGION}")
    print(f"Service: {SERVICE}")
    print(f"Image:   {IMAGE}")
    print()

    # Pre-check: warn if REDIS_URL is localhost
    _check_localhost_redis()
    print()

    # Pre-check: ensure APP_BASE_URL secret exists
    print("--- Pre-check: APP_BASE_URL secret ---")
    _ensure_secret("chain-app-base-url", "PLACEHOLDER")
    print()

    # Step 1: Build with Cloud Build
    print("--- Step 1: Build image ---")
    _run(
        ["gcloud", "builds", "submit",
         "--project", PROJECT_ID,
         "--tag", IMAGE,
         "--timeout", "600s",
         "--machine-type", "e2-highcpu-8",
         "--quiet"],
        desc="Building container image via Cloud Build",
    )
    print(f"  Image built: {IMAGE}")
    print()

    # Step 2: Deploy to Cloud Run
    print("--- Step 2: Deploy to Cloud Run ---")
    deploy_cmd = [
        "gcloud", "run", "deploy", SERVICE,
        "--project", PROJECT_ID,
        "--region", REGION,
        "--image", IMAGE,
        "--platform", "managed",
        "--allow-unauthenticated",
        "--concurrency", "80",
        "--timeout", "300",
        "--memory", "2Gi",
        "--cpu", "1",
        "--min-instances", "0",
        "--max-instances", "5",
        "--set-env-vars", "FLASK_ENV=production,ENV=production,REDIS_SSL_CERT_REQS=required",
        "--quiet",
    ]
    for secret in SECRETS:
        deploy_cmd += ["--update-secrets", secret]

    result = _run(deploy_cmd, desc="Deploying to Cloud Run")
    print()

    # Extract URL from output
    url = None
    for line in (result.stdout or "").splitlines():
        if "Service URL:" in line or "https://" in line:
            for token in line.split():
                if token.startswith("https://"):
                    url = token.rstrip(".")
                    break

    if not url:
        # Fallback: get URL via describe
        desc_result = _run(
            ["gcloud", "run", "services", "describe", SERVICE,
             "--project", PROJECT_ID, "--region", REGION,
             "--format", "json", "--quiet"],
            desc="Fetching service URL",
        )
        try:
            data = json.loads(desc_result.stdout)
            url = data.get("status", {}).get("url", "")
        except json.JSONDecodeError:
            url = ""

    if url:
        print(f"  Deployed URL: {url}")
    else:
        print("  WARNING: Could not determine URL.")
        print(f"  Run: gcloud run services describe {SERVICE} --project {PROJECT_ID} --region {REGION}")
    print()

    # Step 3: Health check
    print("--- Step 3: Health check ---")
    if url:
        health_url = f"{url}/healthz"
        print(f"  Checking {health_url}...")
        time.sleep(15)  # Give Cloud Run a moment to be ready
        import urllib.request
        try:
            req = urllib.request.Request(health_url)
            resp = urllib.request.urlopen(req, timeout=30)
            body = resp.read().decode()
            print(f"  /healthz -> {resp.status}")
            print(f"  response: {body[:200]}")
            if resp.status == 200:
                print("  HEALTH CHECK PASSED")
            else:
                print("  HEALTH CHECK FAILED (non-200 status)")
        except Exception as e:
            print(f"  /healthz -> FAILED: {e}")

        # Verify Redis TLS config
        print()
        redis_health_url = f"{url}/health/redis"
        print(f"  Checking {redis_health_url}...")
        try:
            req = urllib.request.Request(redis_health_url)
            resp = urllib.request.urlopen(req, timeout=30)
            body = resp.read().decode()
            data = json.loads(body)
            scheme = data.get("redis_url_scheme", "")
            ssl_reqs = data.get("ssl_cert_reqs")
            connected = bool(data.get("connected", False))
            print(f"  /health/redis -> {resp.status}")
            print(f"    connected:        {connected}")
            print(f"    redis_url_scheme: {scheme}")
            print(f"    ssl_cert_reqs:    {ssl_reqs}")
            if connected and scheme == "rediss" and ssl_reqs == "required":
                print("  REDIS TLS VERIFICATION PASSED (connected, rediss, required)")
            else:
                print("  REDIS TLS VERIFICATION ISSUE (see above)")
        except Exception as e:
            print(f"  /health/redis -> FAILED: {e}")
    else:
        print("  Skipping health check (no URL)")

    print()
    print("--- Done ---")
    print(f"  URL: {url or 'unknown'}")
    print(f"  To verify: python3 scripts/test_cloudrun_smoke.py --url {url}")


if __name__ == "__main__":
    main()
