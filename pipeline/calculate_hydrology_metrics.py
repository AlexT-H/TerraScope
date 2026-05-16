from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# ============================================================
#
# Inputs:
# - data/processed/parcel_slope_metrics.gpkg
# - data/interim/waterbodies_26915.gpkg
# - data/interim/wetlands_26915_cut.gpkg
# - data/interim/streams_26915.gpkg
#
# Adds:
# - watertype
# - stream_present
# - polygon_water_present
# - water_area_acres
# - water_pct
# - wetland_present
# - wetland_area_acres
# - wetland_pct
#
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------
# Input paths
# ------------------------------------------------------------

PARCELS_PATH = BASE_DIR / "data" / "processed" / "parcel_slope_metrics.gpkg"
WATERBODIES_PATH = BASE_DIR / "data" / "interim" / "waterbodies_26915.gpkg"
WETLANDS_PATH = BASE_DIR / "data" / "interim" / "wetlands_26915_cut.gpkg"
STREAMS_PATH = BASE_DIR / "data" / "interim" / "streams_26915.gpkg"

# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_GPKG = OUTPUT_DIR / "parcel_hydrology_metrics.gpkg"
OUTPUT_GEOJSON = OUTPUT_DIR / "parcel_hydrology_metrics.geojson"


def check_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def clean_geometries(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    """
    Removes null/empty geometries and repairs invalid geometries.
    """
    print(f"Cleaning geometries for {label}...")

    original_count = len(gdf)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        # Fallback for older Shapely versions
        gdf["geometry"] = gdf.buffer(0)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    removed = original_count - len(gdf)
    if removed > 0:
        print(f"Removed {removed} invalid/empty geometries from {label}.")

    return gdf


def ensure_same_crs(
    gdf: gpd.GeoDataFrame,
    target_crs,
    label: str,
) -> gpd.GeoDataFrame:
    """
    Reprojects a layer to match the parcel CRS if needed.
    """
    if gdf.crs is None:
        raise ValueError(f"{label} has no CRS. Assign the correct CRS before running.")

    if gdf.crs != target_crs:
        print(f"Reprojecting {label} from {gdf.crs} to {target_crs}...")
        gdf = gdf.to_crs(target_crs)
    else:
        print(f"{label} CRS already matches parcels.")

    return gdf


def keep_geometry_types(
    gdf: gpd.GeoDataFrame,
    allowed_types: list[str],
    label: str,
) -> gpd.GeoDataFrame:
    """
    Keeps only selected geometry types.
    """
    original_count = len(gdf)

    filtered = gdf[gdf.geometry.geom_type.isin(allowed_types)].copy()

    removed = original_count - len(filtered)
    if removed > 0:
        print(f"{label}: removed {removed} features not in {allowed_types}.")

    if filtered.empty:
        raise ValueError(f"{label} has no usable geometries after filtering.")

    return filtered


def add_presence_from_intersection(
    parcels: gpd.GeoDataFrame,
    features: gpd.GeoDataFrame,
    output_field: str,
) -> gpd.GeoDataFrame:
    """
    Adds True/False depending on whether parcel intersects/touches any feature.
    """
    print(f"Calculating {output_field}...")

    joined = gpd.sjoin(
        parcels[["geometry"]].copy(),
        features[["geometry"]].copy(),
        how="left",
        predicate="intersects",
    )

    matching_indexes = joined[joined["index_right"].notnull()].index.unique()

    parcels[output_field] = parcels.index.isin(matching_indexes)

    return parcels


def calculate_overlap_percentage(
    parcels: gpd.GeoDataFrame,
    polygons: gpd.GeoDataFrame,
    output_pct_field: str,
    output_area_acres_field: str,
) -> gpd.GeoDataFrame:
    """
    Calculates percent and acreage of each parcel covered by polygon features.

    Formula:
    overlap percent = polygon overlap area / parcel area * 100
    """
    print(f"Calculating {output_pct_field}...")

    parcels_work = parcels[["geometry"]].copy()
    parcels_work["_parcel_index"] = parcels.index
    parcels_work["_parcel_area_m2"] = parcels_work.geometry.area

    polygons_work = polygons[["geometry"]].copy()

    intersections = gpd.overlay(
        parcels_work,
        polygons_work,
        how="intersection",
        keep_geom_type=True,
    )

    if intersections.empty:
        parcels[output_pct_field] = 0.0
        parcels[output_area_acres_field] = 0.0
        return parcels

    intersections["_overlap_area_m2"] = intersections.geometry.area

    overlap_by_parcel = (
        intersections
        .groupby("_parcel_index")["_overlap_area_m2"]
        .sum()
    )

    parcel_area_m2 = pd.Series(
        parcels.geometry.area.values,
        index=parcels.index,
        dtype="float64",
    )

    overlap_area_m2 = pd.Series(
        parcels.index.map(overlap_by_parcel).fillna(0.0),
        index=parcels.index,
        dtype="float64",
    )

    pct = (overlap_area_m2 / parcel_area_m2) * 100
    acres = overlap_area_m2 / 4046.8564224

    parcels[output_pct_field] = (
        pct.replace([np.inf, -np.inf], 0)
        .fillna(0)
        .round(2)
    )

    parcels[output_area_acres_field] = (
        acres.replace([np.inf, -np.inf], 0)
        .fillna(0)
        .round(2)
    )

    return parcels


def assign_water_type(row) -> str:
    """
    Creates one simple water type category per parcel.
    """
    has_stream = bool(row.get("stream_present", False))
    has_polygon_water = bool(row.get("polygon_water_present", False))

    if has_stream and has_polygon_water:
        return "Stream + Lake/Pond/Waterbody"
    if has_stream:
        return "Stream"
    if has_polygon_water:
        return "Lake/Pond/Waterbody"
    return "None"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Starting TerraScope hydrology metrics...")

    check_file_exists(PARCELS_PATH, "parcel slope metrics layer")
    check_file_exists(WATERBODIES_PATH, "waterbodies layer")
    check_file_exists(WETLANDS_PATH, "wetlands layer")
    check_file_exists(STREAMS_PATH, "streams layer")

    print(f"Parcels: {PARCELS_PATH}")
    print(f"Waterbodies: {WATERBODIES_PATH}")
    print(f"Wetlands: {WETLANDS_PATH}")
    print(f"Streams: {STREAMS_PATH}")

    # ------------------------------------------------------------
    # Load layers
    # ------------------------------------------------------------
    print("Loading parcels...")
    parcels = gpd.read_file(PARCELS_PATH)

    print("Loading waterbodies...")
    waterbodies = gpd.read_file(WATERBODIES_PATH)

    print("Loading wetlands...")
    wetlands = gpd.read_file(WETLANDS_PATH)

    print("Loading streams...")
    streams = gpd.read_file(STREAMS_PATH)

    if parcels.empty:
        raise ValueError("Parcel layer is empty.")

    if parcels.crs is None:
        raise ValueError("Parcel layer has no CRS. It should be EPSG:26915.")

    # ------------------------------------------------------------
    # Clean geometries
    # ------------------------------------------------------------
    parcels = clean_geometries(parcels, "parcels")
    waterbodies = clean_geometries(waterbodies, "waterbodies")
    wetlands = clean_geometries(wetlands, "wetlands")
    streams = clean_geometries(streams, "streams")

    # ------------------------------------------------------------
    # Match CRS
    # ------------------------------------------------------------
    target_crs = parcels.crs
    print(f"Target CRS: {target_crs}")

    waterbodies = ensure_same_crs(waterbodies, target_crs, "waterbodies")
    wetlands = ensure_same_crs(wetlands, target_crs, "wetlands")
    streams = ensure_same_crs(streams, target_crs, "streams")

    # ------------------------------------------------------------
    # Keep correct geometry types
    # ------------------------------------------------------------
    waterbodies = keep_geometry_types(
        waterbodies,
        ["Polygon", "MultiPolygon"],
        "waterbodies",
    )

    wetlands = keep_geometry_types(
        wetlands,
        ["Polygon", "MultiPolygon"],
        "wetlands",
    )

    streams = keep_geometry_types(
        streams,
        ["LineString", "MultiLineString"],
        "streams",
    )

    # ------------------------------------------------------------
    # Stream presence only
    # ------------------------------------------------------------
    parcels = add_presence_from_intersection(
        parcels=parcels,
        features=streams,
        output_field="stream_present",
    )

    # ------------------------------------------------------------
    # Polygon waterbody presence and percent
    # ------------------------------------------------------------
    parcels = add_presence_from_intersection(
        parcels=parcels,
        features=waterbodies,
        output_field="polygon_water_present",
    )

    parcels = calculate_overlap_percentage(
        parcels=parcels,
        polygons=waterbodies,
        output_pct_field="water_pct",
        output_area_acres_field="water_area_acres",
    )

    # ------------------------------------------------------------
    # Water type
    # ------------------------------------------------------------
    print("Assigning watertype...")
    parcels["watertype"] = parcels.apply(assign_water_type, axis=1)

    # ------------------------------------------------------------
    # Wetland presence and percent
    # ------------------------------------------------------------
    parcels = add_presence_from_intersection(
        parcels=parcels,
        features=wetlands,
        output_field="wetland_present",
    )

    parcels = calculate_overlap_percentage(
        parcels=parcels,
        polygons=wetlands,
        output_pct_field="wetland_pct",
        output_area_acres_field="wetland_area_acres",
    )

    # ------------------------------------------------------------
    # Field cleanup / formatting
    # ------------------------------------------------------------
    bool_fields = [
        "stream_present",
        "polygon_water_present",
        "wetland_present",
    ]

    for field in bool_fields:
        parcels[field] = parcels[field].astype(bool)

    # Optional: create a compact wetland t/f field if you prefer this name.
    parcels["wetland"] = parcels["wetland_present"]

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
        layer="parcel_hydrology_metrics",
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
    print("- watertype")
    print("- stream_present")
    print("- polygon_water_present")
    print("- water_area_acres")
    print("- water_pct")
    print("- wetland")
    print("- wetland_present")
    print("- wetland_area_acres")
    print("- wetland_pct")
    print("")


if __name__ == "__main__":
    main()