#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

sleep 2

# each job in its own process group, so cleanup() can kill its children too
set -m

if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/ in the repository root."
    exit 1
fi
source .venv/bin/activate

source "$SCRIPT_DIR/ports.sh"
# Reads the ports from ports.sh
export TITILER_PORT ML_SERVICE_PORT BACKEND_PORT
export TITILER_BASE_URL="http://127.0.0.1:$TITILER_PORT"
export ML_SERVICE_URL="http://127.0.0.1:$ML_SERVICE_PORT"

cleanup() {
    echo "Shutting down services..."
    for pid in "$ML_PID" "$TITILER_PID" "$BACKEND_PID" "$FRONTEND_PID"; do
        [ -n "$pid" ] || continue
        kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    done
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start all services in the background with logs
echo "Starting ml-service on port $ML_SERVICE_PORT..."
cd "$SCRIPT_DIR/ml-service"
uvicorn app.main:app --host 127.0.0.1 --port "$ML_SERVICE_PORT" &
ML_PID=$!

echo "Starting image-pipeline (Titiler) on port $TITILER_PORT..."
# reuse launch_titiler.sh so the DB URL + GDAL/ulimit tuning stay in one place
( cd "$SCRIPT_DIR/image_pipeline" && bash launch_titiler.sh ) &
TITILER_PID=$!

echo "Starting backend on port $BACKEND_PORT..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

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
