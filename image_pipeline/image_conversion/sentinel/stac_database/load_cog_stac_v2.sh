#!/usr/bin/env bash
# Load the RGB-COG STAC collection built by build_cog_stac_masked.py into pgstac.
#
# ISOLATION: this only ever writes the ONE new collection id
# sentinel-2-l2a-rgb-cog-v2-<year> and its items. pgstac keys items to their
# collection and gives each collection its own partition, so the existing
# sentinel-2-l2a-worldwide-* / -cvce-* collections are untouched. Nothing here
# drops, truncates or deletes anything.
#
# Idempotent: pypgstac --method upsert plus a .loaded marker, so re-running
# skips a finished year and safely redoes a half-loaded one.
#
# Usage:  ./load_cog_stac.sh [year ...]        (default: 2024)
set -u
cd "$(dirname "$0")"

export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=ubuntu PGDATABASE=stac

PSQL=/home/ubuntu/work/saved_data/postgres_pgstac/miniforge3/envs/stac/bin/psql
PYPGSTAC=./venv/bin/pypgstac
OUT_ROOT="$(pwd)/out"

YEARS=("$@")
[[ ${#YEARS[@]} -eq 0 ]] && YEARS=(2024)

for year in "${YEARS[@]}"; do
  DIR="$OUT_ROOT/rgb_cog_v2_$year"
  COLL="sentinel-2-l2a-rgb-cog-v2-$year"

  if [[ ! -f "$DIR/.done" ]]; then
    echo "=== $year: SKIP — build not finished (no $DIR/.done). Run ./run_build_tmux.sh first."
    continue
  fi
  if [[ -f "$DIR/.loaded" ]]; then
    echo "=== $year: already loaded (.loaded marker), skipping"
    continue
  fi

  N=$(wc -l < "$DIR/items.ndjson")
  echo "=== $year: loading collection $COLL + $N items  [$(date +%T)]"

  $PYPGSTAC load collections "$DIR/collection.json" --method upsert \
    || { echo "=== $year: COLLECTION LOAD FAILED"; exit 1; }
  $PYPGSTAC load items "$DIR/items.ndjson" --method upsert \
    || { echo "=== $year: ITEMS LOAD FAILED"; exit 1; }

  touch "$DIR/.loaded"
  echo "=== $year: loaded  [$(date +%T)]"
done

echo
echo "=== per-collection counts (all collections, for reassurance nothing else moved):"
$PSQL -Atc "select collection, count(*), min(datetime)::date, max(datetime)::date from pgstac.items group by collection order by 1;"
echo "=== load finished  [$(date +%T)]"
