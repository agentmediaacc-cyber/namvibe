#!/bin/bash
echo "🔥 FORCE CLEAN INSTALL..."

rm -rf .venv
rm -rf venv

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput

echo "✅ CLEAN BUILD COMPLETE"
