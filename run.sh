#!/usr/bin/env bash
set -euo pipefail

# Simple startup script for local / Railway deployments
# Creates a virtualenv if not present and runs uvicorn.

PYTHON=${PYTHON:-python3}
VEV_DIR="venv"

if [ ! -d "$VEV_DIR" ]; then
  echo "Creating virtualenv..."
  $PYTHON -m venv "$VEV_DIR"
fi

echo "Activating virtualenv..."
# Prefer POSIX-compatible dot for activation (works in sh/bash)
# Try common venv activation paths and fail gracefully if none found
if [ -f "$VEV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$VEV_DIR/bin/activate"
elif [ -f "$VEV_DIR/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  . "$VEV_DIR/Scripts/activate"
else
  echo "Warning: virtualenv activation script not found; continuing without venv"
fi

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting uvicorn..."
exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
