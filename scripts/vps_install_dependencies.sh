#!/bin/bash
set -e

echo "[vps] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    redis-server \
    nginx \
    ffmpeg

echo "[vps] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[vps] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[vps] Installation complete."
echo "Please configure your .env file before running deploy checks."
