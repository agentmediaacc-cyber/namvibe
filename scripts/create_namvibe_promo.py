"""
NamVibe 3-Minute Promotional Video Generator
Creates an animated brand video using MoviePy + FFmpeg
"""
import os, math
from moviepy import *
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
from moviepy.audio.fx import MultiplyVolume

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "namvibe_promo.mp4")
W, H = 1280, 720
FPS = 24

# Brand colours
DEEP_BLUE = (18, 18, 30)
BLUE = (37, 99, 235)
TEAL = (0, 242, 234)
PINK = (236, 72, 153)
PURPLE = (139, 92, 246)
GOLD = (251, 191, 36)
WHITE = (255, 255, 255)
DARK = (10, 10, 20)

def gradient_bg(c1, c2, vertical=True):
    """Create a ColourClip with a gradient-like two-colour split."""
    c = ColorClip((W, H), color=c1).with_duration(1)
    return c

def rounded_rect(w, h, color, radius=20):
    """Simple rounded rect background."""
    return ColorClip((w, h), color=color).with_duration(1)

def make_scene(text_lines, subtitle="", bg1=BLUE, bg2=TEAL, duration=12,
               accent=PINK, logo=True, text_color=WHITE):
    """Create a scene with animated text lines and brand styling."""
    clips = []
    bg = gradient_bg(bg1, bg2)
    # Dark gradient overlay for readability
    overlay = ColorClip((W, H), color=(0, 0, 0)).with_opacity(0.4).with_duration(duration)
    bg = CompositeVideoClip([bg, overlay]).with_duration(duration)

    clips.append(bg)

    # Accent bar at top
    bar = ColorClip((W, 6), color=accent).with_duration(duration)
    clips.append(bar)

    # Main text lines with staggered animation
    total_lines = len(text_lines)
    line_height = 80
    start_y = H // 2 - (total_lines * line_height) // 2

    for i, line in enumerate(text_lines):
        font_size = 72 if i == 0 else 56
        is_title = (i == 0)
        txt = (TextClip(
            font="Arial Bold" if is_title else "Arial",
            text=line,
            font_size=font_size,
            color=text_color,
            stroke_color=DARK if is_title else None,
            stroke_width=1 if is_title else 0,
            duration=duration,
        ).with_position(("center", start_y + i * line_height)))

        clips.append(txt)

    # Subtitle
    if subtitle:
        sub = (TextClip(
            font="Arial",
            text=subtitle,
            font_size=28,
            color=(200, 200, 220),
            duration=duration,
        ).with_position(("center", H - 120)))
        clips.append(sub)

    # Brand watermark bottom-right
    brand = (TextClip(
        font="Arial Bold",
        text="⚡ NamVibe",
        font_size=22,
        color=TEAL,
        duration=duration,
    ).with_position((W - 220, H - 50)))
    clips.append(brand)

    return CompositeVideoClip(clips).with_duration(duration)

def make_closing():
    """Closing call-to-action scene."""
    duration = 12
    clips = []
    bg = ColorClip((W, H), color=DEEP_BLUE).with_duration(duration)
    clips.append(bg)

    # Big logo text
    logo = (TextClip(
        font="Arial Bold",
        text="NamVibe",
        font_size=120,
        color=WHITE,
        stroke_color=PINK,
        stroke_width=2,
        duration=duration,
    ).with_position(("center", H // 2 - 120)))
    clips.append(logo)

    tagline = (TextClip(
        font="Arial",
        text="Where Connection Meets Creation",
        font_size=40,
        color=TEAL,
        duration=duration,
    ).with_position(("center", H // 2)))
    clips.append(tagline)

    # Download buttons placeholder
    cta = (TextClip(
        font="Arial Bold",
        text="→ Join the Vibe ←",
        font_size=56,
        color=PINK,
        duration=duration,
    ).with_position(("center", H // 2 + 100)))
    clips.append(cta)

    url = (TextClip(
        font="Arial",
        text="namvibe.app",
        font_size=28,
        color=(180, 180, 200),
        duration=duration,
    ).with_position(("center", H // 2 + 170)))
    clips.append(url)

    return CompositeVideoClip(clips).with_duration(duration)

def make_transition(text, duration=3):
    """Simple transition card."""
    bg = ColorClip((W, H), color=(10, 10, 25)).with_duration(duration)
    txt = (TextClip(
        font="Arial Bold",
        text=text,
        font_size=64,
        color=PINK,
        duration=duration,
    ).with_position("center"))
    return CompositeVideoClip([bg, txt]).with_duration(duration)


def build_video():
    scenes = []

    # === INTRO ===
    scenes.append(make_scene(
        ["NamVibe", "Where Connection Meets Creation"],
        subtitle="The all-in-one social platform",
        bg1=DEEP_BLUE, bg2=BLUE, accent=TEAL, duration=10,
    ))

    # === SOCIAL HUB ===
    scenes.append(make_scene(
        ["Your Social Hub", "Feed · Stories · Reels · Posts"],
        subtitle="Discover content that matters to you",
        bg1=BLUE, bg2=PURPLE, accent=PINK, duration=14,
    ))

    # === MESSAGING ===
    scenes.append(make_scene(
        ["Rich Messaging", "Chat · Voice Notes · HD Media"],
        subtitle="Real-time messaging with encryption",
        bg1=PURPLE, bg2=PINK, accent=GOLD, duration=14,
    ))

    # === CALLS ===
    scenes.append(make_scene(
        ["Premium Calling", "Audio · Video · Group Calls"],
        subtitle="Crystal-clear WebRTC calls with screen sharing",
        bg1=DEEP_BLUE, bg2=TEAL, accent=PINK, duration=14,
    ))

    # === LIVE ===
    scenes.append(make_scene(
        ["Live Streaming", "Go Live · Interact · Earn Gifts"],
        subtitle="Built-in live engine with real-time chat & tipping",
        bg1=BLUE, bg2=TEAL, accent=GOLD, duration=14,
    ))

    # === CREATIVE STUDIO ===
    scenes.append(make_scene(
        ["Creative Studio", "16 Pro Tools · AI Filters · Effects"],
        subtitle="Camera, beauty, text, stickers, draw, music & more",
        bg1=PURPLE, bg2=DEEP_BLUE, accent=TEAL, duration=14,
    ))

    # === DATING ===
    scenes.append(make_scene(
        ["NamVibe Dating", "Match · Chat · Connect"],
        subtitle="Find meaningful connections in your area",
        bg1=PINK, bg2=PURPLE, accent=GOLD, duration=12,
    ))

    # === MARKETPLACE ===
    scenes.append(make_scene(
        ["Creator Marketplace", "Sell · Buy · Earn NVC"],
        subtitle="Monetize your content with digital currency",
        bg1=DEEP_BLUE, bg2=GOLD, accent=TEAL, duration=12,
    ))

    # === WALLET & NVC ===
    scenes.append(make_scene(
        ["NVC Wallet", "Digital Currency · Tips · Payments"],
        subtitle="Send, receive, and spend NamVibe Coins",
        bg1=TEAL, bg2=BLUE, accent=PINK, duration=12,
    ))

    # === COMMUNITY ===
    scenes.append(make_scene(
        ["Community & Groups", "Events · Forums · Discovery"],
        subtitle="Connect with people who share your interests",
        bg1=DEEP_BLUE, bg2=PURPLE, accent=GOLD, duration=12,
    ))

    # === FEATURE WRAP ===
    scenes.append(make_scene(
        ["Everything in One Place", "Social · Live · Studio · Wallet · Dating"],
        subtitle="NamVibe brings your digital world together",
        bg1=PINK, bg2=BLUE, accent=TEAL, duration=12,
    ))

    # === CLOSING ===
    scenes.append(make_closing())

    print(f"Created {len(scenes)} scenes")

    # Crossfade transitions between scenes
    clips_stack = []
    cursor = 0.0
    fade_duration = 0.5
    for scene in scenes:
        if clips_stack:
            start = cursor - fade_duration
            scene = scene.with_start(start).with_effects([CrossFadeIn(fade_duration)])
        else:
            scene = scene.with_start(0)
        clips_stack.append(scene)
        cursor += scene.duration - (fade_duration if clips_stack else 0)

    final = CompositeVideoClip(clips_stack, size=(W, H))
    print(f"Video duration: {final.duration:.1f}s")

    return final


def add_audio(video):
    """Add background music from ringtone files."""
    ringtone_dir = os.path.join(os.path.dirname(__file__), "..", "static", "ringtones")
    audio_files = [f for f in os.listdir(ringtone_dir) if f.endswith('.mp3')]
    if not audio_files:
        print("No ringtone audio files found")
        return video

    # Use the first ringtone
    audio_path = os.path.join(ringtone_dir, audio_files[0])
    audio = AudioFileClip(audio_path)

    # Loop if needed
    if audio.duration < video.duration:
        n_loops = int(math.ceil(video.duration / audio.duration))
        audio = concatenate_audioclips([audio] * n_loops)

    # Trim to video duration
    audio = audio.subclipped(0, video.duration).with_effects([MultiplyVolume(0.15)])

    return video.with_audio(audio)


if __name__ == "__main__":
    print("=" * 60)
    print("NamVibe Promotional Video Generator")
    print("=" * 60)

    video = build_video()
    video = add_audio(video)

    print(f"\nRendering to {OUTPUT}...")
    video.write_videofile(
        OUTPUT,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="4000k",
        threads=4,
        preset="medium",
    )
    print(f"\n✅ Video saved to: {OUTPUT}")
    print(f"   Duration: {video.duration:.1f}s")
