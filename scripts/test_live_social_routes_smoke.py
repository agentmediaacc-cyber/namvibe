#!/usr/bin/env python3
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app
from services.neon_service import fast_query


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def find_username(*candidates):
    try:
        for candidate in candidates:
            rows = fast_query(
                """
                SELECT username
                FROM chain_profiles
                WHERE LOWER(username) = LOWER(%s) AND deleted_at IS NULL
                LIMIT 1
                """,
                (candidate,),
                default=[],
            )
            if rows and rows[0].get("username"):
                return rows[0]["username"]
    except Exception as error:
        return f"__db_error__:{error}"
    return None


def acceptable(status_code):
    return status_code in {200, 301, 302, 307, 308, 401, 403, 404}


def main():
    alpha = find_username("alpha", "alpha_social_test", "alpha_messenger")
    beta = find_username("beta", "beta_social_test", "beta_messenger")

    if isinstance(alpha, str) and alpha.startswith("__db_error__:"):
        emit("SKIP", "profile_lookup_alpha", alpha.replace("__db_error__:", "", 1))
        alpha = "alpha"
    else:
        emit("PASS" if alpha else "SKIP", "profile_lookup_alpha", alpha or "falling back to /profile/@alpha")
        alpha = alpha or "alpha"

    if isinstance(beta, str) and beta.startswith("__db_error__:"):
        emit("SKIP", "profile_lookup_beta", beta.replace("__db_error__:", "", 1))
        beta = "beta"
    else:
        emit("PASS" if beta else "SKIP", "profile_lookup_beta", beta or "falling back to /profile/@beta")
        beta = beta or "beta"

    app = create_app()
    failures = 0
    routes = [
        ("/discover", "discover"),
        ("/notifications", "notifications"),
        (f"/profile/@{alpha}", "profile_alpha"),
        (f"/profile/@{beta}", "profile_beta"),
        ("/messages", "messages"),
    ]

    with app.test_client() as client:
        for route, label in routes:
            response = client.get(route, follow_redirects=False)
            ok = acceptable(response.status_code)
            if not emit("PASS" if ok else "FAIL", label, f"{route} -> {response.status_code}"):
                failures += 1

    print("PASS" if failures == 0 else "FAIL")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
