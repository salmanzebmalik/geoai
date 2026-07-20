#!/usr/bin/env bash
# pgstac database (conda postgres, TCP only); "titiler" is a read-only role
export DATABASE_URL="postgresql://titiler@127.0.0.1:5432/stac"

# low-zoom mosaic tiles open many JP2s at once -> raise the fd limit
ulimit -n 65536 2>/dev/null || true

# GDAL tuning for local-file JP2/COG reads
export GDAL_CACHEMAX=512
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
export VSI_CACHE=TRUE
export VSI_CACHE_SIZE=536870912

# seconds before a mosaic tile's pgstac search gives up
export TITILER_PGSTAC_SEARCH_TIME_LIMIT=10

# titiler now lives in the consolidated root .venv (not the old venv_titiler_pgstac)
../.venv/bin/uvicorn titiler_app:app \
  --host 127.0.0.1 --port 8001 --workers 2 2>&1 | tee -a titiler.log
