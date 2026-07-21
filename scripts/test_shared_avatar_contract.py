import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.avatar_service import avatar_meta


def check(name, cond):
    if not cond:
        raise AssertionError(name)


def main():
    avatar = avatar_meta({"display_name": "Ada Lovelace", "avatar_url": "/static/uploads/profile/avatars/a.png"})
    check("image detected", avatar["avatar_has_image"] is True)
    check("alt text present", avatar["avatar_alt"] == "Ada Lovelace profile picture")
    check("initials", avatar["avatar_initials"] == "AL")

    fallback = avatar_meta({"username": "user_one"})
    check("fallback no image", fallback["avatar_has_image"] is False)
    check("fallback initials", fallback["avatar_initials"] == "U")
    print("test_shared_avatar_contract_ok")


if __name__ == "__main__":
    main()
