#!/usr/bin/env python3
"""Verify reel upload uses fast path (no ffmpeg, Supabase direct)."""

import sys
sys.path.insert(0, '.')
from api_routes.reels_routes import api_create_reel as upload_reel

import inspect
sig = inspect.signature(upload_reel)
print(f"PART D INFO: upload_reel signature: {sig}")

source = inspect.getsource(upload_reel)
if "ffmpeg" in source.lower():
    print("PART D WARN: ffmpeg dependency found in upload path")
else:
    print("PART D OK: No ffmpeg dependency in reel upload")

if "supabase" in source.lower() or "storage" in source.lower():
    print("PART D OK: Uses Supabase storage for reel upload")
else:
    print("PART D WARN: Supabase storage not referenced directly in upload")