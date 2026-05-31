#!/usr/bin/env bash
source venv_titiler/bin/activate
uvicorn titiler_app:app --host 127.0.0.1 --port 8000
