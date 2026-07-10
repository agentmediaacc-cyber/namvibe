"""Focused contract tests for the advertising platform registration and guards."""
import importlib
import os
import sys

from flask import Flask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")

from api_routes.advertising_routes import advertising_bp  # noqa: E402
from services import advertising_service as ads  # noqa: E402


def _assert(label, condition):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def _make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(advertising_bp)
    return app


def test_main_app_routes_registered():
    app_module = importlib.import_module("app")
    route_map = {rule.rule for rule in app_module.app.url_map.iter_rules()}
    expected = {
        "/advertising/",
        "/advertising/create",
        "/advertising/api/campaigns/create",
        "/advertising/api/campaigns/<campaign_id>/fund",
        "/advertising/api/track/impression",
        "/advertising/api/track/click",
        "/admin/ads/",
        "/admin/ads/campaigns",
        "/admin/ads/fraud",
        "/admin/ads/api/approve",
        "/admin/ads/api/dashboard",
    }
    for route in expected:
        _assert(f"route registered: {route}", route in route_map)


def test_owned_campaign_guards():
    app = _make_app()
    original_get_campaign = ads.get_campaign
    original_get_creatives = ads.get_creatives_for_campaign
    try:
        ads.get_campaign = lambda campaign_id: {"id": campaign_id, "owner_id": "owner-a"}
        ads.get_creatives_for_campaign = lambda campaign_id: [{"id": "cr-1"}]
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["profile_id"] = "owner-b"
            for path in (
                "/advertising/api/campaigns/c-1/creatives",
                "/advertising/api/campaigns/c-1/targeting",
            ):
                resp = client.get(path)
                _assert(f"ownership 404 for {path}", resp.status_code == 404)
            for path in (
                "/advertising/api/campaigns/c-1/update",
                "/advertising/api/campaigns/c-1/pause",
                "/advertising/api/campaigns/c-1/delete",
                "/advertising/api/campaigns/c-1/duplicate",
                "/advertising/api/campaigns/c-1/creatives/add",
                "/advertising/api/campaigns/c-1/placements",
                "/advertising/api/campaigns/c-1/targeting",
            ):
                resp = client.post(path, json={})
                _assert(f"ownership 404 for {path}", resp.status_code == 404)
            resp = client.post("/advertising/api/campaigns/c-1/fund", json={})
            _assert("ownership 403 for fund route", resp.status_code == 403)
    finally:
        ads.get_campaign = original_get_campaign
        ads.get_creatives_for_campaign = original_get_creatives


def test_invalid_numeric_inputs():
    app = _make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["profile_id"] = "owner-a"
        resp = client.post("/advertising/api/campaigns/create", json={"title": "Bad", "budget": "not-a-number"})
        _assert("campaign create rejects invalid budget", resp.status_code == 400)
        _assert("campaign create returns controlled error", resp.get_json().get("error") == "Invalid numeric campaign values")

        resp = client.post("/advertising/api/campaigns/create", json={"title": "Bad", "budget": -1})
        _assert("campaign create rejects negative budget", resp.status_code == 400)
        _assert("campaign create negative budget message", resp.get_json().get("error") == "Campaign amounts must be non-negative")

        resp = client.post("/advertising/api/campaigns/create", json={"title": "Bad", "budget": 100, "daily_budget": 150})
        _assert("campaign create rejects excessive daily budget", resp.status_code == 400)
        _assert("campaign create daily budget message", resp.get_json().get("error") == "Daily budget cannot exceed total budget")

        resp = client.post("/advertising/api/coupon/validate", json={"code": "SUMMER", "amount": "bad"})
        _assert("coupon validate rejects invalid amount", resp.status_code == 400)
        _assert("coupon validate returns controlled error", resp.get_json().get("error") == "Invalid amount")


def test_impression_failure_is_controlled():
    app = _make_app()
    original_record_impression = ads.record_impression
    try:
        ads.record_impression = lambda campaign_id, profile_id=None: False
        with app.test_client() as client:
            resp = client.post("/advertising/api/track/impression", json={"campaign_id": "missing"})
        _assert("impression failure returns 400", resp.status_code == 400)
        _assert("impression failure response stable", resp.get_json().get("error") == "impression_record_failed")
    finally:
        ads.record_impression = original_record_impression


def test_contract_test_mode_does_not_start_threads():
    app_module = importlib.import_module("app")
    _assert("app testing flag enabled", app_module.app.config.get("TESTING") is True)
    _assert("app helper sees test mode", app_module._app_test_mode() is True)


def test_schema_contract_contains_required_objects():
    sql_path = os.path.join(ROOT, "sql", "phase_advertising_platform.sql")
    sql = open(sql_path, "r", encoding="utf-8").read()
    expected_fragments = [
        "CREATE TABLE IF NOT EXISTS chain_ad_impressions",
        "CREATE TABLE IF NOT EXISTS chain_ad_clicks",
        "ADD COLUMN IF NOT EXISTS owner_id",
        "ADD COLUMN IF NOT EXISTS title",
        "ADD COLUMN IF NOT EXISTS starts_at",
        "ADD COLUMN IF NOT EXISTS ends_at",
        "ADD COLUMN IF NOT EXISTS impressions_count",
        "ADD COLUMN IF NOT EXISTS clicks_count",
        "amount_cents BIGINT DEFAULT 0",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_payments_idempotency",
    ]
    for fragment in expected_fragments:
        _assert(f"schema contains {fragment}", fragment in sql)


def run():
    test_main_app_routes_registered()
    test_owned_campaign_guards()
    test_invalid_numeric_inputs()
    test_impression_failure_is_controlled()
    test_contract_test_mode_does_not_start_threads()
    test_schema_contract_contains_required_objects()
    print("PASS: test_phase181_advertising_feature_contract")


if __name__ == "__main__":
    run()
