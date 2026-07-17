#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.browser_smoke_support import run_smoke

if __name__ == "__main__":
    routes = ["/dating/", "/dating/discover", "/dating/matches", "/dating/preferences", "/dating/safety", "/dating/connecting-you/"]
    raise SystemExit(run_smoke(routes))
