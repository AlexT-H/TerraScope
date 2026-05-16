# Data Sources

This document summarizes the spatial data sources used in the Franklin County, Missouri implementation of TerraScope.

---

## Parcels

```text
Layer: Franklin County Parcels
Source: Franklin County GIS ArcGIS FeatureServer
Geometry type: Polygon
Raw path: data/raw/parcels/franklin_parcels_raw.geojson
Processed path: data/interim/analysis_units_26915.gpkg
Processed CRS: EPSG:26915
```

Fields retained for analysis include parcel identifiers, acreage-related fields, and property classification attributes.

Fields removed from public display include owner names and private address attributes.

Parcel acreage is calculated from geometry after reprojection to the analysis CRS. This creates a consistent acreage field and avoids relying on incomplete assessor acreage values.

---

## Elevation / DEM

```text
Layer: 1 meter DEM
Source: USGS 3DEP / The National Map
Format: GeoTIFF
Raw path: data/raw/dem/
Processed CRS: EPSG:26915
```

Elevation data is used to derive slope and terrain metrics. Topographic basemaps are used for visual context only; DEM-derived slope metrics are used for analysis.

---

## Roads

```text
Source: Geofabrik OpenStreetMap extract for Missouri
Use: Road access and nearest-road distance
```

Roads are used to calculate distance to the nearest road and derive access/remoteness scores.

---

## Water Layers

Streams and waterbody layers are used to identify parcel-level hydrology features.

```text
Streams: Franklin County Data FeatureServer
Ponds and Lakes: Franklin County Data FeatureServer
```

Derived metrics include stream presence, polygon waterbody presence, water overlap percentage, and water habitat score.

---

## Wetlands

```text
Source: U.S. Fish & Wildlife Service National Wetlands Inventory
Use: Wetland overlap and wetland habitat scoring
```

Wetland overlap is used as development risk in development-oriented profiles and as potential habitat value in conservation scoring.

---

## Floodplain

```text
Source: FEMA / NFHL flood hazard data
Use: Floodplain overlap and risk scoring
```

Floodplain processing uses high-risk flood hazard zones for development-risk scoring. Broad low-risk/background flood zones are excluded from high-risk floodplain overlap metrics.

---

## Sentinel-2 Imagery

```text
Source: Copernicus Browser
Collection: Sentinel-2 Level-2A
Bands: B04 Red, B08 Near Infrared
Use: NDVI / vegetation analysis
```

NDVI is calculated as:

```text
NDVI = (B08 - B04) / (B08 + B04)
```

Derived metrics include average NDVI, median NDVI, vegetation score, and vegetation class.

---

## Zoning

```text
Source: Franklin County parcel attributes
Fields: Zoning1, Zoning2
Use: Screening context and possible filter/display attribute
```

Zoning is treated as screening context rather than a legal determination. Local zoning rules and land-use regulations should be checked directly with the appropriate authority.

Common zoning shorthand used in the source data includes:

```text
CITY = Municipal jurisdiction
R    = Residential
A    = Agricultural
B    = Commercial / Business
G    = General / higher intensity
W    = Rural / open land
O/P/T/Y = Other or locally defined categories
blank/null = Unknown
```

---

## Service Centers

```text
Path: data/raw/towns/service_centers.csv
Use: Town/service-center proximity and web map reference layer
```

Required fields:

```text
town_name
role
longitude
latitude
```

The web app displays these points as a toggleable blue reference layer.

---

## Public Data Handling

The public portfolio version avoids displaying private owner names and private address attributes.

Large raw datasets such as DEM rasters and satellite imagery are excluded from repository upload depending on file size. The workflow documentation describes the expected file structure and regeneration process.
