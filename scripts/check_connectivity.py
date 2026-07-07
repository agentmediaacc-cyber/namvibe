"""NamVibe — Full Infrastructure Connectivity Check"""

import os
import sys
import time

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ok(msg): print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def header(msg): print(f"\n{CYAN}{BOLD}{msg}{RESET}")

def check_neon():
    header("Neon Database (PostgreSQL)")
    try:
        from services.neon_service import get_neon_health, fast_query
        health = get_neon_health()
        if health.get("connected"):
            ok(f"Connected — latency: {health.get('latency_ms', '?')}ms")
        elif health.get("status") == "disabled":
            warn("Fast local mode — DB ping disabled")
        else:
            fail(f"Not connected: {health.get('error', 'unknown')}")
        try:
            r = fast_query("SELECT 1", timeout_ms=3000)
            if r:
                ok("SELECT 1 works")
        except Exception as e:
            fail(f"Query failed: {e}")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_redis():
    header("Redis")
    try:
        from services.redis_service import get_redis_health, redis_available
        health = get_redis_health()
        avail = redis_available()
        if avail:
            ok(f"Available — ping: {health.get('ping_ms', 0):.1f}ms")
        elif health.get("fallback_mode"):
            warn("Fallback mode enabled (memory cache)")
        else:
            fail("Not available")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_socketio():
    header("Socket.IO")
    try:
        from services.socketio_service import socketio
        async_mode = getattr(socketio, 'async_mode', 'unknown')
        server = getattr(socketio, 'server', None)
        if server is not None:
            ok(f"Initialized — async_mode={async_mode}")
        else:
            warn(f"Server not initialized ({async_mode})")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_livekit():
    header("LiveKit (WebRTC SFU)")
    try:
        from services.livekit_service import get_livekit_server_info, check_livekit_health, livekit_configured
        info = get_livekit_server_info()
        if info.get("configured"):
            ok(f"Configured — host={info['host']}")
            health = check_livekit_health()
            if health.get("ok"):
                ok(f"Server reachable — rooms: {health.get('room_count', 0)}")
            elif health.get("status") == "no_sdk":
                fail("SDK not installed (pip install livekit)")
            else:
                warn(f"Server unreachable: {health.get('error', 'timeout?')}")
        else:
            warn("Not configured — set LIVEKIT_API_KEY and LIVEKIT_API_SECRET")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_turn():
    header("coturn (STUN/TURN)")
    try:
        from services.turn_service import get_turn_status
        status = get_turn_status()
        if status.get("configured"):
            ok(f"Configured — TURN URL: {status['turn_url']}")
        else:
            warn("Not configured — set TURN_URL/TURN_USERNAME/TURN_CREDENTIAL")
        ok(f"STUN servers: {status.get('stun_servers', 0)} built-in (Google)")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_supabase():
    header("Supabase (optional)")
    try:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
        if supabase_url and supabase_key:
            ok("Credentials configured")
            try:
                from supabase import create_client
                sb = create_client(supabase_url, supabase_key)
                ok("Client created successfully")
            except Exception as e:
                warn(f"Client creation failed: {e}")
        else:
            warn("Not configured — set SUPABASE_URL and SUPABASE_ANON_KEY")
    except Exception as e:
        fail(f"Import/check error: {e}")

def check_env():
    header("Environment Variables")
    vars = [
        "APP_NAME", "APP_DOMAIN", "SECRET_KEY",
        "DATABASE_URL", "REDIS_URL",
        "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_HOST",
        "TURN_URL", "TURN_USERNAME", "TURN_CREDENTIAL",
        "SUPABASE_URL", "SUPABASE_ANON_KEY",
    ]
    for v in vars:
        val = os.environ.get(v, "")
        if val:
            masked = val[:8] + "..." if len(val) > 12 else val
            ok(f"{v}={masked}")
        else:
            warn(f"{v} not set")

def check_ffmpeg():
    header("FFmpeg (recording/replay)")
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg:
        ok(f"ffmpeg found: {ffmpeg}")
    else:
        warn("ffmpeg not found — install with: brew install ffmpeg")
    if ffprobe:
        ok(f"ffprobe found: {ffprobe}")
    else:
        warn("ffprobe not found")

def check_packages():
    header("Required Python Packages")
    required = ["flask", "flask_socketio", "psycopg2", "redis", "livekit", "livekit.api",
                 "gunicorn", "gevent", "dotenv", "supabase", "PIL", "cryptography", "requests",
                 "apscheduler", "wtforms", "bleach", "sentry_sdk", "jwt"]
    for pkg in required:
        try:
            __import__(pkg)
            ok(pkg)
        except ImportError:
            fail(f"{pkg} missing")

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")

    print(f"\n{BOLD}═══ NamVibe Infrastructure Connectivity Check ═══{RESET}")
    print(f"  CWD: {os.getcwd()}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    check_env()
    check_neon()
    check_redis()
    check_socketio()
    check_livekit()
    check_turn()
    check_supabase()
    check_ffmpeg()
    check_packages()

    print(f"\n{BOLD}═══ Done ═══{RESET}\n")
