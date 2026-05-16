#!/usr/bin/env bash
set -euo pipefail

SOURCE="outputs/web_layers/pmtiles_source/terrascope_parcels_source.geojson"
OUT_DIR="frontend/public/data"
OUT="$OUT_DIR/terrascope_parcels.pmtiles"

if ! command -v tippecanoe >/dev/null 2>&1; then
  echo "ERROR: tippecanoe is not installed."
  echo ""
  echo "Install inside WSL/Ubuntu:"
  echo "  sudo apt update"
  echo "  sudo apt install -y build-essential libsqlite3-dev zlib1g-dev git"
  echo "  cd ~"
  echo "  git clone https://github.com/felt/tippecanoe.git"
  echo "  cd tippecanoe"
  echo "  make -j"
  echo "  sudo make install"
  exit 1
fi

if [ ! -f "$SOURCE" ]; then
  echo "ERROR: missing $SOURCE"
  echo "Run first: python pipeline/export_pmtiles_source.py"
  exit 1
fi

mkdir -p "$OUT_DIR"

tippecanoe \
  -o "$OUT" \
  -L "parcels:$SOURCE" \
  -zg \
  --minimum-zoom=7 \
  --maximum-zoom=15 \
  --drop-densest-as-needed \
  --extend-zooms-if-still-dropping \
  --force

cp outputs/web_layers/pmtiles_source/parcel_index.json "$OUT_DIR/parcel_index.json"
cp outputs/web_layers/city_reference_points.geojson "$OUT_DIR/city_reference_points.geojson"
cp outputs/web_layers/profile_config.json "$OUT_DIR/profile_config.json"

echo ""
echo "Created:"
ls -lh "$OUT"
echo "$OUT_DIR/parcel_index.json"
echo "$OUT_DIR/city_reference_points.geojson"
echo "$OUT_DIR/profile_config.json"
