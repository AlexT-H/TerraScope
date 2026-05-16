from pathlib import Path
import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data/interim/analysis_units_26915.gpkg"
INPUT_LAYER = "analysis_units"

OUTPUT_FILE = PROJECT_ROOT / "data/interim/analysis_units_with_acres_26915.gpkg"
OUTPUT_LAYER = "analysis_units"


SQ_METERS_PER_ACRE = 4046.8564224
TARGET_CRS = "EPSG:26915"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    print(f"Reading: {INPUT_FILE}")
    parcels = gpd.read_file(INPUT_FILE, layer=INPUT_LAYER)

    if parcels.empty:
        raise RuntimeError("Input parcel layer is empty.")

    print(f"Input CRS: {parcels.crs}")

    if parcels.crs is None:
        raise RuntimeError(
            "Input layer has no CRS. Fix the CRS before calculating acreage."
        )

    if parcels.crs.to_string() != TARGET_CRS:
        print(f"Reprojecting from {parcels.crs} to {TARGET_CRS}")
        parcels = parcels.to_crs(TARGET_CRS)

    print("Fixing invalid geometries if needed...")
    parcels["geometry"] = parcels.geometry.make_valid()

    before_count = len(parcels)
    parcels = parcels[
        parcels.geometry.notna() & ~parcels.geometry.is_empty
    ].copy()
    after_count = len(parcels)

    removed = before_count - after_count
    if removed > 0:
        print(f"Removed {removed} records with null or empty geometry.")

    print("Calculating acreage from geometry...")
    parcels["area_sq_m"] = parcels.geometry.area
    parcels["parcel_acres"] = parcels["area_sq_m"] / SQ_METERS_PER_ACRE
    parcels["parcel_acres_round"] = parcels["parcel_acres"].round(2)

    # Create a fallback ID Series that matches the parcel index
    fallback_ids = pd.Series(
        parcels.index.astype(str),
        index=parcels.index
    )

    # Make sure each parcel has a unit_id
    if "unit_id" not in parcels.columns:
        if "pid" in parcels.columns:
            parcels["unit_id"] = parcels["pid"]
        elif "parcel_number" in parcels.columns:
            parcels["unit_id"] = parcels["parcel_number"]
        elif "OBJECTID" in parcels.columns:
            parcels["unit_id"] = parcels["OBJECTID"].astype(str)
        else:
            parcels["unit_id"] = fallback_ids

    parcels["unit_id"] = parcels["unit_id"].astype("string")
    parcels["unit_id"] = parcels["unit_id"].fillna(fallback_ids)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing: {OUTPUT_FILE}")
    parcels.to_file(
        OUTPUT_FILE,
        layer=OUTPUT_LAYER,
        driver="GPKG",
    )

    print("Done.")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Output layer: {OUTPUT_LAYER}")
    print(f"Output CRS: {parcels.crs}")
    print(f"Parcel count: {len(parcels)}")
    print(f"Minimum acres: {parcels['parcel_acres'].min():,.4f}")
    print(f"Maximum acres: {parcels['parcel_acres'].max():,.4f}")
    print(f"Total acres: {parcels['parcel_acres'].sum():,.2f}")


if __name__ == "__main__":
    main()