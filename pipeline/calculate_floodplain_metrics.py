from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# ============================================================
#
# Input:
# - data/processed/parcel_hydrology_metrics.gpkg
# - data/raw/floodplain/S_FLD_HAZ_AR.shp
#
# Adds:
# - floodplain_present
# - floodplain_area_acres
# - floodplain_pct
# - floodplain_constraint_pass
#
# Output:
# - data/processed/parcel_floodplain_metrics.gpkg
# - data/processed/parcel_floodplain_metrics.geojson
#
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------
# Input paths
# ------------------------------------------------------------

PARCELS_PATH = BASE_DIR / "data" / "processed" / "parcel_hydrology_metrics.gpkg"
FLOODPLAIN_PATH = BASE_DIR / "data" / "raw" / "floodplain" / "S_FLD_HAZ_AR.shp"

# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_GPKG = OUTPUT_DIR / "parcel_floodplain_metrics.gpkg"
OUTPUT_GEOJSON = OUTPUT_DIR / "parcel_floodplain_metrics.geojson"

# Optional QA output so you can load only the filtered floodplain polygons in QGIS.
FILTERED_FLOODPLAIN_GPKG = OUTPUT_DIR / "filtered_high_risk_floodplain.gpkg"


# ------------------------------------------------------------
# Floodplain filtering settings
# ------------------------------------------------------------

HIGH_RISK_FLOOD_ZONES = {
    "A",
    "AE",
    "AH",
    "AO",
    "A99",
    "AR",
    "V",
    "VE",
}


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

    if gdf.empty:
        raise ValueError(f"{label} has no usable geometries after cleaning.")

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
        raise ValueError(
            f"{label} has no CRS. Assign the correct CRS before running this script."
        )

    if gdf.crs != target_crs:
        print(f"Reprojecting {label} from {gdf.crs} to {target_crs}...")
        gdf = gdf.to_crs(target_crs)
    else:
        print(f"{label} CRS already matches parcels.")

    return gdf


def keep_polygon_features(
    gdf: gpd.GeoDataFrame,
    label: str,
) -> gpd.GeoDataFrame:
    """
    Keeps only Polygon and MultiPolygon features.
    """
    allowed_types = ["Polygon", "MultiPolygon"]

    original_count = len(gdf)

    gdf = gdf[gdf.geometry.geom_type.isin(allowed_types)].copy()

    removed = original_count - len(gdf)
    if removed > 0:
        print(f"{label}: removed {removed} non-polygon features.")

    if gdf.empty:
        raise ValueError(f"{label} has no polygon features after filtering.")

    return gdf


def print_floodplain_field_summary(floodplain: gpd.GeoDataFrame) -> None:
    """
    Prints useful FEMA/NFHL fields and unique values for QA.
    """
    print("")
    print("Floodplain fields found:")
    print(list(floodplain.columns))
    print("")

    for field in ["FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"]:
        if field in floodplain.columns:
            print(f"Unique values in {field}:")
            print(
                floodplain[field]
                .astype(str)
                .value_counts(dropna=False)
                .head(30)
                .to_string()
            )
            print("")


def filter_high_risk_floodplain(
    floodplain: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Filters FEMA/NFHL flood hazard polygons down to high-risk floodplain zones.

    Preferred filter:
        FLD_ZONE in HIGH_RISK_FLOOD_ZONES

    If SFHA_TF exists, this script also keeps SFHA_TF = 'T' or 'TRUE',
    but only when FLD_ZONE is missing.

    This avoids treating broad X-zone polygons as floodplain.
    """
    print("Filtering floodplain polygons to high-risk zones...")

    original_count = len(floodplain)

    if "FLD_ZONE" in floodplain.columns:
        floodplain["_fld_zone_clean"] = (
            floodplain["FLD_ZONE"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        filtered = floodplain[
            floodplain["_fld_zone_clean"].isin(HIGH_RISK_FLOOD_ZONES)
        ].copy()

        print(f"Using FLD_ZONE filter: {sorted(HIGH_RISK_FLOOD_ZONES)}")
        print(f"Original floodplain polygons: {original_count:,}")
        print(f"High-risk floodplain polygons kept: {len(filtered):,}")
        print(f"Floodplain polygons removed: {original_count - len(filtered):,}")

    elif "SFHA_TF" in floodplain.columns:
        sfha = (
            floodplain["SFHA_TF"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        filtered = floodplain[sfha.isin(["T", "TRUE", "1", "YES", "Y"])].copy()

        print("FLD_ZONE field not found. Used SFHA_TF filter instead.")
        print(f"Original floodplain polygons: {original_count:,}")
        print(f"SFHA/high-risk polygons kept: {len(filtered):,}")
        print(f"Floodplain polygons removed: {original_count - len(filtered):,}")

    else:
        raise ValueError(
            "Could not find FLD_ZONE or SFHA_TF in the floodplain layer. "
            "Open S_FLD_HAZ_AR.shp in QGIS and inspect the attribute fields."
        )

    if filtered.empty:
        raise ValueError(
            "No high-risk floodplain polygons were kept after filtering. "
            "Open the FEMA layer in QGIS and check FLD_ZONE values."
        )

    if "_fld_zone_clean" in filtered.columns:
        filtered = filtered.drop(columns=["_fld_zone_clean"])

    return filtered


def calculate_overlap_percentage(
    parcels: gpd.GeoDataFrame,
    polygons: gpd.GeoDataFrame,
    output_pct_field: str,
    output_area_acres_field: str,
) -> gpd.GeoDataFrame:
    """
    Calculates percent and acreage of each parcel covered by polygon features.

    Formula:
    floodplain_pct = floodplain_overlap_area / parcel_area * 100
    """
    print(f"Calculating {output_pct_field}...")

    parcels_work = parcels[["geometry"]].copy()
    parcels_work["_parcel_index"] = parcels.index

    polygons_work = polygons[["geometry"]].copy()

    intersections = gpd.overlay(
        parcels_work,
        polygons_work,
        how="intersection",
        keep_geom_type=True,
    )

    if intersections.empty:
        print("No parcel/floodplain intersections found.")
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
        .clip(lower=0, upper=100)
        .round(2)
    )

    parcels[output_area_acres_field] = (
        acres.replace([np.inf, -np.inf], 0)
        .fillna(0)
        .round(2)
    )

    return parcels


def print_output_summary(parcels: gpd.GeoDataFrame) -> None:
    """
    Prints quick QA stats so you can immediately tell if the floodplain
    calculation looks reasonable.
    """
    print("")
    print("Floodplain output summary:")
    print(parcels["floodplain_pct"].describe().to_string())
    print("")

    total = len(parcels)
    gt_0 = int((parcels["floodplain_pct"] > 0).sum())
    gt_20 = int((parcels["floodplain_pct"] > 20).sum())
    eq_100 = int((parcels["floodplain_pct"] >= 99.99).sum())

    print(f"Total parcels: {total:,}")
    print(f"Parcels with floodplain_pct > 0: {gt_0:,} ({gt_0 / total * 100:.2f}%)")
    print(f"Parcels with floodplain_pct > 20: {gt_20:,} ({gt_20 / total * 100:.2f}%)")
    print(f"Parcels with floodplain_pct near 100: {eq_100:,} ({eq_100 / total * 100:.2f}%)")
    print("")

    if gt_20 / total > 0.50:
        print("WARNING:")
        print("More than 50% of parcels have floodplain_pct > 20.")
        print("That may still be possible in some datasets, but it is suspicious.")
        print("Open filtered_high_risk_floodplain.gpkg in QGIS and confirm the polygons.")
        print("")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Starting TerraScope floodplain metrics...")

    check_file_exists(PARCELS_PATH, "parcel hydrology metrics layer")
    check_file_exists(FLOODPLAIN_PATH, "raw floodplain shapefile")

    print(f"Parcels: {PARCELS_PATH}")
    print(f"Floodplain: {FLOODPLAIN_PATH}")

    # ------------------------------------------------------------
    # Load layers
    # ------------------------------------------------------------
    print("Loading parcels...")
    parcels = gpd.read_file(PARCELS_PATH)

    print("Loading floodplain...")
    floodplain = gpd.read_file(FLOODPLAIN_PATH)

    if parcels.empty:
        raise ValueError("Parcel layer is empty.")

    if parcels.crs is None:
        raise ValueError("Parcel layer has no CRS. It should be EPSG:26915.")

    if floodplain.empty:
        raise ValueError("Floodplain layer is empty.")

    # ------------------------------------------------------------
    # Clean geometries
    # ------------------------------------------------------------
    parcels = clean_geometries(parcels, "parcels")
    floodplain = clean_geometries(floodplain, "floodplain")

    # ------------------------------------------------------------
    # Match CRS
    # ------------------------------------------------------------
    target_crs = parcels.crs
    print(f"Target CRS: {target_crs}")

    floodplain = ensure_same_crs(floodplain, target_crs, "floodplain")

    # ------------------------------------------------------------
    # Keep polygon features only
    # ------------------------------------------------------------
    floodplain = keep_polygon_features(floodplain, "floodplain")

    # ------------------------------------------------------------
    # Print FEMA field summary before filtering
    # ------------------------------------------------------------
    print_floodplain_field_summary(floodplain)

    # ------------------------------------------------------------
    # Critical fix:
    # Filter to actual high-risk floodplain zones before overlay.
    # ------------------------------------------------------------
    floodplain = filter_high_risk_floodplain(floodplain)

    # Save filtered floodplain for visual QA in QGIS.
    if FILTERED_FLOODPLAIN_GPKG.exists():
        FILTERED_FLOODPLAIN_GPKG.unlink()

    floodplain.to_file(
        FILTERED_FLOODPLAIN_GPKG,
        driver="GPKG",
        layer="filtered_high_risk_floodplain",
    )

    print(f"Created QA floodplain layer: {FILTERED_FLOODPLAIN_GPKG}")

    # ------------------------------------------------------------
    # Calculate floodplain overlap
    # ------------------------------------------------------------
    parcels = calculate_overlap_percentage(
        parcels=parcels,
        polygons=floodplain,
        output_pct_field="floodplain_pct",
        output_area_acres_field="floodplain_area_acres",
    )

    # ------------------------------------------------------------
    # Presence and constraint fields
    # ------------------------------------------------------------
    parcels["floodplain_present"] = parcels["floodplain_pct"] > 0

    # Default screening rule from the TerraScope methodology:
    # pass if 20% or less of the parcel overlaps high-risk floodplain.
    parcels["floodplain_constraint_pass"] = parcels["floodplain_pct"] <= 20

    print_output_summary(parcels)

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
        layer="parcel_floodplain_metrics",
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
    print("- floodplain_present")
    print("- floodplain_area_acres")
    print("- floodplain_pct")
    print("- floodplain_constraint_pass")
    print("")


if __name__ == "__main__":
    main()
