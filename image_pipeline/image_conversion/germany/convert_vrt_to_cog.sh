#!/usr/bin/env bash
#
# make_cog.sh — Germany 2021 Planet mosaic -> 8-bit RGB JPEG COG
# Bands reordered B,G,R -> R,G,B; per-band stretch + gamma 0.75; alpha -> internal mask
set -euo pipefail

INPUT="${1:-/home/ubuntu/work/satellite_data/germany/2020/2020_08.vrt}"
OUTDIR="/home/ubuntu/work/saved_data/collections/germany"
OUTPUT="${2:-${OUTDIR}/2020_germany_cog.tif}"

HALF=$(( $(nproc) / 2 )); [ "$HALF" -lt 1 ] && HALF=1
GDAL_CACHE=8192  # MB

mkdir -p "$OUTDIR"
[ -f "$INPUT" ] || { echo "ERROR: input not found: $INPUT"; exit 1; }

echo "[$(date '+%F %T')] Building COG: $INPUT -> $OUTPUT (threads: $HALF)"

gdal_translate "$INPUT" "$OUTPUT" \
    -of COG -ot Byte \
    -b 3 -b 2 -b 1 -mask 5 \
    -scale_1 0 1700 0 255 -exponent_1 0.75 \
    -scale_2 0 1300 0 255 -exponent_2 0.75 \
    -scale_3 0 900  0 255 -exponent_3 0.75 \
    -colorinterp red,green,blue \
    -co COMPRESS=JPEG -co QUALITY=90 \
    -co BLOCKSIZE=512 -co BIGTIFF=YES \
    -co OVERVIEW_RESAMPLING=AVERAGE \
    -co NUM_THREADS="$HALF" \
    --config GDAL_CACHEMAX "$GDAL_CACHE" \
    --config GDAL_NUM_THREADS "$HALF"

echo "[$(date '+%F %T')] Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"