"""Phase 104 — Upload local .env secrets to Google Secret Manager.

Usage:
    PROJECT_ID=my-gcp-project python3 scripts/setup_gcloud_secrets_from_env.py

Never prints raw secret values. Outputs only SET/MISSING/UPDATED.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
if not PROJECT_ID:
    print("ERROR: PROJECT_ID env var is required.")
    print("Usage: PROJECT_ID=my-gcp-project python3 scripts/setup_gcloud_secrets_from_env.py")
    sys.exit(1)

# Mapping of .env var name -> Google Secret Manager secret name
SECRET_MAP = {
    "SECRET_KEY": "chain-secret-key",
    "DATABASE_URL": "chain-database-url",
    "REDIS_URL": "chain-redis-url",
    "SUPABASE_URL": "chain-supabase-url",
    "SUPABASE_ANON_KEY": "chain-supabase-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "chain-supabase-service-role-key",
}

# Required but allows missing — the URL is derived from the deployed Cloud Run URL
SOFT_REQUIRED = {
    "APP_BASE_URL": "chain-app-base-url",
}

OPTIONAL_SECRET_MAP = {
    "LIVEKIT_URL": "chain-livekit-url",
    "LIVEKIT_API_KEY": "chain-livekit-api-key",
    "LIVEKIT_API_SECRET": "chain-livekit-api-secret",
    "TURN_SERVER_URL": "chain-turn-server-url",
    "TURN_USERNAME": "chain-turn-username",
    "TURN_PASSWORD": "chain-turn-password",
    "SENTRY_DSN": "chain-sentry-dsn",
}

# Env vars that must NOT be uploaded to Secret Manager (local-only overrides)
SKIP_SECRETS = {"REDIS_SSL_CERT_REQS"}


def _read_env():
    """Read .env file into a dict. Never prints values."""
    if not ENV_PATH.exists():
        print(f"ERROR: .env not found at {ENV_PATH}")
        sys.exit(1)
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env[key] = value
    return env


def _gcloud(*args, check=True, input_data=None):
    cmd = ["gcloud", "--project", PROJECT_ID, "--quiet"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, input=input_data)
    if check and result.returncode != 0:
        print(f"  gcloud error: {result.stderr.strip()[:200]}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _is_localhost_redis(redis_url):
    """Check if a Redis URL points to localhost without exposing the value."""
    cleaned = redis_url.strip()
    if not cleaned:
        return False
    after_proto = cleaned.split("://", 1)[1] if "://" in cleaned else cleaned
    host_part = after_proto.split("@")[-1] if "@" in after_proto else after_proto
    host = host_part.split(":")[0]
    return host in ("localhost", "127.0.0.1")


def main():
    print(f"Project: {PROJECT_ID}")
    print(f"Env file: {ENV_PATH}")
    print()

    env = _read_env()

    redis_url = env.get("REDIS_URL", "")
    if redis_url and _is_localhost_redis(redis_url):
        print("  [WARN] Local Redis URL detected. Cloud Run real-time will be degraded.")
        print("  [WARN] Set a managed Redis URL (Upstash / Memorystore) for full functionality.")
        print("  [WARN] See docs/CLOUD_RUN_REDIS_SETUP.md")
        print()

    required_ok = 0
    required_total = 0

    print("--- Required secrets ---")
    for var_name, secret_name in SECRET_MAP.items():
        required_total += 1
        value = env.get(var_name, "")
        if _create_or_update_secret(secret_name, value, var_name):
            required_ok += 1

    print()
    print("--- Soft-required secrets (okay if missing) ---")
    for var_name, secret_name in SOFT_REQUIRED.items():
        value = env.get(var_name, "")
        _create_or_update_secret(secret_name, value, var_name)

    print()
    # Warn about skipped local-only env vars
    for var_name in SKIP_SECRETS:
        val = env.get(var_name, "")
        if val and val.strip().lower() == "none":
            print(f"  [SKIP] {var_name}=none (local-only macOS override, not uploaded to Cloud Run)")
            print(f"  [INFO] Cloud Run will use default SSL verification (certificate required)")

    print("--- Optional secrets ---")
    for var_name, secret_name in OPTIONAL_SECRET_MAP.items():
        value = env.get(var_name, "")
        _create_or_update_secret(secret_name, value, var_name)

    print()
    print(f"Required: {required_ok}/{required_total} set/updated")
    success = required_ok == required_total
    print(f"Status: {'ALL OK' if success else 'SOME MISSING (check above)'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
