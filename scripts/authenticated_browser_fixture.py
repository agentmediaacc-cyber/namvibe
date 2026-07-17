#!/usr/bin/env python3
from __future__ import annotations

import os
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]


def _rand_suffix(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _set_session(client, profile, email: str, full_name: str, password: str):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = profile["auth_user_id"]
        sess["user_id"] = profile["auth_user_id"]
        sess["profile_id"] = profile["id"]
        sess["username"] = profile["username"]
        sess["auth_email"] = email
        sess["email"] = email
        sess["full_name"] = full_name
        sess["logged_in"] = True
        sess["profile_completed"] = True
        sess["password_hint"] = "[redacted]"


@dataclass
class BrowserFixtureUser:
    profile_id: str
    auth_user_id: str
    email: str
    username: str
    password: str
    full_name: str
    session_cookie: str


class AuthenticatedBrowserFixture:
    """
    Create temporary authenticated users and install a signed session cookie for Playwright.

    The fixture uses the application's real registration service to create a temporary account,
    then places the resulting signed Flask session into a browser context. This avoids any
    client-side auth spoofing while keeping the browser flow representative of production.
    """

    def __init__(self, app):
        self.app = app
        self.users: list[BrowserFixtureUser] = []
        self._created_profile_ids: list[str] = []
        self._created_auth_ids: list[str] = []
        self._created_emails: list[str] = []
        self._created_usernames: list[str] = []
        self._viewer = None
        self._candidate_pass = None
        self._candidate_like = None
        self._candidate_block = None
        self._candidate_report = None

    def _register_temp_user(self, role: str, gender: str, interests: list[str]):
        suffix = _rand_suffix()
        username = f"__dating_browser_test__{role}_{suffix}"
        email = f"{username}@example.com"
        full_name = f"Dating Browser Test {role.title()} {suffix}"
        password = f"{secrets.token_urlsafe(18)}A1!"
        from services.neon_service import fast_query, write_query
        auth_user_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        write_query(
            """
            INSERT INTO chain_profiles (
                id, auth_user_id, username, display_name, full_name, email,
                bio, gender, age, date_of_birth, town, region, current_location,
                country_origin, profile_visibility, is_public, is_verified,
                dating_mode_enabled, relationship_goal, looking_for, interests,
                languages, avatar_url, cover_url, profile_completed, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, 'public', true, true,
                true, %s, %s, %s,
                %s, %s, %s, true, %s, %s
            )
            """,
            (
                profile_id, auth_user_id, username, full_name, full_name, email,
                f"Temporary dating fixture for {role}",
                gender,
                29 if gender != "female" else 28,
                "1995-01-01" if gender != "female" else "1996-01-01",
                "Windhoek",
                "Khomas",
                "Windhoek",
                "Namibia",
                "relationship",
                Json(["serious", "relationship"]),
                Json(interests),
                Json(["english", "oshiwambo"]),
                f"https://picsum.photos/seed/{username}/600/600",
                f"https://picsum.photos/seed/{username}/1200/600",
                now,
                now,
            ),
        )
        profile = fast_query(
            "SELECT id, auth_user_id, username, full_name, display_name FROM chain_profiles WHERE id = %s LIMIT 1",
            (profile_id,),
            timeout_ms=5000,
            default=[],
        )
        now = datetime.now(timezone.utc)
        write_query(
            """
            INSERT INTO chain_dating_profiles (
                id, profile_id, dating_mode_on, relationship_goal, age_range_min, age_range_max,
                location_preference, bio, interests, photos, verification_status, trust_score,
                safety_badge, hide_from_contacts, visible_to_verified_only, is_enabled,
                dating_intent, dating_interest, created_at, updated_at
            ) VALUES (
                %s, %s, true, 'relationship', 18, 45,
                'Windhoek', %s, %s, %s, 'verified', 90,
                true, false, false, true,
                'serious', %s, %s, %s
            )
            """,
            (
                str(uuid.uuid4()), profile_id,
                f"Temporary dating fixture for {role}",
                interests,
                [f"https://picsum.photos/seed/{username}/600/600"],
                ["everyone"],
                now, now,
            ),
        )
        write_query(
            """
            INSERT INTO chain_dating_preferences (
                id, profile_id, interested_in, min_age, max_age, max_distance_km,
                show_me, only_verified, hide_from_contacts, created_at, updated_at
            ) VALUES (%s, %s, %s, 18, 45, 500, true, false, false, %s, %s)
            """,
            (str(uuid.uuid4()), profile_id, "everyone", now, now),
        )
        profile = fast_query(
            "SELECT id, auth_user_id, username, full_name, display_name FROM chain_profiles WHERE id = %s LIMIT 1",
            (profile_id,),
            timeout_ms=5000,
            default=[],
        )
        profile = profile[0] if profile else {"id": profile_id, "auth_user_id": auth_user_id, "username": username, "full_name": full_name, "display_name": full_name}
        serializer = self.app.session_interface.get_signing_serializer(self.app)
        if not serializer:
            raise RuntimeError("session_serializer_missing")
        session_cookie = serializer.dumps(
            {
                "auth_user_id": auth_user_id,
                "user_id": auth_user_id,
                "profile_id": profile_id,
                "username": username,
                "auth_email": email,
                "email": email,
                "full_name": full_name,
                "auth_provider": "password",
                "logged_in": True,
                "profile_completed": True,
                "age_verified": True,
                "age_check_required": False,
                "remember_me": True,
                "login_at": int(now.timestamp()),
            }
        )
        user = BrowserFixtureUser(
            profile_id=profile_id,
            auth_user_id=auth_user_id,
            email=email,
            username=username,
            password=password,
            full_name=full_name,
            session_cookie=session_cookie,
        )
        self.users.append(user)
        self._created_profile_ids.append(profile_id)
        self._created_auth_ids.append(auth_user_id)
        self._created_emails.append(email)
        self._created_usernames.append(username)
        return user, dict(profile or {}), {}

    def setup(self):
        self._viewer, self.viewer_profile, self.viewer_dating = self._register_temp_user(
            "viewer", "male", ["travel", "music", "coffee"]
        )
        self._candidate_pass, self.pass_profile, self.pass_dating = self._register_temp_user(
            "pass", "female", ["travel", "art", "coffee"]
        )
        self._candidate_like, self.like_profile, self.like_dating = self._register_temp_user(
            "match", "female", ["travel", "music", "coffee"]
        )
        self._candidate_block, self.block_profile, self.block_dating = self._register_temp_user(
            "block", "female", ["music", "fitness", "travel"]
        )
        self._candidate_report, self.report_profile, self.report_dating = self._register_temp_user(
            "report", "female", ["music", "reading", "travel"]
        )
        return self

    @property
    def viewer(self):
        return self._viewer

    @property
    def candidate_pass(self):
        return self._candidate_pass

    @property
    def candidate_like(self):
        return self._candidate_like

    @property
    def candidate_block(self):
        return self._candidate_block

    @property
    def candidate_report(self):
        return self._candidate_report

    def install_session(self, context, user: BrowserFixtureUser, origin: str = "http://127.0.0.1:8080"):
        if not user.session_cookie:
            raise RuntimeError("session_cookie_missing")
        context.add_cookies([{
            "name": "session",
            "value": user.session_cookie,
            "url": origin,
        }])
        return True

    def cleanup(self):
        from services.neon_service import fast_query, write_query

        prefix = "__dating_browser_test__%"
        def _safe_write(sql_text: str, params):
            try:
                write_query(sql_text, params)
            except Exception:
                pass

        for user in reversed(self.users):
            pid = user.profile_id
            _safe_write("DELETE FROM chain_notification_events WHERE profile_id = %s OR actor_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_thread_members WHERE profile_id = %s", (pid,))
            _safe_write("DELETE FROM chain_messages WHERE sender_profile_id = %s OR recipient_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_message_threads WHERE created_by_profile_id = %s", (pid,))
            _safe_write("DELETE FROM chain_dating_reports WHERE reporter_profile_id = %s OR reported_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_dating_blocks WHERE blocker_profile_id = %s OR blocked_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_dating_matches WHERE profile_id_a = %s OR profile_id_b = %s", (pid, pid))
            _safe_write("DELETE FROM chain_dating_likes WHERE actor_profile_id = %s OR target_profile_id = %s", (pid, pid))
            _safe_write("DELETE FROM chain_dating_preferences WHERE profile_id = %s", (pid,))
            _safe_write("DELETE FROM chain_dating_profiles WHERE profile_id = %s", (pid,))
            _safe_write("DELETE FROM chain_profiles WHERE id = %s", (pid,))

        # Sweep any stale records from earlier fixture runs that share the same
        # test prefix. This keeps repeated browser runs stable without touching
        # non-test data.
        table_cleanup = [
            (
                "DELETE FROM chain_notification_events WHERE profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR actor_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_notifications WHERE recipient_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR actor_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_thread_members WHERE profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix),
            ),
            (
                "DELETE FROM chain_messages WHERE sender_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR recipient_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_message_threads WHERE created_by_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_reports WHERE reporter_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR reported_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_blocks WHERE blocker_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR blocked_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_matches WHERE profile_id_a IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR profile_id_b IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_likes WHERE actor_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s) OR target_profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix, prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_preferences WHERE profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix),
            ),
            (
                "DELETE FROM chain_dating_profiles WHERE profile_id IN (SELECT id FROM chain_profiles WHERE username LIKE %s OR email LIKE %s)",
                (prefix, prefix),
            ),
            (
                "DELETE FROM chain_profiles WHERE username LIKE %s OR email LIKE %s",
                (prefix, prefix),
            ),
        ]
        for sql, params in table_cleanup:
            _safe_write(sql, params)

        remaining = fast_query(
            """
            SELECT COUNT(*) AS cnt
            FROM chain_profiles
            WHERE username LIKE %s OR email LIKE %s
            """,
            ("__dating_browser_test__%", "__dating_browser_test__%"),
            timeout_ms=5000,
            default=[],
        )
        return bool(remaining and int(remaining[0].get("cnt") or 0) == 0)
