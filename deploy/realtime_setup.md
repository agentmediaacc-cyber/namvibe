# Namvibe Realtime Setup

This document adds Redis and ASGI support for Namvibe realtime chat, notification badges, presence, and call signaling.

## Safety notes

- Do not place secrets in this file.
- Keep `DATABASE_URL`, Supabase keys, SMTP credentials, and OAuth secrets in environment variables only.
- Review the service and nginx examples before applying them on production.

## 1. Install Redis

```bash
sudo apt update
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl restart redis-server
sudo systemctl status redis-server
```

Namvibe uses `REDIS_URL` when available. If it is not set, the default runtime value is:

```text
redis://127.0.0.1:6379/0
```

## 2. Install Python dependencies

```bash
cd /var/www/namvibe
source venv/bin/activate
pip install -r requirements.txt
```

## 3. HTTP and WebSocket deployment options

### Option A: Keep Gunicorn for HTTP and add Daphne/Uvicorn for ASGI

- Keep Gunicorn serving the standard Django WSGI app for normal HTTP traffic.
- Run a separate ASGI process for websocket traffic:

```bash
daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

You can also use Uvicorn if preferred:

```bash
uvicorn config.asgi:application --host 127.0.0.1 --port 8001
```

### Option B: Run Daphne/Uvicorn for both HTTP and WebSockets

This is simpler operationally, but only switch once you confirm parity with the current Gunicorn setup.

## 4. Nginx websocket proxy snippet

Add a websocket-aware location block that forwards websocket traffic to the ASGI service:

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Keep the standard Django HTTP routes proxied to the current Gunicorn upstream if you stay with Option A.

## 5. Validation

```bash
cd /var/www/namvibe
source venv/bin/activate
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

Then verify:

- homepage loads
- `/messages/` loads after login
- topbar bell and message badges update live in another tab
- call lobby opens only for accepted friends

## 6. Restart sequence

```bash
sudo systemctl restart redis-server
sudo systemctl restart namvibe
sudo systemctl restart nginx
```

If you run Daphne/Uvicorn under systemd, restart that service too.
