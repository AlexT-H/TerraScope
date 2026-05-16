from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterstats import zonal_stats


# ============================================================
# Calculate parcel-level slope metrics from slope.tif
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------
# INPUTS
# Change PARCELS_PATH if your parcel file has a different name.
# ------------------------------------------------------------------

PARCEL_CANDIDATES = [
    BASE_DIR / "data" / "interim" / "clipped" / "parcels_clipped.geojson",
    BASE_DIR / "data" / "interim" / "clipped" / "parcels_clipped.gpkg",
    BASE_DIR / "data" / "interim" / "analysis_units_26915.geojson",
    BASE_DIR / "data" / "interim" / "analysis_units_26915.gpkg",
]

SLOPE_PATH = BASE_DIR / "data" / "processed" / "slope.tif"

# ------------------------------------------------------------------
# OUTPUTS
# ------------------------------------------------------------------

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_GEOJSON = OUTPUT_DIR / "parcel_slope_metrics.geojson"
OUTPUT_GPKG = OUTPUT_DIR / "parcel_slope_metrics.gpkg"


def find_existing_file(candidates):
    """
    Finds the first existing file from a list of possible paths.
    """
    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find a parcel file. Update PARCEL_CANDIDATES in this script."
    )


def clean_numeric(value, decimals=2):
    """
    Converts numpy values to normal Python floats and rounds them.
    Handles None and NaN safely.
    """
    if value is None:
        return None

    try:
        if np.isnan(value):
            return None
    except TypeError:
        pass

    return round(float(value), decimals)


def slope_range_metrics(values):
    """
    Calculates median slope and percent of parcel area in slope ranges.

    Because each raster pixel represents the same area, the percentage
    of pixels in each slope range approximates percentage of parcel area.
    """
    arr = np.array(values, dtype="float32")

    # Remove masked, NaN, and invalid values
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return {
            "median_slope_pct": None,
            "pct_under_5_slope": None,
            "pct_5_to_15_slope": None,
            "pct_over_15_slope": None,
        }

    total = arr.size

    pct_under_5 = (np.sum((arr >= 0) & (arr < 5)) / total) * 100
    pct_5_to_15 = (np.sum((arr >= 5) & (arr < 15)) / total) * 100
    pct_over_15 = (np.sum(arr >= 15) / total) * 100

    return {
        "median_slope_pct": clean_numeric(np.median(arr)),
        "pct_under_5_slope": clean_numeric(pct_under_5),
        "pct_5_to_15_slope": clean_numeric(pct_5_to_15),
        "pct_over_15_slope": clean_numeric(pct_over_15),
    }


def assign_slope_class(row):
    """
    Assigns an overall parcel slope class based on the dominant terrain pattern.
    """
    pct_under_5 = row.get("pct_under_5_slope")
    pct_5_to_15 = row.get("pct_5_to_15_slope")
    pct_over_15 = row.get("pct_over_15_slope")

    if pct_under_5 is None or np.isnan(pct_under_5):
        return "Unknown"

    if pct_under_5 >= 60:
        return "Gentle"
    elif pct_5_to_15 >= 50:
        return "Moderate"
    elif pct_over_15 >= 40:
        return "Steep"
    else:
        return "Mixed"


def calculate_terrain_score(row):
    """
    Temporary terrain score from 0 to 100.

    This is not the final suitability score.
    """
    pct_under_5 = row.get("pct_under_5_slope")
    pct_5_to_15 = row.get("pct_5_to_15_slope")
    pct_over_15 = row.get("pct_over_15_slope")

    if pct_under_5 is None or np.isnan(pct_under_5):
        return None

    score = (
        pct_under_5 * 1.0
        + pct_5_to_15 * 0.6
        + pct_over_15 * 0.1
    )

    return clean_numeric(max(0, min(score, 100)))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    parcels_path = find_existing_file(PARCEL_CANDIDATES)

    if not SLOPE_PATH.exists():
        raise FileNotFoundError(f"Could not find slope raster: {SLOPE_PATH}")

    print("Starting parcel slope metrics...")
    print(f"Parcels: {parcels_path}")
    print(f"Slope raster: {SLOPE_PATH}")

    # ------------------------------------------------------------
    # 1. Load parcels
    # ------------------------------------------------------------
    parcels = gpd.read_file(parcels_path)

    if parcels.empty:
        raise ValueError("Parcel file loaded, but it contains no features.")

    if parcels.crs is None:
        raise ValueError(
            "Parcel layer has no CRS. It should be EPSG:26915 before analysis."
        )

    # ------------------------------------------------------------
    # 2. Validate/fix geometries
    # ------------------------------------------------------------
    print("Fixing parcel geometries...")

    parcels["geometry"] = parcels.geometry.make_valid()
    parcels = parcels[~parcels.geometry.is_empty]
    parcels = parcels[parcels.geometry.notnull()].copy()

    if parcels.empty:
        raise ValueError("No valid parcel geometries remain after geometry cleanup.")

    # ------------------------------------------------------------
    # 3. Check raster CRS and NoData
    # ------------------------------------------------------------
    with rasterio.open(SLOPE_PATH) as src:
        raster_crs = src.crs
        nodata = src.nodata

    if raster_crs is None:
        raise ValueError("Slope raster has no CRS.")

    if parcels.crs != raster_crs:
        print(f"Reprojecting parcels from {parcels.crs} to {raster_crs}...")
        parcels = parcels.to_crs(raster_crs)
    else:
        print("Parcel CRS matches slope raster CRS.")

    # ------------------------------------------------------------
    # 4. Basic zonal stats: mean, max, median
    # ------------------------------------------------------------
    print("Calculating mean, max, and median slope per parcel...")

    basic_stats = zonal_stats(
        vectors=parcels,
        raster=str(SLOPE_PATH),
        stats=["mean", "max", "median", "count"],
        nodata=nodata,
        all_touched=False,
        geojson_out=False,
    )

    parcels["avg_slope_pct"] = [
        clean_numeric(item.get("mean")) for item in basic_stats
    ]

    parcels["max_slope_pct"] = [
        clean_numeric(item.get("max")) for item in basic_stats
    ]

    parcels["median_slope_pct"] = [
        clean_numeric(item.get("median")) for item in basic_stats
    ]

    parcels["_slope_pixel_count"] = [
        item.get("count", 0) for item in basic_stats
    ]

    # ------------------------------------------------------------
    # 5. Slope range percentages
    # ------------------------------------------------------------
    print("Calculating slope range percentages per parcel...")

    raster_array_stats = zonal_stats(
        vectors=parcels,
        raster=str(SLOPE_PATH),
        stats=[],
        nodata=nodata,
        all_touched=False,
        raster_out=True,
        geojson_out=False,
    )

    pct_under_5_values = []
    pct_5_to_15_values = []
    pct_over_15_values = []

    for item in raster_array_stats:
        mini_raster = item.get("mini_raster_array")

        if mini_raster is None:
            pct_under_5_values.append(None)
            pct_5_to_15_values.append(None)
            pct_over_15_values.append(None)
            continue

        # mini_raster_array is usually a masked array.
        if hasattr(mini_raster, "compressed"):
            values = mini_raster.compressed()
        else:
            values = np.array(mini_raster).ravel()

        metrics = slope_range_metrics(values)

        pct_under_5_values.append(metrics["pct_under_5_slope"])
        pct_5_to_15_values.append(metrics["pct_5_to_15_slope"])
        pct_over_15_values.append(metrics["pct_over_15_slope"])

    parcels["pct_under_5_slope"] = pct_under_5_values
    parcels["pct_5_to_15_slope"] = pct_5_to_15_values
    parcels["pct_over_15_slope"] = pct_over_15_values

    # ------------------------------------------------------------
    # 6. Parcel-level slope class
    # ------------------------------------------------------------
    print("Assigning parcel slope classes...")

    parcels["slope_class"] = parcels.apply(assign_slope_class, axis=1)

    # ------------------------------------------------------------
    # 7. Temporary terrain score
    # ------------------------------------------------------------
    print("Calculating terrain score...")

    parcels["terrain_score"] = parcels.apply(calculate_terrain_score, axis=1)

    # ------------------------------------------------------------
    # 8. Slope constraint pass/fail
    # ------------------------------------------------------------
    print("Calculating slope constraint pass/fail...")

    parcels["slope_constraint_pass"] = parcels["pct_over_15_slope"].apply(
        lambda value: bool(value <= 40) if value is not None and not np.isnan(value) else False
    )

    # ------------------------------------------------------------
    # 9. Optional parcel acreage check
    # ------------------------------------------------------------
    # EPSG:26915 uses meters, so area is square meters.
    # 1 acre = 4046.8564224 square meters.
    if "area_acres" not in parcels.columns:
        parcels["area_acres"] = parcels.geometry.area / 4046.8564224
        parcels["area_acres"] = parcels["area_acres"].round(2)

    # ------------------------------------------------------------
    # 10. Remove temporary helper fields
    # ------------------------------------------------------------
    parcels = parcels.drop(columns=["_slope_pixel_count"], errors="ignore")

    # ------------------------------------------------------------
    # 11. Export outputs
    # ------------------------------------------------------------
    print("Saving outputs...")

    if OUTPUT_GEOJSON.exists():
        OUTPUT_GEOJSON.unlink()

    if OUTPUT_GPKG.exists():
        OUTPUT_GPKG.unlink()

    parcels.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    parcels.to_file(OUTPUT_GPKG, driver="GPKG", layer="parcel_slope_metrics")

    print("Done.")
    print(f"Created GeoJSON: {OUTPUT_GEOJSON}")
    print(f"Created GeoPackage: {OUTPUT_GPKG}")
    print("")
    print("Fields added:")
    print("- avg_slope_pct")
    print("- max_slope_pct")
    print("- median_slope_pct")
    print("- pct_under_5_slope")
    print("- pct_5_to_15_slope")
    print("- pct_over_15_slope")
    print("- slope_class")
    print("- terrain_score")
    print("- slope_constraint_pass")
    print("")

if __name__ == "__main__":
    main()