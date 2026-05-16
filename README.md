# TerraScope

TerraScope is an interactive rural land suitability screening web application. The current implementation focuses on Franklin County, Missouri, and combines an offline GIS processing workflow, parcel-level suitability modeling, a FastAPI backend, and a MapLibre/PMTiles frontend.

The project demonstrates a full geospatial application workflow: data acquisition, spatial preprocessing, raster/vector metric generation, suitability scoring, vector-tile web optimization, backend API development, and interactive web mapping.

> TerraScope is an exploratory geospatial decision-support tool. It compares rural land suitability scenarios using public spatial data and transparent assumptions. It should not replace professional site assessment, legal review, environmental review, engineering review, surveying, permitting, zoning review, or local planning guidance.

---

## Core Features

- Parcel-level rural land suitability screening
- Multiple preset suitability profiles
- Session-only custom suitability profile
- Editable scoring variables and weights
- Custom map recoloring from user-adjusted weights
- Ranked parcel search
- Search-result zoom-to-parcel
- Prominent selected-parcel highlight
- Simple parcel popup with parcel ID and suitability score
- Detailed parcel metrics in the sidebar
- Toggleable parcel analysis layer
- Toggleable city/service-center reference layer
- OpenStreetMap and topographic basemap options
- Fast PMTiles/vector-tile map rendering
- FastAPI backend for scoring, lookup, and ranking

---

## Suitability Profiles

TerraScope includes four preset profiles:

```text
Residential / Homestead
Agriculture / Open Land
Event Venue / Rural Tourism
Conservation / Habitat
```

Each profile uses a different weighted combination of parcel-level component scores. The same parcel may score highly for one use case and poorly for another.

The web app also includes a custom profile mode. Users can open the **Variables & Weights** section, inspect the scoring variables, edit the weights, normalize the total weight to 100%, and view the resulting map recoloring for the current session.

---

## Repository Structure

```text
terraScope/
├── backend/
│   ├── main.py
│   ├── scoring.py
│   ├── schemas.py
│   ├── requirements.txt
│   └── data/
│       └── scored_metrics.csv
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── docs/
│   ├── data_sources.md
│   ├── methodology.md
│   ├── scoring_model.md
│   └── workflow.md
│
├── frontend/
│   ├── package.json
│   ├── public/
│   │   └── data/
│   │       ├── terrascope_parcels.pmtiles
│   │       ├── parcel_index.json
│   │       ├── city_reference_points.geojson
│   │       └── profile_config.json
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── index.css
│       └── main.jsx
│
├── outputs/
│   └── web_layers/
│
├── pipeline/
│   ├── finalize_metrics.py
│   ├── score_parcels.py
│   ├── export_pmtiles_source.py
│   └── ...
│
├── tools/
│   └── build_pmtiles_wsl.sh
│
└── README.md
```

---

## Technology Stack

### GIS and Data Processing

- Python
- GeoPandas
- Pandas
- NumPy
- GeoPackage
- GeoJSON
- QGIS
- Tippecanoe
- PMTiles

### Backend

- FastAPI
- Uvicorn
- Pandas
- Pydantic

### Frontend

- React
- Vite
- MapLibre GL JS
- PMTiles JavaScript protocol
- Tailwind CSS
- Lucide React icons

---

## Data and Application Outputs

Processed analysis outputs:

```text
data/processed/final_metrics.gpkg
data/processed/final_metrics.csv
data/processed/scored_parcels.gpkg
data/processed/scored_metrics.csv
```

Frontend web outputs:

```text
frontend/public/data/terrascope_parcels.pmtiles
frontend/public/data/parcel_index.json
frontend/public/data/city_reference_points.geojson
frontend/public/data/profile_config.json
```

Backend data:

```text
backend/data/scored_metrics.csv
```

---

## Local Operation

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

For PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Backend API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

Common endpoints:

```text
GET /health
GET /profiles
GET /parcels/{unit_id}
POST /rank
POST /score
POST /parcels/{unit_id}/score
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The local frontend is usually available at:

```text
http://localhost:5173
```

The frontend expects the following files in `frontend/public/data/`:

```text
terrascope_parcels.pmtiles
parcel_index.json
city_reference_points.geojson
profile_config.json
```

---

## Web Map Operation

### Suitability Profile

The profile dropdown changes the parcel coloring and score interpretation.

### Variables & Weights

The **Variables & Weights** panel exposes the scoring model used by the selected profile. Editing any weight activates a session-only custom suitability profile.

### Map Layers

The map supports:

```text
OpenStreetMap basemap
Topographic basemap
Analysis Map overlay
Cities / Service Centers overlay
```

### Parcel Selection

Clicking a parcel:

```text
opens a basic popup
shows parcel ID and suitability score
highlights the selected parcel
loads detailed metrics in the sidebar
```

### Ranked Search

Ranked search filters parcels by:

```text
minimum score
minimum acreage
maximum floodplain percentage
maximum wetland percentage
maximum road distance
maximum town distance
stream presence
```

Clicking a ranked result pans/zooms to the parcel and loads its details.

---

## Deployment

The frontend is a Vite application and can be deployed on Vercel.

Recommended Vercel settings:

```text
Framework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

For full public functionality, the FastAPI backend should be deployed separately and the frontend should be configured with:

```text
VITE_API_BASE_URL=https://your-backend-url
```

If no deployed backend is configured, the public frontend can still display the PMTiles map, profile styling, custom client-side map recoloring, layer toggles, and basic map popups. Ranked search and full parcel detail lookup require the backend.

---

## Documentation

Additional documentation is included in:

```text
docs/data_sources.md
docs/methodology.md
docs/scoring_model.md
docs/workflow.md
```

---

## Credits

Interface icons are from Lucide Icons through the `lucide-react` package.

Basemaps include OpenStreetMap and Esri topographic tiles.

---

## Responsible Use

TerraScope is intended for exploratory screening and portfolio demonstration. It is not a substitute for professional due diligence, land-use review, engineering review, surveying, environmental review, legal review, planning review, or permitting decisions.
