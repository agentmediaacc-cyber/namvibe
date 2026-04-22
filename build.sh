#!/usr/bin/env bash
set -e

export NAMVIBE_BUILD=1

echo "Collecting static..."
python3 manage.py collectstatic --noinput

if [ -n "${DATABASE_URL:-}" ]; then
  echo "Running migrations..."
  python3 manage.py migrate
else
  echo "Skipping migrations during build because DATABASE_URL is not set."
fi

echo "Checking project..."
python3 manage.py check
