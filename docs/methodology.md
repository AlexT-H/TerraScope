# Methodology

## Overview

TerraScope evaluates rural parcel suitability by transforming spatial datasets into parcel-level metrics, normalizing those metrics into component scores, and combining them into use-case-specific suitability profiles.

The methodology is organized around a separation of concerns:

```text
offline GIS processing = metric generation and scoring
PMTiles = fast map rendering
FastAPI = parcel lookup, scoring, and ranking
frontend = profile selection, custom weights, layer control, and interaction
```

This design keeps heavy geospatial processing outside the browser while still supporting interactive suitability exploration.

---

## Analysis Unit

The parcel is the analysis unit. Each parcel receives geometry-derived and overlay-derived attributes that describe terrain, access, flood/wetland exposure, vegetation, proximity, and habitat context.

---

## Coordinate Reference Systems

### Analysis CRS

The Franklin County implementation uses:

```text
EPSG:26915
NAD83 / UTM zone 15N
```

A projected CRS is used for distance, area, and overlay calculations.

### Web CRS

Web exports are converted to:

```text
EPSG:4326
WGS84 longitude/latitude
```

This CRS is used for GeoJSON and PMTiles source data.

For other regions, the analysis CRS should be replaced with an appropriate local projected CRS, while web exports should still be converted to EPSG:4326.

---

## Data Inputs

The model uses several categories of geospatial data.

### Parcels

Parcel geometries define the screening units. Parcel acreage is calculated from geometry rather than relying only on assessor-provided acreage fields.

### Elevation and Slope

Elevation data is used to derive slope and terrain metrics.

Common fields include:

```text
avg_slope_pct
max_slope_pct
median_slope_pct
pct_under_5_slope
pct_5_to_15_slope
pct_over_15_slope
terrain_score
slope_score
slope_class
```

### Hydrology and Water Features

Hydrology layers identify streams, ponds, lakes, and waterbody overlap.

Common fields include:

```text
stream_present
polygon_water_present
water_pct
water_habitat_score
```

### Wetlands

Wetland overlap is calculated per parcel.

Common fields include:

```text
wetland_present
wetland_pct
wetland_habitat_score
```

Wetlands are treated differently depending on the profile. They may represent development risk or conservation value.

### Floodplain

Floodplain overlap is calculated per parcel using high-risk flood hazard polygons.

Common fields include:

```text
floodplain_present
floodplain_area_acres
floodplain_pct
floodplain_constraint_pass
```

The Franklin County implementation filters flood hazard data to high-risk zones such as:

```text
A
AE
AH
AO
A99
AR
V
VE
```

This avoids treating broad low-risk/background zones as high-risk floodplain.

### Road Access

Road access is represented by distance to the nearest road.

Common fields include:

```text
distance_to_nearest_road_m
road_access_class
access_score
low_access_score
```

`access_score` rewards road proximity.  
`low_access_score` rewards remoteness.

### Town and Service-Center Proximity

Town/service-center points are used for proximity scoring and map reference.

Common fields include:

```text
nearest_town
nearest_town_role
distance_to_nearest_town_km
proximity_score
```

### Vegetation / NDVI

NDVI-derived metrics are used as a vegetation proxy.

Common fields include:

```text
avg_ndvi
median_ndvi
vegetation_score
vegetation_class
```

---

## Component Scores

Raw spatial metrics are normalized into 0-100 component scores. Higher values generally indicate stronger suitability for that component.

Component scores include:

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

### Risk Score

Risk score combines floodplain and wetland overlap:

```text
risk_penalty = floodplain_pct * 0.60 + wetland_pct * 0.40
risk_score = 100 - risk_penalty
```

Higher `risk_score` values represent lower floodplain/wetland conflict.

---

## Suitability Profiles

TerraScope uses profile-specific scores rather than one universal suitability score. This is important because parcel suitability depends on intended use.

### Residential / Homestead

```text
slope_score       = 0.30
access_score      = 0.20
proximity_score   = 0.15
risk_score        = 0.25
vegetation_score  = 0.05
acreage_score     = 0.05
```

This profile emphasizes gentle terrain, access, proximity to services, and lower flood/wetland conflict.

### Agriculture / Open Land

```text
slope_score       = 0.25
vegetation_score  = 0.25
acreage_score     = 0.20
access_score      = 0.15
risk_score        = 0.15
```

This profile emphasizes usable terrain, vegetation, parcel size, road access, and low risk.

### Event Venue / Rural Tourism

```text
access_score           = 0.25
proximity_score        = 0.20
terrain_variety_score  = 0.20
risk_score             = 0.20
acreage_score          = 0.10
vegetation_score       = 0.05
```

This profile emphasizes access, service proximity, terrain variation, low risk, and acreage.

### Conservation / Habitat

```text
vegetation_score       = 0.25
water_habitat_score    = 0.25
wetland_habitat_score  = 0.15
acreage_score          = 0.15
low_access_score       = 0.10
terrain_variety_score  = 0.10
```

This profile emphasizes vegetation, water, wetlands, parcel size, remoteness, and terrain variation.

---

## Custom Suitability Profile

The frontend supports a session-only custom profile. Users can edit weights for the component scores and normalize the weights to 100%.

The custom score is calculated as:

```text
custom_score = sum(component_score * user_weight)
```

Custom profile behavior:

```text
map recolors using custom weights
selected parcel score updates
ranked search can use custom weights
custom settings are not saved permanently
```

---

## Constraint Handling

Development-oriented profiles apply constraint thresholds for risk or terrain conflict. Constrained parcels are not deleted from the dataset. They remain visible but their final score is capped.

Current cap:

```text
final_score = min(raw_score, 40)
```

This preserves spatial context and makes unsuitable parcels explainable instead of invisible.

---

## Suitability Classes

Scores are classified as:

```text
80 - 100 = Very High
65 - 79  = High
50 - 64  = Moderate
35 - 49  = Low
0 - 34   = Very Low
```

---

## Web Architecture

The web application uses:

```text
MapLibre GL JS
PMTiles parcel layer
FastAPI backend
parcel_index.json
city_reference_points.geojson
```

The PMTiles layer contains only the fields needed for map display and client-side custom scoring:

```text
geometry
unit_id
preset score/class fields
component score fields
```

Full parcel metrics remain in the backend CSV.

---

## Interface Design

The interface separates quick spatial interpretation from detailed metrics:

```text
map popup = parcel ID and suitability score
sidebar = detailed metrics
selected parcel layer = prominent highlight
city layer = blue reference circles
layer toggles = basemap/context control
variables panel = scoring transparency
```

---

## Quality Control

Quality control includes:

```text
CRS verification
geometry validation
acreage validation
percentage clipping
NDVI clipping
floodplain zone filtering
score distribution review
constraint review
QGIS visual inspection
web map performance testing
backend API testing
ranked search testing
custom weighting testing
```

---

## Limitations

TerraScope is a screening model, not an authoritative recommendation engine.

Known limitations include:

```text
public data may be incomplete or outdated
zoning is not fully integrated into scoring
soil productivity is not modeled
utility access is not fully modeled
road distance does not guarantee legal access
NDVI varies by season and imagery date
floodplain and wetland data require authoritative verification
custom weights are user assumptions
```
