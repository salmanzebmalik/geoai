# GeoAI production ports

| Port | Service | Binding | Access |
|------|---------|---------|--------|
| 8000 | Nginx GPU gateway | 0.0.0.0 | New VM only |
| 8001 | TiTiler | 127.0.0.1 | GPU localhost only |
| 8002 | ML service | 127.0.0.1 | GPU localhost only |
| 8003 | Backend | 127.0.0.1 | GPU localhost only |

Port 8000 routes:
- /api/ -> 127.0.0.1:8003
- /image-api/ -> 127.0.0.1:8001
