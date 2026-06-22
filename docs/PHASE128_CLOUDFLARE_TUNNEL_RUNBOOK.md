# Phase 128 — Cloudflare Tunnel & Production Runbook

## How NamVibe Hosting Works

```ascii
User Browser → namvibe.com → Cloudflare Edge → Cloudflare Tunnel → localhost:8080 → Gunicorn → Flask app:app
```

**Important:** Cloudflare does *not* host the Flask application. Cloudflare only provides:

- DNS resolution (namvibe.com → Cloudflare edge IPs)
- TLS/SSL termination (HTTPS)
- DDoS protection
- Reverse proxy (forwards requests through the tunnel)

The actual Flask application runs **locally on a Mac mini / laptop** behind a
Cloudflare Tunnel (cloudflared). This is a lightweight production setup suitable
for beta/early-stage traffic.

---

## Infrastructure Requirements

| Component | Port | Must Always Run |
|---|---|---|
| Gunicorn (Flask app) | 0.0.0.0:8080 | Yes |
| cloudflared (tunnel) | — (outbound only) | Yes |
| macOS (host OS) | — | Yes — must stay awake |

---

## How to Start Manually

### 1. Start Gunicorn

```bash
cd /Users/admin/Desktop/chain_app
python3 scripts/start_phase128_production_local.py
```

Use `--restart` to kill an existing Gunicorn first:

```bash
python3 scripts/start_phase128_production_local.py --restart
```

### 2. Start Cloudflare Tunnel

```bash
python3 scripts/start_phase128_tunnel.py
```

### 3. Verify Everything

```bash
python3 scripts/check_phase128_production_health.py
```

---

## Launchd Services (Auto-Start on Boot/Login)

For production reliability, both Gunicorn and cloudflared should start
automatically when macOS boots or the user logs in.

### Prerequisites

1. Edit the plist files to update `__PROJECT_ROOT__` placeholders:

   ```bash
   # Find and replace __PROJECT_ROOT__ with your actual project path
   sed -i '' 's|__PROJECT_ROOT__|/Users/admin/Desktop/chain_app|g' \
     ops/macos/com.namvibe.gunicorn.plist

   sed -i '' 's|__PROJECT_ROOT__|/Users/admin/Desktop/chain_app|g' \
     ops/macos/com.namvibe.cloudflared.plist

   # Also update __HOME__ and __TUNNEL_ID__ in the cloudflared plist
   sed -i '' 's|__HOME__|/Users/admin|g' \
     ops/macos/com.namvibe.cloudflared.plist
   sed -i '' 's|__TUNNEL_ID__|8f008f0f-9d5e-4b7f-b67e-08e0f1c83921|g' \
     ops/macos/com.namvibe.cloudflared.plist
   ```

2. Copy plist files to `~/Library/LaunchAgents/`:

   ```bash
   cp ops/macos/com.namvibe.gunicorn.plist ~/Library/LaunchAgents/
   cp ops/macos/com.namvibe.cloudflared.plist ~/Library/LaunchAgents/
   ```

3. Load the services:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.namvibe.gunicorn.plist
   launchctl load ~/Library/LaunchAgents/com.namvibe.cloudflared.plist
   ```

### Verify Launchd Services

```bash
launchctl list | grep namvibe
# Should show both com.namvibe.gunicorn and com.namvibe.cloudflared
```

---

## How to Stop Services

### Manual Stop

```bash
# Kill Gunicorn
kill $(cat tmp/namvibe_gunicorn.pid) 2>/dev/null
pkill -f "gunicorn.*:8080" 2>/dev/null

# Kill cloudflared
pkill -f "cloudflared.*tunnel" 2>/dev/null
```

### Launchd Stop

```bash
launchctl unload ~/Library/LaunchAgents/com.namvibe.gunicorn.plist
launchctl unload ~/Library/LaunchAgents/com.namvibe.cloudflared.plist
```

### Prevent Auto-Start

```bash
# Remove plist files to prevent loading on next boot
rm ~/Library/LaunchAgents/com.namvibe.gunicorn.plist
rm ~/Library/LaunchAgents/com.namvibe.cloudflared.plist
```

---

## How to Check Logs

| Service | Log File |
|---|---|
| Gunicorn (manual) | `logs/gunicorn_phase128.log` |
| Gunicorn (launchd) | `logs/gunicorn_launchd.log` |
| Cloudflared (manual) | `logs/cloudflared_phase128.log` |
| Cloudflared (launchd) | `logs/cloudflared_launchd.log` |

```bash
# Tail Gunicorn logs
tail -f logs/gunicorn_phase128.log

# Search for errors
grep -i "error\|critical\|traceback" logs/gunicorn_phase128.log

# Tail cloudflared logs
tail -f logs/cloudflared_phase128.log
```

---

## How to Verify Live Site

```bash
# Full health check
python3 scripts/check_phase128_production_health.py

# Quick curl checks
curl -sI https://namvibe.com/ | head -5
curl -s https://namvibe.com/ | grep -o "phase12[0-9]"
curl -sI https://www.namvibe.com/ | head -5
curl -sI https://namvibe.com/static/js/namvibe_home_pro.js | head -3
curl -sI https://namvibe.com/static/css/namvibe_home_pro.css | head -3

# Live build verification
python3 scripts/verify_phase127_live_build.py
```

---

## Risks of Hosting Production from a Mac

### 1. Sleep & Power Management

macOS may sleep, hibernate, or throttle the network when:

- The lid is closed (laptop)
- The system is idle for too long
- Power source changes (battery vs AC)

**Mitigations:**

```bash
# Prevent sleep while logged in (terminal)
caffeinate -dimsu

# Or use Amphetamine app (App Store) for a GUI keep-awake
# Or use Third-party tool: KeepingYouAwake
```

### 2. Network Changes

- Wi-Fi disconnects/interference
- IP address changes (DHCP renewal)
- Network interface switching (Wi-Fi <-> Ethernet)

**Mitigation:** Use Ethernet if possible. cloudflared reconnects automatically
after brief network interruptions.

### 3. Power Outages

- No battery backup = immediate downtime
- Even with battery, Mac will eventually shut down

**Mitigation:** Connect to a UPS (Uninterruptible Power Supply).

### 4. macOS Updates

- macOS may force-restart after an update
- Kernel panics or software updates can interrupt service

**Mitigation:** Turn off "Automatically restart" in System Settings.
Apply updates manually during maintenance windows.

### 5. Resource Limits

- Single machine, single Gunicorn worker
- No horizontal scaling
- RAM/CPU shared with desktop applications

**Mitigation:** 1 worker is intentional (WebSocket requirement). Monitor
memory with `top -l 1 -o mem`.

### 6. Security

- Physical access risk (laptop can be stolen)
- No security group / firewall configuration
- Local network exposure

**Mitigation:** Keep the Mac in a secure location, use a strong password,
enable FileVault encryption.

---

## Recommendation: Move to VPS / Cloud Run

For production traffic above beta levels, migrate to:

| Option | Pros | Cons |
|---|---|---|
| Google Cloud Run | Managed, auto-scaling, cheap at low traffic | Requires containerization |
| DigitalOcean Droplet | Fixed cost, full control | Manual setup |
| Railway / Render | Easy deploy from git | Slightly more expensive |
| AWS ECS / Fargate | Enterprise-grade | Complex setup |

**Migration path:**

1. Containerize the app (Dockerfile already exists)
2. Push to Google Artifact Registry / Docker Hub
3. Deploy to Cloud Run with `--min-instances 1` for zero cold start
4. Update Cloudflare Tunnel ingress to point to Cloud Run URL
5. Decommission local Mac hosting

---

## Quick Reference

```bash
# === START ===
python3 scripts/start_phase128_production_local.py
python3 scripts/start_phase128_tunnel.py

# === CHECK ===
python3 scripts/check_phase128_production_health.py

# === STOP ===
kill $(cat tmp/namvibe_gunicorn.pid)
pkill -f cloudflared.*tunnel

# === LOGS ===
tail -f logs/gunicorn_phase128.log
tail -f logs/cloudflared_phase128.log

# === LAUNCHD ===
launchctl load   ~/Library/LaunchAgents/com.namvibe.gunicorn.plist
launchctl unload ~/Library/LaunchAgents/com.namvibe.gunicorn.plist
launchctl load   ~/Library/LaunchAgents/com.namvibe.cloudflared.plist
launchctl unload ~/Library/LaunchAgents/com.namvibe.cloudflared.plist
```
