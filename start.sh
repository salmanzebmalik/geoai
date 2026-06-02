#!/bin/bash
chmod +x start.sh
set -e 

pkill -f uvicorn || true
sleep 2

source /home/ubuntu/work/saved_data/geoai-project/geoai/.venv/bin/activate 


ML_SERVICE_DIR="/home/ubuntu/work/saved_data/geoai-project/geoai/ml-service"
IMAGE_PIPELINE_DIR="/home/ubuntu/work/saved_data/geoai-project/geoai/image_pipeline"
BACKEND_DIR="/home/ubuntu/work/saved_data/geoai-project/geoai/backend"


echo "Starting ml-service on port 8000..."
cd "$ML_SERVICE_DIR"
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

echo "Starting image-pipeline (Titiler) on port 8001..."
cd "$IMAGE_PIPELINE_DIR"
uvicorn titiler_app:app --host 127.0.0.1 --port 8001 &

echo "Starting backend on port 8002..."
cd "$BACKEND_DIR"
uvicorn app.main:app --host 127.0.0.1 --port 8002 &