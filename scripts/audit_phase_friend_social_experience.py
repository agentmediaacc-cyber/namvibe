#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FILES_WITH_PROFILE_LINKS = [
    ROOT / "templates/discover/index.html",
    ROOT / "templates/profile/index.html",
    ROOT / "templates/notifications/index.html",
    ROOT / "static/js/namvibe_notifications.js",
    ROOT / "static/js/profile_systems.js",
]

NOTIFICATION_FILES = [
    ROOT / "templates/notifications/index.html",
    ROOT / "static/js/namvibe_notifications.js",
    ROOT / "services/notification_center_service.py",
]


def check(name, ok, detail, failures):
    if ok:
        print(f"PASS [{name}] {detail}")
        return
    failures.append(f"{name}: {detail}")
    print(f"FAIL [{name}] {detail}")


def main():
    failures = []

    for path in FILES_WITH_PROFILE_LINKS:
        text = path.read_text(encoding="utf-8")
        bad_patterns = ["/profile/<username>", "/profile/{{ username }}", "/profile/${"]
        found = [pattern for pattern in bad_patterns if pattern in text]
        check(
            f"profile_routes:{path.name}",
            not found,
            "no legacy username routes" if not found else f"found {found}",
            failures,
        )

    discover_text = (ROOT / "templates/discover/index.html").read_text(encoding="utf-8")
    check("discover_profile_route", '/profile/@{{ profile.username }}' in discover_text, "discover cards route to /profile/@username", failures)
    check("discover_avatar_real", "profile.avatar_url" in discover_text, "discover cards render avatar_url", failures)

    notif_service = (ROOT / "services/notification_center_service.py").read_text(encoding="utf-8")
    notif_js = (ROOT / "static/js/namvibe_notifications.js").read_text(encoding="utf-8")
    check("notification_open_url", "open_url" in notif_service and "action_url" in notif_service, "notification service sets safe URLs", failures)
    check("notification_accept_request_id", "data-request-id" in notif_js, "notification actions use request ids", failures)
    check("notification_db_rendering", "fetch('/api/notifications" in notif_js, "notifications render from API/DB feed", failures)

    combined_notif_text = "\n".join(path.read_text(encoding="utf-8") for path in NOTIFICATION_FILES)
    fake_hits = [term for term in ("hardcoded", "demo", "test notification") if term in combined_notif_text.lower()]
    check("notification_no_fake_content", not fake_hits, "no fake notification labels in notification surfaces" if not fake_hits else f"found {fake_hits}", failures)

    profile_template = (ROOT / "templates/profile/index.html").read_text(encoding="utf-8")
    profile_service = (ROOT / "services/profile_service.py").read_text(encoding="utf-8")
    view_service = (ROOT / "services/profile_view_service.py").read_text(encoding="utf-8")
    check("profile_gallery_preview", "pv.gallery_preview" in profile_template, "profile template renders gallery preview", failures)
    check("gallery_viewed_profile_id", "get_profile_gallery(profile[\"id\"], viewer_id=viewer_id" in profile_service, "gallery service loads viewed profile gallery", failures)
    check("mutual_friends_surface", "mutual_friends_items" in view_service and "mutual_friends_count" in profile_template, "mutual friend data is exposed on public profile", failures)

    if failures:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
