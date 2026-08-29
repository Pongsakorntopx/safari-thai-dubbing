#!/bin/bash
set -e

# Run Thai Dubbing FastAPI Backend
cd "$(dirname "$0")/backend"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[INFO] Created .env from .env.example. Please add your GEMINI_API_KEY if needed."
    fi
fi

echo "========================================================"
echo " 🎙️ Starting Safari AI Thai Dubbing Backend Server..."
echo " Endpoint: http://localhost:8000"
echo " Health:   http://localhost:8000/health"
echo "========================================================"

./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
