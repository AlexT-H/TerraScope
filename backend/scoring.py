import math
from typing import Any


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except Exception:
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def classify_suitability(score: float) -> str:
    if score >= 80:
        return "Very High"
    if score >= 65:
        return "High"
    if score >= 50:
        return "Moderate"
    if score >= 35:
        return "Low"
    return "Very Low"


def weighted_score(parcel: dict[str, Any], weights: dict[str, float]) -> float:
    total = 0.0
    for score_field, weight in weights.items():
        total += safe_float(parcel.get(score_field), 0.0) * weight
    return round(clamp(total), 2)


def apply_constraints(
    parcel: dict[str, Any],
    raw_score: float,
    constraints: dict[str, float],
) -> dict[str, Any]:
    floodplain_pct = safe_float(parcel.get("floodplain_pct"), 0.0)
    wetland_pct = safe_float(parcel.get("wetland_pct"), 0.0)
    steep_pct = safe_float(parcel.get("pct_over_15_slope"), 0.0)

    notes = []

    if floodplain_pct > constraints.get("max_floodplain_pct", 100):
        notes.append(f"Floodplain exceeds {constraints['max_floodplain_pct']}%")

    if wetland_pct > constraints.get("max_wetland_pct", 100):
        notes.append(f"Wetland exceeds {constraints['max_wetland_pct']}%")

    if steep_pct > constraints.get("max_pct_over_15_slope", 100):
        notes.append(f"Steep slope exceeds {constraints['max_pct_over_15_slope']}%")

    constrained = len(notes) > 0

    if constrained:
        final_score = min(raw_score, 40.0)
    else:
        final_score = raw_score

    return {
        "score": round(clamp(final_score), 2),
        "raw_score": round(clamp(raw_score), 2),
        "class": classify_suitability(final_score),
        "constraint_flag": constrained,
        "constraint_notes": "; ".join(notes) if notes else "None",
    }


def score_parcel(
    parcel: dict[str, Any],
    profile_key: str,
    custom_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    if profile_key not in SCORING_PROFILES:
        raise ValueError(f"Unknown profile: {profile_key}")

    profile = SCORING_PROFILES[profile_key]
    weights = custom_weights or profile["weights"]

    raw = weighted_score(parcel, weights)
    result = apply_constraints(parcel, raw, profile["constraints"])

    return {
        "unit_id": parcel.get("unit_id"),
        "profile": profile_key,
        "profile_label": profile["display_name"],
        **result,
        "breakdown": {
            field: {
                "value": safe_float(parcel.get(field), 0.0),
                "weight": weight,
                "weighted_value": round(safe_float(parcel.get(field), 0.0) * weight, 2),
            }
            for field, weight in weights.items()
        },
    }


def score_many(
    parcels: list[dict[str, Any]],
    profile_key: str,
    custom_weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    results = []

    for parcel in parcels:
        scored = score_parcel(parcel, profile_key, custom_weights)
        results.append({
            **parcel,
            "api_score": scored["score"],
            "api_raw_score": scored["raw_score"],
            "api_class": scored["class"],
            "api_constraint_flag": scored["constraint_flag"],
            "api_constraint_notes": scored["constraint_notes"],
            "api_breakdown": scored["breakdown"],
        })

    return results
