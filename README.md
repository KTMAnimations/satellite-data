# SatelliteMigration

Satellite imagery analysis platform for detecting seasonal migration patterns, urban growth, and activity changes using proxy metrics from free satellite data.

## Quick Reference

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Seed regions
docker-compose exec api python scripts/seed_regions.py
```

**URLs:** Frontend `localhost:5173` | API `localhost:8000` | Docs `localhost:8000/docs`

## Development

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## GitHub Pages (Frontend Only)

GitHub Pages can host the **static frontend** (`frontend/`), but it **cannot** run the FastAPI backend (`backend/`) or workers.

This repo includes a Pages deploy workflow at `.github/workflows/deploy-pages.yml` that builds and publishes `frontend/dist`.

Required config:

- **Backend must be hosted elsewhere** (Docker, a VM, etc) and must allow your Pages origin via `CORS_ORIGINS`.
- In GitHub repo settings, set a repository variable `VITE_API_URL` to your API base (example: `https://api.example.com/api/v1`).

Notes:

- The workflow sets `VITE_ROUTER_MODE=hash` to avoid SPA refresh 404s on GitHub Pages (`/#/regions`, etc).
- If you deploy somewhere that supports SPA rewrites, set `VITE_ROUTER_MODE=browser` (or unset it) for clean URLs.

## Architecture

```
backend/
├── app/
│   ├── api/        # REST endpoints
│   ├── core/       # Config, database, security
│   ├── models/     # SQLAlchemy models
│   ├── schemas/    # Pydantic schemas
│   └── services/   # Business logic
└── alembic/        # Database migrations

frontend/src/
├── components/     # UI components
├── pages/          # Page components
├── services/       # API client
└── store/          # Zustand state
```

## Tech Stack

- **Frontend:** React, TypeScript, Leaflet, D3.js
- **Backend:** FastAPI (async Python)
- **Database:** PostgreSQL + PostGIS
- **Cache/Queue:** Redis, Celery
- **Containers:** Docker Compose

## Data Sources

| Source | Type | Resolution |
|--------|------|------------|
| Sentinel-2 | Optical imagery | 10m |
| VIIRS | Nighttime lights | 375m |
| GHSL | Built-up areas | 10m |
| OpenStreetMap | Roads, POIs | Vector |

## API Endpoints

```
GET/POST  /api/v1/regions              # List/create regions
GET       /api/v1/regions/{id}         # Region details
GET       /api/v1/metrics/{region_id}  # Time series data
POST      /api/v1/analysis             # Request analysis
GET       /api/v1/analysis/{id}/status # Check status
POST      /api/v1/analysis/compare     # Compare periods
POST      /api/v1/exports/pdf|csv|animation
GET       /api/v1/tiles/{region}/{metric}/{z}/{x}/{y}.png
```

## Environment Variables

See `.env.example` for all options. Key settings:

- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `GEE_SERVICE_ACCOUNT` - Google Earth Engine account
- `GEE_KEY_FILE` - Path to GEE credentials

## Proxy Metrics

| Metric | Description | Notes |
|--------|-------------|-------|
| Nighttime Lights | Artificial light intensity (nW/cm²/sr) | Population/economic proxy |
| NDVI | Vegetation density (-1 to 1) | Urban sprawl tracking |
| Urban Density | Built-up area ratio (0-1) | Spectral indices |
| Parking Occupancy | Large lot analysis | Commercial activity proxy |

## Limitations

- **Resolution:** 10m cannot detect individual vehicles (need 30cm)
- **Proxy accuracy:** Correlational, not causal
- **Cloud cover:** Data gaps in some regions/periods
- **Temporal lag:** Composite generation delays

## License

MIT
