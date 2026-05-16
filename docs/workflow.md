# Workflow

This document describes how to run TerraScope as a reusable GIS suitability pipeline. The current implementation is configured for Franklin County, Missouri, but the same pipeline can be reused for another county or region by changing the input datasets, CRS, file names, and data-source-specific field mappings at the beginning of the workflow.

TerraScope is organized as an offline spatial-processing pipeline plus a lightweight web application:

```text
raw data
→ cleaned/interim layers
→ parcel-level metrics
→ finalized metrics
→ suitability scoring
→ web map export
→ FastAPI backend
→ MapLibre frontend
```

The pipeline is designed so the expensive GIS work happens before the app runs. The web app displays precomputed parcel scores and uses the backend for ranked search and parcel detail lookup.

---

## Reusing TerraScope for Another Region

To reuse TerraScope outside Franklin County, start by replacing the regional input datasets and updating the hardcoded paths/CRS values inside the pipeline scripts.

The main values that usually need to change are:

```text
study boundary source
parcel source URL or file path
target projected CRS
DEM/elevation file name
road layer path
hydrology layer URLs or paths
wetland layer path
floodplain layer path and flood-zone field names
town/service-center CSV
Sentinel-2 red/NIR raster file names
zoning field names
output file names if region-specific names are used
```

The Franklin County project uses:

```text
Analysis CRS: EPSG:26915
Web export CRS: EPSG:4326
```

For another region, use an appropriate local projected CRS for analysis, such as a local State Plane CRS or UTM zone. Keep web-facing outputs in EPSG:4326.

Most project scripts use this pattern:

```python
BASE_DIR = Path(__file__).resolve().parents[1]
```

or:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

That means scripts are intended to live inside:

```text
pipeline/
```

and should be run from the project root.

---

## Expected Project Structure

```text
terraScope/
├── backend/
│   ├── main.py
│   ├── scoring.py
│   ├── schemas.py
│   ├── requirements.txt
│   └── data/
│       └── scored_metrics.csv
│
├── data/
│   ├── raw/
│   │   ├── boundary/
│   │   ├── floodplain/
│   │   ├── hydrography/
│   │   ├── parcels/
│   │   └── towns/
│   │       └── service_centers.csv
│   ├── interim/
│   └── processed/
│
├── frontend/
│   ├── public/
│   │   └── data/
│   └── src/
│
├── outputs/
│   └── web_layers/
│
├── pipeline/
│   ├── download_mo_boundary.py
│   ├── download_franklin_parcels.py
│   ├── calculate_parcel_acreage.py
│   ├── prepare_zoning_from_parcels.py
│   ├── download_water_layers.py
│   ├── calculate_slope.py
│   ├── calculate_slope_class.py
│   ├── calculate_parcel_slope_metrics.py
│   ├── calculate_hydrology_metrics.py
│   ├── calculate_floodplain_metrics.py
│   ├── calculate_access_metrics.py
│   ├── calculate_ndvi_metrics.py
│   ├── finalize_metrics.py
│   ├── score_parcels.py
│   ├── export_pmtiles_source.py
│   └── export_web_layers.py
│
└── tools/
    └── build_pmtiles_wsl.sh
```

---

## Script Execution Order

The recommended full rebuild order is:

```bash
conda activate terrascope-gis

python pipeline/download_mo_boundary.py
python pipeline/download_franklin_parcels.py
python pipeline/calculate_parcel_acreage.py
python pipeline/prepare_zoning_from_parcels.py
python pipeline/download_water_layers.py

python pipeline/calculate_slope.py
python pipeline/calculate_slope_class.py
python pipeline/calculate_parcel_slope_metrics.py

python pipeline/calculate_hydrology_metrics.py
python pipeline/calculate_floodplain_metrics.py
python pipeline/calculate_access_metrics.py
python pipeline/calculate_ndvi_metrics.py

python pipeline/finalize_metrics.py
python pipeline/score_parcels.py
python pipeline/export_pmtiles_source.py
```

Then build PMTiles in WSL:

```bash
cd "/mnt/c/Users/axel2/Desktop/side projects/Gus/GIS_Projects/terraScope"
bash tools/build_pmtiles_wsl.sh
```

The `export_web_layers.py` script is retained as a lightweight GeoJSON export option. The production/current web map uses `export_pmtiles_source.py` plus `tools/build_pmtiles_wsl.sh`.

---

# Data Preparation Scripts

## 1. `download_mo_boundary.py`

Purpose:

```text
Downloads the county boundary used as the study area clipping boundary.
```

Current Franklin County behavior:

```text
Source: Census TIGER/Line county boundary ZIP
Filter: Missouri STATEFP = 29 and Franklin County COUNTYFP = 071
Output: data/interim/franklin_county_mo_boundary_26915.gpkg
Layer: franklin_county_boundary
CRS: EPSG:26915
```

Run:

```bash
python pipeline/download_mo_boundary.py
```

For another region, update:

```text
COUNTIES_URL if using a different boundary source
state/county filter values
output file name
target CRS
layer name if desired
```

Expected output:

```text
data/interim/franklin_county_mo_boundary_26915.gpkg
```

---

## 2. `download_franklin_parcels.py`

Purpose:

```text
Downloads parcel polygons from the Franklin County ArcGIS FeatureServer and creates the initial parcel analysis layer.
```

Current Franklin County behavior:

```text
Source: Franklin County Data FeatureServer layer 37
Raw output: data/raw/parcels/franklin_mo_parcels_raw.geojson
Interim output: data/interim/analysis_units_26915.gpkg
Output CRS: EPSG:26915
Public-safe retained fields: OBJECTID, PID, Zoning1, Zoning2
```

Run:

```bash
python pipeline/download_franklin_parcels.py
```

For another region, update:

```text
PARCEL_LAYER_URL
PARCEL_QUERY_URL
KEEP_FIELDS
RAW_OUTPUT
INTERIM_OUTPUT
target CRS conversion inside the script
field used for unit_id if needed
```

This script intentionally excludes owner, mailing address, situs address, and legal-description fields from the public-safe parcel output.

Expected outputs:

```text
data/raw/parcels/franklin_mo_parcels_raw.geojson
data/interim/analysis_units_26915.gpkg
```

---

## 3. `calculate_parcel_acreage.py`

Purpose:

```text
Validates parcel geometry, calculates acreage from geometry, and ensures each parcel has a stable unit_id.
```

Current inputs:

```text
data/interim/analysis_units_26915.gpkg
Layer: analysis_units
```

Current outputs:

```text
data/interim/analysis_units_with_acres_26915.gpkg
Layer: analysis_units
```

Run:

```bash
python pipeline/calculate_parcel_acreage.py
```

For another region, update:

```text
INPUT_FILE
INPUT_LAYER
OUTPUT_FILE
OUTPUT_LAYER
TARGET_CRS
unit_id fallback fields if the parcel source uses different ID fields
```

Expected fields added or checked:

```text
area_sq_m
parcel_acres
parcel_acres_round
unit_id
```

---

## 4. `prepare_zoning_from_parcels.py`

Purpose:

```text
Standardizes parcel zoning attributes into reusable zoning context fields.
```

Current inputs:

```text
data/interim/analysis_units_with_acres_26915.gpkg
Layer: analysis_units
```

Current outputs:

```text
data/interim/parcels_zoning_26915.gpkg
Layer: parcels_zoning
```

Run:

```bash
python pipeline/prepare_zoning_from_parcels.py
```

For another region, update:

```text
INPUT_FILE
INPUT_LAYER
OUTPUT_FILE
OUTPUT_LAYER
TARGET_CRS
zoning field names
zoning classification rules
zoning context text
```

Expected fields added:

```text
zoning_1_clean
zoning_2_clean
primary_zoning
zoning_category
zoning_context
has_zoning
```

This layer is useful as zoning context for QA and possible display/filtering. The current suitability scoring model does not treat zoning as a primary weighted score.

---

## 5. `download_water_layers.py`

Purpose:

```text
Downloads Franklin County waterbody and stream layers, clips them to the study boundary, and reprojects them to the project CRS.
```

Current inputs:

```text
data/interim/franklin_county_mo_boundary_26915.gpkg
Layer: franklin_county_boundary
```

Current outputs:

```text
data/raw/hydrography/waterbodies_raw.geojson
data/raw/hydrography/streams_raw.geojson
data/interim/waterbodies_26915.gpkg
data/interim/streams_26915.gpkg
```

Run:

```bash
python pipeline/download_water_layers.py
```

For another region, update:

```text
BOUNDARY_FILE
BOUNDARY_LAYER
TARGET_CRS
LAYERS dictionary
ArcGIS layer URLs
raw output names
interim output names
field list requested from the service
```

Expected reusable result:

```text
polygon waterbody layer
line stream layer
both clipped/reprojected to the analysis CRS
```

---

# Terrain Processing Scripts

## 6. `calculate_slope.py`

Purpose:

```text
Creates a percent-slope raster from the clipped DEM using gdaldem.
```

Current input:

```text
data/interim/franklin_county_dem_cut.tif
```

Current output:

```text
data/processed/slope.tif
```

Run:

```bash
python pipeline/calculate_slope.py
```

For another region, update:

```text
GDALDEM path if QGIS/GDAL is installed somewhere else
input_dem
output_slope
```

This script calls:

```text
gdaldem slope -p -compute_edges
```

The `-p` option creates percent slope.

---

## 7. `calculate_slope_class.py`

Purpose:

```text
Classifies the percent-slope raster into slope classes.
```

Current input:

```text
data/processed/slope.tif
```

Current output:

```text
data/processed/slope_class.tif
```

Run:

```bash
python pipeline/calculate_slope_class.py
```

Current class rules:

```text
1 = 0% to <5%
2 = 5% to <15%
3 = 15% to <25%
4 = 25%+
0 = NoData
```

For another region, update only the input/output paths if using different file names. The class thresholds can remain the same or be edited for a different suitability model.

---

## 8. `calculate_parcel_slope_metrics.py`

Purpose:

```text
Calculates parcel-level slope metrics from slope.tif.
```

Current input candidates:

```text
data/interim/clipped/parcels_clipped.geojson
data/interim/clipped/parcels_clipped.gpkg
data/interim/analysis_units_26915.geojson
data/interim/analysis_units_26915.gpkg
```

Current slope input:

```text
data/processed/slope.tif
```

Current outputs:

```text
data/processed/parcel_slope_metrics.geojson
data/processed/parcel_slope_metrics.gpkg
```

Run:

```bash
python pipeline/calculate_parcel_slope_metrics.py
```

For another region, update:

```text
PARCEL_CANDIDATES
SLOPE_PATH
OUTPUT_GEOJSON
OUTPUT_GPKG
```

Expected fields added:

```text
avg_slope_pct
max_slope_pct
median_slope_pct
pct_under_5_slope
pct_5_to_15_slope
pct_over_15_slope
slope_class
terrain_score
slope_constraint_pass
```

Current slope class logic:

```text
pct_under_5_slope >= 60  → Gentle
pct_5_to_15_slope >= 50  → Moderate
pct_over_15_slope >= 40  → Steep
otherwise                → Mixed
```

Current terrain score:

```text
terrain_score =
pct_under_5_slope * 1.0
+ pct_5_to_15_slope * 0.6
+ pct_over_15_slope * 0.1
```

---

# Vector Overlay and Proximity Scripts

## 9. `calculate_hydrology_metrics.py`

Purpose:

```text
Adds stream, polygon waterbody, and wetland metrics to the parcel slope metrics layer.
```

Current inputs:

```text
data/processed/parcel_slope_metrics.gpkg
data/interim/waterbodies_26915.gpkg
data/interim/wetlands_26915_cut.gpkg
data/interim/streams_26915.gpkg
```

Current outputs:

```text
data/processed/parcel_hydrology_metrics.gpkg
data/processed/parcel_hydrology_metrics.geojson
```

Run:

```bash
python pipeline/calculate_hydrology_metrics.py
```

For another region, update:

```text
PARCELS_PATH
WATERBODIES_PATH
WETLANDS_PATH
STREAMS_PATH
OUTPUT_GPKG
OUTPUT_GEOJSON
```

Expected fields added:

```text
watertype
stream_present
polygon_water_present
water_area_acres
water_pct
wetland_present
wetland_area_acres
wetland_pct
```

Interpretation:

```text
streams = line features, used for presence/type
waterbodies = polygon features, used for water area and water_pct
wetlands = polygon features, used for wetland area and wetland_pct
```

---

## 10. `calculate_floodplain_metrics.py`

Purpose:

```text
Adds high-risk floodplain overlap metrics to parcel hydrology metrics.
```

Current inputs:

```text
data/processed/parcel_hydrology_metrics.gpkg
data/raw/floodplain/S_FLD_HAZ_AR.shp
```

Current outputs:

```text
data/processed/parcel_floodplain_metrics.gpkg
data/processed/parcel_floodplain_metrics.geojson
data/processed/filtered_high_risk_floodplain.gpkg
```

Run:

```bash
python pipeline/calculate_floodplain_metrics.py
```

For another region, update:

```text
PARCELS_PATH
FLOODPLAIN_PATH
OUTPUT_GPKG
OUTPUT_GEOJSON
FILTERED_FLOODPLAIN_GPKG
HIGH_RISK_FLOOD_ZONES if the source uses different zone categories
field filtering logic if the floodplain dataset does not use FLD_ZONE or SFHA_TF
```

Expected fields added:

```text
floodplain_present
floodplain_area_acres
floodplain_pct
floodplain_constraint_pass
```

Current high-risk flood zones:

```text
A
AE
AH
AO
A99
AR
V
VE
```

This script also creates a filtered high-risk floodplain QA layer so the floodplain polygons used in scoring can be reviewed in QGIS.

---

## 11. `calculate_access_metrics.py`

Purpose:

```text
Adds nearest-road and nearest-town/service-center proximity metrics.
```

Current inputs:

```text
data/processed/parcel_floodplain_metrics.gpkg
data/interim/roads_cut.gpkg
data/raw/towns/service_centers.csv
```

Current outputs:

```text
data/processed/parcel_access_metrics.gpkg
data/processed/parcel_access_metrics.geojson
data/interim/town_centers_26915.gpkg
```

Run:

```bash
python pipeline/calculate_access_metrics.py
```

For another region, update:

```text
PARCELS_PATH
ROADS_PATH
TOWNS_CSV_PATH
OUTPUT_GPKG
OUTPUT_GEOJSON
TOWN_OUTPUT_PATH
```

The service-center CSV must contain:

```text
town_name
longitude
latitude
```

Optional field:

```text
role
```

Expected fields added:

```text
distance_to_nearest_road_m
road_access_class
nearest_town
nearest_town_role
distance_to_nearest_town_km
```

The script assumes the parcel CRS uses meters, so the nearest-road distance is interpreted as meters.

---

## 12. `calculate_ndvi_metrics.py`

Purpose:

```text
Calculates NDVI from red/NIR imagery and summarizes vegetation metrics by parcel.
```

Current inputs:

```text
data/processed/parcel_access_metrics.gpkg
data/interim/s2_b04_red_franklin_26916.tif
data/interim/s2_b08_nir_franklin_26916.tif
```

Current outputs:

```text
data/interim/temp_ndvi/red_aligned_to_parcels.tif
data/interim/temp_ndvi/nir_aligned_to_parcels.tif
data/processed/ndvi_current.tif
data/processed/parcel_ndvi_metrics.gpkg
data/processed/parcel_ndvi_metrics.geojson
```

Run:

```bash
python pipeline/calculate_ndvi_metrics.py
```

For another region, update:

```text
PARCELS_PATH
RED_PATH
NIR_PATH
TEMP_DIR
ALIGNED_RED_PATH
ALIGNED_NIR_PATH
NDVI_PATH
OUTPUT_GPKG
OUTPUT_GEOJSON
```

NDVI formula:

```text
NDVI = (NIR - Red) / (NIR + Red)
```

Expected fields added:

```text
avg_ndvi
median_ndvi
vegetation_score
vegetation_class
```

The script aligns the NIR raster to the red/reference raster and parcel CRS before calculating NDVI.

---

# Final Metrics and Scoring Scripts

## 13. `finalize_metrics.py`

Purpose:

```text
Creates a cleaned final metrics dataset from the parcel NDVI metrics layer.
```

Current input:

```text
data/processed/parcel_ndvi_metrics.gpkg
```

Current outputs:

```text
data/processed/final_metrics.gpkg
data/processed/final_metrics.csv
```

Run:

```bash
python pipeline/finalize_metrics.py
```

For another region, update:

```text
INPUT_GPKG
OUTPUT_GPKG
OUTPUT_CSV
TARGET_CRS
EXPECTED_FIELDS if the regional workflow adds/removes metrics
```

This script performs:

```text
CRS check/reprojection
geometry validation
null/empty geometry removal
unit_id verification
area_acres recalculation
percentage clipping
NDVI clipping
boolean field standardization
expected field reporting
GeoPackage export
CSV export
```

Expected final dataset role:

```text
one row per parcel
all metric fields cleaned and ready for scoring
```

---

## 14. `score_parcels.py`

Purpose:

```text
Creates component scores, profile scores, constraints, classes, and final scored outputs.
```

Current input:

```text
data/processed/final_metrics.gpkg
```

Current outputs:

```text
data/processed/scored_parcels.gpkg
data/processed/scored_metrics.csv
```

Run:

```bash
python pipeline/score_parcels.py
```

For another region, update:

```text
INPUT_GPKG
OUTPUT_GPKG
OUTPUT_CSV
TARGET_CRS
SCORING_PROFILES if regional use cases or weights differ
constraint thresholds if regional risk tolerances differ
```

Preset scoring profiles:

```text
agriculture_open_land
residential_homestead
event_venue_rural_tourism
conservation_habitat
```

Component scores created or used include:

```text
slope_score
access_score
low_access_score
proximity_score
risk_score
vegetation_score
acreage_score
water_habitat_score
wetland_habitat_score
terrain_variety_score
```

The scored CSV should be copied into:

```text
backend/data/scored_metrics.csv
```

The scored GeoPackage is used by the web export scripts.

---

# Web Export Scripts

## 15. `export_pmtiles_source.py`

Purpose:

```text
Creates the web source files used by the MapLibre/PMTiles frontend.
```

Current inputs:

```text
data/processed/scored_parcels.gpkg
data/raw/towns/service_centers.csv
```

Current outputs:

```text
outputs/web_layers/pmtiles_source/terrascope_parcels_source.geojson
outputs/web_layers/pmtiles_source/parcel_index.json
outputs/web_layers/city_reference_points.geojson
outputs/web_layers/profile_config.json
```

Run:

```bash
python pipeline/export_pmtiles_source.py
```

For another region, update:

```text
INPUT_GPKG
SERVICE_CENTERS_CSV
WEB_DIR
SRC_DIR
TILE_FIELDS if the frontend needs different fields
PROFILE_CONFIG if profiles or display names change
```

The PMTiles source includes:

```text
geometry
unit_id
preset score/class fields
component score fields used by custom suitability weights
```

The script converts parcel geometry to:

```text
EPSG:4326
```

for web export.

---

## 16. `tools/build_pmtiles_wsl.sh`

Purpose:

```text
Builds the PMTiles file from the exported parcel source GeoJSON.
```

Run in WSL from the project root:

```bash
cd "/mnt/c/Users/axel2/Desktop/side projects/Gus/GIS_Projects/terraScope"
bash tools/build_pmtiles_wsl.sh
```

Expected outputs copied to the frontend:

```text
frontend/public/data/terrascope_parcels.pmtiles
frontend/public/data/parcel_index.json
frontend/public/data/city_reference_points.geojson
frontend/public/data/profile_config.json
```

The frontend needs all four files.

---

## 17. `export_web_layers.py`

Purpose:

```text
Creates a lightweight GeoJSON-based web export.
```

Current inputs:

```text
data/processed/scored_parcels.gpkg
data/raw/towns/service_centers.csv
```

Current outputs:

```text
outputs/web_layers/scored_parcels_map.geojson
outputs/web_layers/city_reference_points.geojson
outputs/web_layers/parcel_lookup_min.json
outputs/web_layers/profile_config.json
```

Run:

```bash
python pipeline/export_web_layers.py
```

Use case:

```text
backup/simple GeoJSON export
debugging
small-region frontend testing
non-PMTiles prototype
```

The current production-style frontend uses the PMTiles workflow instead of this GeoJSON export because PMTiles performs better with many parcel polygons.

---

# Backend Operation

## Required Backend File

Before running the backend, make sure this file exists:

```text
backend/data/scored_metrics.csv
```

It should come from:

```text
data/processed/scored_metrics.csv
```

or from a rounded/optimized copy of the same scored metrics table.

## Run Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

For PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Main API functions:

```text
GET /health
GET /profiles
GET /parcels/{unit_id}
POST /rank
POST /score
POST /parcels/{unit_id}/score
```

The backend is responsible for:

```text
loading scored_metrics.csv
serving full parcel details
ranking parcels
handling selected profile scoring
handling custom user weights
returning score breakdowns
```

The backend does not run heavy GIS operations.

---

# Frontend Operation

## Required Frontend Files

The MapLibre frontend expects:

```text
frontend/public/data/terrascope_parcels.pmtiles
frontend/public/data/parcel_index.json
frontend/public/data/city_reference_points.geojson
frontend/public/data/profile_config.json
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Local frontend URL:

```text
http://localhost:5173
```

## Frontend Features

The frontend provides:

```text
profile selector
Variables & Weights custom profile panel
editable weights and sliders
custom map recoloring
base layer switching
analysis layer toggle
city/service-center layer toggle
ranked search
search-result zoom
parcel click popup
selected parcel highlight
sidebar metric breakdown
```

---

# Validation Checklist

After a complete rebuild, validate the pipeline before publishing.

## File Checks

Confirm these exist:

```text
data/interim/analysis_units_26915.gpkg
data/processed/slope.tif
data/processed/slope_class.tif
data/processed/parcel_slope_metrics.gpkg
data/processed/parcel_hydrology_metrics.gpkg
data/processed/parcel_floodplain_metrics.gpkg
data/processed/filtered_high_risk_floodplain.gpkg
data/processed/parcel_access_metrics.gpkg
data/processed/ndvi_current.tif
data/processed/parcel_ndvi_metrics.gpkg
data/processed/final_metrics.gpkg
data/processed/scored_parcels.gpkg
data/processed/scored_metrics.csv
frontend/public/data/terrascope_parcels.pmtiles
backend/data/scored_metrics.csv
```

## QGIS Checks

Review:

```text
parcel alignment against basemap
boundary clipping
slope raster
slope class raster
parcel slope metrics
hydrology presence fields
water and wetland overlap
filtered high-risk floodplain layer
floodplain_pct
road distance patterns
town/service-center locations
NDVI raster
vegetation score distribution
profile score distribution
top-ranked parcels by profile
```

## Web App Checks

Review:

```text
PMTiles layer loads
profile selector recolors map
custom weights recolor map
city/service-center layer toggles
analysis layer toggles
parcel popup appears
selected parcel highlight appears
ranked search returns results
ranked search zooms to selected parcel
backend details load in sidebar
```

---

# Production Build and Deployment

## Frontend Build

```bash
cd frontend
npm run build
npm run preview
```

For Vercel:

```text
Framework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

The deployed frontend must include:

```text
frontend/public/data/terrascope_parcels.pmtiles
frontend/public/data/parcel_index.json
frontend/public/data/city_reference_points.geojson
frontend/public/data/profile_config.json
```

## Backend URL Configuration

The frontend reads the backend URL from:

```text
VITE_API_BASE_URL
```

Local fallback:

```text
http://127.0.0.1:8000
```

Production value:

```text
https://your-backend-url
```

For full public functionality, deploy the FastAPI backend separately and set `VITE_API_BASE_URL` in the frontend hosting environment.

---

# Reusable Pipeline Summary

To rerun TerraScope for the current region:

```bash
conda activate terrascope-gis

python pipeline/download_mo_boundary.py
python pipeline/download_franklin_parcels.py
python pipeline/calculate_parcel_acreage.py
python pipeline/prepare_zoning_from_parcels.py
python pipeline/download_water_layers.py
python pipeline/calculate_slope.py
python pipeline/calculate_slope_class.py
python pipeline/calculate_parcel_slope_metrics.py
python pipeline/calculate_hydrology_metrics.py
python pipeline/calculate_floodplain_metrics.py
python pipeline/calculate_access_metrics.py
python pipeline/calculate_ndvi_metrics.py
python pipeline/finalize_metrics.py
python pipeline/score_parcels.py
python pipeline/export_pmtiles_source.py
```

Then in WSL:

```bash
bash tools/build_pmtiles_wsl.sh
```

Then update backend data:

```text
copy data/processed/scored_metrics.csv
to   backend/data/scored_metrics.csv
```

Then run:

```bash
cd backend
python -m uvicorn main:app --reload
```

and:

```bash
cd frontend
npm run dev
```

To reuse the pipeline for a new region, change the input data sources, paths, CRS, field names, and region-specific output names in the top configuration section of the scripts, then run the same sequence.
