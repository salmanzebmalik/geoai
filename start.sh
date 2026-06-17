#!/bin/bash
# chmod +x start.sh
set -e 

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"


pkill -f uvicorn || true
sleep 2

# Activate venv
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/ in the repository root."
    exit 1
fi
source .venv/bin/activate

# Relative paths:
ML_SERVICE_DIR="ml-service"
IMAGE_PIPELINE_DIR="image_pipeline"
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"


echo "Starting ml-service on port 8000..."
cd "$SCRIPT_DIR/$ML_SERVICE_DIR"
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

echo "Starting image-pipeline (Titiler) on port 8001..."
cd "$SCRIPT_DIR/$IMAGE_PIPELINE_DIR"
uvicorn titiler_app:app --host 127.0.0.1 --port 8001 &

echo "Starting backend on port 8002..."
cd "$SCRIPT_DIR/$BACKEND_DIR"
uvicorn app.main:app --host 127.0.0.1 --port 8002 &

# echo "Starting frontend dev server..."
# cd "$SCRIPT_DIR/$FRONTEND_DIR"
# npm run dev