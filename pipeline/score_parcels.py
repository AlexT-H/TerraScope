from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_GPKG = BASE_DIR / "data" / "processed" / "final_metrics.gpkg"
OUTPUT_GPKG = BASE_DIR / "data" / "processed" / "scored_parcels.gpkg"
OUTPUT_CSV = BASE_DIR / "data" / "processed" / "scored_metrics.csv"

TARGET_CRS = "EPSG:26915"


SCORING_PROFILES = {
    "agriculture_open_land": {
        "display_name": "Agriculture / Open Land",
        "weights": {
            "slope_score": 0.25,
            "vegetation_score": 0.25,
            "acreage_score": 0.20,
            "access_score": 0.15,
            "risk_score": 0.15,
        },
        "constraints": {
            "max_floodplain_pct": 35,
            "max_wetland_pct": 35,
            "max_pct_over_15_slope": 45,
        },
    },
    "residential_homestead": {
        "display_name": "Residential / Homestead",
        "weights": {
            "slope_score": 0.30,
            "access_score": 0.20,
            "proximity_score": 0.15,
            "risk_score": 0.25,
            "vegetation_score": 0.05,
            "acreage_score": 0.05,
        },
        "constraints": {
            "max_floodplain_pct": 20,
            "max_wetland_pct": 20,
            "max_pct_over_15_slope": 40,
        },
    },
    "event_venue_rural_tourism": {
        "display_name": "Event Venue / Rural Tourism",
        "weights": {
            "access_score": 0.25,
            "proximity_score": 0.20,
            "terrain_variety_score": 0.20,
            "risk_score": 0.20,
            "acreage_score": 0.10,
            "vegetation_score": 0.05,
        },
        "constraints": {
            "max_floodplain_pct": 20,
            "max_wetland_pct": 20,
            "max_pct_over_15_slope": 55,
        },
    },
    "conservation_habitat": {
        "display_name": "Conservation / Habitat",
        "weights": {
            "vegetation_score": 0.25,
            "water_habitat_score": 0.25,
            "wetland_habitat_score": 0.15,
            "acreage_score": 0.15,
            "low_access_score": 0.10,
            "terrain_variety_score": 0.10,
        },
        "constraints": {
            "max_floodplain_pct": 100,
            "max_wetland_pct": 100,
            "max_pct_over_15_slope": 100,
        },
    },
}


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            "Missing required fields in final_metrics.gpkg:\n"
            + "\n".join(f"  - {col}" for col in missing)
            + "\n\nGo back to Phase 3 or the relevant Phase 2 script and confirm these fields were created."
        )


def numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)

    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def clip_0_100(series: pd.Series) -> pd.Series:
    return series.clip(lower=0, upper=100)


def score_inverse_linear(
    values: pd.Series,
    best_value: float,
    worst_value: float,
) -> pd.Series:
    """
    Higher score for smaller values.
    Example: distance to road.
    """
    values = pd.to_numeric(values, errors="coerce")
    score = 100 * (worst_value - values) / (worst_value - best_value)
    return clip_0_100(score.fillna(0))


def score_linear(
    values: pd.Series,
    worst_value: float,
    best_value: float,
) -> pd.Series:
    """
    Higher score for larger values.
    Example: acreage.
    """
    values = pd.to_numeric(values, errors="coerce")
    score = 100 * (values - worst_value) / (best_value - worst_value)
    return clip_0_100(score.fillna(0))


def weighted_sum(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    total = pd.Series(0.0, index=df.index)

    for score_col, weight in weights.items():
        if score_col not in df.columns:
            print(f"WARNING: Missing score column '{score_col}'. Treating as 0.")
            component = pd.Series(0.0, index=df.index)
        else:
            component = numeric_series(df, score_col, default=0)

        total += component * weight

    return clip_0_100(total)


def classify_suitability(score: float) -> str:
    if pd.isna(score):
        return "Unknown"
    if score >= 80:
        return "Very High"
    if score >= 65:
        return "High"
    if score >= 50:
        return "Moderate"
    if score >= 35:
        return "Low"
    return "Very Low"


def apply_constraints(
    df: pd.DataFrame,
    constraints: dict[str, float],
    raw_score_col: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Apply profile hard constraints.

    Constrained parcels are not removed.
    Their score is capped at 40 so users can still see the parcel and understand
    why it was penalized.
    """
    constrained = pd.Series(False, index=df.index)
    notes = pd.Series("", index=df.index, dtype="object")

    floodplain = numeric_series(df, "floodplain_pct", default=0)
    wetland = numeric_series(df, "wetland_pct", default=0)
    steep = numeric_series(df, "pct_over_15_slope", default=0)

    max_floodplain = constraints.get("max_floodplain_pct", 100)
    max_wetland = constraints.get("max_wetland_pct", 100)
    max_steep = constraints.get("max_pct_over_15_slope", 100)

    floodplain_fail = floodplain > max_floodplain
    wetland_fail = wetland > max_wetland
    steep_fail = steep > max_steep

    constrained = constrained | floodplain_fail | wetland_fail | steep_fail

    notes = np.where(
        floodplain_fail,
        notes + f"Floodplain exceeds {max_floodplain}%; ",
        notes,
    )
    notes = pd.Series(notes, index=df.index, dtype="object")

    notes = np.where(
        wetland_fail,
        notes + f"Wetland exceeds {max_wetland}%; ",
        notes,
    )
    notes = pd.Series(notes, index=df.index, dtype="object")

    notes = np.where(
        steep_fail,
        notes + f"Steep slope exceeds {max_steep}%; ",
        notes,
    )
    notes = pd.Series(notes, index=df.index, dtype="object")

    raw_score = numeric_series(df, raw_score_col, default=0)
    constrained_score = raw_score.copy()

    constrained_score = np.where(
        constrained,
        np.minimum(constrained_score, 40),
        constrained_score,
    )

    constrained_score = pd.Series(constrained_score, index=df.index)
    constrained_score = clip_0_100(constrained_score)

    notes = pd.Series(notes, index=df.index, dtype="object").str.strip()
    notes = notes.replace("", "None")

    return constrained_score, constrained, notes


def add_component_scores(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print_header("Creating Component Scores")

    require_columns(
        gdf,
        [
            "area_acres",
            "pct_under_5_slope",
            "pct_5_to_15_slope",
            "pct_over_15_slope",
            "terrain_score",
            "distance_to_nearest_road_m",
            "distance_to_nearest_town_km",
            "water_pct",
            "wetland_pct",
            "floodplain_pct",
            "vegetation_score",
        ],
    )

    # Slope score:
    # Uses your Phase 2 terrain_score directly.
    gdf["slope_score"] = clip_0_100(numeric_series(gdf, "terrain_score", default=0))

    # Access score:
    # Closer to road is better.
    # 0 m = 100, 2000+ m = 0.
    gdf["access_score"] = score_inverse_linear(
        numeric_series(gdf, "distance_to_nearest_road_m", default=np.nan),
        best_value=0,
        worst_value=2000,
    )

    # Low access score:
    # Farther from road is better for conservation.
    # 0 m = 0, 2000+ m = 100.
    gdf["low_access_score"] = score_linear(
        numeric_series(gdf, "distance_to_nearest_road_m", default=np.nan),
        worst_value=0,
        best_value=2000,
    )

    # Proximity score:
    # Closer to town/service center is better for residential and venue profiles.
    # 0 km = 100, 30+ km = 0.
    gdf["proximity_score"] = score_inverse_linear(
        numeric_series(gdf, "distance_to_nearest_town_km", default=np.nan),
        best_value=0,
        worst_value=30,
    )

    # Risk score:
    # Higher score means less floodplain/wetland conflict.
    floodplain_pct = numeric_series(gdf, "floodplain_pct", default=0).clip(0, 100)
    wetland_pct = numeric_series(gdf, "wetland_pct", default=0).clip(0, 100)

    risk_penalty = (floodplain_pct * 0.6) + (wetland_pct * 0.4)
    gdf["risk_score"] = clip_0_100(100 - risk_penalty)

    # Vegetation score:
    # Uses Phase 2 vegetation_score directly.
    gdf["vegetation_score"] = clip_0_100(
        numeric_series(gdf, "vegetation_score", default=0)
    )

    # Acreage score:
    # Larger parcels score higher up to 50 acres.
    gdf["acreage_score"] = score_linear(
        numeric_series(gdf, "area_acres", default=0),
        worst_value=0,
        best_value=50,
    )

    # Water habitat score:
    # For conservation/habitat, streams and water bodies are positive.
    stream_present = (
        gdf["stream_present"].fillna(False).astype(bool)
        if "stream_present" in gdf.columns
        else pd.Series(False, index=gdf.index)
    )
    polygon_water_present = (
        gdf["polygon_water_present"].fillna(False).astype(bool)
        if "polygon_water_present" in gdf.columns
        else pd.Series(False, index=gdf.index)
    )
    water_pct = numeric_series(gdf, "water_pct", default=0).clip(0, 100)

    gdf["water_habitat_score"] = 0.0
    gdf.loc[stream_present, "water_habitat_score"] += 35
    gdf.loc[polygon_water_present, "water_habitat_score"] += 35
    gdf["water_habitat_score"] += score_linear(water_pct, 0, 20) * 0.30
    gdf["water_habitat_score"] = clip_0_100(gdf["water_habitat_score"])

    # Wetland habitat score:
    # Wetlands are a development constraint but can be habitat value.
    gdf["wetland_habitat_score"] = score_linear(wetland_pct, 0, 30)

    # Terrain variety score:
    # Useful for venue/tourism/conservation profiles.
    pct_gentle = numeric_series(gdf, "pct_under_5_slope", default=0).clip(0, 100)
    pct_moderate = numeric_series(gdf, "pct_5_to_15_slope", default=0).clip(0, 100)
    pct_steep = numeric_series(gdf, "pct_over_15_slope", default=0).clip(0, 100)

    terrain_variety = (
        pct_moderate * 0.55
        + pct_gentle * 0.30
        + np.minimum(pct_steep, 20) * 0.75
    )

    gdf["terrain_variety_score"] = clip_0_100(terrain_variety)

    component_cols = [
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

    print("Created component scores:")
    for col in component_cols:
        print(
            f"  {col}: min={gdf[col].min():.2f}, "
            f"mean={gdf[col].mean():.2f}, "
            f"max={gdf[col].max():.2f}"
        )

    return gdf


def add_profile_scores(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print_header("Creating Profile Scores")

    for profile_key, profile in SCORING_PROFILES.items():
        print(f"\nScoring profile: {profile['display_name']}")

        weights = profile["weights"]
        constraints = profile["constraints"]

        raw_col = f"{profile_key}_raw_score"
        final_col = f"{profile_key}_score"
        class_col = f"{profile_key}_class"
        constrained_col = f"{profile_key}_constraint_flag"
        notes_col = f"{profile_key}_constraint_notes"

        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0):
            print(
                f"WARNING: Weights for {profile_key} add to {weight_sum:.3f}, not 1.0."
            )

        gdf[raw_col] = weighted_sum(gdf, weights)

        final_score, constrained, notes = apply_constraints(
            df=gdf,
            constraints=constraints,
            raw_score_col=raw_col,
        )

        gdf[final_col] = final_score
        gdf[constrained_col] = constrained
        gdf[notes_col] = notes
        gdf[class_col] = gdf[final_col].apply(classify_suitability)

        print(
            f"  {final_col}: min={gdf[final_col].min():.2f}, "
            f"mean={gdf[final_col].mean():.2f}, "
            f"max={gdf[final_col].max():.2f}"
        )
        print(f"  constrained parcels: {gdf[constrained_col].sum():,}")

    # Default map score for first web-map styling.
    default_profile = "residential_homestead"
    gdf["default_profile"] = default_profile
    gdf["overall_suitability_score"] = gdf[f"{default_profile}_score"]
    gdf["suitability_class"] = gdf[f"{default_profile}_class"]

    return gdf


def create_score_summary_csv(gdf: gpd.GeoDataFrame, output_csv: Path) -> None:
    csv_df = gdf.drop(columns="geometry").copy()
    csv_df.to_csv(output_csv, index=False)


def print_top_examples(gdf: gpd.GeoDataFrame, profile_key: str, n: int = 10) -> None:
    score_col = f"{profile_key}_score"

    if score_col not in gdf.columns:
        return

    cols_to_show = [
        "unit_id",
        "area_acres",
        score_col,
        f"{profile_key}_class",
        "slope_score",
        "access_score",
        "proximity_score",
        "risk_score",
        "vegetation_score",
        "acreage_score",
    ]

    existing_cols = [col for col in cols_to_show if col in gdf.columns]

    print_header(f"Top {n} Parcels: {profile_key}")
    print(
        gdf[existing_cols]
        .sort_values(score_col, ascending=False)
        .head(n)
        .to_string(index=False)
    )


def main() -> None:
    print_header("TerraScope Phase 4: Scoring Model")

    if not INPUT_GPKG.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_GPKG}")

    print(f"Reading:\n{INPUT_GPKG}")
    gdf = gpd.read_file(INPUT_GPKG)

    print(f"\nRows loaded: {len(gdf):,}")
    print(f"Input CRS: {gdf.crs}")

    if gdf.crs is None:
        raise ValueError("Input has no CRS. Fix final_metrics.gpkg before scoring.")

    if gdf.crs.to_string() != TARGET_CRS:
        print(f"Reprojecting from {gdf.crs} to {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)

    require_columns(gdf, ["unit_id"])

    gdf = add_component_scores(gdf)
    gdf = add_profile_scores(gdf)

    print_header("Exporting Scored Outputs")

    OUTPUT_GPKG.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_GPKG.exists():
        OUTPUT_GPKG.unlink()

    gdf.to_file(OUTPUT_GPKG, layer="scored_parcels", driver="GPKG")
    print(f"Saved GeoPackage:\n{OUTPUT_GPKG}")

    create_score_summary_csv(gdf, OUTPUT_CSV)
    print(f"Saved CSV:\n{OUTPUT_CSV}")

    for profile_key in SCORING_PROFILES:
        print_top_examples(gdf, profile_key, n=10)

    print_header("Finished")

    print("Phase 4 scoring complete.")
    print("\nMain outputs:")
    print(f"  {OUTPUT_GPKG}")
    print(f"  {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
