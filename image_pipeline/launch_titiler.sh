#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# source "$SCRIPT_DIR/../ports.sh"
TITILER_PORT="${TITILER_PORT:-8001}" # Used for deployment

# pgstac database (conda postgres, TCP only); "titiler" is a read-only role
export DATABASE_URL="postgresql://titiler@127.0.0.1:5432/stac"

# low-zoom mosaic tiles open many JP2s at once -> raise the fd limit
ulimit -n 65536 2>/dev/null || true

# GDAL tuning for local-file JP2/COG reads
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR

# Raster block cache per worker process, in MB (x8 workers = ~8 GB total).
export GDAL_CACHEMAX=1024

# How many COGs stay open between requests instead of being reopened (default 100).
# Each open dataset costs a file descriptor; the ulimit above covers this.
export GDAL_MAX_DATASET_POOL_SIZE=300

# Threads per worker for ZSTD decompression; kept small so 8 workers do not oversubscribe.
export GDAL_NUM_THREADS=4

# Off deliberately: no measurable gain on a kernel-mounted filesystem, and its size limit is per file handle.
export VSI_CACHE=FALSE

# seconds before a mosaic tile's pgstac search gives up
export TITILER_PGSTAC_SEARCH_TIME_LIMIT=15

# Stop reading candidate scenes once the tile is fully covered (safe with real polygon footprints).
export TITILER_PGSTAC_SEARCH_EXITWHENFULL=true

# Skip scenes that would sit entirely underneath ones already read (same reason).
export TITILER_PGSTAC_SEARCH_SKIPCOVERED=true

# titiler now lives in the consolidated root .venv (not the old venv_titiler_pgstac)
../.venv/bin/uvicorn titiler_app:app \
  --host 127.0.0.1 --port "$TITILER_PORT" --workers 8 2>&1 | tee -a titiler.log
