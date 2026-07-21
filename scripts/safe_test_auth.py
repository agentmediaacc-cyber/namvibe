#!/usr/bin/env python3
from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query


def _rand_suffix(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class SafeTestUser:
    profile_id: str
    auth_user_id: str
    email: str
    username: str
    full_name: str
    session_cookie: str


class SafeAuthenticatedSession:
    """Create and clean up a temporary authenticated profile for safe tests."""

    def __init__(self, app, prefix: str = "__safe_auth_test__"):
        self.app = app
        self.prefix = prefix
        self.user: SafeTestUser | None = None

    def create(self, *, role: str = "viewer", is_public: bool = True, profile_type: str = "member") -> SafeTestUser:
        suffix = _rand_suffix()
        username = f"{self.prefix}{role}_{suffix}"
        email = f"{username}@example.com"
        full_name = f"Safe Auth {role.title()} {suffix}"
        auth_user_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        write_query(
            """
            INSERT INTO chain_profiles (
                id, auth_user_id, username, display_name, full_name, email,
                profile_type, is_public, profile_completed, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s)
            """,
            (
                profile_id,
                auth_user_id,
                username,
                full_name,
                full_name,
                email,
                profile_type,
                is_public,
                now,
                now,
            ),
        )

        self.user = SafeTestUser(
            profile_id=profile_id,
            auth_user_id=auth_user_id,
            email=email,
            username=username,
            full_name=full_name,
            session_cookie=self._sign_session_cookie(profile_id, auth_user_id, username, email, full_name),
        )
        return self.user

    def _sign_session_cookie(self, profile_id: str, auth_user_id: str, username: str, email: str, full_name: str) -> str:
        serializer = self.app.session_interface.get_signing_serializer(self.app)
        if not serializer:
            raise RuntimeError("session_serializer_missing")
        return serializer.dumps(
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
            }
        )

    def attach_session(self, client, user: SafeTestUser | None = None):
        user = user or self.user
        if not user:
            raise RuntimeError("safe_test_user_missing")
        with client.session_transaction() as sess:
            sess["auth_user_id"] = user.auth_user_id
            sess["user_id"] = user.auth_user_id
            sess["profile_id"] = user.profile_id
            sess["username"] = user.username
            sess["auth_email"] = user.email
            sess["email"] = user.email
            sess["full_name"] = user.full_name
            sess["logged_in"] = True
            sess["profile_completed"] = True
        return client

    def cleanup(self):
        if not self.user:
            return
        pid = self.user.profile_id
        email = self.user.email
        username = self.user.username
        for sql, params in [
            ("DELETE FROM chain_notifications WHERE recipient_profile_id = %s OR actor_profile_id = %s", (pid, pid)),
            ("DELETE FROM chain_friend_requests WHERE sender_profile_id = %s OR recipient_profile_id = %s", (pid, pid)),
            ("DELETE FROM chain_friends WHERE profile_id_1 = %s OR profile_id_2 = %s", (pid, pid)),
            ("DELETE FROM chain_messages WHERE sender_profile_id = %s OR recipient_profile_id = %s", (pid, pid)),
            ("DELETE FROM chain_thread_members WHERE profile_id = %s", (pid,)),
            ("DELETE FROM chain_message_threads WHERE created_by_profile_id = %s", (pid,)),
            ("DELETE FROM chain_profile_views WHERE viewer_profile_id = %s OR viewed_profile_id = %s", (pid, pid)),
            ("DELETE FROM chain_premium_subscriptions WHERE profile_id = %s", (pid,)),
            ("DELETE FROM chain_subscriptions WHERE subscriber_profile_id = %s", (pid,)),
            ("DELETE FROM chain_profiles WHERE id = %s OR email = %s OR username = %s", (pid, email, username)),
        ]:
            try:
                write_query(sql, params)
            except Exception:
                pass

        self.user = None
