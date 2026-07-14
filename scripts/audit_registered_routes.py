#!/usr/bin/env python3
"""Print the registered Flask routes and highlight duplicate method+rule pairs."""

from collections import defaultdict
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEMA_CHECK", "1")


def main():
    from app import app

    rows = []
    pair_map = defaultdict(list)
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: (r.rule, sorted(r.methods))):
      methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
      endpoint = rule.endpoint
      view = app.view_functions.get(endpoint)
      module = getattr(view, "__module__", "unknown") if view else "unknown"
      row = {"methods": methods, "rule": rule.rule, "endpoint": endpoint, "module": module}
      rows.append(row)
      for method in methods:
        pair_map[(method, rule.rule)].append(row)

    print("HTTP_METHOD | URL_RULE | ENDPOINT | MODULE")
    for row in rows:
      print(f"{','.join(row['methods'])} | {row['rule']} | {row['endpoint']} | {row['module']}")

    print("\nDUPLICATES")
    dupes = [(k, v) for k, v in pair_map.items() if len(v) > 1]
    if not dupes:
      print("none")
      return 0
    for (method, rule), entries in dupes:
      print(f"{method} {rule}")
      for entry in entries:
        print(f"  - {entry['endpoint']} ({entry['module']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
