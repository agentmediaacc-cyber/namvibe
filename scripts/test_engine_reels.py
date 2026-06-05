import unittest
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view
from flask import Flask

class TestReelsEngine(unittest.TestCase):
    def test_list_reels_public(self):
        reels = list_reels(limit=5)
        self.assertIsInstance(reels, list)

    def test_reels_upload_redirects_login(self):
        app = Flask(__name__)
        from api_routes.reels_routes import reels_bp
        from api_routes.auth_routes import auth_bp
        app.register_blueprint(reels_bp)
        app.register_blueprint(auth_bp)
        with app.test_client() as client:
            resp = client.get('/reels/upload')
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/auth/login', resp.location)

if __name__ == "__main__":
    unittest.main()
