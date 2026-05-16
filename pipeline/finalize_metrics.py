from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_GPKG = BASE_DIR / "data" / "processed" / "parcel_ndvi_metrics.gpkg"
OUTPUT_GPKG = BASE_DIR / "data" / "processed" / "final_metrics.gpkg"
OUTPUT_CSV = BASE_DIR / "data" / "processed" / "final_metrics.csv"

TARGET_CRS = "EPSG:26915"
ACRES_PER_SQ_METER = 0.00024710538146717


EXPECTED_FIELDS = [
    "unit_id",
    "area_acres",

    "avg_slope_pct",
    "max_slope_pct",
    "median_slope_pct",
    "pct_under_5_slope",
    "pct_5_to_15_slope",
    "pct_over_15_slope",
    "slope_class",
    "terrain_score",
    "slope_constraint_pass",

    "watertype",
    "stream_present",
    "polygon_water_present",
    "water_pct",
    "wetland_present",
    "wetland_pct",

    "floodplain_present",
    "floodplain_pct",
    "floodplain_constraint_pass",

    "distance_to_nearest_road_m",
    "road_access_class",
    "nearest_town",
    "nearest_town_role",
    "distance_to_nearest_town_km",

    "avg_ndvi",
    "median_ndvi",
    "vegetation_score",
    "vegetation_class",
]


PERCENT_FIELDS = [
    "pct_under_5_slope",
    "pct_5_to_15_slope",
    "pct_over_15_slope",
    "water_pct",
    "wetland_pct",
    "floodplain_pct",
    "terrain_score",
    "vegetation_score",
]

NDVI_FIELDS = [
    "avg_ndvi",
    "median_ndvi",
]

BOOLEAN_FIELDS = [
    "slope_constraint_pass",
    "stream_present",
    "polygon_water_present",
    "wetland_present",
    "floodplain_present",
    "floodplain_constraint_pass",
]


def print_header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main():
    print_header("TerraScope Phase 3: Finalize Metrics")

    if not INPUT_GPKG.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_GPKG}")

    print(f"Reading input file:\n{INPUT_GPKG}")
    gdf = gpd.read_file(INPUT_GPKG)

    print(f"\nRows loaded: {len(gdf):,}")
    print(f"Input CRS: {gdf.crs}")

    # ---------------------------------------------------------------------
    # 1. Confirm / fix CRS
    # ---------------------------------------------------------------------
    print_header("Checking CRS")

    if gdf.crs is None:
        raise ValueError(
            "Input file has no CRS. Open it in QGIS and confirm the correct CRS before continuing."
        )

    if gdf.crs.to_string() != TARGET_CRS:
        print(f"Reprojecting from {gdf.crs} to {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)
    else:
        print(f"CRS is already {TARGET_CRS}")

    # ---------------------------------------------------------------------
    # 2. Validate geometries
    # ---------------------------------------------------------------------
    print_header("Checking Geometry")

    starting_count = len(gdf)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    removed_empty = starting_count - len(gdf)
    print(f"Removed null/empty geometries: {removed_empty:,}")

    invalid_count = (~gdf.geometry.is_valid).sum()
    print(f"Invalid geometries before repair: {invalid_count:,}")

    if invalid_count > 0:
        gdf["geometry"] = gdf.geometry.buffer(0)
        invalid_after = (~gdf.geometry.is_valid).sum()
        print(f"Invalid geometries after buffer(0): {invalid_after:,}")

    # ---------------------------------------------------------------------
    # 3. Stable unit_id
    # ---------------------------------------------------------------------
    print_header("Checking unit_id")

    if "unit_id" not in gdf.columns:
        print("unit_id not found. Creating unit_id from row index.")
        gdf["unit_id"] = ["unit_" + str(i).zfill(6) for i in range(len(gdf))]
    else:
        missing_unit_ids = gdf["unit_id"].isna().sum()
        duplicate_unit_ids = gdf["unit_id"].duplicated().sum()

        print(f"Missing unit_id values: {missing_unit_ids:,}")
        print(f"Duplicate unit_id values: {duplicate_unit_ids:,}")

        gdf["unit_id"] = gdf["unit_id"].astype(str)

        if missing_unit_ids > 0 or duplicate_unit_ids > 0:
            print("Fixing missing/duplicate unit_id values.")
            gdf["unit_id"] = ["unit_" + str(i).zfill(6) for i in range(len(gdf))]

    # ---------------------------------------------------------------------
    # 4. Recalculate area_acres
    # ---------------------------------------------------------------------
    print_header("Recalculating area_acres")

    gdf["area_acres"] = gdf.geometry.area * ACRES_PER_SQ_METER

    print("Area recalculated from geometry.")
    print(gdf["area_acres"].describe())

    # ---------------------------------------------------------------------
    # 5. Clip percentage fields to 0–100
    # ---------------------------------------------------------------------
    print_header("Clipping percentage and score fields")

    for field in PERCENT_FIELDS:
        if field in gdf.columns:
            gdf[field] = pd.to_numeric(gdf[field], errors="coerce")
            before_min = gdf[field].min(skipna=True)
            before_max = gdf[field].max(skipna=True)

            gdf[field] = gdf[field].clip(lower=0, upper=100)

            after_min = gdf[field].min(skipna=True)
            after_max = gdf[field].max(skipna=True)

            print(
                f"{field}: before [{before_min}, {before_max}] "
                f"after [{after_min}, {after_max}]"
            )
        else:
            print(f"Missing percentage/score field: {field}")

    # ---------------------------------------------------------------------
    # 6. Clip NDVI fields to -1 to 1
    # ---------------------------------------------------------------------
    print_header("Clipping NDVI fields")

    for field in NDVI_FIELDS:
        if field in gdf.columns:
            gdf[field] = pd.to_numeric(gdf[field], errors="coerce")
            before_min = gdf[field].min(skipna=True)
            before_max = gdf[field].max(skipna=True)

            gdf[field] = gdf[field].clip(lower=-1, upper=1)

            after_min = gdf[field].min(skipna=True)
            after_max = gdf[field].max(skipna=True)

            print(
                f"{field}: before [{before_min}, {before_max}] "
                f"after [{after_min}, {after_max}]"
            )
        else:
            print(f"Missing NDVI field: {field}")

    # ---------------------------------------------------------------------
    # 7. Clean boolean fields
    # ---------------------------------------------------------------------
    print_header("Cleaning boolean fields")

    for field in BOOLEAN_FIELDS:
        if field in gdf.columns:
            gdf[field] = gdf[field].fillna(False).astype(bool)
            print(f"{field}: cleaned as boolean")
        else:
            print(f"Missing boolean field: {field}")

    # ---------------------------------------------------------------------
    # 8. Check expected fields
    # ---------------------------------------------------------------------
    print_header("Checking Expected Final Fields")

    missing_fields = [field for field in EXPECTED_FIELDS if field not in gdf.columns]

    if missing_fields:
        print("WARNING: Missing expected fields:")
        for field in missing_fields:
            print(f"  - {field}")
    else:
        print("All expected fields are present.")

    # ---------------------------------------------------------------------
    # 9. Null report
    # ---------------------------------------------------------------------
    print_header("Null / Missing Value Report")

    null_report = gdf[EXPECTED_FIELDS].isna().sum() if not missing_fields else gdf.isna().sum()
    null_report = null_report[null_report > 0].sort_values(ascending=False)

    if len(null_report) == 0:
        print("No null values found in checked fields.")
    else:
        print(null_report)

    # ---------------------------------------------------------------------
    # 10. Export final GeoPackage
    # ---------------------------------------------------------------------
    print_header("Exporting final_metrics.gpkg")

    OUTPUT_GPKG.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_GPKG.exists():
        OUTPUT_GPKG.unlink()

    gdf.to_file(OUTPUT_GPKG, layer="final_metrics", driver="GPKG")

    print(f"Saved GeoPackage:\n{OUTPUT_GPKG}")

    # ---------------------------------------------------------------------
    # 11. Export final CSV without geometry
    # ---------------------------------------------------------------------
    print_header("Exporting final_metrics.csv")

    csv_df = gdf.drop(columns="geometry").copy()
    csv_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved CSV:\n{OUTPUT_CSV}")

    # ---------------------------------------------------------------------
    # 12. Final summary
    # ---------------------------------------------------------------------
    print_header("Final Summary")

    print(f"Final row count: {len(gdf):,}")
    print(f"Final CRS: {gdf.crs}")
    print(f"Final fields: {len(gdf.columns):,}")


if __name__ == "__main__":
    main()