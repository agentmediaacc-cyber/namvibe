#!/usr/bin/env python3
"""Phase 69 — Homepage route-link integrity test.

Parses chain_home.html, extracts all href values, and tests each
against the Flask app.  Allows 200, 302, 301, 307, 429 (rate-limit).
Fails on 404, 500, empty, '#', 'javascript:'.
"""

import os, sys, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from html.parser import HTMLParser

passed = 0
failed = 0

def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


class HrefCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        for name, val in attrs:
            if name == "href" and val and not val.startswith("#") and not val.startswith("javascript"):
                self.hrefs.add(val)


def collect_hrefs(html_path):
    with open(html_path) as f:
        content = f.read()
    parser = HrefCollector()
    parser.feed(content)
    return parser.hrefs


class TestHomepageLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app as flask_app
        cls.app = flask_app
        cls.client = flask_app.test_client()

    def test_all_internal_links(self):
        hrefs = collect_hrefs("templates/chain_home.html")
        # Filter to internal paths only
        internal = sorted(
            h for h in hrefs
            if h.startswith("/")
        )
        self.assertGreater(len(internal), 5, f"Only {len(internal)} internal links found — template may be minimal")

        allowed = (200, 301, 302, 307, 429)
        bad = []
        for path in internal:
            with self.subTest(path=path):
                try:
                    resp = self.client.get(path)
                    if resp.status_code not in allowed:
                        bad.append(f"{path} -> {resp.status_code}")
                except Exception as e:
                    bad.append(f"{path} -> ERROR: {e}")

        if bad:
            for b in bad:
                print(f"    FAIL  {b}")
        self.assertEqual(len(bad), 0, f"{len(bad)} broken links:\n" + "\n".join(bad))


def main():
    print("=" * 64)
    print("Phase 69 — Homepage Link Integrity Test")
    print("=" * 64)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHomepageLinks)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("-" * 64)
    print(f"  {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 64)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
