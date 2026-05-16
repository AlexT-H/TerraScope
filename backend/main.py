from pathlib import Path
import os
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# =============================================================================
# TerraScope FastAPI Backend
# =============================================================================
#
# Expected project structure:
#
# backend/
# ├── main.py
# └── data/
#     └── scored_metrics.csv
#
# Local run:
#   cd backend
#   python -m uvicorn main:app --reload
#
# Vercel:
#   Root Directory: backend
#   backend/vercel.json routes all requests to main.py
#
# =============================================================================


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "scored_metrics.csv"


app = FastAPI(
    title="TerraScope API",
    description="Parcel suitability scoring, ranked search, and parcel detail API.",
    version="1.0.0",
)


# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
#
# Local frontend:
#   http://localhost:5173
#
# Production:
#   Set FRONTEND_ORIGIN in Vercel backend project settings, for example:
#   https://your-terrascope-frontend.vercel.app
#
# Temporary test value:
#   FRONTEND_ORIGIN=*
#
# -----------------------------------------------------------------------------

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

if FRONTEND_ORIGIN == "*":
    allowed_origins = ["*"]
    allow_credentials = False
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        FRONTEND_ORIGIN,
    ]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Suitability Profile Configuration
# -----------------------------------------------------------------------------

SCORING_PROFILES: dict[str, dict[str, Any]] = {
    "residential_homestead": {
        "display_name": "Residential / Homestead",
        "score_field": "residential_homestead_score",
        "class_field": "residential_homestead_class",
        "constraint_notes_field": "residential_homestead_constraint_notes",
        "weights": {
            "slope_score": 0.30,
            "access_score": 0.20,
            "proximity_score": 0.15,
            "risk_score": 0.25,
            "vegetation_score": 0.05,
            "acreage_score": 0.05,
        },
    },
    "agriculture_open_land": {
        "display_name": "Agriculture / Open Land",
        "score_field": "agriculture_open_land_score",
        "class_field": "agriculture_open_land_class",
        "constraint_notes_field": "agriculture_open_land_constraint_notes",
        "weights": {
            "slope_score": 0.25,
            "vegetation_score": 0.25,
            "acreage_score": 0.20,
            "access_score": 0.15,
            "risk_score": 0.15,
        },
    },
    "event_venue_rural_tourism": {
        "display_name": "Event Venue / Rural Tourism",
        "score_field": "event_venue_rural_tourism_score",
        "class_field": "event_venue_rural_tourism_class",
        "constraint_notes_field": "event_venue_rural_tourism_constraint_notes",
        "weights": {
            "access_score": 0.25,
            "proximity_score": 0.20,
            "terrain_variety_score": 0.20,
            "risk_score": 0.20,
            "acreage_score": 0.10,
            "vegetation_score": 0.05,
        },
    },
    "conservation_habitat": {
        "display_name": "Conservation / Habitat",
        "score_field": "conservation_habitat_score",
        "class_field": "conservation_habitat_class",
        "constraint_notes_field": "conservation_habitat_constraint_notes",
        "weights": {
            "vegetation_score": 0.25,
            "water_habitat_score": 0.25,
            "wetland_habitat_score": 0.15,
            "acreage_score": 0.15,
            "low_access_score": 0.10,
            "terrain_variety_score": 0.10,
        },
    },
}


DISPLAY_COLUMNS = [
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
    "watertype",
    "stream_present",
    "polygon_water_present",
    "water_pct",
    "wetland_present",
    "wetland_pct",
    "floodplain_present",
    "floodplain_pct",
    "distance_to_nearest_road_m",
    "road_access_class",
    "nearest_town",
    "nearest_town_role",
    "distance_to_nearest_town_km",
    "avg_ndvi",
    "median_ndvi",
    "vegetation_class",
]


# -----------------------------------------------------------------------------
# Lazy Data Loading
# -----------------------------------------------------------------------------

_parcels_df: pd.DataFrame | None = None


def get_parcels_df() -> pd.DataFrame:
    global _parcels_df

    if _parcels_df is not None:
        return _parcels_df

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Could not find scored metrics CSV at: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH, low_memory=False)

    if "unit_id" not in df.columns:
        raise ValueError("scored_metrics.csv is missing required column: unit_id")

    df["unit_id"] = df["unit_id"].astype(str)

    _parcels_df = df
    return _parcels_df


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def clean_value(value: Any) -> Any:
    """Convert NumPy/Pandas values into JSON-safe Python values."""
    if value is None:
        return None

    if isinstance(value, (float, np.floating)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)

    if isinstance(value, (int, np.integer)):
        return int(value)

    if isinstance(value, (bool, np.bool_)):
        return bool(value)

    if pd.isna(value):
        return None

    return value


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: clean_value(value) for key, value in record.items()}


def numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def classify_score(score: float | int | None) -> str:
    if score is None:
        return "Unknown"

    try:
        score_float = float(score)
    except (TypeError, ValueError):
        return "Unknown"

    if score_float >= 80:
        return "Very High"
    if score_float >= 65:
        return "High"
    if score_float >= 50:
        return "Moderate"
    if score_float >= 35:
        return "Low"
    return "Very Low"


def get_profile(profile_key: str | None) -> dict[str, Any]:
    if not profile_key:
        return SCORING_PROFILES["residential_homestead"]

    if profile_key not in SCORING_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{profile_key}'. Valid options: {list(SCORING_PROFILES.keys())}",
        )

    return SCORING_PROFILES[profile_key]


def calculate_weighted_score_for_df(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    total = pd.Series(0.0, index=df.index)

    for field, weight in weights.items():
        weight_float = float(weight or 0)
        if weight_float <= 0:
            continue

        component = numeric_series(df, field, default=0.0)
        total += component * weight_float

    return total.clip(lower=0, upper=100)


def calculate_weighted_score_for_record(record: dict[str, Any], weights: dict[str, float]) -> float:
    total = 0.0

    for field, weight in weights.items():
        try:
            component = float(record.get(field, 0) or 0)
            weight_float = float(weight or 0)
        except (TypeError, ValueError):
            component = 0.0
            weight_float = 0.0

        total += component * weight_float

    return max(0.0, min(100.0, total))


def extract_custom_weights(payload: dict[str, Any]) -> dict[str, float] | None:
    weights = payload.get("weights")

    if not isinstance(weights, dict) or not weights:
        return None

    clean_weights: dict[str, float] = {}

    for field, value in weights.items():
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            numeric_value = 0.0

        if numeric_value > 0:
            clean_weights[field] = numeric_value

    return clean_weights or None


def add_api_fields_to_record(
    record: dict[str, Any],
    profile_key: str,
    custom_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    profile = get_profile(profile_key)

    if custom_weights:
        api_score = calculate_weighted_score_for_record(record, custom_weights)
        api_class = classify_score(api_score)
        api_constraint_notes = "Custom profile score; preset constraints not applied."
    else:
        score_field = profile["score_field"]
        class_field = profile["class_field"]
        notes_field = profile["constraint_notes_field"]

        api_score = record.get(score_field)
        api_class = record.get(class_field) or classify_score(api_score)
        api_constraint_notes = record.get(notes_field, "None")

    record["api_profile"] = "custom" if custom_weights else profile_key
    record["api_profile_label"] = "Custom Suitability Profile" if custom_weights else profile["display_name"]
    record["api_score"] = clean_value(api_score)
    record["api_class"] = api_class
    record["api_constraint_notes"] = api_constraint_notes

    return clean_record(record)


def limited_record(row: pd.Series, extra_columns: list[str] | None = None) -> dict[str, Any]:
    columns = list(DISPLAY_COLUMNS)

    if extra_columns:
        for col in extra_columns:
            if col not in columns:
                columns.append(col)

    available = [col for col in columns if col in row.index]
    return row[available].to_dict()


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "TerraScope API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "base_dir": str(BASE_DIR),
        "data_path": str(DATA_PATH),
        "data_file_exists": DATA_PATH.exists(),
        "frontend_origin": FRONTEND_ORIGIN,
    }


@app.get("/debug-data")
def debug_data() -> dict[str, Any]:
    try:
        df = get_parcels_df()
        return {
            "status": "ok",
            "rows": int(len(df)),
            "columns_count": int(len(df.columns)),
            "columns_preview": list(df.columns[:30]),
            "data_file": str(DATA_PATH),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/profiles")
def profiles() -> dict[str, Any]:
    return {
        "default_profile": "residential_homestead",
        "profiles": [
            {
                "key": key,
                "display_name": profile["display_name"],
                "score_field": profile["score_field"],
                "class_field": profile["class_field"],
                "weights": profile["weights"],
            }
            for key, profile in SCORING_PROFILES.items()
        ],
    }


@app.get("/parcels/{unit_id}")
def get_parcel(unit_id: str, profile: str = "residential_homestead") -> dict[str, Any]:
    df = get_parcels_df()
    unit_id = str(unit_id)

    match = df[df["unit_id"].astype(str) == unit_id]

    if match.empty:
        raise HTTPException(status_code=404, detail=f"Parcel not found: {unit_id}")

    row = match.iloc[0]
    profile_config = get_profile(profile)

    extra_columns = [
        profile_config["score_field"],
        profile_config["class_field"],
        profile_config["constraint_notes_field"],
        "agriculture_open_land_score",
        "agriculture_open_land_class",
        "residential_homestead_score",
        "residential_homestead_class",
        "event_venue_rural_tourism_score",
        "event_venue_rural_tourism_class",
        "conservation_habitat_score",
        "conservation_habitat_class",
    ]

    record = limited_record(row, extra_columns=extra_columns)
    return add_api_fields_to_record(record, profile)


@app.post("/rank")
def rank_parcels(payload: dict[str, Any]) -> dict[str, Any]:
    df = get_parcels_df().copy()

    profile_key = payload.get("profile", "residential_homestead")
    profile = get_profile(profile_key)
    custom_weights = extract_custom_weights(payload)

    if custom_weights:
        df["_api_score"] = calculate_weighted_score_for_df(df, custom_weights)
        df["_api_class"] = df["_api_score"].apply(classify_score)
        df["_api_constraint_notes"] = "Custom profile score; preset constraints not applied."
        api_profile_label = "Custom Suitability Profile"
    else:
        score_field = profile["score_field"]
        class_field = profile["class_field"]
        notes_field = profile["constraint_notes_field"]

        if score_field not in df.columns:
            raise HTTPException(status_code=500, detail=f"Missing score field in data: {score_field}")

        df["_api_score"] = pd.to_numeric(df[score_field], errors="coerce").fillna(0)
        df["_api_class"] = df[class_field] if class_field in df.columns else df["_api_score"].apply(classify_score)
        df["_api_constraint_notes"] = df[notes_field] if notes_field in df.columns else "None"
        api_profile_label = profile["display_name"]

    min_score = payload.get("min_score")
    if min_score is not None:
        df = df[df["_api_score"] >= float(min_score)]

    min_area_acres = payload.get("min_area_acres")
    if min_area_acres is not None:
        df = df[numeric_series(df, "area_acres", default=0) >= float(min_area_acres)]

    max_floodplain_pct = payload.get("max_floodplain_pct")
    if max_floodplain_pct is not None:
        df = df[numeric_series(df, "floodplain_pct", default=0) <= float(max_floodplain_pct)]

    max_wetland_pct = payload.get("max_wetland_pct")
    if max_wetland_pct is not None:
        df = df[numeric_series(df, "wetland_pct", default=0) <= float(max_wetland_pct)]

    max_distance_to_road_m = payload.get("max_distance_to_road_m")
    if max_distance_to_road_m is not None:
        df = df[numeric_series(df, "distance_to_nearest_road_m", default=np.inf) <= float(max_distance_to_road_m)]

    max_distance_to_town_km = payload.get("max_distance_to_town_km")
    if max_distance_to_town_km is not None:
        df = df[numeric_series(df, "distance_to_nearest_town_km", default=np.inf) <= float(max_distance_to_town_km)]

    stream_present = payload.get("stream_present")
    if stream_present is not None and "stream_present" in df.columns:
        desired = bool(stream_present)
        stream_values = df["stream_present"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
        df = df[stream_values == desired]

    limit = int(payload.get("limit", 25))
    limit = max(1, min(limit, 500))

    df = df.sort_values("_api_score", ascending=False).head(limit)

    results: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        record = limited_record(
            row,
            extra_columns=[
                "_api_score",
                "_api_class",
                "_api_constraint_notes",
                profile["score_field"],
                profile["class_field"],
            ],
        )

        record["api_profile"] = "custom" if custom_weights else profile_key
        record["api_profile_label"] = api_profile_label
        record["api_score"] = clean_value(row["_api_score"])
        record["api_class"] = clean_value(row["_api_class"])
        record["api_constraint_notes"] = clean_value(row["_api_constraint_notes"])

        results.append(clean_record(record))

    return {
        "profile": "custom" if custom_weights else profile_key,
        "profile_label": api_profile_label,
        "count": len(results),
        "results": results,
    }


@app.post("/score")
def score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    df = get_parcels_df()

    profile_key = payload.get("profile", "residential_homestead")
    profile = get_profile(profile_key)
    custom_weights = extract_custom_weights(payload)

    if custom_weights:
        scores = calculate_weighted_score_for_df(df, custom_weights)
        profile_label = "Custom Suitability Profile"
    else:
        score_field = profile["score_field"]
        if score_field not in df.columns:
            raise HTTPException(status_code=500, detail=f"Missing score field in data: {score_field}")
        scores = pd.to_numeric(df[score_field], errors="coerce").fillna(0)
        profile_label = profile["display_name"]

    return {
        "profile": "custom" if custom_weights else profile_key,
        "profile_label": profile_label,
        "count": int(len(scores)),
        "min": clean_value(scores.min()),
        "max": clean_value(scores.max()),
        "mean": clean_value(scores.mean()),
        "median": clean_value(scores.median()),
    }


@app.post("/parcels/{unit_id}/score")
def score_parcel(unit_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    df = get_parcels_df()
    unit_id = str(unit_id)

    match = df[df["unit_id"].astype(str) == unit_id]

    if match.empty:
        raise HTTPException(status_code=404, detail=f"Parcel not found: {unit_id}")

    row = match.iloc[0]
    record = row.to_dict()

    profile_key = payload.get("profile", "residential_homestead")
    profile = get_profile(profile_key)
    custom_weights = extract_custom_weights(payload)

    weights = custom_weights if custom_weights else profile["weights"]
    score = calculate_weighted_score_for_record(record, weights)

    components = []

    for field, weight in weights.items():
        raw_value = clean_value(record.get(field, 0))
        try:
            contribution = float(raw_value or 0) * float(weight or 0)
        except (TypeError, ValueError):
            contribution = 0.0

        components.append(
            {
                "field": field,
                "value": raw_value,
                "weight": weight,
                "contribution": clean_value(contribution),
            }
        )

    return {
        "unit_id": unit_id,
        "profile": "custom" if custom_weights else profile_key,
        "profile_label": "Custom Suitability Profile" if custom_weights else profile["display_name"],
        "score": clean_value(score),
        "class": classify_score(score),
        "components": components,
    }
