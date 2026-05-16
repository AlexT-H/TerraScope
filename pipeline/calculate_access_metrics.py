from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point


# ============================================================
#
# Inputs:
# - data/processed/parcel_floodplain_metrics.gpkg
# - data/interim/roads_cut.gpkg
# - data/raw/towns/service_centers.csv
#
# Adds:
# - distance_to_nearest_road_m
# - road_access_class
# - nearest_town
# - nearest_town_role
# - distance_to_nearest_town_km
#
# Outputs:
# - data/processed/parcel_access_metrics.gpkg
# - data/processed/parcel_access_metrics.geojson
# - data/interim/town_centers_26915.gpkg
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------
# Input paths
# ------------------------------------------------------------

PARCELS_PATH = BASE_DIR / "data" / "processed" / "parcel_floodplain_metrics.gpkg"
ROADS_PATH = BASE_DIR / "data" / "interim" / "roads_cut.gpkg"
TOWNS_CSV_PATH = BASE_DIR / "data" / "raw" / "towns" / "service_centers.csv"

# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_GPKG = OUTPUT_DIR / "parcel_access_metrics.gpkg"
OUTPUT_GEOJSON = OUTPUT_DIR / "parcel_access_metrics.geojson"

TOWN_OUTPUT_PATH = BASE_DIR / "data" / "interim" / "town_centers_26915.gpkg"


def check_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def clean_geometries(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    print(f"Cleaning geometries for {label}...")

    original_count = len(gdf)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        gdf["geometry"] = gdf.buffer(0)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    removed = original_count - len(gdf)
    if removed > 0:
        print(f"Removed {removed} invalid/empty geometries from {label}.")

    if gdf.empty:
        raise ValueError(f"{label} has no usable geometries after cleaning.")

    return gdf


def ensure_same_crs(
    gdf: gpd.GeoDataFrame,
    target_crs,
    label: str,
) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError(f"{label} has no CRS. Assign/reproject it before running.")

    if gdf.crs != target_crs:
        print(f"Reprojecting {label} from {gdf.crs} to {target_crs}...")
        gdf = gdf.to_crs(target_crs)
    else:
        print(f"{label} CRS already matches parcels.")

    return gdf


def keep_line_features(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    allowed_types = ["LineString", "MultiLineString"]

    original_count = len(gdf)
    gdf = gdf[gdf.geometry.geom_type.isin(allowed_types)].copy()

    removed = original_count - len(gdf)
    if removed > 0:
        print(f"{label}: removed {removed} non-line features.")

    if gdf.empty:
        raise ValueError(f"{label} has no line features after filtering.")

    return gdf


def load_town_centers(csv_path: Path, target_crs) -> gpd.GeoDataFrame:
    """
    Loads town/service center points from CSV.

    Required columns:
    - town_name
    - longitude
    - latitude

    Optional column:
    - role
    """
    print(f"Loading town/service centers from: {csv_path}")

    towns_df = pd.read_csv(csv_path)

    required_columns = ["town_name", "longitude", "latitude"]

    missing = [col for col in required_columns if col not in towns_df.columns]
    if missing:
        raise ValueError(
            f"Town CSV is missing required columns: {missing}. "
            f"Expected columns: town_name, longitude, latitude"
        )

    if "role" not in towns_df.columns:
        towns_df["role"] = "service center"

    towns_df = towns_df.dropna(subset=["town_name", "longitude", "latitude"]).copy()

    if towns_df.empty:
        raise ValueError("Town CSV has no usable rows after removing missing coordinates.")

    towns = gpd.GeoDataFrame(
        towns_df,
        geometry=[
            Point(xy)
            for xy in zip(towns_df["longitude"], towns_df["latitude"])
        ],
        crs="EPSG:4326",
    )

    towns = towns.to_crs(target_crs)

    return towns


def calculate_nearest_road_distance(
    parcels: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Calculates nearest distance from each parcel to the nearest road.

    Since EPSG:26915 uses meters, the output distance is in meters.
    """
    print("Calculating distance_to_nearest_road_m...")

    nearest = gpd.sjoin_nearest(
        parcels[["geometry"]].copy(),
        roads[["geometry"]].copy(),
        how="left",
        distance_col="distance_to_nearest_road_m",
    )

    distances = nearest.groupby(nearest.index)["distance_to_nearest_road_m"].min()

    parcels["distance_to_nearest_road_m"] = parcels.index.map(distances)

    parcels["distance_to_nearest_road_m"] = (
        parcels["distance_to_nearest_road_m"]
        .replace([np.inf, -np.inf], np.nan)
        .round(2)
    )

    return parcels


def classify_road_access(distance_m):
    if pd.isna(distance_m):
        return "Unknown"

    if distance_m <= 100:
        return "Excellent"
    elif distance_m <= 500:
        return "Good"
    elif distance_m <= 1000:
        return "Moderate"
    else:
        return "Poor"


def calculate_nearest_town(
    parcels: gpd.GeoDataFrame,
    towns: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Calculates nearest town/service center and distance in kilometers.
    """
    print("Calculating nearest_town and distance_to_nearest_town_km...")

    nearest = gpd.sjoin_nearest(
        parcels[["geometry"]].copy(),
        towns[["town_name", "role", "geometry"]].copy(),
        how="left",
        distance_col="_distance_to_town_m",
    )

    nearest_sorted = nearest.sort_values("_distance_to_town_m")
    nearest_deduped = nearest_sorted[~nearest_sorted.index.duplicated(keep="first")]

    parcels["nearest_town"] = parcels.index.map(nearest_deduped["town_name"])
    parcels["nearest_town_role"] = parcels.index.map(nearest_deduped["role"])

    parcels["distance_to_nearest_town_km"] = (
        parcels.index.map(nearest_deduped["_distance_to_town_m"]) / 1000
    )

    parcels["distance_to_nearest_town_km"] = (
        parcels["distance_to_nearest_town_km"]
        .replace([np.inf, -np.inf], np.nan)
        .round(2)
    )

    return parcels


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOWN_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Starting TerraScope access metrics...")

    check_file_exists(PARCELS_PATH, "parcel floodplain metrics layer")
    check_file_exists(ROADS_PATH, "roads layer")
    check_file_exists(TOWNS_CSV_PATH, "town/service centers CSV")

    print(f"Parcels: {PARCELS_PATH}")
    print(f"Roads: {ROADS_PATH}")
    print(f"Towns CSV: {TOWNS_CSV_PATH}")

    # ------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------
    print("Loading parcels...")
    parcels = gpd.read_file(PARCELS_PATH)

    print("Loading roads...")
    roads = gpd.read_file(ROADS_PATH)

    if parcels.empty:
        raise ValueError("Parcel layer is empty.")

    if parcels.crs is None:
        raise ValueError("Parcel layer has no CRS. It should be EPSG:26915.")

    if roads.empty:
        raise ValueError("Roads layer is empty.")

    # ------------------------------------------------------------
    # Clean and align data
    # ------------------------------------------------------------
    parcels = clean_geometries(parcels, "parcels")
    roads = clean_geometries(roads, "roads")

    target_crs = parcels.crs
    print(f"Target CRS: {target_crs}")

    roads = ensure_same_crs(roads, target_crs, "roads")
    roads = keep_line_features(roads, "roads")

    # ------------------------------------------------------------
    # Load town points from CSV
    # ------------------------------------------------------------
    towns = load_town_centers(TOWNS_CSV_PATH, target_crs)

    # Save town points for QA in QGIS.
    if TOWN_OUTPUT_PATH.exists():
        TOWN_OUTPUT_PATH.unlink()

    towns.to_file(
        TOWN_OUTPUT_PATH,
        driver="GPKG",
        layer="town_centers",
    )

    print(f"Saved town centers for QA: {TOWN_OUTPUT_PATH}")

    # ------------------------------------------------------------
    # Calculate road access
    # ------------------------------------------------------------
    parcels = calculate_nearest_road_distance(parcels, roads)

    parcels["road_access_class"] = parcels["distance_to_nearest_road_m"].apply(
        classify_road_access
    )

    # ------------------------------------------------------------
    # Calculate town proximity
    # ------------------------------------------------------------
    parcels = calculate_nearest_town(parcels, towns)

    # ------------------------------------------------------------
    # Save outputs
    # ------------------------------------------------------------
    print("Saving outputs...")

    if OUTPUT_GPKG.exists():
        OUTPUT_GPKG.unlink()

    if OUTPUT_GEOJSON.exists():
        OUTPUT_GEOJSON.unlink()

    parcels.to_file(
        OUTPUT_GPKG,
        driver="GPKG",
        layer="parcel_access_metrics",
    )

    parcels.to_file(
        OUTPUT_GEOJSON,
        driver="GeoJSON",
    )

    print("")
    print("Done.")
    print(f"Created: {OUTPUT_GPKG}")
    print(f"Created: {OUTPUT_GEOJSON}")
    print("")
    print("Fields added:")
    print("- distance_to_nearest_road_m")
    print("- road_access_class")
    print("- nearest_town")
    print("- nearest_town_role")
    print("- distance_to_nearest_town_km")
    print("")


if __name__ == "__main__":
    main()