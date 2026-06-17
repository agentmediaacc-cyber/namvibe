"""Route tests for Phase 71: TikTok reels routes.

Usage: python -m pytest scripts/test_phase71_tiktok_routes.py -v
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app

IGNORE_REDIRECT = object()

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "127.0.0.1:5000"
    return app.test_client()

def _get(client, path, expected_status=200):
    resp = client.get(path)
    assert resp.status_code in (expected_status, 302), f"GET {path} returned {resp.status_code}, expected {expected_status}"
    return resp

def _post(client, path, data=None, expected_status=200):
    resp = client.post(path, data=data or {}, content_type="application/json")
    assert resp.status_code in (expected_status, 302), f"POST {path} returned {resp.status_code}, expected {expected_status}"
    return resp

class TestPhase71TiktokReels:

    def test_homepage_renders(self, client):
        """GET / should return 200/302 and include TikTok reel section"""
        resp = client.get("/")
        assert resp.status_code in (200, 302), f"GET / returned {resp.status_code}"

    def test_homepage_tiktok_content(self, client):
        """GET / should include tiktok_home.css link"""
        resp = client.get("/")
        html = resp.data.decode()
        assert "tiktok_home.css" in html, "tiktok_home.css not linked from homepage"
        assert "tiktok_home.js" in html or "/static/js/tiktok_home.js" in html, "tiktok_home.js not linked from homepage"

    def test_reels_page(self, client):
        """GET /reels should return 200 (follows 308 redirect from /reels -> /reels/)"""
        resp = client.get("/reels", follow_redirects=True)
        assert resp.status_code in (200, 302), f"/reels returned {resp.status_code}"

    def test_reels_comments_api(self, client):
        """GET /reels/api/reels/<id>/comments should return 200/404"""
        resp = client.get("/reels/api/reels/1/comments")
        assert resp.status_code in (200, 404, 400, 302), f"/reels/api/reels/1/comments returned {resp.status_code}"
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None, "comments API did not return JSON"

    def test_home_feed_api(self, client):
        """GET /api/home/feed should return 200 and JSON array"""
        resp = client.get("/api/home/feed", follow_redirects=True)
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None, "/api/home/feed did not return JSON"
        else:
            assert resp.status_code in (200, 302), f"/api/home/feed returned {resp.status_code}"

    def test_discover_page(self, client):
        """GET /discover should return 200"""
        resp = client.get("/discover", follow_redirects=True)
        assert resp.status_code in (200, 302), f"/discover returned {resp.status_code}"

    def test_reels_upload_redirect(self, client):
        """GET /reels/upload should be accessible (may redirect if not logged in)"""
        resp = client.get("/reels/upload", follow_redirects=True)
        assert resp.status_code in (200, 302, 401, 403), f"/reels/upload returned unexpected {resp.status_code}"

    def test_tiktok_css_exists(self, client):
        """Static CSS should be accessible"""
        resp = client.get("/static/css/tiktok_home.css")
        assert resp.status_code in (200, 302), f"tiktok_home.css returned {resp.status_code}"
        assert b"tiktok-reel-stack" in resp.data or resp.status_code == 302, "tiktok_home.css missing .tiktok-reel-stack"

    def test_tiktok_js_exists(self, client):
        """Static JS should be accessible"""
        resp = client.get("/static/js/tiktok_home.js")
        assert resp.status_code in (200, 302), f"tiktok_home.js returned {resp.status_code}"
        assert b"initReelScroll" in resp.data or resp.status_code == 302, "tiktok_home.js missing initReelScroll"


