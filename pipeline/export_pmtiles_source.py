from pathlib import Path
import geopandas as gpd
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_GPKG = BASE_DIR / "data" / "processed" / "scored_parcels.gpkg"
SERVICE_CENTERS_CSV = BASE_DIR / "data" / "raw" / "towns" / "service_centers.csv"

WEB_DIR = BASE_DIR / "outputs" / "web_layers"
SRC_DIR = WEB_DIR / "pmtiles_source"

SOURCE_GEOJSON = SRC_DIR / "terrascope_parcels_source.geojson"
PARCEL_INDEX_JSON = SRC_DIR / "parcel_index.json"
CITY_GEOJSON = WEB_DIR / "city_reference_points.geojson"
PROFILE_CONFIG_JSON = WEB_DIR / "profile_config.json"

WEB_CRS = "EPSG:4326"

# Keep profile scores/classes for preset styling, plus component scores for
# session-only custom suitability profiles in the frontend.
TILE_FIELDS = [
    "unit_id",

    "overall_suitability_score",
    "suitability_class",

    "agriculture_open_land_score",
    "agriculture_open_land_class",

    "residential_homestead_score",
    "residential_homestead_class",

    "event_venue_rural_tourism_score",
    "event_venue_rural_tourism_class",

    "conservation_habitat_score",
    "conservation_habitat_class",

    # Component scores used by the editable custom profile UI.
    "slope_score",
    "access_score",
    "low_access_score",
    "proximity_score",
    "risk_score",
    "vegetation_score",
    "acreage_score",
    "water_habitat_score",
    "wetland_habitat_score",
    "terrain_variety_score",
]

PROFILE_CONFIG = {
    "defaultProfile": "residential_homestead",
    "profiles": [
        {
            "key": "residential_homestead",
            "label": "Residential / Homestead",
            "scoreField": "residential_homestead_score",
            "classField": "residential_homestead_class",
            "weights": {
                "slope_score": 0.30,
                "access_score": 0.20,
                "proximity_score": 0.15,
                "risk_score": 0.25,
                "vegetation_score": 0.05,
                "acreage_score": 0.05,
            },
        },
        {
            "key": "agriculture_open_land",
            "label": "Agriculture / Open Land",
            "scoreField": "agriculture_open_land_score",
            "classField": "agriculture_open_land_class",
            "weights": {
                "slope_score": 0.25,
                "vegetation_score": 0.25,
                "acreage_score": 0.20,
                "access_score": 0.15,
                "risk_score": 0.15,
            },
        },
        {
            "key": "event_venue_rural_tourism",
            "label": "Event Venue / Rural Tourism",
            "scoreField": "event_venue_rural_tourism_score",
            "classField": "event_venue_rural_tourism_class",
            "weights": {
                "access_score": 0.25,
                "proximity_score": 0.20,
                "terrain_variety_score": 0.20,
                "risk_score": 0.20,
                "acreage_score": 0.10,
                "vegetation_score": 0.05,
            },
        },
        {
            "key": "conservation_habitat",
            "label": "Conservation / Habitat",
            "scoreField": "conservation_habitat_score",
            "classField": "conservation_habitat_class",
            "weights": {
                "vegetation_score": 0.25,
                "water_habitat_score": 0.25,
                "wetland_habitat_score": 0.15,
                "acreage_score": 0.15,
                "low_access_score": 0.10,
                "terrain_variety_score": 0.10,
            },
        },
    ],
}

def make_json_safe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col == "geometry":
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
        elif pd.api.types.is_bool_dtype(df[col]):
            df[col] = df[col].fillna(False).astype(bool)
        else:
            df[col] = df[col].fillna("").astype(str)
    return df

def export_parcels():
    if not INPUT_GPKG.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_GPKG}")

    SRC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {INPUT_GPKG}")
    gdf = gpd.read_file(INPUT_GPKG)

    if gdf.empty:
        raise ValueError("scored_parcels.gpkg is empty.")
    if gdf.crs is None:
        raise ValueError("scored_parcels.gpkg has no CRS.")
    if "unit_id" not in gdf.columns:
        raise ValueError("Missing unit_id.")

    fields = [f for f in TILE_FIELDS if f in gdf.columns]
    missing = [f for f in TILE_FIELDS if f not in gdf.columns]
    if missing:
        print("Missing tile fields:")
        for f in missing:
            print(f"  - {f}")

    tile_gdf = gdf[fields + ["geometry"]].copy().to_crs(WEB_CRS)

    tile_gdf["geometry"] = tile_gdf.geometry.simplify(
        tolerance=0.00003,
        preserve_topology=True,
    )
    tile_gdf = make_json_safe(tile_gdf)

    if SOURCE_GEOJSON.exists():
        SOURCE_GEOJSON.unlink()

    print(f"Writing {SOURCE_GEOJSON}")
    tile_gdf.to_file(SOURCE_GEOJSON, driver="GeoJSON")
    print(f"Source GeoJSON size: {SOURCE_GEOJSON.stat().st_size / (1024*1024):.2f} MB")

    print(f"Writing {PARCEL_INDEX_JSON}")
    bounds = tile_gdf.bounds
    index_df = pd.DataFrame({
        "unit_id": tile_gdf["unit_id"].astype(str),
        "west": bounds["minx"].round(6),
        "south": bounds["miny"].round(6),
        "east": bounds["maxx"].round(6),
        "north": bounds["maxy"].round(6),
    })
    index_df.to_json(PARCEL_INDEX_JSON, orient="records", indent=2)
    print(f"Parcel index size: {PARCEL_INDEX_JSON.stat().st_size / (1024*1024):.2f} MB")

def export_cities():
    if not SERVICE_CENTERS_CSV.exists():
        print(f"Service centers CSV not found, skipping: {SERVICE_CENTERS_CSV}")
        return

    towns = pd.read_csv(SERVICE_CENTERS_CSV)
    required = ["town_name", "role", "longitude", "latitude"]
    missing = [c for c in required if c not in towns.columns]
    if missing:
        raise ValueError(f"service_centers.csv missing columns: {missing}")

    towns["longitude"] = pd.to_numeric(towns["longitude"], errors="coerce")
    towns["latitude"] = pd.to_numeric(towns["latitude"], errors="coerce")
    towns = towns.dropna(subset=["longitude", "latitude"]).copy()

    cities = gpd.GeoDataFrame(
        towns[required],
        geometry=gpd.points_from_xy(towns["longitude"], towns["latitude"]),
        crs=WEB_CRS,
    )
    cities = make_json_safe(cities)

    if CITY_GEOJSON.exists():
        CITY_GEOJSON.unlink()

    print(f"Writing {CITY_GEOJSON}")
    cities.to_file(CITY_GEOJSON, driver="GeoJSON")

def export_profiles():
    print(f"Writing {PROFILE_CONFIG_JSON}")
    pd.Series(PROFILE_CONFIG).to_json(PROFILE_CONFIG_JSON, indent=2)

def main():
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    export_parcels()
    export_cities()
    export_profiles()
    print("Finished pmtiles Export")

if __name__ == "__main__":
    main()
