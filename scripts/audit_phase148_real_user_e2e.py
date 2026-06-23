#!/usr/bin/env python3
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "gunicorn_error.log"
BASE_URL = "http://127.0.0.1:8080"
BAD_STATUSES = {500, 502, 503, 504}
TIMEOUT_SECONDS = 8.0
DEGRADED_FLAG = "window.NAMVIBE_HOME_DEGRADED = true;"


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirectHandler())


@dataclass
class CheckResult:
    name: str
    method: str
    path: str
    status: Optional[int]
    elapsed_ms: float
    ok: bool
    detail: str


def fetch(path: str, method: str = "GET", data: Optional[bytes] = None, host: Optional[str] = None):
    headers = {}
    if host:
        headers["Host"] = host
    if method == "POST":
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with OPENER.open(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - start) * 1000
            return resp.status, body, dict(resp.headers), elapsed_ms, None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - start) * 1000
        return exc.code, body, dict(exc.headers), elapsed_ms, None
    except (URLError, TimeoutError, OSError) as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return None, "", {}, elapsed_ms, str(exc)


def run_check(name: str, path: str, allowed_statuses, method: str = "GET", data: Optional[bytes] = None, host: Optional[str] = None):
    status, body, headers, elapsed_ms, error = fetch(path, method=method, data=data, host=host)
    if error:
        return CheckResult(name, method, path, status, elapsed_ms, False, error), body, headers
    if status in BAD_STATUSES:
        return CheckResult(name, method, path, status, elapsed_ms, False, f"bad status {status}"), body, headers
    if status not in allowed_statuses:
        return CheckResult(name, method, path, status, elapsed_ms, False, f"unexpected status {status}"), body, headers
    return CheckResult(name, method, path, status, elapsed_ms, True, "ok"), body, headers


def extract_template_errors(log_text: str) -> List[str]:
    matches = re.findall(r'File "([^"]+)", line (\d+).*(Template|jinja|render)', log_text, flags=re.IGNORECASE)
    return [f"{path}:{line}" for path, line, _ in matches]


def main():
    starting_log = LOG_PATH.read_text(errors="replace") if LOG_PATH.exists() else ""
    host = "namvibe.com"

    route_specs = [
        ("GET /", "GET", "/", {200}, None),
        ("GET /auth/login", "GET", "/auth/login", {200}, None),
        ("GET /auth/register", "GET", "/auth/register", {200}, None),
        ("GET /profile/@beta", "GET", "/profile/@beta", {200}, None),
        ("GET /reels/", "GET", "/reels/", {200}, None),
        ("GET /messages/", "GET", "/messages/", {200, 302}, None),
        ("GET /notifications/", "GET", "/notifications/", {200, 302}, None),
        ("GET /wallet/", "GET", "/wallet/", {200, 302}, None),
        ("GET /dating/", "GET", "/dating/", {200, 302}, None),
        ("GET /settings/", "GET", "/settings/", {200, 302}, None),
        ("POST /reels/api/reels/view/batch", "POST", "/reels/api/reels/view/batch", {200}, b'{"reel_ids":["smoke-phase148"]}'),
        ("GET /api/homepage/feed", "GET", "/api/homepage/feed", {200}, None),
    ]

    results: List[CheckResult] = []
    homepage_body = ""
    homepage_headers: Dict[str, str] = {}
    for name, method, path, allowed_statuses, data in route_specs:
        result, body, headers = run_check(name, path, allowed_statuses, method=method, data=data, host=host)
        results.append(result)
        if path == "/":
            homepage_body = body
            homepage_headers = headers

    static_results: List[CheckResult] = []
    css_path = "/static/css/namvibe_home_pro.css"
    js_path = "/static/js/namvibe_home_pro.js?v=phase127"
    css_result, _, _ = run_check(f"GET {css_path}", css_path, {200}, host=host)
    js_result, _, _ = run_check(f"GET {js_path}", js_path, {200}, host=host)
    static_results.extend([css_result, js_result])
    results.extend(static_results)

    degraded_flag_ok = DEGRADED_FLAG in homepage_body
    degraded_result = CheckResult(
        "Homepage degraded flag",
        "GET",
        "/",
        200 if degraded_flag_ok else None,
        0.0,
        degraded_flag_ok,
        "ok" if degraded_flag_ok else "missing degraded flag",
    )
    results.append(degraded_result)

    ending_log = LOG_PATH.read_text(errors="replace") if LOG_PATH.exists() else ""
    new_log = ending_log[len(starting_log):] if ending_log.startswith(starting_log) else ending_log
    missing_template = re.findall(r"(TemplateNotFound|jinja2\.exceptions\.[A-Za-z]+|render_template)", new_log)
    template_locations = extract_template_errors(new_log)
    template_ok = not missing_template
    results.append(CheckResult(
        "Missing template errors",
        "LOG",
        "logs/gunicorn_error.log",
        None,
        0.0,
        template_ok,
        "ok" if template_ok else ", ".join(template_locations[:5]) or "template error found in logs",
    ))

    failures = [r for r in results if not r.ok]
    slowest = sorted([r for r in results if r.method in {"GET", "POST"}], key=lambda item: item.elapsed_ms, reverse=True)[:5]
    timing_gates = {
        "GET /": 3000,
        "GET /profile/@beta": 3000,
        "GET /api/homepage/feed": 3000,
    }
    for result in results:
        limit_ms = timing_gates.get(result.name)
        if limit_ms is not None and result.elapsed_ms > limit_ms and result.ok:
            result.ok = False
            result.detail = f"timing gate exceeded: {round(result.elapsed_ms, 2)}ms > {limit_ms}ms"
            failures.append(result)
    slowest = sorted([r for r in results if r.method in {"GET", "POST"}], key=lambda item: item.elapsed_ms, reverse=True)[:5]

    summary = {
        "target": BASE_URL,
        "virtual_host": host,
        "results": [
            {
                "name": r.name,
                "status": r.status,
                "elapsed_ms": round(r.elapsed_ms, 2),
                "ok": r.ok,
                "detail": r.detail,
            }
            for r in results
        ],
        "slowest_5": [
            {"name": r.name, "status": r.status, "elapsed_ms": round(r.elapsed_ms, 2)}
            for r in slowest
        ],
        "log_template_locations": template_locations[:5],
        "homepage_assets": {
            "css": css_path,
            "js": js_path,
            "degraded_flag": degraded_flag_ok,
            "content_type": homepage_headers.get("Content-Type"),
        },
        "pass": not failures,
    }

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
