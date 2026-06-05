from pprint import pprint

from app import create_app
from services.profile_service import get_current_profile


def main():
    app = create_app()
    with app.test_request_context("/api/profile/current"):
        profile = get_current_profile()
        print("session_auth_user_id:", None)
        pprint(profile)


if __name__ == "__main__":
    main()
