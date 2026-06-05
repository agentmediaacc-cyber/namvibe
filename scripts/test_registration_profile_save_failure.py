import contextlib
import io
import os
import re
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA_COLUMNS = {
    "id",
    "auth_user_id",
    "email",
    "normalized_email",
    "username",
    "username_slug",
    "full_name",
    "display_name",
    "phone",
    "normalized_phone",
    "country_origin",
    "country",
    "region",
    "town",
    "email_verified",
    "is_verified",
    "profile_completed",
    "onboarding_step",
    "profile_type",
    "terms_accepted",
    "human_confirmed",
    "created_at",
    "updated_at",
}


def _form(email, username, password="Password123!"):
    return {
        "email": email,
        "password": password,
        "confirm_password": password,
        "username": username,
        "full_name": "Profile Save Tester",
        "phone_code": "+264",
        "phone": "811234567",
        "country_origin": "Namibia",
        "current_country": "Namibia",
        "region": "Khomas",
        "town": "Windhoek",
        "agreement_true_details": "on",
        "agreement_identity_use": "on",
        "agreement_username_privacy": "on",
        "agreement_standards": "on",
        "agreement_no_abuse": "on",
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
    }


def _signup_client(auth_user_id, email):
    supabase = MagicMock()
    supabase.auth.sign_up.return_value = SimpleNamespace(
        user=SimpleNamespace(id=auth_user_id, email=email, user_metadata={}),
        session=None,
    )
    return supabase


def _patch_common(supabase):
    return [
        patch("services.auth_service.get_supabase", return_value=supabase),
        patch("services.auth_service.get_auth_user_by_email", return_value=None),
        patch("services.auth_service.safe_select", return_value=[]),
        patch("services.auth_service._supabase_auth_email_exists", return_value=False),
        patch("services.auth_service._profile_exists_by_username", return_value=False),
        patch("services.profile_service.fast_query", return_value=[]),
        patch("services.profile_service._direct_profile_lookup", return_value=None),
        patch("services.profile_service.safe_select", return_value=[]),
        patch("services.profile_service._ensure_profile_dependencies", return_value=None, create=True),
        patch("services.auth_service._ensure_profile_dependencies", return_value=None),
        patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)),
        patch("api_routes.profile_routes.is_profile_complete", return_value=True),
        patch("api_routes.profile_routes.get_profile_bundle", side_effect=lambda *args, **kwargs: {"profile": kwargs.get("viewer") or {}}),
        patch("api_routes.profile_routes.build_profile_dashboard", side_effect=lambda *args, **kwargs: {"profile": kwargs.get("profile") or (args[0] if args else {})}),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
        patch("api_routes.profile_routes.render_template", return_value="Not Verified"),
    ]


def _run_with_patches(patches, fn):
    stack = contextlib.ExitStack()
    with stack:
        for item in patches:
            stack.enter_context(item)
        return fn()


def main():
    os.environ["FLASK_ENV"] = "development"
    os.environ["ENV"] = "development"
    os.environ["CHAIN_FAST_LOCAL"] = "1"

    from app import create_app
    from services import profile_service

    app = create_app()
    app.config["TESTING"] = True

    failing_auth_user_id = str(uuid.uuid4())
    failing_email = f"profilefail_{uuid.uuid4().hex[:10]}@example.com"
    failing_username = f"profilefail_{uuid.uuid4().hex[:8]}"
    failing_supabase = _signup_client(failing_auth_user_id, failing_email)

    def failing_write_query(sql, params=None, timeout_ms=None):
        raise RuntimeError('Database connection pool is unavailable; column "current_country" does not exist')

    failure_log = io.StringIO()

    def failure_case():
        client = app.test_client()
        with contextlib.redirect_stdout(failure_log), contextlib.redirect_stderr(failure_log):
            response = client.post("/auth/register", data=_form(failing_email, failing_username), follow_redirects=False)
        print("failure_register_status", response.status_code)
        print("failure_register_location", response.headers.get("Location"))
        assert response.status_code == 302
        assert response.headers.get("Location") == "/profile/"
        with client.session_transaction() as sess:
            assert sess.get("auth_user_id") == failing_auth_user_id
            assert sess.get("user_id") == failing_auth_user_id
            assert sess.get("profile_id")
            assert sess.get("email") == failing_email
            assert sess.get("dev_profile")
        profile_response = client.get("/profile/", follow_redirects=False)
        print("failure_profile_status", profile_response.status_code)
        print("failure_profile_not_verified", "Not Verified" in profile_response.get_data(as_text=True))
        assert profile_response.status_code == 200
        assert "Not Verified" in profile_response.get_data(as_text=True)

    _run_with_patches(
        [
            *_patch_common(failing_supabase),
            patch("services.profile_service._chain_profile_columns_set", return_value=SCHEMA_COLUMNS),
            patch("services.profile_service.write_query", side_effect=failing_write_query),
        ],
        failure_case,
    )
    logs = failure_log.getvalue()
    print("failure_logged_insert", "profile_insert_failed" in logs or "_neon_insert_profile failed" in logs)
    print("failure_logged_missing_column", "current_country" in logs)
    assert "profile_insert_failed" in logs or "_neon_insert_profile failed" in logs
    assert "current_country" in logs

    success_auth_user_id = str(uuid.uuid4())
    success_email = f"profilesave_{uuid.uuid4().hex[:10]}@example.com"
    success_username = f"profilesave_{uuid.uuid4().hex[:8]}"
    success_supabase = _signup_client(success_auth_user_id, success_email)
    saved_rows = {}

    def success_write_query(sql, params=None, timeout_ms=None):
        if "INSERT INTO chain_profiles" in sql:
            columns = [part.strip() for part in re.search(r"INSERT INTO chain_profiles \((.*?)\)", sql, re.S).group(1).split(",")]
            unexpected = sorted(set(columns) - SCHEMA_COLUMNS)
            assert not unexpected, unexpected
            row = {column: value for column, value in zip(columns, params or [])}
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("email_verified", False)
            row.setdefault("is_verified", False)
            saved_rows[row["auth_user_id"]] = row
            return [row]
        if "UPDATE chain_profiles" in sql:
            profile_id = (params or [])[-1]
            row = next((item for item in saved_rows.values() if item.get("id") == profile_id), None)
            if not row:
                return []
            assignments = re.search(r"SET (.*?), updated_at", sql, re.S).group(1).split(",")
            columns = [item.split("=")[0].strip() for item in assignments]
            unexpected = sorted(set(columns) - SCHEMA_COLUMNS)
            assert not unexpected, unexpected
            for column, value in zip(columns, params or []):
                row[column] = value
            return [row]
        return []

    def success_case():
        profile_service._CHAIN_PROFILE_COLUMNS_CACHE = set(SCHEMA_COLUMNS)
        client = app.test_client()
        response = client.post("/auth/register", data=_form(success_email, success_username), follow_redirects=False)
        print("success_register_status", response.status_code)
        print("success_register_location", response.headers.get("Location"))
        assert response.status_code == 302
        assert response.headers.get("Location") == "/profile/"
        row = saved_rows.get(success_auth_user_id)
        print("success_profile_saved", bool(row))
        assert row
        assert row.get("auth_user_id") == success_auth_user_id
        assert row.get("email") == success_email
        assert row.get("username") == success_username
        assert row.get("full_name") == "Profile Save Tester"
        assert row.get("phone") == "+264811234567"
        assert row.get("country_origin") == "Namibia"
        assert row.get("region") == "Khomas"
        assert row.get("town") == "Windhoek"
        assert row.get("email_verified") is False
        assert row.get("is_verified") is False
        with client.session_transaction() as sess:
            assert sess.get("auth_user_id") == success_auth_user_id
            assert sess.get("user_id") == success_auth_user_id
            assert sess.get("profile_id") == row.get("id")
            assert sess.get("email") == success_email
        with patch("api_routes.profile_routes.get_current_profile", return_value=row):
            profile_response = client.get("/profile/", follow_redirects=False)
        print("success_profile_status", profile_response.status_code)
        print("success_profile_not_verified", "Not Verified" in profile_response.get_data(as_text=True))
        assert profile_response.status_code == 200
        assert "Not Verified" in profile_response.get_data(as_text=True)

    _run_with_patches(
        [
            *_patch_common(success_supabase),
            patch("services.profile_service._chain_profile_columns_set", return_value=SCHEMA_COLUMNS),
            patch("services.profile_service.write_query", side_effect=success_write_query),
        ],
        success_case,
    )


if __name__ == "__main__":
    main()
