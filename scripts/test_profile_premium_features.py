#!/usr/bin/env python3
"""Premium profile feature verification."""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {name}" + (f" - {detail}" if detail else ""))
    return bool(condition)


def route_rules(app):
    return {str(rule): rule for rule in app.url_map.iter_rules()}


def has_rule(rules, rule):
    return rule in rules


def source_has_route(routes_src, fragment):
    return fragment in routes_src


def main():
    sys.path.insert(0, str(ROOT))
    failures = 0

    try:
        from app import app
        ok_app = True
    except Exception as exc:
        print(f"FAIL: import app - {exc}")
        return 1

    rules = route_rules(app)
    routes_src = read("api_routes/profile_routes.py")
    profile_index = read("templates/profile/index.html")
    profile_header = read("templates/profile/partials/profile_header.html")
    profile_tabs = read("templates/profile/partials/profile_tabs.html")
    profile_css = read("static/css/profile_premium.css") + "\n" + read("static/css/chain_profile.css")

    required_routes = [
        "/profile/",
        "/profile/edit",
        "/profile/avatar",
        "/profile/cover",
        "/profile/@<username>",
        "/profile/@<username>/follow",
        "/profile/@<username>/report",
        "/profile/@<username>/block",
        "/profile/follow/<profile_id>",
        "/profile/report/<profile_id>",
        "/profile/block/<profile_id>",
        "/profile/unblock/<target_id>",
        "/profile/security",
        "/profile/privacy",
        "/profile/settings/privacy",
        "/profile/wallet",
        "/profile/<user_id>/follow",
    ]
    for rule in required_routes:
        failures += not check(f"profile route exists {rule}", has_rule(rules, rule))

    with app.test_client() as client:
        for path in ["/profile/", "/profile/edit", "/profile/security", "/profile/privacy", "/profile/wallet"]:
            try:
                response = client.get(path, follow_redirects=False)
                failures += not check(f"{path} returns 200/302 not 500", response.status_code in {200, 302}, str(response.status_code))
            except Exception as exc:
                failures += not check(f"{path} returns 200/302 not 500", False, str(exc))

    for template_name in [
        "profile/base_profile.html",
        "profile/index.html",
        "profile/edit.html",
        "profile/privacy.html",
        "profile/security.html",
        "profile/partials/profile_header.html",
        "profile/partials/profile_tabs.html",
        "profile/partials/profile_empty_state.html",
    ]:
        try:
            app.jinja_env.get_template(template_name)
            failures += not check(f"profile template compiles {template_name}", True)
        except Exception as exc:
            failures += not check(f"profile template compiles {template_name}", False, str(exc))

    route_fragments = {
        "avatar upload": '@profile_bp.route("/avatar"',
        "cover upload": '@profile_bp.route("/cover"',
        "follow username": '@profile_bp.route("/@<username>/follow"',
        "follow toggle": '@profile_bp.route("/<user_id>/follow"',
        "block": '@profile_bp.route("/@<username>/block"',
        "report": '@profile_bp.route("/@<username>/report"',
        "privacy": '@profile_bp.route("/privacy"',
        "security": '@profile_bp.route("/security"',
    }
    for name, fragment in route_fragments.items():
        failures += not check(f"{name} route declared", source_has_route(routes_src, fragment))

    link_checks = {
        "wallet link": "/wallet" in profile_index or "/profile/wallet" in profile_index,
        "dating link": "/matching/" in profile_index or "/dating" in profile_index,
        "message button": "/messages/start/" in profile_index + profile_header,
        "call button": "/calls/start/" in profile_index + profile_header,
    }
    for name, ok in link_checks.items():
        failures += not check(name, ok)

    private_tokens = ("email", "auth_user_id", "access_token", "refresh_token")
    public_templates = profile_index + "\n" + profile_header + "\n" + read("templates/profile/public.html")
    exposed = [token for token in private_tokens if re.search(r"{{[^}]*\\b" + re.escape(token) + r"\\b", public_templates)]
    failures += not check("public profile does not expose private tokens", not exposed, ", ".join(exposed))

    failures += not check("default avatar fallback exists", "static/img/default_avatar.png" in "\n".join(p.as_posix() for p in (ROOT / "static/img").glob("*")) or "profile-avatar" in profile_css)
    failures += not check("default cover fallback exists", "profile-cover-fallback" in profile_header and "profile-cover-fallback" in profile_css)
    failures += not check("mobile CSS exists", "@media" in profile_css and ("max-width: 768px" in profile_css or "max-width: 760px" in profile_css))

    follow_buttons = (profile_index + profile_header).count("data-profile-follow")
    failures += not check("profile buttons are not duplicated", follow_buttons <= 2, f"follow buttons={follow_buttons}")

    for tab in ("posts", "reels", "media", "live", "store", "about", "saved", "liked"):
        failures += not check(f"profile tab exists {tab}", f'data-tab-target="{tab}"' in profile_tabs)

    count_tokens = ("posts_count", "reels_count", "followers_count", "following_count", "stats_data", "public_stats")
    failures += not check("counts render safely", all(token in profile_header for token in count_tokens))

    placeholder_tokens = (
        "picsum",
        "pravatar",
        "unsplash",
        "12.4K",
        "450.75",
        "African next-generation",
        "Windhoek, Namibia",
        "Sample Post",
        "Placeholder",
    )
    profile_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "templates/profile").glob("**/*.html")
    )
    found_placeholders = [token for token in placeholder_tokens if token in profile_sources]
    failures += not check("no placeholder profile content", not found_placeholders, ", ".join(found_placeholders))

    seed_tokens = ("chain_star", "chain_moon", "chain_gold", "chain_million", "chain_premium", "@chain.local")
    found_seed = [token for token in seed_tokens if token in profile_sources]
    failures += not check("no test/demo user content in public profile UI", not found_seed, ", ".join(found_seed))

    if failures:
        print(f"FAIL: {failures} profile checks failed")
        return 1
    print("PASS: profile premium feature checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
