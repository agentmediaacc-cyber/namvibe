#!/usr/bin/env python3
"""Check accessibility essentials: aria-labels, readable text, visible placeholders."""

import re, sys

issues = []

files_to_check = [
    "templates/partials/camera_creator.html",
    "templates/posts/detail.html",
    "templates/business/flyer_generator.html",
]

for fp in files_to_check:
    try:
        with open(fp) as f:
            content = f.read()
    except FileNotFoundError:
        issues.append(f"MISSING: {fp}")
        continue

    # Check for aria-labels on interactive elements
    btn_count = len(re.findall(r'<button\b', content))
    aria_count = len(re.findall(r'aria-label\s*=', content))
    if btn_count > 1 and aria_count < btn_count * 0.5:
        issues.append(f"{fp}: {btn_count} buttons but only {aria_count} aria-labels")

    # Check for placeholder texts on inputs and textareas
    input_count = len(re.findall(r'<input\b', content))
    placeholder_count = len(re.findall(r'placeholder\s*=', content))
    textarea_count = len(re.findall(r'<textarea\b', content))
    textarea_placeholder = len(re.findall(r'<textarea[^>]*placeholder', content))
    if input_count > 0 and placeholder_count < input_count * 0.5:
        issues.append(f"{fp}: {input_count} inputs but only {placeholder_count} placeholders")
    if textarea_count > 0 and textarea_placeholder < textarea_count:
        issues.append(f"{fp}: textarea missing placeholder")

    # Check for < 16px font-size only on input/textarea elements (creator/editor inputs)
    input_small = re.findall(r'(<input[^>]*?style[^>]*?font-size\s*:\s*(1[0-5]px|\dpx))', content, re.IGNORECASE)
    textarea_small = re.findall(r'(<textarea[^>]*?style[^>]*?font-size\s*:\s*(1[0-5]px|\dpx))', content, re.IGNORECASE)
    if input_small:
        issues.append(f"{fp}: input font-size < 16px ({input_small})")
    if textarea_small:
        issues.append(f"{fp}: textarea font-size < 16px ({textarea_small})")

    # Check for white-on-white risk in inputs
    for m in re.finditer(r'(<input[^>]*?style[^>]*?color\s*:\s*#[fF]{3,6})', content):
        chunk = content[max(0, m.start()-200):m.end()+200]
        if re.search(r'background[^}]*#[fF]', chunk):
            issues.append(f"{fp}: possible white-on-white in input near '{m.group()[:60]}'")

if issues:
    for i in issues:
        print(f"ACCESSIBILITY: {i}")
    sys.exit(1)
else:
    print("PART I OK: Basic accessibility checks passed")