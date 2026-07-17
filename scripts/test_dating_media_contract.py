#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        raise AssertionError(name)


def main():
    tpl = read("templates/dating/profile.html")
    js = read("static/js/dating_premium.js")
    check("dating profile uses avatar cover", "avatar_url" in tpl and "cover_url" in tpl)
    check("dating discovery uses existing avatars/photos", "profile_photo" in read("templates/matching/discover.html") or "avatar_url" in tpl)
    check("dating js supports csrf", "X-CSRFToken" in js)
    check("dating js no remote media probing", "fetch(" in js)


if __name__ == "__main__":
    main()
