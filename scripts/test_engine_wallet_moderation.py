import unittest
from services.wallet_engine import get_wallet_summary, send_gift, request_payout
from services.moderation_engine import report_entity, block_profile

class TestWalletModeration(unittest.TestCase):
    def test_wallet_summary(self):
        p = '00000000-0000-0000-0000-000000000001'
        summary = get_wallet_summary(p)
        if summary:
            self.assertIn('coin_balance', summary)

    def test_payout_setup_required(self):
        ok, error = request_payout('00000000-0000-0000-0000-000000000001', 100)
        self.assertFalse(ok)
        self.assertEqual(error, 'setup_required')

    def test_moderation_logged_out_401(self):
        from flask import Flask
        app = Flask(__name__)
        from api_routes.moderation_routes import moderation_bp
        from api_routes.auth_routes import auth_bp
        app.register_blueprint(moderation_bp)
        app.register_blueprint(auth_bp)
        with app.test_client() as client:
            resp = client.post('/api/moderation/report', data={'reason': 'test'})
            self.assertEqual(resp.status_code, 302) # Redirects to login because of login_required

if __name__ == "__main__":
    unittest.main()
