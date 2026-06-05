# CHAIN Production Deployment Guide

## Prerequisites
- **Ubuntu 22.04+ VPS** recommended
- **Neon**: Primary PostgreSQL database
- **Supabase**: Auth, Storage, and Realtime fallback
- **Redis**: Realtime state, Caching, and RQ Queues

## 1. Local Pre-check
Before pushing to production, run:
```bash
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/launch_readiness.py
```

## 2. VPS Installation
Run the following script to install system dependencies and set up the environment:
```bash
bash scripts/vps_install_dependencies.sh
```

## 3. Environment Configuration
Create a `.env` file in the root directory (copy from `.env.production.example`):
```bash
SECRET_KEY=your-long-secure-random-key
FLASK_ENV=production
DATABASE_URL=postgres://user:pass@host/db
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
REDIS_URL=redis://localhost:6379/0
```

## 4. Production Hardening
### Database Migration
Apply the latest schema safely:
```bash
PYTHONPATH=. python3 scripts/migrate_neon.py
```

### Supabase Storage
Ensure all required buckets are present:
```bash
PYTHONPATH=. python3 scripts/check_supabase_buckets.py
```

### Security Audit
Run a final security check:
```bash
PYTHONPATH=. python3 scripts/security_audit.py
```

## 5. Service Configuration
### systemd
Copy the service files and enable them:
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable chain chain-worker
sudo systemctl start chain chain-worker
```

*For Realtime (Socket.IO) mode:*
```bash
sudo systemctl enable chain-realtime
sudo systemctl start chain-realtime
```

### Nginx
Configure the reverse proxy:
```bash
sudo cp nginx/chain.conf.example /etc/nginx/sites-available/chain
sudo ln -s /etc/nginx/sites-available/chain /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 6. Realtime & Workers
- **RQ Worker**: Handles media processing and cleanup tasks.
- **WebSocket**: Enabled via `chain-realtime.service`.

## 7. Troubleshooting
- **Logs**: `journalctl -u chain -f`
- **Redis**: `redis-cli ping`
- **Neon**: Check connection pool in Dashboard.

## Rollback
1. Revert to previous Git tag.
2. If schema changes are incompatible, restore Neon from backup.

