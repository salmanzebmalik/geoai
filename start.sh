#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

pkill -f uvicorn || true
sleep 2

if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/ in the repository root."
    exit 1
fi
source .venv/bin/activate

# Function to stop all background processes on exit
cleanup() {
    echo "Shutting down services..."
    pkill -f uvicorn || true
    pkill -f "npm run dev" || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start all services in the background with logs
echo "Starting ml-service on port 8010..."
cd "$SCRIPT_DIR/ml-service"
uvicorn app.main:app --host 127.0.0.1 --port 8010 &
ML_PID=$!

echo "Starting image-pipeline (Titiler) on port 8011..."
cd "$SCRIPT_DIR/image_pipeline"
uvicorn titiler_app:app --host 127.0.0.1 --port 8011 &
TITILER_PID=$!

echo "Starting backend on port 8012..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --host 127.0.0.1 --port 8012 &
BACKEND_PID=$!

# Wait for services
sleep 3

echo "All services are running!"
echo "Starting frontend dev server..."
echo "Press Ctrl+C to stop all services"

cd "$SCRIPT_DIR/frontend"
npm run dev &

# Wait for all background processes
wait