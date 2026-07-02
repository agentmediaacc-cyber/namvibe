#!/usr/bin/env python3
"""Generate a 2-minute NamVibe promo animation video.

Uses Pillow, numpy, and imageio (no moviepy dependency).
Output: static/media/samples/namvibe_promo.mp4
"""

import os, sys, math, textwrap
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_ENV", "development")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "media", "samples")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "namvibe_promo.mp4")
os.makedirs(OUTPUT_DIR, exist_ok=True)

W, H = 1080, 1920  # 9:16 portrait (mobile-friendly)
FPS = 24
DURATION = 120  # 2 minutes
TOTAL_FRAMES = FPS * DURATION

# ── Colour palette (NamVibe brand) ──
BG_DARK = (10, 10, 26)
BG_CARD = (20, 20, 50)
ACCENT_BLUE = (59, 130, 246)
ACCENT_PURPLE = (139, 92, 246)
ACCENT_CYAN = (34, 211, 238)
ACCENT_PINK = (236, 72, 153)
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 220)
MED_GRAY = (120, 120, 160)
GRADIENT_COLORS = [ACCENT_BLUE, ACCENT_PURPLE, ACCENT_CYAN]

def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def gradient_colors(t):
    idx = t * (len(GRADIENT_COLORS) - 1)
    i = int(idx)
    frac = idx - i
    if i >= len(GRADIENT_COLORS) - 1:
        return GRADIENT_COLORS[-1]
    return lerp_color(GRADIENT_COLORS[i], GRADIENT_COLORS[i + 1], frac)

def draw_gradient_bg(draw, t_offset=0):
    for y in range(H):
        cy = y / H
        c = gradient_colors((cy + t_offset) % 1.0)
        draw.line([(0, y), (W, y)], fill=c, width=1)

def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill)

def draw_star(draw, cx, cy, r, n=5, fill=(255, 255, 255)):
    points = []
    for i in range(2 * n):
        angle = math.pi / 2 + math.pi * i / n
        radius = r if i % 2 == 0 else r * 0.4
        points.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    draw.polygon(points, fill=fill)

def draw_sparkle(draw, cx, cy, size, color):
    draw.line([(cx - size, cy), (cx + size, cy)], fill=color, width=2)
    draw.line([(cx, cy - size), (cx, cy + size)], fill=color, width=2)

def draw_icon_heart(draw, cx, cy, size, fill_color):
    # Simple heart shape using arcs and lines
    r = size * 0.5
    left_lobe = (cx - r, cy - r * 0.6, cx, cy + r * 0.4)
    right_lobe = (cx, cy - r * 0.6, cx + r, cy + r * 0.4)
    draw.ellipse(left_lobe, fill=fill_color)
    draw.ellipse(right_lobe, fill=fill_color)
    draw.polygon([(cx - r * 0.8, cy + r * 0.1), (cx + r * 0.8, cy + r * 0.1), (cx, cy + r * 1.2)], fill=fill_color)

def draw_icon_chat(draw, cx, cy, size, fill_color):
    s = size * 0.5
    draw.ellipse([cx - s, cy - s * 0.8, cx + s, cy + s * 0.8], fill=fill_color)
    # tail
    draw.polygon([(cx + s * 0.3, cy + s * 0.3), (cx + s * 0.8, cy + s * 0.8), (cx + s * 0.1, cy + s * 0.5)], fill=fill_color)

def draw_icon_live(draw, cx, cy, size, fill_color):
    s = size * 0.5
    draw.ellipse([cx - s, cy - s, cx + s, cy + s], fill=fill_color)
    # play triangle
    ts = s * 0.45
    draw.polygon([(cx - ts * 0.4, cy - ts), (cx - ts * 0.4, cy + ts), (cx + ts * 0.8, cy)], fill=WHITE)

def draw_icon_star(draw, cx, cy, size, fill_color):
    draw_star(draw, cx, cy, size * 0.5, fill=fill_color)

# ── Scene definitions ──

def render_frame(frame_idx):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    progress = frame_idx / TOTAL_FRAMES
    scene_idx = int(progress * 7)  # 7 scenes
    scene_t = (progress * 7) - scene_idx

    # Load fonts
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
        font_subtitle = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_emoji = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 60)
    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_body = font_title
        font_small = font_title
        font_emoji = font_title

    if scene_idx == 0:
        # ── Scene 1: Logo + tagline (fade in/out) ──
        alpha = min(1.0, scene_t * 3) if scene_t < 0.5 else max(0.0, 1 - (scene_t - 0.5) * 3)
        draw_gradient_bg(draw, progress * 0.1)
        # Logo star
        star_cx, star_cy = W // 2, H // 2 - 200
        r = 80 + 20 * math.sin(progress * 4 * math.pi)
        draw_star(draw, star_cx, star_cy, int(r), fill=lerp_color(ACCENT_BLUE, ACCENT_CYAN, (math.sin(progress * 2) + 1) / 2))
        # Title
        title = "NamVibe"
        try:
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = 300
        tx, ty = (W - tw) // 2, H // 2 - 40
        text_color = lerp_color(WHITE, ACCENT_CYAN, (math.sin(progress * 1.5) + 1) / 2)
        draw.text((tx, ty), title, fill=text_color, font=font_title)
        # Tagline
        tagline = "Where Connections Come Alive"
        try:
            bbox = draw.textbbox((0, 0), tagline, font=font_subtitle)
            sw = bbox[2] - bbox[0]
        except Exception:
            sw = 400
        draw.text(((W - sw) // 2, ty + 100), tagline, fill=LIGHT_GRAY, font=font_subtitle)
        # Subtitle
        sub = "Real-time Social Discovery Platform"
        try:
            bbox = draw.textbbox((0, 0), sub, font=font_body)
            sw2 = bbox[2] - bbox[0]
        except Exception:
            sw2 = 400
        draw.text(((W - sw2) // 2, ty + 170), sub, fill=MED_GRAY, font=font_body)
        # Sparkles
        for i in range(12):
            angle = progress * 2 * math.pi + i * math.pi / 6
            sx = W // 2 + 300 * math.cos(angle)
            sy = H // 2 - 100 + 200 * math.sin(angle * 0.7)
            sp = max(0, math.sin(progress * 3 + i)) * 15
            draw_sparkle(draw, int(sx), int(sy), int(sp) + 3, lerp_color(ACCENT_CYAN, ACCENT_PURPLE, i / 12))

    elif scene_idx == 1:
        # ── Scene 2: Features overview ──
        draw.rectangle([(0, 0), (W, H)], fill=BG_DARK)
        # Header
        draw.text((60, 80), "What is NamVibe?", fill=WHITE, font=font_title)
        draw.text((60, 180), "A real-time social discovery platform", fill=LIGHT_GRAY, font=font_subtitle)
        # Feature cards
        features = [
            ("\U0001f44d Like & Engage", "Double-tap to like posts\nComment, share, and save", ACCENT_BLUE),
            ("\U0001f4f9 Live Streaming", "Go live, earn gifts\nReal-time chat & interaction", ACCENT_PURPLE),
            ("\U0001f3ac Short-form Reels", "Vertical video feed\nSwipe up for more", ACCENT_CYAN),
            ("\U0001f4ac Instant Messaging", "Real-time chat\nGroup calls & threads", ACCENT_PINK),
        ]
        for i, (title, desc, accent) in enumerate(features):
            y_base = 320 + i * 380
            alpha = max(0, min(1, (scene_t * 5 - i * 0.3)))
            if alpha <= 0:
                continue
            bx, by, bw, bh = 80, y_base, W - 160, 340
            draw_rounded_rect(draw, (bx, by, bx + bw, by + bh), 20, fill=BG_CARD)
            # Accent bar
            draw_rounded_rect(draw, (bx + 20, by + 20, bx + 60, by + 80), 10, fill=accent)
            draw.text((bx + 90, by + 25), title, fill=WHITE, font=font_body)
            draw.text((bx + 90, by + 85), desc, fill=LIGHT_GRAY, font=font_small)

    elif scene_idx == 2:
        # ── Scene 3: Social Feed demo ──
        draw.rectangle([(0, 0), (W, H)], fill=BG_DARK)
        draw.text((60, 60), "Your Social Feed", fill=WHITE, font=font_title)
        draw.text((60, 150), "Real content. Real people. Real-time.", fill=LIGHT_GRAY, font=font_subtitle)
        # Simulated feed cards
        for i in range(4):
            y_base = 280 + i * 380
            offset_progress = (scene_t + i * 0.25) % 1.0
            slide = int(60 * math.sin(offset_progress * math.pi * 2))
            bx, by, bw, bh = 100, y_base, W - 200, 340
            draw_rounded_rect(draw, (bx + slide, by, bx + bw + slide, by + bh), 20, fill=BG_CARD)
            # Avatar
            draw.ellipse([bx + 30 + slide, by + 30, bx + 90 + slide, by + 90], fill=lerp_color(ACCENT_BLUE, ACCENT_PURPLE, i / 3))
            # Username
            usernames = ["alex_creative", "sam_adventures", "jordan_music", "taylor_art"]
            draw.text((bx + 110 + slide, by + 40), usernames[i], fill=WHITE, font=font_body)
            # Time
            draw.text((bx + 110 + slide, by + 85), "2h ago", fill=MED_GRAY, font=font_small)
            # Content
            content = [
                "Just dropped a new track! \U0001f3b6",
                "Sunset at the beach \U0001f305",
                "Live tonight at 8pm! \U0001f534",
                "New artwork in progress \U0001f3a8"
            ][i]
            draw.text((bx + 30 + slide, by + 130), content[i], fill=LIGHT_GRAY, font=font_small)
            # Action bar
            like_x = bx + 30 + slide
            draw_icon_heart(draw, like_x, by + 230, 20, ACCENT_PINK if i % 2 == 0 else MED_GRAY)
            draw.text((like_x + 30, by + 215), f"{42 + i * 7}", fill=LIGHT_GRAY, font=font_small)

    elif scene_idx == 3:
        # ── Scene 4: Live Streaming ──
        draw.rectangle([(0, 0), (W, H)], fill=BG_DARK)
        # "Live now" header
        for i in range(3):
            pulse = math.sin(progress * 8 + i * 2) * 0.5 + 0.5
            lx, ly = 120 + i * 350, 300 + int(50 * pulse)
            lw, lh = 300, 500
            draw_rounded_rect(draw, (lx, ly, lx + lw, ly + lh), 20, fill=lerp_color(BG_CARD, (30, 30, 60), pulse))
            draw_rounded_rect(draw, (lx + 10, ly + 10, lx + 80, ly + 40), 10, fill=ACCENT_PINK)
            draw.text((lx + 20, ly + 15), "LIVE", fill=WHITE, font=font_small)
            # Viewer count
            viewers = [1284, 3562, 891][i]
            draw.text((lx + 100, ly + 15), f"\U0001f441 {viewers}", fill=LIGHT_GRAY, font=font_small)
        draw.text((60, 80), "Go Live in Seconds", fill=WHITE, font=font_title)
        draw.text((60, 170), "Broadcast to the world. Earn gifts. Chat live.", fill=LIGHT_GRAY, font=font_subtitle)
        # Bottom CTA
        cta_y = H - 180
        draw_rounded_rect(draw, (W // 2 - 200, cta_y, W // 2 + 200, cta_y + 80), 40, fill=ACCENT_PURPLE)
        draw.text((W // 2 - 80, cta_y + 15), "Start Streaming", fill=WHITE, font=font_body)

    elif scene_idx == 4:
        # ── Scene 5: Reels / Video ──
        draw.rectangle([(0, 0), (W, H)], fill=BG_DARK)
        draw.text((60, 60), "Vertical Reels", fill=WHITE, font=font_title)
        draw.text((60, 150), "Short-form videos. Endless entertainment.", fill=LIGHT_GRAY, font=font_subtitle)
        # Vertical reel cards (phone-like)
        for i in range(3):
            rx = 150 + i * 320
            ry = 350
            rw, rh = 260, 460
            tilt = 5 * math.sin(progress * 3 + i * 1.5)
            draw_rounded_rect(draw, (rx + tilt, ry, rx + rw + tilt, ry + rh), 16, fill=BG_CARD)
            # Thumbnail area
            draw_rounded_rect(draw, (rx + 10 + tilt, ry + 10, rx + rw - 10 + tilt, ry + rh // 2 + 20), 12,
                              fill=lerp_color(ACCENT_BLUE, ACCENT_PURPLE, i / 2))
            draw_icon_star(draw, rx + rw // 2 + tilt, ry + rh // 4 + 10, 30, WHITE)
            # Bottom info
            usernames = ["music_maker", "travel_vibes", "food_fun"][i]
            draw.text((rx + 15 + tilt, ry + rh // 2 + 40), usernames, fill=WHITE, font=font_body)
            draw_icon_heart(draw, rx + 15 + tilt, ry + rh - 40, 16, ACCENT_PINK)
            draw.text((rx + 35 + tilt, ry + rh - 55), "2.4k", fill=LIGHT_GRAY, font=font_small)

    elif scene_idx == 5:
        # ── Scene 6: Messaging / Chat ──
        draw.rectangle([(0, 0), (W, H)], fill=BG_DARK)
        draw.text((60, 60), "Real-time Messaging", fill=WHITE, font=font_title)
        draw.text((60, 150), "Chat, call, and connect instantly.", fill=LIGHT_GRAY, font=font_subtitle)
        # Simulated chat bubbles
        messages = [
            ("Hey! Are you going live tonight?", False),
            ("Yes! 8pm sharp \U0001f525", True),
            ("Awesome, I'll be there!", False),
            ("Bring your friends! \U0001f389", True),
        ]
        bubble_y = 300
        for i, (msg, is_me) in enumerate(messages):
            offset = (scene_t + i * 0.15) % 1.0
            if offset < 0.3:
                continue
            msg_alpha = min(1, (offset - 0.3) * 5)
            bx = 200 if is_me else 80
            bw = min(600, len(msg) * 20 + 40)
            bubble_color = ACCENT_PURPLE if is_me else BG_CARD
            draw_rounded_rect(draw, (bx, bubble_y, bx + bw, bubble_y + 70), 16, fill=bubble_color)
            draw.text((bx + 20, bubble_y + 18), msg, fill=WHITE, font=font_small)
            bubble_y += 90

    elif scene_idx == 6:
        # ── Scene 7: CTA + Outro ──
        alpha = min(1.0, scene_t * 3) if scene_t < 0.5 else 1.0
        draw_gradient_bg(draw, progress * 0.2)
        # Big star
        star_cx, star_cy = W // 2, H // 2 - 300
        r = 100 + 30 * math.sin(progress * 6 * math.pi)
        draw_star(draw, star_cx, star_cy, int(r),
                  fill=lerp_color(ACCENT_BLUE, ACCENT_CYAN, (math.sin(progress * 3) + 1) / 2))
        # Download / Join text
        title = "Join NamVibe Today"
        try:
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = 400
        draw.text(((W - tw) // 2, H // 2 - 80), title, fill=WHITE, font=font_title)
        tagline = "Available now on Web, iOS & Android"
        try:
            bbox = draw.textbbox((0, 0), tagline, font=font_subtitle)
            sw = bbox[2] - bbox[0]
        except Exception:
            sw = 400
        draw.text(((W - sw) // 2, H // 2 + 20), tagline, fill=LIGHT_GRAY, font=font_subtitle)
        # CTA Button
        btn_y = H // 2 + 120
        draw_rounded_rect(draw, (W // 2 - 200, btn_y, W // 2 + 200, btn_y + 80), 40, fill=ACCENT_PURPLE)
        draw.text((W // 2 - 60, btn_y + 15), "Get Started", fill=WHITE, font=font_body)
        # Bottom copyright
        year = datetime.now().year
        draw.text((60, H - 80), f"\u00a9 {year} NamVibe. All rights reserved.", fill=MED_GRAY, font=font_small)
        # Tagline at bottom
        draw.text((60, H - 140), "namvibe.com", fill=lerp_color(ACCENT_CYAN, ACCENT_BLUE, (math.sin(progress * 2) + 1) / 2),
                  font=font_body)

    return np.array(img)


# ── Render video ──
print(f"Rendering {TOTAL_FRAMES} frames ({DURATION}s @ {FPS}fps)...")
t0 = datetime.now()
writer = imageio.get_writer(OUTPUT_PATH, fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p")
for i in range(TOTAL_FRAMES):
    frame = render_frame(i)
    writer.append_data(frame)
    if i % (FPS * 10) == 0:
        pct = i / TOTAL_FRAMES * 100
        elapsed = (datetime.now() - t0).total_seconds()
        eta = (elapsed / (i + 1)) * (TOTAL_FRAMES - i - 1) if i > 0 else 0
        print(f"  {pct:.0f}% ({i}/{TOTAL_FRAMES}) — ETA {eta:.0f}s")
writer.close()
elapsed = (datetime.now() - t0).total_seconds()
print(f"\nDone! Rendered {TOTAL_FRAMES} frames in {elapsed:.1f}s")
size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
print(f"Output: {OUTPUT_PATH} ({size_mb:.1f} MB)")
