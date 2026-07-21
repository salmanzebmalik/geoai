#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

#pkill -f uvicorn || true
sleep 2

# Run each background job in its own process group so cleanup() can kill a
# job's children too (e.g. the uvicorn+tee pipeline inside launch_titiler.sh)
set -m

if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/ in the repository root."
    exit 1
fi
source .venv/bin/activate

# Function to stop only the processes (and their children) this script started
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
echo "Starting ml-service on port 8002..."
cd "$SCRIPT_DIR/ml-service"
uvicorn app.main:app --host 127.0.0.1 --port 8002 &
ML_PID=$!

echo "Starting image-pipeline (Titiler) on port 8001..."
# reuse launch_titiler.sh so the DB URL + GDAL/ulimit tuning stay in one place
( cd "$SCRIPT_DIR/image_pipeline" && bash launch_titiler.sh ) &
TITILER_PID=$!

echo "Starting backend on port 8000..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
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