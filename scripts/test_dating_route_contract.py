#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        raise AssertionError(name)


def main():
    app_py = read("app.py")
    routes = read("api_routes/dating_routes.py")
    matching = read("api_routes/matching_routes.py")

    check("dating blueprint registered once", app_py.count("app.register_blueprint(dating_bp)") == 1)
    check("connecting you registered once", app_py.count("register_connecting_you_routes(app)") == 1)
    check("dating routes are blueprint-based", "Blueprint(\"dating\"" in routes)
    check("discover is GET only", "@dating_bp.route(\"/discover\")" in routes)
    check("like is POST", '@dating_bp.route("/api/like", methods=["POST"])' in routes)
    check("pass is POST", '@dating_bp.route("/api/pass", methods=["POST"])' in routes)
    check("super-like is POST", '@dating_bp.route("/api/super-like", methods=["POST"])' in routes)
    check("report is POST", '@dating_bp.route("/api/report", methods=["POST"])' in routes)
    check("preferences is GET/POST", '@dating_bp.route("/api/preferences", methods=["GET", "POST"])' in routes)
    check("mode is POST", '@dating_bp.route("/api/mode", methods=["POST"])' in routes)
    check("restrict is POST", '@dating_bp.route("/api/restrict", methods=["POST"])' in routes)
    check("match page route exists", '@dating_bp.route("/matches")' in routes)
    check("preferences page route exists", '@dating_bp.route("/preferences")' in routes)
    check("safety page route exists", '@dating_bp.route("/safety")' in routes)
    check("dating route contract uses login_required", "login_required" in routes)
    check("CSRF token referenced in dating JS", "X-CSRFToken" in read("templates/dating/discover.html"))
    check("matching GET mutations are preserved only for redirect compatibility", 'methods=["GET", "POST"]' in matching)
    check("matching template uses forms for actions", "<form class=\"actions\"" in read("templates/matching/discover.html"))


if __name__ == "__main__":
    main()
