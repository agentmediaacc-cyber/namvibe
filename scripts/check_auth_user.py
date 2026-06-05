import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth_service import get_auth_user_by_email

def check_user(email):
    print(f"Checking Supabase Auth for: {email}")
    user = get_auth_user_by_email(email)
    
    if not user:
        print("RESULT: NOT FOUND")
        return

    print("RESULT: FOUND")
    print(f"ID: {getattr(user, 'id', 'N/A')}")
    print(f"Email: {getattr(user, 'email', 'N/A')}")
    print(f"Confirmed At: {getattr(user, 'confirmed_at', 'Not confirmed')}")
    print(f"Created At: {getattr(user, 'created_at', 'N/A')}")
    print(f"Last Sign In At: {getattr(user, 'last_sign_in_at', 'Never')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check_auth_user.py <email>")
        sys.exit(1)
        
    check_user(sys.argv[1])
