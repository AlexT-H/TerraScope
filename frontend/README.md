# TerraScope Frontend

React/Vite frontend for TerraScope.

## Local Setup

From the TerraScope project root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL, usually:

```text
http://localhost:5173
```

## Data Required

Copy these generated pipeline outputs into `frontend/public/data/`:

```text
outputs/web_layers/scored_parcels_web.geojson
outputs/web_layers/profile_config.json
```

Expected frontend paths:

```text
frontend/public/data/scored_parcels_web.geojson
frontend/public/data/profile_config.json
```

## Backend API

The ranked search calls:

```text
http://127.0.0.1:8000/rank
```

You can change this in `.env`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

For public deployment, either deploy the backend separately and set `VITE_API_BASE_URL`, or keep the public demo as a static map first.
