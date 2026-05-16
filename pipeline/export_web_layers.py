from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_GPKG = BASE_DIR / "data" / "processed" / "scored_parcels.gpkg"
SERVICE_CENTERS_CSV = BASE_DIR / "data" / "raw" / "towns" / "service_centers.csv"

OUTPUT_DIR = BASE_DIR / "outputs" / "web_layers"
OUTPUT_MAP_GEOJSON = OUTPUT_DIR / "scored_parcels_map.geojson"
OUTPUT_CITIES_GEOJSON = OUTPUT_DIR / "city_reference_points.geojson"
OUTPUT_LOOKUP_JSON = OUTPUT_DIR / "parcel_lookup_min.json"
OUTPUT_PROFILE_CONFIG = OUTPUT_DIR / "profile_config.json"

WEB_CRS = "EPSG:4326"


MAP_FIELDS = [
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
]


LOOKUP_FIELDS = [
    "unit_id",
    "overall_suitability_score",
    "suitability_class",
    "area_acres",
    "nearest_town",
    "residential_homestead_score",
    "agriculture_open_land_score",
    "event_venue_rural_tourism_score",
    "conservation_habitat_score",
]


PROFILE_CONFIG = {
    "profiles": [
        {
            "key": "residential_homestead",
            "label": "Residential / Homestead",
            "scoreField": "residential_homestead_score",
            "classField": "residential_homestead_class",
        },
        {
            "key": "agriculture_open_land",
            "label": "Agriculture / Open Land",
            "scoreField": "agriculture_open_land_score",
            "classField": "agriculture_open_land_class",
        },
        {
            "key": "event_venue_rural_tourism",
            "label": "Event Venue / Rural Tourism",
            "scoreField": "event_venue_rural_tourism_score",
            "classField": "event_venue_rural_tourism_class",
        },
        {
            "key": "conservation_habitat",
            "label": "Conservation / Habitat",
            "scoreField": "conservation_habitat_score",
            "classField": "conservation_habitat_class",
        },
    ],
    "defaultProfile": "residential_homestead",
}


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def simplify_geometries(gdf: gpd.GeoDataFrame, tolerance_degrees: float) -> gpd.GeoDataFrame:
    """
    Simplifies geometry after converting to EPSG:4326.

    Recommended values:
        0.00005 = more detail, larger file
        0.00010 = balanced
        0.00020 = smaller/faster, more generalized
    """
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(
        tolerance=tolerance_degrees,
        preserve_topology=True,
    )
    return gdf


def make_json_safe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if col == "geometry":
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
        elif pd.api.types.is_bool_dtype(df[col]):
            df[col] = df[col].fillna(False).astype(bool)
        else:
            df[col] = df[col].fillna("").astype(str)

    return df


def export_parcel_map_layer() -> None:
    print_header("Creating lightweight parcel analysis layer")

    if not INPUT_GPKG.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_GPKG}")

    print(f"Reading:\n{INPUT_GPKG}")
    gdf = gpd.read_file(INPUT_GPKG)

    if gdf.empty:
        raise ValueError("Input scored parcel layer is empty.")

    if gdf.crs is None:
        raise ValueError("Input scored parcel layer has no CRS.")

    if "unit_id" not in gdf.columns:
        raise ValueError("Missing unit_id. The frontend needs unit_id for backend lookup.")

    print(f"Rows: {len(gdf):,}")
    print(f"Input CRS: {gdf.crs}")

    available_map_fields = [field for field in MAP_FIELDS if field in gdf.columns]
    missing_map_fields = [field for field in MAP_FIELDS if field not in gdf.columns]

    if missing_map_fields:
        print("Warning: missing map fields:")
        for field in missing_map_fields:
            print(f"  - {field}")

    map_gdf = gdf[available_map_fields + ["geometry"]].copy()

    print(f"Converting parcel layer to {WEB_CRS}...")
    map_gdf = map_gdf.to_crs(WEB_CRS)

    print("Simplifying parcel geometries...")
    map_gdf = simplify_geometries(map_gdf, tolerance_degrees=0.00010)

    map_gdf = make_json_safe(map_gdf)

    if OUTPUT_MAP_GEOJSON.exists():
        OUTPUT_MAP_GEOJSON.unlink()

    print(f"Writing:\n{OUTPUT_MAP_GEOJSON}")
    map_gdf.to_file(OUTPUT_MAP_GEOJSON, driver="GeoJSON")

    map_size_mb = OUTPUT_MAP_GEOJSON.stat().st_size / (1024 * 1024)
    print(f"Parcel map GeoJSON size: {map_size_mb:.2f} MB")

    if map_size_mb > 25:
        print("")
        print("WARNING: Parcel map GeoJSON is still large.")
        print("Try increasing simplify tolerance from 0.00010 to 0.00020.")
        print("Long-term fix: PMTiles/vector tiles.")


def export_city_reference_layer() -> None:
    print_header("Creating city/service-center reference layer")

    if not SERVICE_CENTERS_CSV.exists():
        print(f"Warning: service centers CSV not found: {SERVICE_CENTERS_CSV}")
        print("Skipping city reference layer export.")
        return

    towns = pd.read_csv(SERVICE_CENTERS_CSV)

    required = ["town_name", "role", "longitude", "latitude"]
    missing = [field for field in required if field not in towns.columns]

    if missing:
        raise ValueError(
            "service_centers.csv is missing required columns:\n"
            + "\n".join(f"  - {field}" for field in missing)
        )

    towns["longitude"] = pd.to_numeric(towns["longitude"], errors="coerce")
    towns["latitude"] = pd.to_numeric(towns["latitude"], errors="coerce")
    towns = towns.dropna(subset=["longitude", "latitude"]).copy()

    if towns.empty:
        raise ValueError("No valid town/service-center coordinates found.")

    city_gdf = gpd.GeoDataFrame(
        towns[["town_name", "role", "longitude", "latitude"]].copy(),
        geometry=gpd.points_from_xy(towns["longitude"], towns["latitude"]),
        crs=WEB_CRS,
    )

    city_gdf = make_json_safe(city_gdf)

    if OUTPUT_CITIES_GEOJSON.exists():
        OUTPUT_CITIES_GEOJSON.unlink()

    print(f"Writing:\n{OUTPUT_CITIES_GEOJSON}")
    city_gdf.to_file(OUTPUT_CITIES_GEOJSON, driver="GeoJSON")

    print(f"City/service-center points: {len(city_gdf):,}")
    print(f"City reference GeoJSON size: {OUTPUT_CITIES_GEOJSON.stat().st_size / 1024:.2f} KB")


def export_lookup_and_config() -> None:
    print_header("Creating lookup JSON and profile config")

    gdf = gpd.read_file(INPUT_GPKG)

    available_lookup_fields = [field for field in LOOKUP_FIELDS if field in gdf.columns]
    lookup_df = pd.DataFrame(gdf[available_lookup_fields]).copy()
    lookup_df = make_json_safe(lookup_df)

    print(f"Writing:\n{OUTPUT_LOOKUP_JSON}")
    lookup_df.to_json(OUTPUT_LOOKUP_JSON, orient="records", indent=2)

    print(f"Lookup JSON size: {OUTPUT_LOOKUP_JSON.stat().st_size / (1024 * 1024):.2f} MB")

    print(f"Writing:\n{OUTPUT_PROFILE_CONFIG}")
    pd.Series(PROFILE_CONFIG).to_json(OUTPUT_PROFILE_CONFIG, indent=2)


def main() -> None:
    print_header("TerraScope Fast Web Export + City Reference Layer")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    export_parcel_map_layer()
    export_city_reference_layer()
    export_lookup_and_config()

    print_header("Finished")
    print("Created:")
    print(f"  {OUTPUT_MAP_GEOJSON}")
    print(f"  {OUTPUT_CITIES_GEOJSON}")
    print(f"  {OUTPUT_LOOKUP_JSON}")
    print(f"  {OUTPUT_PROFILE_CONFIG}")
    print("")


if __name__ == "__main__":
    main()
