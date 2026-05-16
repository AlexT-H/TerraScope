from pathlib import Path
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data/interim/analysis_units_with_acres_26915.gpkg"
INPUT_LAYER = "analysis_units"

OUTPUT_FILE = PROJECT_ROOT / "data/interim/parcels_zoning_26915.gpkg"
OUTPUT_LAYER = "parcels_zoning"

TARGET_CRS = "EPSG:26915"


def clean_zoning_value(value):
    """
    Standardize zoning text values.
    Converts blanks, null-like values, and zeros to None.
    """
    if value is None:
        return None

    value = str(value).strip().upper()

    if value in ["", "NONE", "NULL", "NAN", "0", "<NA>"]:
        return None

    return value


def classify_zoning(zoning_code):

    z = clean_zoning_value(zoning_code)

    if z is None:
        return "Unknown"

    if z == "CITY":
        return "Municipal Jurisdiction"

    if z == "R":
        return "Residential"

    if z == "A":
        return "Agricultural"

    if z == "B":
        return "Commercial / Business"

    if z == "G":
        return "General / Higher Intensity"

    if z == "W":
        return "Rural / Open Land"

    if z in ["O", "P", "T", "Y"]:
        return "Other County Zoning"

    return "Other / Unclassified"


def make_zoning_context(category):
    """
    Adds a plain-English context field for popups and documentation.
    """
    context = {
        "Municipal Jurisdiction": (
            "Parcel appears to be inside a city or municipal zoning area; "
            "county zoning should not be treated as the final authority."
        ),
        "Residential": "Residential zoning context.",
        "Agricultural": "Agricultural or rural land-use context.",
        "Commercial / Business": "Commercial or business zoning context.",
        "General / Higher Intensity": "General or potentially higher-intensity zoning context.",
        "Rural / Open Land": "Rural, open-land, or low-intensity zoning context.",
        "Other County Zoning": "County zoning code present, but exact district meaning needs verification.",
        "Other / Unclassified": "Zoning value does not match the current TerraScope lookup.",
        "Unknown": "No usable zoning value was found.",
    }

    return context.get(category, "No zoning context available.")


def get_existing_column(gdf, possible_names):
    """
    Returns the first matching column from possible_names.
    Case-insensitive.
    """
    lower_to_actual = {col.lower(): col for col in gdf.columns}

    for name in possible_names:
        match = lower_to_actual.get(name.lower())
        if match:
            return match

    return None


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    print(f"Reading: {INPUT_FILE}")
    parcels = gpd.read_file(INPUT_FILE, layer=INPUT_LAYER)

    if parcels.empty:
        raise RuntimeError("Input parcel layer is empty.")

    if parcels.crs is None:
        raise RuntimeError("Input parcel layer has no CRS. Fix CRS before continuing.")

    if parcels.crs.to_string() != TARGET_CRS:
        print(f"Reprojecting from {parcels.crs} to {TARGET_CRS}")
        parcels = parcels.to_crs(TARGET_CRS)

    zoning_1_col = get_existing_column(parcels, ["zoning_1", "Zoning1"])
    zoning_2_col = get_existing_column(parcels, ["zoning_2", "Zoning2"])

    if zoning_1_col is None and zoning_2_col is None:
        raise RuntimeError(
            "No zoning fields found. Expected zoning_1/Zoning1 or zoning_2/Zoning2."
        )

    if zoning_1_col:
        parcels["zoning_1_clean"] = parcels[zoning_1_col].apply(clean_zoning_value)
    else:
        parcels["zoning_1_clean"] = None

    if zoning_2_col:
        parcels["zoning_2_clean"] = parcels[zoning_2_col].apply(clean_zoning_value)
    else:
        parcels["zoning_2_clean"] = None

    parcels["primary_zoning"] = parcels["zoning_1_clean"].fillna(parcels["zoning_2_clean"])
    parcels["zoning_category"] = parcels["primary_zoning"].apply(classify_zoning)
    parcels["zoning_context"] = parcels["zoning_category"].apply(make_zoning_context)
    parcels["has_zoning"] = parcels["primary_zoning"].notna()

    candidate_keep_cols = [
        "unit_id",
        "pid",
        "pid_alt",
        "parcel_number",
        "split_parcel_number",
        "parcel_acres",
        "parcel_acres_round",
        "area_sq_m",
        "primary_zoning",
        "zoning_1_clean",
        "zoning_2_clean",
        "zoning_category",
        "zoning_context",
        "has_zoning",
        "geometry",
    ]

    keep_cols = [col for col in candidate_keep_cols if col in parcels.columns]
    zoning = parcels[keep_cols].copy()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing: {OUTPUT_FILE}")
    zoning.to_file(
        OUTPUT_FILE,
        layer=OUTPUT_LAYER,
        driver="GPKG",
    )

    print("Done.")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Output layer: {OUTPUT_LAYER}")
    print(f"CRS: {zoning.crs}")
    print(f"Parcel count: {len(zoning)}")
    print()
    print("Zoning category counts:")
    print(zoning["zoning_category"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
