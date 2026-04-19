#!/bin/bash

# --- CONFIGURATION ---
VENV_DIR="venv"
FASTAPI_PORT=8000
FASTAPI_MODULE="app.main:app"

echo "🟢 Starting ACE Real Estate backend..."

# --- CREATE AND ACTIVATE VENV ---
if [ ! -d "$VENV_DIR" ]; then
  echo "🔧 Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "✅ Virtual environment activated"

# --- START FASTAPI ONLY ---
echo "⚙️ Starting FastAPI on port $FASTAPI_PORT..."
uvicorn "$FASTAPI_MODULE" --port $FASTAPI_PORT --reload
