from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scoring import SCORING_PROFILES, score_parcel, score_many
from schemas import ScoreRequest, RankRequest


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "scored_metrics.csv"

def load_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Could not find scored metrics CSV at: {DATA_PATH}")
    return pd.read_csv(DATA_PATH)

parcels_df = load_data()

app = FastAPI(
    title="TerraScope API",
    description="Small API for TerraScope parcel suitability scoring and ranking.",
    version="0.1.0",
)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        FRONTEND_ORIGIN,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_parcels() -> list[dict[str, Any]]:
    if not parcels_df.exists():
        raise FileNotFoundError(
            f"Missing backend data file: {DATA_PATH}. "
            "Copy data/processed/scored_metrics.csv to backend/data/scored_metrics.csv"
        )

    df = pd.read_csv(parcels_df)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/profiles")
def get_profiles() -> dict[str, Any]:
    return {
        "default_profile": "residential_homestead",
        "profiles": [
            {
                "key": key,
                "display_name": value["display_name"],
                "weights": value["weights"],
                "constraints": value["constraints"],
            }
            for key, value in SCORING_PROFILES.items()
        ],
    }


@app.get("/parcels/{unit_id}")
def get_parcel(unit_id: str) -> dict[str, Any]:
    parcels = load_parcels()

    for parcel in parcels:
        if str(parcel.get("unit_id")) == str(unit_id):
            return parcel

    raise HTTPException(status_code=404, detail=f"Parcel not found: {unit_id}")


@app.post("/score")
def score(request: ScoreRequest) -> dict[str, Any]:
    parcels = load_parcels()

    try:
        scored = score_many(
            parcels=parcels,
            profile_key=request.profile,
            custom_weights=request.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    scored = sorted(scored, key=lambda row: row["api_score"], reverse=True)

    return {
        "profile": request.profile,
        "count": len(scored),
        "results": scored[: request.limit],
    }


@app.post("/rank")
def rank(request: RankRequest) -> dict[str, Any]:
    parcels = load_parcels()

    try:
        scored = score_many(
            parcels=parcels,
            profile_key=request.profile,
            custom_weights=request.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    filtered = []

    for row in scored:
        if request.min_score is not None and row["api_score"] < request.min_score:
            continue

        if request.min_area_acres is not None:
            if float(row.get("area_acres") or 0) < request.min_area_acres:
                continue

        if request.max_floodplain_pct is not None:
            if float(row.get("floodplain_pct") or 0) > request.max_floodplain_pct:
                continue

        if request.max_wetland_pct is not None:
            if float(row.get("wetland_pct") or 0) > request.max_wetland_pct:
                continue

        if request.max_avg_slope_pct is not None:
            if float(row.get("avg_slope_pct") or 0) > request.max_avg_slope_pct:
                continue

        if request.max_distance_to_road_m is not None:
            if float(row.get("distance_to_nearest_road_m") or 0) > request.max_distance_to_road_m:
                continue

        if request.max_distance_to_town_km is not None:
            if float(row.get("distance_to_nearest_town_km") or 0) > request.max_distance_to_town_km:
                continue

        if request.stream_present is not None:
            value = row.get("stream_present")
            if isinstance(value, str):
                value = value.strip().lower() in ["true", "1", "yes", "y"]
            else:
                value = bool(value)

            if value != request.stream_present:
                continue

        filtered.append(row)

    filtered = sorted(filtered, key=lambda row: row["api_score"], reverse=True)

    return {
        "profile": request.profile,
        "count": len(filtered),
        "results": filtered[: request.limit],
    }

@app.get("/")
def root():
    return {
        "name": "TerraScope API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_file_exists": DATA_PATH.exists(),
        "data_file": str(DATA_PATH)
    }

@app.post("/parcels/{unit_id}/score")
def score_single_parcel(unit_id: str, request: ScoreRequest) -> dict[str, Any]:
    parcels = load_parcels()

    for parcel in parcels:
        if str(parcel.get("unit_id")) == str(unit_id):
            try:
                return score_parcel(
                    parcel=parcel,
                    profile_key=request.profile,
                    custom_weights=request.weights,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

    raise HTTPException(status_code=404, detail=f"Parcel not found: {unit_id}")
