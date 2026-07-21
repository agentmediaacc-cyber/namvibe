import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.profile_service import normalize_profile


def check(name, cond):
    if not cond:
        raise AssertionError(name)


def main():
    profile = normalize_profile({"username": "new_user", "display_name": "New User"})
    check("default premium tier is free", profile["premium_tier"] == "free")
    check("default is not premium", profile["is_premium"] is False)
    print("test_new_user_free_tier_contract_ok")


if __name__ == "__main__":
    main()
