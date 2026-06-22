# Phase 129 — Production Safety & Beta Monitoring

## Overview

This phase adds safety guards for NamVibe's current Cloudflare Tunnel + Mac-hosted
production setup. The key additions are:

- **Awake Guard**: prevents macOS sleep using `caffeinate -dimsu`
- **Stop Script**: safely stops Gunicorn, cloudflared, and caffeinate
- **Beta Monitor**: periodic health checks with JSONL logging
- **Status Script**: single command to view full production state
- **Secrets Audit**: ensures secrets are not committed to git

---

## Keep Mac Awake

NamVibe runs from your local Mac. If the Mac sleeps, the site goes down.

### Start Awake Guard

```bash
python3 scripts/start_phase129_awake_guard.py
```

This runs `caffeinate -dimsu` which prevents:
- **d** — display sleep
- **i** — idle sleep
- **m** — lid sleep (clamshell mode)
- **s** — system sleep
- **u** — user idle sleep

### Verify

```bash
pgrep -f "caffeinate.*-dimsu"   # should show a PID
```

### Stop

```bash
python3 scripts/stop_phase129_production_local.py --awake
```

### Auto-Start on Login (launchd)

```bash
sed -i '' 's|__PROJECT_ROOT__|/Users/admin/Desktop/chain_app|g' \
  ops/macos/com.namvibe.awake.plist
cp ops/macos/com.namvibe.awake.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.namvibe.awake.plist
```

---

## Start / Stop Gunicorn

### Start

```bash
python3 scripts/start_phase128_production_local.py
```

### Restart

```bash
python3 scripts/start_phase128_production_local.py --restart
```

### Stop

```bash
python3 scripts/stop_phase129_production_local.py
```

---

## Start / Stop Cloudflare Tunnel

### Start

```bash
python3 scripts/start_phase128_tunnel.py
```

### Stop

```bash
python3 scripts/stop_phase129_production_local.py --tunnel
```

---

## Stop Everything

```bash
python3 scripts/stop_phase129_production_local.py --all
```

This stops Gunicorn, cloudflared, and the awake guard.

---

## Run Beta Monitor

### Single Check

```bash
python3 scripts/monitor_phase129_beta_health.py
```

Checks all endpoints once and writes JSONL to `logs/beta_health_phase129.jsonl`.

### Continuous Loop

```bash
python3 scripts/monitor_phase129_beta_health.py --loop --interval 60
```

Checks every 60 seconds until Ctrl+C. Useful for monitoring during development
or deployment verification.

### Read Monitor Logs

```bash
cat logs/beta_health_phase129.jsonl | python3 -m json.tool --no-ensure-ascii 2>/dev/null || cat logs/beta_health_phase129.jsonl
```

Or tail recent entries:

```bash
tail -5 logs/beta_health_phase129.jsonl
```

---

## Check Production Status

```bash
python3 scripts/status_phase129_production.py
```

Shows:
- Git branch, latest commit, working tree cleanness
- Port 8080 status
- Gunicorn / cloudflared / caffeinate running state
- Local and live health check results
- /healthz details (Redis, DB, uptime)
- Last 5 monitor log entries

---

## How to Avoid Committing Secrets

### .gitignore Protection

The `.gitignore` file excludes:
- `.env` and `.env.*` files
- `secrets/` directory
- `logs/` directory (all log files)
- `tmp/` directory (PID files)
- `*.pem`, `*.key`, `*.crt`, `*.p12` (TLS keys)
- `*.sqlite`, `*.db` (databases)
- `*.bak`, `*.pid`, `*.log`
- `.cloudflared/*.json` (tunnel credentials)

### Run Secrets Audit

```bash
python3 scripts/audit_phase129_secrets_safety.py
```

Checks:
- No .env files tracked
- No secrets/ files tracked
- No logs/ files tracked
- No private keys tracked
- No cloudflared credentials tracked
- .gitignore contains all required patterns
- Source files are free of secret patterns

### Important: Never

- `git add .env` or `git add -f .env`
- Commit files containing `SUPABASE_SERVICE_ROLE_KEY` or `DATABASE_URL`
- Print environment variables containing secrets from scripts
- Store cloudflared credentials JSON in the repo

---

## How to Read Logs

| Log File | Contents |
|---|---|
| `logs/gunicorn_phase128.log` | Gunicorn access/error logs |
| `logs/gunicorn_launchd.log` | Gunicorn logs when run via launchd |
| `logs/cloudflared_phase128.log` | Cloudflare tunnel logs |
| `logs/cloudflared_launchd.log` | Cloudflare tunnel logs when run via launchd |
| `logs/awake_guard_phase129.log` | Awake guard logs |
| `logs/awake_guard_launchd.log` | Awake guard logs when run via launchd |
| `logs/beta_health_phase129.jsonl` | Beta health monitor (JSONL format) |

```bash
# Tail latest activity
tail -f logs/gunicorn_phase128.log

# Check for errors
grep -i "error" logs/gunicorn_phase128.log

# Check health history
tail -10 logs/beta_health_phase129.jsonl

# Quick status
python3 scripts/status_phase129_production.py
```

---

## Risks of Laptop Hosting (Recap)

| Risk | Impact | Mitigation |
|---|---|---|
| Mac sleeps | Site down | `caffeinate -dimsu` or Amphetamine app |
| Power outage | Site down | UPS battery backup |
| Wi-Fi drop | Tunnel broken | Use Ethernet; cloudflared reconnects auto |
| macOS update | Forced restart | Disable "Automatically restart" in System Settings |
| Theft | Data breach | FileVault encryption, strong password |
| No scaling | Traffic spike = slow | 1 worker intentional (WebSocket), but limited |

---

## Recommendation: Move to VPS / Cloud Run

This Mac-hosted setup is suitable for **beta and early testing** only.

For production launch, migrate to:

1. **Google Cloud Run** — auto-scaling, managed SSL, free tier
2. **DigitalOcean App Platform** — fixed pricing, simple deploy
3. **Railway / Render** — git-push deploy, built-in PostgreSQL

The Dockerfile and `gunicorn.conf.py` are already configured for Cloud Run.
Update `--min-instances 1` to avoid cold starts.
