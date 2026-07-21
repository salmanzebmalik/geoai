#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

stop_services() {
    pkill -f "uvicorn .*--port (8011|8012|8013)" || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    true
}

stop_services
sleep 2

if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/ in the repository root."
    exit 1
fi
source .venv/bin/activate

cleanup() {
    echo "Shutting down services..."
    stop_services
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start all services in the background with logs
echo "Starting ml-service on port 8012..."
cd "$SCRIPT_DIR/ml-service"
uvicorn app.main:app --host 127.0.0.1 --port 8012 &

echo "Starting image-pipeline (Titiler) on port 8011..."
# reuse launch_titiler.sh so the DB URL + GDAL/ulimit tuning stay in one place
( cd "$SCRIPT_DIR/image_pipeline" && bash launch_titiler.sh ) &

echo "Starting backend on port 8013..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --host 127.0.0.1 --port 8013 &

# Wait for services
sleep 3

echo "All services are running!"
echo "Starting frontend dev server..."
echo "Press Ctrl+C to stop all services"

cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

# Wait for all background processes
wait