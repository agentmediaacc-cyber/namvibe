import sys
import os
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_routes.auth_routes import auth_bp

def test_login_flow():
    print("Testing Login Flow Messages...")
    
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "test_secret"
    app.register_blueprint(auth_bp)
    
    with app.test_client() as client:
        # 1. Test password_reset message
        res = client.get("/auth/login?password_reset=1")
        assert res.status_code == 200
        assert b"Password updated. You can now log in." in res.data
        print("[OK] Login page shows password reset success")
        
        # 2. Test registered message
        res = client.get("/auth/login?registered=1")
        assert res.status_code == 200
        assert b"Account created. Check your email" in res.data
        print("[OK] Login page shows registration success")
        
        # 3. Test oauth_error message
        res = client.get("/auth/login?oauth_error=1")
        assert res.status_code == 200
        assert b"We could not complete social login" in res.data
        print("[OK] Login page shows OAuth error")

    print("\nLogin Flow Tests Passed!")

if __name__ == "__main__":
    try:
        test_login_flow()
    except Exception as e:
        print(f"Tests failed: {e}")
        sys.exit(1)
