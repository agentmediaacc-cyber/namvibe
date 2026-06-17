#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_REGISTER_TEXT = [
    "Step 1 of 7",
    "Your account starts here",
    "chain-register-progress-text",
]


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status} {name}" + (f" - {detail}" if detail else ""))
    return bool(condition)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def main():
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("ENV", "development")
    os.environ.setdefault("FLASK_TESTING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")
    os.environ.setdefault("SECRET_KEY", "final-stability-local-secret")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    failures = 0
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    register_resp = client.get("/auth/register")
    register_html = register_resp.get_data(as_text=True)
    failures += not check("/auth/register returns 200", register_resp.status_code == 200, f"got {register_resp.status_code}")
    failures += not check("register page omits old step text", not any(text in register_html for text in OLD_REGISTER_TEXT))
    failures += not check("register page has csrf_token", 'name="csrf_token"' in register_html)
    failures += not check("register page has action /auth/register", 'action="/auth/register"' in register_html)
    failures += not check("register page method POST", re.search(r"<form[^>]+method=[\"']POST[\"']", register_html, re.I) is not None)
    failures += not check("register GET sets session cookie", "session=" in register_resp.headers.get("Set-Cookie", ""))

    csrf_resp = client.post(
        "/auth/register",
        data={"email": "csrf-check@local.test", "username": "csrfcheck", "password": "Password123!", "confirm_password": "Password123!", "terms": "on"},
    )
    csrf_body = csrf_resp.get_data(as_text=True)
    failures += not check("POST without csrf handled friendly", csrf_resp.status_code == 200 and "Your session expired. Please try again." in csrf_body)

    for route in (
        "/auth/api/check-email?email=check@local.test",
        "/auth/api/check-username?username=checkuser",
        "/auth/api/check-phone?phone=0812345678",
    ):
        resp = client.get(route)
        is_json = resp.is_json
        failures += not check(f"{route} returns JSON", resp.status_code == 200 and is_json, f"status {resp.status_code}")
        if is_json:
            try:
                json.dumps(resp.get_json())
            except Exception as error:
                failures += not check(f"{route} JSON serializable", False, str(error))

    js_paths = list((ROOT / "static" / "js").glob("*.js"))
    js_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in js_paths)
    chain_register = read("static/js/chain_register.js") if (ROOT / "static/js/chain_register.js").exists() else ""
    auth_minimal = read("static/js/auth_minimal.js") if (ROOT / "static/js/auth_minimal.js").exists() else ""
    register_js = chain_register + "\n" + auth_minimal
    failures += not check('JS has no fetch("/auth/register")', 'fetch("/auth/register")' not in js_text and "fetch('/auth/register')" not in js_text)
    failures += not check("register JS has no preventDefault", "preventDefault" not in register_js)

    css = read("static/css/chain_auth.css")
    css_mobile_ok = (
        "font-size: 16px" in css
        and "min-height: 48px" in css
        and ("background: #fff" in css or "background: #ffffff" in css)
        and "color: #0f172a" in css
        and "caret-color: #0f172a" in css
        and "touch-action: auto" in css
    )
    failures += not check("CSS has mobile input rules", css_mobile_ok)

    compile_cmd = [
        sys.executable,
        "-m",
        "py_compile",
        "app.py",
        "api_routes/auth_routes.py",
        "services/auth_service.py",
        "services/profile_service.py",
    ]
    compile_result = subprocess.run(compile_cmd, cwd=ROOT, text=True, capture_output=True)
    failures += not check("Flask auth/profile files compile", compile_result.returncode == 0, compile_result.stderr.strip())

    active_template = read("templates/auth/register.html")
    failures += not check("active template contains no old register text", not any(text in active_template for text in OLD_REGISTER_TEXT))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
