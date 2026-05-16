# TerraScope Backend

Small FastAPI backend for TerraScope scoring and ranking.

## Setup

From the project root:

```bash
mkdir backend\data
copy data\processed\scored_metrics.csv backend\data\scored_metrics.csv
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

```text
GET /health
GET /profiles
GET /parcels/{unit_id}
POST /score
POST /rank
POST /parcels/{unit_id}/score
```
