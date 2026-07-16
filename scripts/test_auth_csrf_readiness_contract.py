#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _extract_csrf(html: str) -> str | None:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    from app import create_app, _make_apk_csrf_token

    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)

    with app.test_client() as client:
        response = client.get("/auth/register")
        html = response.get_data(as_text=True)
        token = _extract_csrf(html)
        with app.app_context():
            apk_token = _make_apk_csrf_token(app, "/auth/register")
        ok = True
        ok &= check("registration page returns 200", response.status_code == 200, str(response.status_code))
        ok &= check("registration page sets csrf token", bool(token))
        ok &= check("registration page sets apk csrf token", 'name="apk_csrf_token"' in html)
        ok &= check("registration page is not hardwired to old localhost port", "127.0.0.1:5000" not in html and "localhost:5000" not in html)

        payload = {
            "csrf_token": token or "",
            "apk_csrf_token": apk_token,
            "full_name": "Offline Contract User",
            "email": "offline.contract@example.com",
            "username": "offlinecontract",
            "password": "Phase78RealPass!",
            "confirm_password": "Phase78RealPass!",
            "terms": "on",
        }
        with patch("api_routes.auth_routes.register_chain_user") as register_mock:
            register_mock.return_value = {"ok": True, "requires_confirmation": True}
            post_response = client.post("/auth/register", data=payload, follow_redirects=False)
            ok &= check("csrf-protected registration accepted by route", post_response.status_code in (200, 302, 303), str(post_response.status_code))
            ok &= check("registration route calls service layer once", register_mock.call_count == 1, str(register_mock.call_count))
            call_args = register_mock.call_args.args
            call_kwargs = register_mock.call_args.kwargs
            extra = call_kwargs.get("extra") or {}
            ok &= check("csrf validity reaches service layer", extra.get("csrf_valid") is True, str(extra))

        missing_apk_payload = dict(payload)
        missing_apk_payload.pop("apk_csrf_token")
        with patch("api_routes.auth_routes.register_chain_user") as register_mock:
            register_mock.return_value = {"ok": True, "requires_confirmation": True}
            missing_apk_response = client.post("/auth/register", data=missing_apk_payload, follow_redirects=False)
            ok &= check("missing apk token still returns controlled response", missing_apk_response.status_code in (200, 302, 303), str(missing_apk_response.status_code))
            ok &= check("service layer not called without apk token", register_mock.call_count == 0, str(register_mock.call_count))
            ok &= check("missing-apk response stays on register page", "Your session expired" in missing_apk_response.get_data(as_text=True) or "Create Account" in missing_apk_response.get_data(as_text=True))

    print("TEST_OK auth csrf readiness contract" if ok else "TEST_FAIL auth csrf readiness contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
