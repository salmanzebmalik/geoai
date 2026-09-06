#!/usr/bin/env bash
# Start the pgstac PostgreSQL server if it is not already running.
# Nothing starts it automatically after a server restart — run this first,
# then the tile server: ~/work/saved_data/simon/geoai/image_pipeline/launch_titiler.sh
set -u
BASE=/home/ubuntu/work/saved_data/postgres_pgstac
BIN=$BASE/miniforge3/envs/stac/bin
DATA=$BASE/pgdata

if "$BIN/pg_isready" -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
  echo "postgres already running on 127.0.0.1:5432"
  exit 0
fi

exec "$BIN/pg_ctl" -D "$DATA" -o "-p 5432" -l "$BASE/postgres.log" start
