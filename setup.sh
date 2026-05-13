#!/usr/bin/env bash
set -e

echo ""
echo "============================================="
echo "  Nebulynx Oncall System — Setup"
echo "============================================="

# 1. Python version check
PYTHON=$(python3 --version 2>&1)
echo "[✓] $PYTHON"

# 2. Virtual environment
if [ ! -d ".venv" ]; then
  echo "[→] Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "[✓] Virtual environment active."

# 3. Install dependencies
echo "[→] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "[✓] Dependencies installed."

# 4. .env file
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[!] .env created from .env.example — fill in your credentials."
else
  echo "[✓] .env already exists."
fi

# 5. Initialize database
echo "[→] Initializing database..."
python run.py --init-db
echo "[✓] Database initialized."

echo ""
echo "============================================="
echo "  NEXT STEPS"
echo "============================================="
echo ""
echo "1. Edit .env — especially GMAIL_APP_PASSWORD"
echo ""
echo "2. Start ngrok in a separate terminal:"
echo "     ngrok http 5001"
echo "   (ngrok auto-updates Twilio webhooks on startup)"
echo ""
echo "3. Start the server:"
echo "     source .venv/bin/activate && python run.py"
echo ""
echo "4. Open the admin panel:"
echo "     http://localhost:5000"
echo "     Username: admin   Password: admin123"
echo ""
echo "5. IMPORTANT — Twilio trial accounts:"
echo "   Verify all engineer phone numbers at:"
echo "   https://console.twilio.com/us1/develop/phone-numbers/verified"
echo ""
echo "============================================="
