#!/usr/bin/env bash
set -e
set +H

cd ~/Desktop/namvibe
source venv/bin/activate

if [ -f ./.env.supabase ]; then
  set -a
  source ./.env.supabase
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Refusing to start with a local fallback."
  exit 1
fi

echo "=== DATABASE_URL ==="
echo "$DATABASE_URL"

echo "=== DJANGO DATABASE ENGINE ==="
python3 manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE']); print(settings.DATABASES['default']['NAME'])"

echo "=== DJANGO CHECK ==="
python3 manage.py check

echo "=== MIGRATE ==="
python3 manage.py migrate

echo "=== COLLECTSTATIC ==="
python3 manage.py collectstatic --noinput

echo "=== RUNSERVER ==="
python3 manage.py runserver 0.0.0.0:8000
