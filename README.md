# Exeter Astro

Local-first satellite proxy metrics explorer for detecting seasonal migration patterns, urban growth, and activity changes using free satellite datasets.

This repo is optimized for **personal/local use** and runs **without Docker**:
- **Backend:** FastAPI + SQLite + Google Earth Engine (server-side compute + map tiles)
- **Frontend:** React + Vite + Leaflet

## Quickstart (no Docker)

### 1) Configure environment

Create a repo-root `.env` (see `.env.example`).

For Earth Engine you can either:
- Authenticate interactively with `earthengine authenticate`, or
- Use a service account JSON (`GEE_SERVICE_ACCOUNT_KEY`) + `GEE_PROJECT_ID`.

### 2) Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# predefined regions are auto-seeded on first API request (if missing)
# (optional) you can also run the seeder manually:
# python ../scripts/seed_regions.py

uvicorn app.main:app --reload --port 8000
```

### 3) Frontend

```bash
cd frontend
npm install

# ensure API requests go through the Vite dev proxy (avoids CORS issues):
# echo "VITE_API_URL=/api/v1" > .env

npm run dev
```

Open:
- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

## Notes

- Map overlays load Earth Engine tiles via the backend tile proxy; an internet connection and valid EE credentials are required.
- If you see slow tile loads or EE quota errors during fast pans/zooms, tune `GEE_MAX_CONCURRENT_REQUESTS` and the tile cache settings in `.env`.
- Exports run as lightweight background tasks inside the API process (no Redis/Celery).
