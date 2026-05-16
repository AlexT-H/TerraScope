from pathlib import Path
import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data/raw/boundary"
INTERIM_DIR = PROJECT_ROOT / "data/interim"

RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

COUNTIES_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip"

raw_output = RAW_DIR / "tl_2025_us_county.zip"
boundary_output = INTERIM_DIR / "franklin_county_mo_boundary_26915.gpkg"

print("Reading Census county boundaries...")
counties = gpd.read_file(COUNTIES_URL)

# Missouri = STATEFP 29
# Franklin County, Missouri = COUNTYFP 071
franklin_mo = counties[
    (counties["STATEFP"] == "29") &
    (counties["COUNTYFP"] == "071")
].copy()

if franklin_mo.empty:
    raise RuntimeError("Franklin County, Missouri was not found.")

franklin_mo = franklin_mo.to_crs("EPSG:26915")

franklin_mo.to_file(
    boundary_output,
    layer="franklin_county_boundary",
    driver="GPKG"
)

print(f"Saved: {boundary_output}")
print(f"CRS: {franklin_mo.crs}")
print(f"Bounds: {franklin_mo.total_bounds}")