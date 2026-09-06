#!/usr/bin/env bash
# Convert Sentinel-2 RGB to 8-bit COGs -- CORRECTED RECIPE.
#
# ONE RULE: the value 0 means "no data", and nothing else. Everything follows.
#
#   gdalwarp   ... -srcnodata 0 -dstnodata 0     (fill stays exactly 0)
#   gdal_translate ... -a_nodata 0               (declare it)
#              ... -co OVERVIEWS=IGNORE_EXISTING (build the pyramid fresh)
#              ... -co COMPRESS=ZSTD             (lossless; 0 stays 0)
#
# WHY EACH PIECE MATTERS -- all three earlier bugs came from breaking one of them:
#
# 1. -srcnodata 0 tells gdalwarp that 0 is nodata in the source .jp2 (the
#    Sentinel-2 L2A convention: valid reflectance starts at 1), so bilinear
#    resampling stops bleeding the source's black border into real pixels.
#
# 2. Lossless compression keeps 0 exactly 0. Under JPEG q90, DCT ringing lifted
#    the fill to 1-10 DN -- a 204x increase over lossless on identical data --
#    so nothing downstream could tell fill from dark ground. That was the
#    original black-edge bug.
#
# 3. -a_nodata 0 + OVERVIEWS=IGNORE_EXISTING fixes the zoomed-out images.
#    GDAL's AVERAGE resampling skips nodata but is NOT alpha-aware, so the
#    previous alpha-band build averaged fill into real data at every scene edge
#    and drew a thin dark diagonal line -- visible only when zoomed out, because
#    only the overviews were affected. IGNORE_EXISTING is required because a
#    warped VRT otherwise exposes the .jp2 pyramid and the resampling flag
#    silently does nothing.
#
# Measured against the previous alpha-band build, same scene:
#   dark edge pixels at /2,/4,/8,/16 : 2781,989,779,411  ->  0,0,0,0
#   overview accuracy vs truth       : 10.52 DN RMSE     ->  8.85 DN
#   fill pixels correctly transparent: 94588/94625       ->  93506/93506
#   valid pixels wrongly all-zero    : 37                ->  0
#   file size                        : 181 MB            ->  162 MB (3 bands)
#
# NO ALPHA BAND. 3 bands, not 4. Transparency comes from nodata, which viewers
# honour automatically -- a pixel is transparent when all three bands are 0.
# Do NOT also pass a nodata query parameter at render time; it is redundant.
#
# SAFETY: writes to a NEW output tree. The existing 40 GB of COGs under
# sentinel_rgb_cogs/ and the live pgstac collection are untouched, so this is
# fully reversible.
#
# Usage:
#   ./run_convert_masked_tmux.sh              # tmux session 'cog_convert'
#   ./convertjp2tocog_masked.sh               # foreground
#   ./convertjp2tocog_masked.sh --dry-run     # list work, convert nothing
#   PARALLEL=4 ./convertjp2tocog_masked.sh    # fewer concurrent scenes
set -uo pipefail

TILE_LIST="${TILE_LIST:-/home/ubuntu/work/saved_data/collections/germany_tiles.txt}"
RAW_BASE="${RAW_BASE:-/home/ubuntu/work/satellite_data/raw_sentinel_data}"
OUT_BASE="${OUT_BASE:-/home/ubuntu/work/saved_data/collections/sentinel_rgb_cogs_v2}"
YEARS_STR="${YEARS:-2024}"

# 48 cores on this box. PARALLEL scenes x THREADS each; leave headroom for the
# running postgres/titiler. One scene takes ~45 s at THREADS=8.
PARALLEL="${PARALLEL:-5}"
THREADS="${THREADS:-8}"
GDAL_CACHE="${GDAL_CACHE:-4096}"

# Compression. Measured on one 11277x11307 scene (all variants scored 0 edge
# defects, because the MASK is what fixes edges — not the codec):
#
#   codec                size     lossless        z11 tile latency
#   ZSTD  PREDICTOR=2   260.9 MB  yes, bit-exact   26.9 ms   <- default
#   DEFLATE PREDICTOR=2 274.5 MB  yes              29.9 ms
#   WEBP  QUALITY=100   149.7 MB  yes, bit-exact   68.2 ms
#   LZW   PREDICTOR=2   306.4 MB  yes              39.3 ms
#   JPEG  QUALITY=90     39.8 MB  no, PSNR 36.9dB  20.9 ms
#
# ZSTD is the default: bit-exact pixels for +6 ms per tile over JPEG, and 46 GB
# smaller than DEFLATE across the collection. Set COMPRESS=JPEG to keep the
# original 1x disk footprint instead (~40 GB vs ~262 GB) — the edges are fixed
# either way.
#
# NB `-co LOSSLESS=YES` is NOT a valid COG option; it is silently ignored and
# yields a LOSSY WebP. Lossless WebP is `-co COMPRESS=WEBP -co QUALITY=100`.
# `-co PHOTOMETRIC=RGB` is also unsupported by the COG driver.
COMPRESS="${COMPRESS:-ZSTD}"
case "$COMPRESS" in
  ZSTD)    COMPRESS_CO=(-co COMPRESS=ZSTD    -co PREDICTOR=2 -co LEVEL=9) ;;
  DEFLATE) COMPRESS_CO=(-co COMPRESS=DEFLATE -co PREDICTOR=2 -co LEVEL=6) ;;
  LZW)     COMPRESS_CO=(-co COMPRESS=LZW     -co PREDICTOR=2) ;;
  WEBP)    COMPRESS_CO=(-co COMPRESS=WEBP    -co QUALITY=100) ;;
  JPEG)    COMPRESS_CO=(-co COMPRESS=JPEG    -co QUALITY=90) ;;
  *) echo "ERROR: unknown COMPRESS=$COMPRESS (ZSTD|DEFLATE|LZW|WEBP|JPEG)"; exit 1 ;;
esac
export COMPRESS

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# ---------------------------------------------------------------- worker mode
# Called once per scene by xargs. Kept in this same file so there is one script.
if [[ "${1:-}" == "--worker" ]]; then
  SCENE_DIR="$2"; YEAR_OUTDIR="$3"
  SCENE_ID="$(basename "$SCENE_DIR")"
  OUTPUT="${YEAR_OUTDIR}/${SCENE_ID}_rgb_3857_cog.tif"
  PART="${OUTPUT}.part"

  [[ -f "$OUTPUT" ]] && { echo "[skip] $SCENE_ID (exists)"; exit 0; }

  RED="${SCENE_DIR}/${SCENE_ID}_B04_10m.jp2"
  GREEN="${SCENE_DIR}/${SCENE_ID}_B03_10m.jp2"
  BLUE="${SCENE_DIR}/${SCENE_ID}_B02_10m.jp2"
  for f in "$RED" "$GREEN" "$BLUE"; do
    [[ -f "$f" ]] || { echo "[MISS] $SCENE_ID missing $(basename "$f")"; exit 0; }
    # the raw archive contains 0-byte failed downloads
    [[ $(stat -c%s "$f") -ge 100000 ]] || { echo "[MISS] $SCENE_ID truncated $(basename "$f")"; exit 0; }
  done

  TMPDIR="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR"' EXIT
  S=$(date +%s)

  gdalbuildvrt -q -separate "$TMPDIR/rgb.vrt" "$RED" "$GREEN" "$BLUE" || {
    echo "[FAIL] $SCENE_ID gdalbuildvrt"; exit 0; }

  # -srcnodata 0 : source 0 is Sentinel-2 nodata, do not resample it into data
  # -dstalpha    : emit an alpha band -> becomes the COG's internal mask
  gdalwarp -q -of VRT -t_srs EPSG:3857 -r bilinear \
    -srcnodata 0 -dstnodata 0 \
    -multi -wo NUM_THREADS="$THREADS" \
    --config GDAL_CACHEMAX "$GDAL_CACHE" --config GDAL_NUM_THREADS "$THREADS" \
    "$TMPDIR/rgb.vrt" "$TMPDIR/rgb_3857.vrt" || {
      echo "[FAIL] $SCENE_ID gdalwarp"; exit 0; }

  # Write to .part first: a kill mid-write must not leave a truncated file that
  # the next run mistakes for finished work.
  gdal_translate -q "$TMPDIR/rgb_3857.vrt" "$PART" \
    -of COG -ot Byte \
    -scale_1 0 3000 0 255 \
    -scale_2 0 3000 0 255 \
    -scale_3 0 3000 0 255 \
    -colorinterp red,green,blue \
    -a_nodata 0 \
    "${COMPRESS_CO[@]}" \
    -co BLOCKSIZE=512 \
    -co BIGTIFF=YES \
    -co OVERVIEWS=IGNORE_EXISTING \
    -co OVERVIEW_RESAMPLING=AVERAGE \
    -co NUM_THREADS="$THREADS" \
    --config GDAL_CACHEMAX "$GDAL_CACHE" --config GDAL_NUM_THREADS "$THREADS" || {
      echo "[FAIL] $SCENE_ID gdal_translate"; rm -f "$PART"; exit 0; }

  # The whole point of the recipe is that 0 means nodata and nothing else.
  # Refuse to publish a file that lost that declaration.
  if ! gdalinfo "$PART" 2>/dev/null | grep -q "NoData Value=0"; then
    echo "[FAIL] $SCENE_ID has no NoData=0 declaration — discarded"; rm -f "$PART"; exit 0
  fi

  mv -f "$PART" "$OUTPUT"
  E=$(date +%s)
  echo "[ok]   $SCENE_ID  $((E-S))s  $(du -h "$OUTPUT" | cut -f1)"
  exit 0
fi

# ------------------------------------------------------------------ main mode
[[ -f "$TILE_LIST" ]] || { echo "ERROR: tile list not found: $TILE_LIST"; exit 1; }
command -v gdal_translate >/dev/null || { echo "ERROR: gdal not on PATH"; exit 1; }

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

echo "=== RGB COG re-conversion WITH internal mask"
echo "    gdal        : $(gdalinfo --version)"
echo "    tile list   : $TILE_LIST  ($(grep -c . "$TILE_LIST") tiles)"
echo "    raw base    : $RAW_BASE"
echo "    OUT base    : $OUT_BASE   <-- new tree; existing COGs untouched"
echo "    years       : $YEARS_STR"
echo "    compression : $COMPRESS  ${COMPRESS_CO[*]}"
echo "    parallelism : $PARALLEL scenes x $THREADS threads"
echo "    started     : $(date -Is)"
echo

# Build the work list first so we can report the real total up front.
WORKLIST="$(mktemp)"
trap 'rm -f "$WORKLIST"' EXIT
NTOTAL=0 NSKIP=0
for YEAR in $YEARS_STR; do
  while IFS= read -r TILE || [[ -n "$TILE" ]]; do
    [[ -z "$TILE" ]] && continue
    TILE_DIR="${RAW_BASE}/worldwide_${YEAR}_only_download/${TILE}"
    [[ -d "$TILE_DIR" ]] || { echo "SKIP: no raw dir for ${YEAR}/${TILE}"; continue; }
    YEAR_OUTDIR="${OUT_BASE}/${YEAR}/${TILE}"
    [[ $DRY_RUN -eq 1 ]] || mkdir -p "$YEAR_OUTDIR"
    for SCENE_DIR in "$TILE_DIR"/L2A_*; do
      [[ -d "$SCENE_DIR" ]] || continue
      SCENE_ID="$(basename "$SCENE_DIR")"
      if [[ -f "${YEAR_OUTDIR}/${SCENE_ID}_rgb_3857_cog.tif" ]]; then
        NSKIP=$((NSKIP+1)); continue
      fi
      printf '%s\t%s\n' "$SCENE_DIR" "$YEAR_OUTDIR" >> "$WORKLIST"
      NTOTAL=$((NTOTAL+1))
    done
  done < "$TILE_LIST"
done

echo "=== $NTOTAL scenes to convert, $NSKIP already done"
if [[ $NTOTAL -eq 0 ]]; then echo "nothing to do."; exit 0; fi
EST=$(( NTOTAL * 45 / PARALLEL / 60 ))
echo "=== rough estimate: ${EST} min at ~45 s/scene over $PARALLEL workers"
case "$COMPRESS" in
  ZSTD) PER=261 ;; DEFLATE) PER=275 ;; LZW) PER=306 ;; WEBP) PER=150 ;; JPEG) PER=40 ;;
esac
echo "=== disk needed: ~$(( NTOTAL * PER / 1024 )) GB at COMPRESS=$COMPRESS   (free: $(df -h "$(dirname "$OUT_BASE")" | tail -1 | awk '{print $4}'))"
echo

if [[ $DRY_RUN -eq 1 ]]; then
  echo "--dry-run: first 10 scenes that would be converted:"
  head -10 "$WORKLIST" | cut -f1 | xargs -rn1 basename
  exit 0
fi

# Each worker prints one line; xargs keeps $PARALLEL of them busy.
tr '\t' '\n' < "$WORKLIST" \
  | xargs -r -n2 -P "$PARALLEL" "$SELF" --worker

echo
NDONE=$(find "$OUT_BASE" -name '*_rgb_3857_cog.tif' | wc -l)
NPART=$(find "$OUT_BASE" -name '*.part' | wc -l)
echo "=== finished $(date -Is)"
echo "    outputs now on disk : $NDONE"
echo "    leftover .part files: $NPART  (should be 0)"
echo "    total size          : $(du -sh "$OUT_BASE" 2>/dev/null | cut -f1)"
echo
echo "Next: rebuild the STAC catalogue against the new tree, into a NEW"
echo "collection id, then point the viewer at it and drop '&nodata=0'."
