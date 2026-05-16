from pathlib import Path
import math
import requests
import pandas as pd
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PARCEL_LAYER_URL = (
    "https://services7.arcgis.com/HM4C7tGF5KT34U6h/ArcGIS/rest/services/"
    "Franklin_County_Data/FeatureServer/37"
)

PARCEL_QUERY_URL = f"{PARCEL_LAYER_URL}/query"

RAW_OUTPUT = PROJECT_ROOT / "data/raw/parcels/franklin_mo_parcels_raw.geojson"
INTERIM_OUTPUT = PROJECT_ROOT / "data/interim/analysis_units_26915.gpkg"

RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
INTERIM_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Public-safe fields only.
# Owner, mailing address, situs address, and legal description are intentionally excluded.
KEEP_FIELDS = [
    "OBJECTID",
    "PID",
    "Zoning1",
    "Zoning2",
]


def get_layer_metadata():
    params = {"f": "json"}
    response = requests.get(PARCEL_LAYER_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def get_valid_fields(metadata):
    available_fields = {field["name"] for field in metadata["fields"]}
    valid_fields = [field for field in KEEP_FIELDS if field in available_fields]

    missing_fields = [field for field in KEEP_FIELDS if field not in available_fields]

    if missing_fields:
        print(f"Skipping missing fields: {missing_fields}")

    return valid_fields


def get_count():
    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json",
    }

    response = requests.get(PARCEL_QUERY_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"Count request failed: {data}")

    return data["count"]


def download_page(offset, page_size, out_fields):
    params = {
        "where": "1=1",
        "outFields": ",".join(out_fields),
        "returnGeometry": "true",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
        "orderByFields": "OBJECTID ASC",
        "outSR": 4326,
    }

    response = requests.get(PARCEL_QUERY_URL, params=params, timeout=120)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"Query failed at offset {offset}: {data}")

    if "features" not in data:
        raise RuntimeError(f"No features returned at offset {offset}: {data}")

    return gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")


def main():
    metadata = get_layer_metadata()
    out_fields = get_valid_fields(metadata)

    print(f"Using fields: {out_fields}")

    total = get_count()
    print(f"Total parcel records: {total}")

    page_size = 2000
    pages = math.ceil(total / page_size)

    chunks = []

    for page in range(pages):
        offset = page * page_size
        print(f"Downloading records {offset + 1} to {min(offset + page_size, total)}")

        gdf = download_page(offset, page_size, out_fields)

        if not gdf.empty:
            chunks.append(gdf)

    if not chunks:
        raise RuntimeError("No parcel features were downloaded.")

    parcels = gpd.GeoDataFrame(
        pd.concat(chunks, ignore_index=True),
        crs="EPSG:4326",
    )

    # Create stable analysis ID
    if "pid" in parcels.columns:
        parcels["unit_id"] = parcels["pid"]
    elif "pid_alt" in parcels.columns:
        parcels["unit_id"] = parcels["pid_alt"]
    else:
        parcels["unit_id"] = parcels["OBJECTID"].astype(str)

    parcels["unit_id"] = parcels["unit_id"].fillna(parcels["OBJECTID"].astype(str))

    # Save raw public-safe GeoJSON
    parcels.to_file(RAW_OUTPUT, driver="GeoJSON")

    # Reproject to analysis CRS
    parcels_26915 = parcels.to_crs("EPSG:26915")

    parcels_26915.to_file(
        INTERIM_OUTPUT,
        layer="analysis_units",
        driver="GPKG",
    )

    print("Done.")
    print(f"Raw public-safe parcels saved to: {RAW_OUTPUT}")
    print(f"Analysis parcels saved to: {INTERIM_OUTPUT}")
    print(f"CRS: {parcels_26915.crs}")
    print(f"Parcel count: {len(parcels_26915)}")


if __name__ == "__main__":
    main()