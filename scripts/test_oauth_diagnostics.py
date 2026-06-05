import sys
import os
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_routes.auth_routes import auth_bp

def test_oauth_diagnostics():
    print("Testing OAuth Diagnostics...")
    
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "test_secret"
    app.register_blueprint(auth_bp)
    
    with app.test_client() as client:
        res = client.get("/auth/oauth-diagnostics")
        assert res.status_code == 200
        assert b"OAuth Diagnostics" in res.data
        assert b"Redirect URLs" in res.data
        print("[OK] /auth/oauth-diagnostics 200")
        
        # Test missing code redirect
        res = client.get("/auth/google/callback")
        assert res.status_code == 302
        assert "/auth/login?oauth_error=1" in res.location
        print("[OK] Missing OAuth code redirects to login with error")

    print("\nOAuth Diagnostics Tests Passed!")

if __name__ == "__main__":
    try:
        test_oauth_diagnostics()
    except Exception as e:
        print(f"Tests failed: {e}")
        sys.exit(1)
