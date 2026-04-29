import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import Client
from django.urls import reverse


def main():
    client = Client()
    route_map = {
        "home": reverse("home"),
        "login": reverse("login"),
        "signup": reverse("signup"),
        "profile": reverse("profile_root"),
        "dashboard": reverse("dashboard"),
        "feed": reverse("feed"),
        "wallet": reverse("wallet_home"),
        "messages": reverse("messages_home"),
    }
    print("Namvibe smoke routes")
    for label, path in route_map.items():
        response = client.get(path, follow=False)
        print(f"{label:10s} {response.status_code} {path}")


if __name__ == "__main__":
    main()
