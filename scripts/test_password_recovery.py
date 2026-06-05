import sys
import os
from flask import Flask, session

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_routes.auth_routes import auth_bp
from services.auth_service import send_password_reset, verify_recovery_token
from unittest.mock import MagicMock, patch

def test_password_recovery():
    print("Testing Password Recovery Flow...")
    
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "test_secret"
    app.register_blueprint(auth_bp)
    
    with app.test_request_context():
        # 1. Test forgot password GET
        with app.test_client() as client:
            res = client.get("/auth/forgot-password")
            assert res.status_code == 200
            print("[OK] /auth/forgot-password GET 200")
            
            # 2. Test forgot password POST
            with patch("services.auth_service.get_supabase") as mock_supabase:
                res = client.post("/auth/forgot-password", data={"email": "test@example.com"})
                assert res.status_code == 200
                assert b"If this email exists" in res.data
                print("[OK] /auth/forgot-password POST generic success")
                
            # 3. Test reset-password GET (without token)
            res = client.get("/auth/reset-password")
            assert res.status_code == 200
            print("[OK] /auth/reset-password GET 200 (logged out/no token)")
            
            # 4. Test callback redirect for recovery
            res = client.get("/auth/callback?type=recovery&code=test_code")
            assert res.status_code == 302
            assert "/auth/reset-password" in res.location
            assert "code=test_code" in res.location
            print("[OK] /auth/callback recovery redirects to /auth/reset-password")

    print("\nPassword Recovery Flow Tests Passed!")

if __name__ == "__main__":
    try:
        test_password_recovery()
    except Exception as e:
        print(f"Tests failed: {e}")
        sys.exit(1)
