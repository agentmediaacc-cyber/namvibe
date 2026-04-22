#!/usr/bin/env bash
set -e

export NAMVIBE_BUILD=1

echo "Collecting static..."
python3 manage.py collectstatic --noinput

echo "Skipping migrations during build."
echo "Runtime must still provide DATABASE_URL for the real PostgreSQL/Supabase connection."

echo "Checking project..."
python3 manage.py check
