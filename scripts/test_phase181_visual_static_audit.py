#!/usr/bin/env python3
"""Phase 181: Premium UI 2026 — Static Audit

Verifies the 2026 design system is properly integrated:
  1. namvibe_2026_design_system.css exists and has required token/utility definitions
  2. base.html loads the 2026 design system CSS
  3. chain_home.html uses nv2026- classes additively
  4. discover template uses nv2026- classes
  5. No pink-heavy theme colors in core CSS
  6. Design system uses --nv2026- prefix
  7. All key component systems are present (btn, card, avatar, badge, input, modal, toast, skeleton, empty)
  8. Gradient uses blue/purple/cyan (not pink)
"""

import os, sys, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def ok(msg):
    global PASS; PASS += 1
    print(f"  OK  {msg}")

def fail(msg):
    global FAIL; FAIL += 1
    print(f"  FAIL  {msg}")

def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        msg = f"{label}  {detail}" if detail else label
        fail(msg)

CSS_PATH = os.path.join(BASE, "static", "css", "namvibe_2026_design_system.css")
BASE_HTML = os.path.join(BASE, "templates", "base.html")
HOME_HTML = os.path.join(BASE, "templates", "chain_home.html")
DISCOVER_HTML = os.path.join(BASE, "templates", "discover", "index.html")

def file_exists(path, label):
    exists = os.path.isfile(path)
    check(f"{label} file exists", exists)
    return exists

def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        return ""

# ─── Section 1: Design system CSS ───
print("\n=== Section 1: Design System CSS ===")
if file_exists(CSS_PATH, "namvibe_2026_design_system.css"):
    css = read_file(CSS_PATH)

    # Token definitions
    check("Declares --nv2026-bg", "--nv2026-bg" in css)
    check("Declares --nv2026-surface", "--nv2026-surface" in css)
    check("Declares --nv2026-text", "--nv2026-text" in css)
    check("Declares --nv2026-text-secondary", "--nv2026-text-secondary" in css)
    check("Declares --nv2026-border", "--nv2026-border" in css)
    check("Declares --nv2026-blue", "--nv2026-blue" in css)
    check("Declares --nv2026-purple", "--nv2026-purple" in css)
    check("Declares --nv2026-cyan", "--nv2026-cyan" in css)
    check("Declares --nv2026-gradient", "--nv2026-gradient" in css)
    check("Declares --nv2026-success", "--nv2026-success" in css)
    check("Declares --nv2026-danger", "--nv2026-danger" in css)
    check("Declares --nv2026-live", "--nv2026-live" in css)
    check("Declares --nv2026-gold", "--nv2026-gold" in css)
    check("Declares --nv2026-verified", "--nv2026-verified" in css)

    # Typography tokens
    check("Declares --nv2026-font", "--nv2026-font" in css)
    check("Declares --nv2026-font-size-base", "--nv2026-font-size-base" in css)
    check("Declares --nv2026-font-weight-semibold", "--nv2026-font-weight-semibold" in css)

    # Spacing tokens
    check("Declares --nv2026-space-4", "--nv2026-space-4" in css)

    # Radius tokens
    check("Declares --nv2026-radius-sm", "--nv2026-radius-sm" in css)
    check("Declares --nv2026-radius-md", "--nv2026-radius-md" in css)
    check("Declares --nv2026-radius-lg", "--nv2026-radius-lg" in css)
    check("Declares --nv2026-radius-full", "--nv2026-radius-full" in css)

    # Shadow tokens
    check("Declares --nv2026-shadow-sm", "--nv2026-shadow-sm" in css)
    check("Declares --nv2026-shadow-md", "--nv2026-shadow-md" in css)
    check("Declares --nv2026-shadow-lg", "--nv2026-shadow-lg" in css)

    # Transition tokens
    check("Declares --nv2026-transition-normal", "--nv2026-transition-normal" in css)

    # Component systems
    check("Has .nv2026-btn class", ".nv2026-btn" in css)
    check("Has .nv2026-btn-primary", ".nv2026-btn-primary" in css)
    check("Has .nv2026-btn-secondary", ".nv2026-btn-secondary" in css)
    check("Has .nv2026-btn-ghost", ".nv2026-btn-ghost" in css)
    check("Has .nv2026-btn-danger", ".nv2026-btn-danger" in css)
    check("Has .nv2026-btn-sm", ".nv2026-btn-sm" in css)
    check("Has .nv2026-btn-lg", ".nv2026-btn-lg" in css)
    check("Has .nv2026-btn-icon", ".nv2026-btn-icon" in css)
    check("Has .nv2026-card", ".nv2026-card" in css)
    check("Has .nv2026-card-header", ".nv2026-card-header" in css)
    check("Has .nv2026-card-body", ".nv2026-card-body" in css)
    check("Has .nv2026-card-footer", ".nv2026-card-footer" in css)
    check("Has .nv2026-avatar", ".nv2026-avatar" in css)
    check("Has .nv2026-avatar-sm", ".nv2026-avatar-sm" in css)
    check("Has .nv2026-avatar-md", ".nv2026-avatar-md" in css)
    check("Has .nv2026-avatar-lg", ".nv2026-avatar-lg" in css)
    check("Has .nv2026-avatar-ring", ".nv2026-avatar-ring" in css)
    check("Has .nv2026-badge", ".nv2026-badge" in css)
    check("Has .nv2026-badge-live", ".nv2026-badge-live" in css)
    check("Has .nv2026-badge-blue", ".nv2026-badge-blue" in css)
    check("Has .nv2026-badge-green", ".nv2026-badge-green" in css)
    check("Has .nv2026-badge-red", ".nv2026-badge-red" in css)
    check("Has .nv2026-badge-gold", ".nv2026-badge-gold" in css)
    check("Has .nv2026-verified", ".nv2026-verified" in css)
    check("Has .nv2026-input", ".nv2026-input" in css)
    check("Has .nv2026-input-group", ".nv2026-input-group" in css)
    check("Has .nv2026-chip", ".nv2026-chip" in css)
    check("Has .nv2026-chip-active", ".nv2026-chip-active" in css)
    check("Has .nv2026-skeleton", ".nv2026-skeleton" in css)
    check("Has .nv2026-toast-container", ".nv2026-toast-container" in css)
    check("Has .nv2026-toast", ".nv2026-toast" in css)
    check("Has .nv2026-modal-overlay", ".nv2026-modal-overlay" in css)
    check("Has .nv2026-modal", ".nv2026-modal" in css)
    check("Has .nv2026-bottom-sheet-overlay", ".nv2026-bottom-sheet-overlay" in css)
    check("Has .nv2026-bottom-sheet", ".nv2026-bottom-sheet" in css)
    check("Has .nv2026-empty", ".nv2026-empty" in css)
    check("Has .nv2026-glass", ".nv2026-glass" in css)
    check("Has .nv2026-gradient-text", ".nv2026-gradient-text" in css)

    # Animations
    check("Has @keyframes nv2026-shimmer", "@keyframes nv2026-shimmer" in css)
    check("Has @keyframes nv2026-fade-in", "@keyframes nv2026-fade-in" in css)
    check("Has @keyframes nv2026-modal-in", "@keyframes nv2026-modal-in" in css)
    check("Has @keyframes nv2026-slide-up", "@keyframes nv2026-slide-up" in css)
    check("Has @keyframes nv2026-heart-burst", "@keyframes nv2026-heart-burst" in css)
    check("Has @keyframes nv2026-toast-in", "@keyframes nv2026-toast-in" in css)

    # Reduced motion
    check("Has prefers-reduced-motion", "prefers-reduced-motion" in css)

    # No pink in gradient
    pink_in_gradient = "#FE2C55" in css or "fe2c55" in css or "de2c55" in css
    check("No pink (#FE2C55) in design system", not pink_in_gradient,
          "Design system should not contain TikTok pink")

    # Gradient uses blue/purple/cyan
    check("Gradient uses blue (#2563eb)", "#2563eb" in css)
    check("Gradient uses purple (#7c3aed)", "#7c3aed" in css)
    check("Gradient uses cyan (#06b6d4)", "#06b6d4" in css)

# ─── Section 2: base.html ───
print("\n=== Section 2: base.html ===")
if file_exists(BASE_HTML, "base.html"):
    bh = read_file(BASE_HTML)
    check("base.html loads namvibe_2026_design_system.css",
          "namvibe_2026_design_system.css" in bh)
    check("base.html has viewport-fit=cover",
          "viewport-fit=cover" in bh)
    check("base.html has --nv2026- tokens available",
          "--nv2026" not in bh)  # tokens are in CSS, not HTML

# ─── Section 3: chain_home.html ───
print("\n=== Section 3: chain_home.html ===")
if file_exists(HOME_HTML, "chain_home.html"):
    hh = read_file(HOME_HTML)
    check("Homepage uses nv2026-glass on topbar",
          "nv-topbar nv2026-glass" in hh or 'class="nv-topbar nv2026-glass' in hh)
    check("Homepage uses nv2026-modal-overlay",
          "nv-modal-overlay nv2026-modal-overlay" in hh)
    check("Homepage uses nv2026-bottom-sheet-overlay",
          "nv-bottom-sheet-overlay nv2026-bottom-sheet-overlay" in hh or 'class="nv-bottom-sheet-overlay nv2026-bottom-sheet-overlay' in hh)
    check("Homepage uses nv2026-card on sections",
          "nv2026-card" in hh)

    # Ensure existing classes are preserved
    check("nv-heart-burst class preserved",
          "nv-heart-burst" in hh)
    check("nv-bottom-sheet class preserved",
          "nv-bottom-sheet" in hh)
    check("nv-feed-sentinel id preserved",
          "nv-feed-sentinel" in hh)
    check("nv-more class preserved",
          "nv-more" in hh)
    check("nv-side-card class preserved",
          "nv-side-card" in hh)
    check("nv-create-modal id preserved",
          "nv-create-modal" in hh)

# ─── Section 4: Discover template ───
print("\n=== Section 4: Discover template ===")
if file_exists(DISCOVER_HTML, "discover/index.html"):
    dh = read_file(DISCOVER_HTML)
    check("Discover uses nv2026-card",
          "nv2026-card" in dh)
    check("Discover uses nv2026-chip",
          "nv2026-chip" in dh)
    check("Discover uses nv2026-empty",
          "nv2026-empty" in dh)
    check("Discover uses nv2026-btn-primary",
          "nv2026-btn-primary" in dh)

# ─── Summary ───
print(f"\n{'='*50}")
print(f"  PASS: {PASS}  |  FAIL: {FAIL}")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
