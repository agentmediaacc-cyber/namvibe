# CHAIN VPS Run Book

## Prerequisites

### System
- Ubuntu 22.04+ (tested)
- 4+ vCPU, 4-8 GB RAM, 20 GB+ SSD
- Domain name with DNS A record pointing to VPS IP
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Environment Variables (set in `/etc/environment` or systemd override)
```bash
CHAIN_ENV=production
CHAIN_DEV_TOOLS=0
CHAIN_SHOW_TEST_CONTENT=0
DATABASE_URL=postgres://user:pass@host/db?sslmode=require
REDIS_URL=redis://:password@host:6379/0
JWT_SECRET_KEY=<random-64-char-hex>
SECRET_KEY=<random-64-char-hex>
SENTRY_DSN=<optional>
TURN_SERVER_URL=<optional>
TURN_USERNAME=<optional>
TURN_PASSWORD=<optional>
```

### Required Services
- PostgreSQL 15+ (Neon Standard or self-hosted)
- Redis 7+ (Upstash or self-hosted)
- Nginx 1.24+
- Python 3.11+
- Supervisor or systemd

---

## Step 1: System Setup

```bash
# Update system
apt update && apt upgrade -y
apt install -y nginx python3.11 python3.11-venv git curl fail2ban logrotate

# Create app user
adduser --system --group chain
usermod -aG chain $USER
```

## Step 2: Clone & Install

```bash
mkdir -p /opt/chain
cd /opt/chain
git clone <repo-url> .
git checkout main

# Python venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Apply indexes
python3 scripts/apply_phase71_performance_indexes.py
python3 scripts/apply_phase74_full_speed_indexes.py

# Apply DB migrations
python3 scripts/apply_phase70_dating_fix.py
```

## Step 3: Nginx

```bash
cp nginx/chain.conf.example /etc/nginx/sites-available/chain
ln -s /etc/nginx/sites-available/chain /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Edit domain name in the config
sed -i 's/your_domain.com/your-actual-domain.com/g' /etc/nginx/sites-available/chain

# SSL with Certbot
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-actual-domain.com

# Test and reload
nginx -t && systemctl reload nginx
```

## Step 4: Web Worker (gunicorn)

```bash
cp systemd/chain.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable chain
systemctl start chain
journalctl -u chain -f  # watch logs
```

## Step 5: WebSocket Worker

```bash
cp systemd/chain-realtime.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable chain-realtime
systemctl start chain-realtime
```

## Step 6: Background Worker (RQ)

```bash
cp systemd/chain-worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable chain-worker
systemctl start chain-worker
```

## Step 7: Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

## Step 8: Monitoring

```bash
# Fail2ban for SSH
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
systemctl restart fail2ban

# Logrotate for app logs
cat > /etc/logrotate.d/chain << 'EOF'
/opt/chain/var/log/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF

# Uptime monitoring (optional)
# Install https://healthchecks.io or similar
```

## Step 9: Verify

```bash
# Run production checks
export DATABASE_URL="..." REDIS_URL="..."
python3 scripts/test_phase75_real_user_journey.py
python3 scripts/test_phase76_load_and_scale.py

# Smoke test endpoints
curl -s -o /dev/null -w "%{http_code}" https://your-domain.com/     # Should be 200
curl -s -o /dev/null -w "%{http_code}" https://your-domain.com/login  # Should be 200
```

---

## Architecture

```
                         ┌─────────────┐
                         │   Nginx :443 │
                         └──────┬──────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────┴───────┐       ┌───────┴───────┐
            │ Gunicorn :5055│       │ GeventWS :5056│  (WebSocket)
            │ (9 workers)   │       │ (1 worker)    │
            └───────┬───────┘       └───────┬───────┘
                    │                       │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │      Redis :6379      │
                    │  (message_queue)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │    Neon Postgres      │
                    │  (max 20 connections) │
                    └───────────────────────┘

Background:
  RQ Worker (1 process) — notifications, payouts, cleanup
```

## Capacity

| Metric | Estimate |
|--------|----------|
| Concurrent users | ~200-500 |
| Daily active users | ~1,000-5,000 |
| DB connections | 20 (pool max) |
| DB query timeout | 10s default, 2s fast |
| Redis connections | Unlimited (Upstash) |
| WebSocket conns | ~1,000 per worker |
| Static files | Nginx direct, 30d cache |

## Scaling Beyond 1,000 DAU

1. **Connection pooling** → PgBouncer sidecar for Neon
2. **Read replicas** → Point read queries to replica; writes to primary
3. **Redis Cluster** → Sharded Redis for SocketIO
4. **Auto-scaling** → Horizontal gunicorn behind load balancer
5. **CDN** → Cloudflare/CacheFly for static assets
6. **TURN server** → coturn for WebRTC behind NAT

## Troubleshooting

### "Database connection pool is unavailable"
Circuit breaker tripped after 5 failures. Wait 30s for auto-recovery.
Check Neon cold start: first query after inactivity takes 3-6s.

### "Redis connection failed"
Memory fallback activated. SocketIO falls to single-node mode.
Check `REDIS_URL` env var and network access.

### "502 Bad Gateway"
- Gunicorn not running: `systemctl status chain`
- Gunicorn crashed: `journalctl -u chain --no-pager -n 50`
- Port mismatch: Check `bind` in `gunicorn.conf.py` vs nginx proxy_pass

### "WebSocket connection failed"
Ping timeout 20s, ping interval 10s. Check:
- `systemctl status chain-realtime`
- nginx WebSocket upgrade headers in config
- Redis message_queue configuration

### High memory usage
- Each gunicorn worker: ~100-200MB
- Reduce workers: edit `gunicorn.conf.py` -> `workers = multiprocessing.cpu_count() * 2 + 1`
- Check for memory leak: `ps aux --sort=-%mem | head`

## Maintenance

### Daily
```bash
journalctl --since "24 hours ago" -u chain | grep -i "error\|exception\|traceback" | wc -l
```

### Weekly
```bash
python3 scripts/apply_phase71_performance_indexes.py  # idempotent
python3 scripts/apply_phase74_full_speed_indexes.py
```

### Monthly
```bash
# Repack Neon DB (if self-hosted)
VACUUM ANALYZE;

# Rotate secrets
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export SECRET_KEY=$(openssl rand -hex 32)

# Update system
apt update && apt upgrade -y
```
