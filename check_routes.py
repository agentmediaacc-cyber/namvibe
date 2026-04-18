import re
from pathlib import Path
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.urls import get_resolver

resolver = get_resolver()
names = set()

def walk(patterns, namespace=""):
    for p in patterns:
        if hasattr(p, "url_patterns"):
            child_namespace = f"{namespace}{p.namespace}:" if getattr(p, "namespace", None) else namespace
            walk(p.url_patterns, child_namespace)
        else:
            if p.name:
                names.add(p.name)
                if namespace:
                    names.add(f"{namespace}{p.name}")

walk(resolver.url_patterns)

print("=== REGISTERED URL NAMES ===")
for n in sorted(names):
    print(n)

template_pat = re.compile(r"""{%\s*url\s+['"]([^'"]+)['"]""")
python_pats = [
    re.compile(r"""reverse\(['"]([^'"]+)['"]"""),
    re.compile(r"""redirect\(['"]([^'"]+)['"]"""),
]

print("\n=== MISSING TEMPLATE URL NAMES ===")
for path in Path("templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    for name in template_pat.findall(text):
        if name not in names:
            print(f"{path}: missing -> {name}")

print("\n=== PYTHON URL USAGE NOT FOUND ===")
for path in Path(".").rglob("*.py"):
    s = str(path)
    if any(skip in s for skip in ["venv", ".git", "migrations", "__pycache__"]):
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pat in python_pats:
        for name in pat.findall(text):
            if name not in names:
                print(f"{path}: missing -> {name}")
