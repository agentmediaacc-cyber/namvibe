#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts" / "authenticated_browser_fixture.py"
SMOKE = ROOT / "scripts" / "test_dating_browser_smoke.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing:{needle}")


def main() -> int:
    fixture = _read(FIXTURE)
    smoke = _read(SMOKE)

    # Fixture namespace and session isolation
    _require(fixture, "__dating_browser_test__")
    _require(fixture, "def install_session(")
    _require(fixture, "auth_user_id")
    _require(fixture, "profile_id")
    _require(fixture, "session_cookie")

    # Cleanup must be reverse-ordered, bounded, and marker-scoped.
    _require(fixture, "prefix = \"__dating_browser_test__%\"")
    _require(fixture, "def _safe_write(")
    _require(fixture, "table_cleanup")
    _require(fixture, "SELECT COUNT(*) AS cnt")
    for table in (
        "chain_notification_events",
        "chain_notifications",
        "chain_thread_members",
        "chain_messages",
        "chain_message_threads",
        "chain_dating_reports",
        "chain_dating_blocks",
        "chain_dating_matches",
        "chain_dating_likes",
        "chain_dating_preferences",
        "chain_dating_profiles",
        "chain_profiles",
    ):
        _require(fixture, table)

    # Browser smoke must probe identity through /dating/ and classify aborted requests.
    _require(smoke, '_probe_identity(page, [fixture.viewer.full_name, fixture.viewer.username, fixture.viewer.email])')
    _require(smoke, '_goto(page, "/dating/")')
    _require(smoke, "ERR_ABORTED")
    _require(smoke, "wait_for_function(")
    _require(smoke, "matches_api")
    _require(smoke, "fixture.install_session(context, fixture.viewer")

    print("TEST_OK dating browser fixture contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
