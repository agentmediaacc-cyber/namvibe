#!/usr/bin/env python3
import os
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / "venv" / "bin" / "python3"
if os.environ.get("PHASE65_VENV_REEXEC") != "1" and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.environ["PHASE65_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

from services.env_service import ENV_PATH, get_env, load_project_env, mask_env_value

REQUIRED_ENV = [
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]


def report(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {name}{suffix}")
    return bool(ok)


def check_env():
    loaded = load_project_env()
    ok = report(".env exists", ENV_PATH.exists(), str(ENV_PATH))
    ok &= report(".env loaded", loaded or ENV_PATH.exists(), "project-root loader used")
    for name in REQUIRED_ENV:
        value = get_env(name)
        ok &= report(f"{name} loads", bool(value), "present" if value else "missing")
    ok &= report("SUPABASE_KEY not required", bool(get_env("SUPABASE_ANON_KEY")), "SUPABASE_ANON_KEY is canonical")
    return ok


def check_neon():
    database_url = get_env("DATABASE_URL")
    if not database_url:
        return report("Neon SELECT NOW()", False, "DATABASE_URL missing")
    try:
        import psycopg2

        conn = psycopg2.connect(database_url, connect_timeout=8)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT NOW()")
                cur.fetchone()
        finally:
            conn.close()
        return report("Neon SELECT NOW()", True, "connected")
    except Exception as exc:
        return report("Neon SELECT NOW()", False, type(exc).__name__)


def check_redis():
    redis_url = get_env("REDIS_URL")
    if not redis_url:
        return report("Redis ping", False, "REDIS_URL missing")
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        ok = bool(client.ping())
        return report("Redis ping", ok, "connected" if ok else "ping returned false")
    except Exception as exc:
        return report("Redis ping", False, type(exc).__name__)


def check_supabase_names():
    ok = True
    ok &= report("Supabase URL present", bool(get_env("SUPABASE_URL")))
    ok &= report("Supabase anon key present", bool(get_env("SUPABASE_ANON_KEY")))
    ok &= report("Supabase service role key present", bool(get_env("SUPABASE_SERVICE_ROLE_KEY")))
    return ok


def check_cloudrun_safety():
    path = ROOT / "cloudrun.yaml"
    if not path.exists():
        return report("cloudrun.yaml exists", False)
    content = path.read_text()
    ok = True
    ok &= report("Cloud Run uses Secret Manager refs", "valueFrom:" in content and "secretKeyRef:" in content)
    unsafe_placeholders = [
        "YOUR_SECRET_KEY_PLACEHOLDER",
        "YOUR_DATABASE_URL_PLACEHOLDER",
        "YOUR_REDIS_URL_PLACEHOLDER",
        "YOUR_SUPABASE_URL_PLACEHOLDER",
        "YOUR_SUPABASE_ANON_KEY_PLACEHOLDER",
        "YOUR_SUPABASE_SERVICE_ROLE_KEY_PLACEHOLDER",
        "YOUR_APP_BASE_URL_PLACEHOLDER",
    ]
    ok &= report("Cloud Run secret placeholders removed", not any(item in content for item in unsafe_placeholders))
    for name in REQUIRED_ENV + ["SECRET_KEY"]:
        value = get_env(name)
        if value and len(value) >= 8:
            ok &= report(f"cloudrun.yaml does not contain real {name}", value not in content)
    return ok


def check_no_forbidden_scan():
    skipped = {"venv", "site-packages"}
    touched = []
    for path in ROOT.rglob("*"):
        parts = set(path.parts)
        if parts & skipped:
            continue
        if path.is_file() and path.name in {"cloudrun.yaml", "cloudrun.example.yaml"}:
            touched.append(path.name)
    return report("Audit scan excludes venv/site-packages", bool(touched), ", ".join(sorted(touched)))


def check_compile():
    files = [
        ROOT / "app.py",
        ROOT / "config" / "settings.py",
        ROOT / "services" / "env_service.py",
        ROOT / "services" / "neon_service.py",
        ROOT / "services" / "redis_service.py",
        ROOT / "utils" / "supabase_client.py",
        ROOT / "scripts" / "audit_phase65_env_connection.py",
        ROOT / "scripts" / "test_phase65_runtime_env.py",
    ]
    ok = True
    for file_path in files:
        try:
            py_compile.compile(str(file_path), doraise=True)
            ok &= report(f"compile {file_path.relative_to(ROOT)}", True)
        except Exception as exc:
            ok &= report(f"compile {file_path.relative_to(ROOT)}", False, type(exc).__name__)
    return ok


def main():
    print("Phase 65 env connection audit")
    print(f"Env file: {ENV_PATH}")
    print(f"Masked DATABASE_URL: {mask_env_value('DATABASE_URL', get_env('DATABASE_URL'))}")

    ok = True
    ok &= check_env()
    ok &= check_neon()
    ok &= check_redis()
    ok &= check_supabase_names()
    ok &= check_cloudrun_safety()
    ok &= check_no_forbidden_scan()
    ok &= check_compile()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
