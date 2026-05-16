from pathlib import Path
import requests
import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BOUNDARY_FILE = PROJECT_ROOT / "data/interim/franklin_county_mo_boundary_26915.gpkg"
BOUNDARY_LAYER = "franklin_county_boundary"

RAW_DIR = PROJECT_ROOT / "data/raw/hydrography"
INTERIM_DIR = PROJECT_ROOT / "data/interim"

RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CRS = "EPSG:26915"

LAYERS = {
    "waterbodies": {
        "url": "https://services7.arcgis.com/HM4C7tGF5KT34U6h/arcgis/rest/services/Franklin_County_Data/FeatureServer/24",
        "raw_output": RAW_DIR / "waterbodies_raw.geojson",
        "interim_output": INTERIM_DIR / "waterbodies_26915.gpkg",
        "layer_name": "waterbodies",
    },
    "streams": {
        "url": "https://services7.arcgis.com/HM4C7tGF5KT34U6h/arcgis/rest/services/Franklin_County_Data/FeatureServer/25",
        "raw_output": RAW_DIR / "streams_raw.geojson",
        "interim_output": INTERIM_DIR / "streams_26915.gpkg",
        "layer_name": "streams",
    },
}


def arcgis_post(url, params):
    response = requests.post(url, data=params, timeout=120)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(f"ArcGIS error from {url}: {data}")

    return data


def get_metadata(layer_url):
    return arcgis_post(layer_url, {"f": "json"})


def get_count(layer_url):
    query_url = f"{layer_url}/query"

    data = arcgis_post(
        query_url,
        {
            "where": "1=1",
            "returnCountOnly": "true",
            "f": "json",
        },
    )

    return data["count"]


def download_page(layer_url, offset, page_size):
    query_url = f"{layer_url}/query"

    data = arcgis_post(
        query_url,
        {
            "where": "1=1",
            "outFields": "OBJECT_ID,TYPE,NAME,MAPID",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": 4326,
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "orderByFields": "OBJECT_ID ASC",
        },
    )

    features = data.get("features", [])

    if not features:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")


def download_layer(layer_key, cfg, boundary=None):
    print("=" * 80)
    print(f"Downloading {layer_key}")

    metadata = get_metadata(cfg["url"])

    print(f"Layer name: {metadata.get('name')}")
    print(f"Geometry type: {metadata.get('geometryType')}")
    print(f"Max record count: {metadata.get('maxRecordCount')}")

    total = get_count(cfg["url"])
    print(f"Feature count: {total}")

    page_size = min(metadata.get("maxRecordCount", 2000), 2000)

    chunks = []

    for offset in range(0, total, page_size):
        print(f"Downloading records {offset + 1} to {min(offset + page_size, total)}")

        gdf = download_page(cfg["url"], offset, page_size)

        if not gdf.empty:
            chunks.append(gdf)

    if not chunks:
        print(f"No features downloaded for {layer_key}.")
        return

    gdf = gpd.GeoDataFrame(
        pd.concat(chunks, ignore_index=True),
        crs="EPSG:4326",
    )

    gdf.to_file(cfg["raw_output"], driver="GeoJSON")
    print(f"Saved raw: {cfg['raw_output']}")

    gdf_26915 = gdf.to_crs(TARGET_CRS)

    if boundary is not None:
        print("Clipping to Franklin County boundary...")
        gdf_26915 = gpd.clip(gdf_26915, boundary)

    gdf_26915.to_file(
        cfg["interim_output"],
        layer=cfg["layer_name"],
        driver="GPKG",
    )

    print(f"Saved interim: {cfg['interim_output']}")
    print(f"Output CRS: {gdf_26915.crs}")
    print(f"Output feature count: {len(gdf_26915)}")


def main():
    boundary = None

    if BOUNDARY_FILE.exists():
        print(f"Reading boundary: {BOUNDARY_FILE}")
        boundary = gpd.read_file(BOUNDARY_FILE, layer=BOUNDARY_LAYER).to_crs(TARGET_CRS)
    else:
        print("Boundary file not found. Layers will be downloaded and reprojected, but not clipped.")

    for layer_key, cfg in LAYERS.items():
        download_layer(layer_key, cfg, boundary)


if __name__ == "__main__":
    main()