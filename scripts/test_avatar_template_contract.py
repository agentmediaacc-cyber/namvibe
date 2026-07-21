#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys

from jinja2 import Environment, FileSystemLoader

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    env.globals["profile"] = {}
    tmpl = env.get_template("components/avatar.html")
    image_html = tmpl.module.avatar({"avatar_url": "/static/uploads/x.png", "display_name": "Ada Lovelace"}, size="md", loading="eager")
    fallback_html = tmpl.module.avatar({"display_name": "Ada Lovelace"}, size="md", loading="lazy")

    ok = True
    ok &= check("image state renders img", "<img" in image_html and "avatar_url" not in image_html, image_html[:200])
    ok &= check("fallback state renders initials or icon", "nv-avatar__fallback" in fallback_html and ("nv-avatar-initials" in fallback_html or "svg" in fallback_html), fallback_html[:200])
    ok &= check("image alt text present", 'alt="Ada Lovelace profile picture"' in image_html, image_html[:200])
    ok &= check("data-avatar-has-image true", 'data-avatar-has-image="true"' in image_html, image_html[:200])
    ok &= check("data-avatar-has-image false", 'data-avatar-has-image="false"' in fallback_html, fallback_html[:200])
    print("TEST_OK avatar template contract" if ok else "TEST_FAIL avatar template contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
