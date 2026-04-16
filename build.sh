#!/bin/bash
set -e

echo "🔥 INSTALLING DEPENDENCIES..."
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt

echo "🧪 VERIFYING requests..."
python - <<'PY'
import requests
print("requests ok:", requests.__version__)
PY

echo "📦 COLLECTING STATIC..."
python manage.py collectstatic --noinput

echo "✅ BUILD COMPLETE"
