#!/usr/bin/env bash
set -e

echo "Collecting static..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Checking project..."
python manage.py check
