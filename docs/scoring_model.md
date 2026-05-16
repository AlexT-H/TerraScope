# Scoring Model

## Overview

The TerraScope scoring model converts parcel-level GIS metrics into normalized suitability scores. These scores support comparison across multiple land-use profiles and user-defined custom weighting.

The model is designed for exploratory screening. It is transparent, reproducible, and intended to support further review rather than replace professional due diligence.

---

## Input Dataset

The scoring model uses the cleaned final metrics dataset:

```text
data/processed/final_metrics.gpkg
```

Each row represents one parcel and contains terrain, hydrology, floodplain, wetland, access, proximity, acreage, and vegetation metrics.

---

## Output Datasets

The scoring script creates:

```text
data/processed/scored_parcels.gpkg
data/processed/scored_metrics.csv
```

The GeoPackage supports QGIS review and web map preparation. The CSV supports backend scoring, ranking, tabular review, and score debugging.

---

## Scoring Process

The model follows this process:

```text
read cleaned parcel metrics
convert raw metrics into normalized component scores
apply profile-specific weights
apply constraint rules
create final profile scores
assign suitability classes
export scored spatial and tabular outputs
```

---

## Component Scores

### Slope Score

Field:

```text
slope_score
```

Source metric:

```text
terrain_score
```

The slope score rewards parcels with more usable terrain and penalizes parcels dominated by steep slopes.

### Access Score

Field:

```text
access_score
```

Source metric:

```text
distance_to_nearest_road_m
```

Current rule:

```text
0 meters from road = 100
2,000 meters or more from road = 0
```

### Low Access Score

Field:

```text
low_access_score
```

Source metric:

```text
distance_to_nearest_road_m
```

Current rule:

```text
0 meters from road = 0
2,000 meters or more from road = 100
```

This score represents remoteness and is used by the conservation profile.

### Proximity Score

Field:

```text
proximity_score
```

Source metric:

```text
distance_to_nearest_town_km
```

Current rule:

```text
0 kilometers from town/service center = 100
30 kilometers or more from town/service center = 0
```

### Risk Score

Field:

```text
risk_score
```

Source metrics:

```text
floodplain_pct
wetland_pct
```

Formula:

```text
risk_penalty = floodplain_pct * 0.60 + wetland_pct * 0.40
risk_score = 100 - risk_penalty
```

### Vegetation Score

Field:

```text
vegetation_score
```

Source metric:

```text
avg_ndvi
```

This score represents relative vegetation density/health.

### Acreage Score

Field:

```text
acreage_score
```

Source metric:

```text
area_acres
```

Current rule:

```text
0 acres = 0
50 acres or more = 100
```

### Water Habitat Score

Field:

```text
water_habitat_score
```

Source metrics:

```text
stream_present
polygon_water_present
water_pct
```

This score treats streams and water features as positive habitat indicators.

### Wetland Habitat Score

Field:

```text
wetland_habitat_score
```

Source metric:

```text
wetland_pct
```

This score treats wetland presence as potential conservation value.

### Terrain Variety Score

Field:

```text
terrain_variety_score
```

Source metrics:

```text
pct_under_5_slope
pct_5_to_15_slope
pct_over_15_slope
```

This score rewards parcels with a useful mix of terrain conditions.

---

## Preset Suitability Profiles

### Agriculture / Open Land

Weights:

```text
slope_score       = 0.25
vegetation_score  = 0.25
acreage_score     = 0.20
access_score      = 0.15
risk_score        = 0.15
```

Constraint thresholds:

```text
floodplain_pct <= 35
wetland_pct <= 35
pct_over_15_slope <= 45
```

### Residential / Homestead

Weights:

```text
slope_score       = 0.30
access_score      = 0.20
proximity_score   = 0.15
risk_score        = 0.25
vegetation_score  = 0.05
acreage_score     = 0.05
```

Constraint thresholds:

```text
floodplain_pct <= 20
wetland_pct <= 20
pct_over_15_slope <= 40
```

### Event Venue / Rural Tourism

Weights:

```text
access_score           = 0.25
proximity_score        = 0.20
terrain_variety_score  = 0.20
risk_score             = 0.20
acreage_score          = 0.10
vegetation_score       = 0.05
```

Constraint thresholds:

```text
floodplain_pct <= 20
wetland_pct <= 20
pct_over_15_slope <= 55
```

### Conservation / Habitat

Weights:

```text
vegetation_score       = 0.25
water_habitat_score    = 0.25
wetland_habitat_score  = 0.15
acreage_score          = 0.15
low_access_score       = 0.10
terrain_variety_score  = 0.10
```

Constraint thresholds:

```text
floodplain_pct <= 100
wetland_pct <= 100
pct_over_15_slope <= 100
```

The conservation profile intentionally treats floodplains and wetlands as potential habitat value rather than only as development risk.

---

## Custom Profile Scoring

The web app supports session-only custom weights.

Available custom weight variables:

```text
slope_score
access_score
low_access_score
proximity_score
risk_score
vegetation_score
acreage_score
water_habitat_score
wetland_habitat_score
terrain_variety_score
```

Formula:

```text
custom_score = sum(component_score * custom_weight)
```

Custom weights can be normalized to 100% in the web interface.

---

## Constraint Handling

Constrained parcels remain visible but receive a capped score.

Current rule:

```text
constrained_score = min(raw_score, 40)
```

Constraint notes are stored in fields such as:

```text
residential_homestead_constraint_notes
event_venue_rural_tourism_constraint_notes
agriculture_open_land_constraint_notes
conservation_habitat_constraint_notes
```

---

## Suitability Classes

```text
80 - 100 = Very High
65 - 79  = High
50 - 64  = Moderate
35 - 49  = Low
0 - 34   = Very Low
```

---

## Backend Use

The backend loads scored parcel metrics and supports:

```text
profile listing
parcel lookup
ranked search
custom weighted scoring
single parcel score breakdown
```

The backend does not perform heavy GIS processing. Raster processing, overlays, and distance calculations remain offline pipeline tasks.

---

## Limitations

The scoring model is transparent and reproducible, but it is not a professional site assessment.

Limitations include:

```text
public data may be incomplete or outdated
parcel boundaries may not represent development feasibility
zoning is not fully integrated into the score
soil productivity is not modeled
utility access is not modeled
road distance does not guarantee legal access
floodplain and wetland data require authoritative review
NDVI varies seasonally
custom weights are user-defined assumptions
```

---

## Responsible Framing

```text
TerraScope is an exploratory geospatial decision-support tool. It compares rural land suitability scenarios using public spatial data and user-defined assumptions. It should not replace professional site assessment, legal review, environmental review, engineering review, or local planning guidance.
```
