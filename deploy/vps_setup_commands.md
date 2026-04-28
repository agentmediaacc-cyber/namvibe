# Namvibe VPS Setup

Use these examples as a safe deployment checklist for a DigitalOcean VPS. Do not place secrets in this repository.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

## 2. App directory

```bash
sudo mkdir -p /srv/namvibe
sudo chown $USER:$USER /srv/namvibe
git clone <your-repo-url> /srv/namvibe/app
cd /srv/namvibe/app
python3 -m venv /srv/namvibe/venv
source /srv/namvibe/venv/bin/activate
pip install -r requirements.txt
```

## 3. Environment file

Create `/srv/namvibe/.env` with production values only on the server.

Required examples:

```env
DEBUG=False
SECRET_KEY=replace-with-real-secret
DATABASE_URL=replace-with-real-database-url
ALLOWED_HOSTS=example.com,www.example.com
```

Do not commit the real `.env` file.

## 4. Django release checks

```bash
source /srv/namvibe/venv/bin/activate
cd /srv/namvibe/app
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py test
```

## 5. Systemd service

```bash
sudo cp deploy/namvibe.service.example /etc/systemd/system/namvibe.service
sudo systemctl daemon-reload
sudo systemctl enable namvibe
sudo systemctl start namvibe
sudo systemctl status namvibe
```

## 6. Nginx

```bash
sudo cp deploy/nginx-namvibe.conf.example /etc/nginx/sites-available/namvibe
sudo ln -s /etc/nginx/sites-available/namvibe /etc/nginx/sites-enabled/namvibe
sudo nginx -t
sudo systemctl reload nginx
```

## 7. Health checks

Verify these endpoints after deploy:

```bash
curl -I http://127.0.0.1:8000/healthz
curl -I http://127.0.0.1:8000/health/db
curl -I https://example.com/healthz
curl -I https://example.com/health/db
```

## 8. Ongoing release flow

```bash
cd /srv/namvibe/app
git pull origin main
source /srv/namvibe/venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl restart namvibe
sudo systemctl reload nginx
```
