# SatelliteMigration

A web application that analyzes satellite imagery to detect seasonal migration patterns, urban growth, and activity changes using proxy metrics derived from free satellite data.

## Overview

This platform uses satellite-derived proxy metrics to estimate population and activity patterns. At 10m resolution (Sentinel-2), individual vehicles cannot be detected, so we use correlational proxies instead.

### Key Features

- **Region Selection**: Predefined cities/regions or custom polygon drawing
- **Temporal Analysis**: Full Sentinel-2 archive (2015+) with seasonal comparisons
- **Proxy Metrics**: Nighttime lights, vegetation (NDVI), urban density, parking occupancy
- **Visualizations**: Interactive heatmaps, time-lapse animations, comparative charts
- **Exports**: PDF reports, CSV data, GIF/WebM animations

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Running with Docker

```bash
# Clone the repository
git clone <repository-url>
cd satellite-data

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Seed predefined regions
docker-compose exec api python scripts/seed_regions.py
```

The application will be available at:
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Development Setup

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL and Redis (via Docker)
docker-compose up -d db redis

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript, Leaflet, D3.js |
| Backend | FastAPI (Python), async |
| Database | PostgreSQL + PostGIS |
| Cache | Redis |
| Task Queue | Celery |
| Containers | Docker Compose |

### Data Sources

| Source | Data Type | Resolution |
|--------|-----------|------------|
| Sentinel-2 | Optical imagery | 10m |
| VIIRS | Nighttime lights | 375m |
| GHSL | Built-up areas | 10m |
| OpenStreetMap | Road networks, POIs | Vector |

### Project Structure

```
satellite-data/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── core/      # Config, database, security
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   └── services/  # Business logic
│   └── alembic/       # Database migrations
├── frontend/          # React application
│   └── src/
│       ├── components/  # UI components
│       ├── pages/       # Page components
│       ├── services/    # API client
│       └── store/       # Zustand state
├── workers/           # Celery tasks
├── scripts/           # Utility scripts
└── data/              # Data storage
```

## API Endpoints

```
# Regions
GET    /api/v1/regions              # List regions
POST   /api/v1/regions              # Create custom region
GET    /api/v1/regions/{id}         # Get region details

# Metrics
GET    /api/v1/metrics/{region_id}  # Get time series data

# Analysis
POST   /api/v1/analysis             # Request new analysis
GET    /api/v1/analysis/{id}/status # Check status
POST   /api/v1/analysis/compare     # Compare periods

# Exports
POST   /api/v1/exports/pdf          # Generate PDF report
POST   /api/v1/exports/csv          # Export CSV data
POST   /api/v1/exports/animation    # Generate animation

# Tiles
GET    /api/v1/tiles/{region}/{metric}/{z}/{x}/{y}.png
```

## Configuration

### Environment Variables

See `.env.example` for all available options.

Key settings:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `GEE_SERVICE_ACCOUNT`: Google Earth Engine service account
- `GEE_KEY_FILE`: Path to GEE key file

### Satellite Provider Setup

**Google Earth Engine:**
```bash
python scripts/setup_gee.py
```

**Microsoft Planetary Computer:**
No setup required - free access.

## Proxy Metrics Explained

### Nighttime Lights (VIIRS)
- Measures artificial light intensity
- Proxy for population density and economic activity
- Unit: nW/cm²/sr

### NDVI (Vegetation Index)
- Measures vegetation density
- Values: -1 to 1 (higher = more vegetation)
- Used to track urban sprawl

### Urban Density
- Estimates built-up area using spectral indices
- Ratio: 0 to 1

### Parking Occupancy
- Analyzes large parking lots
- Proxy for commercial activity
- Limited by 10m resolution

## Limitations

1. **Resolution**: Cannot detect individual vehicles (10m vs 30cm needed)
2. **Proxy accuracy**: Metrics are correlational, not causal
3. **Cloud cover**: Some regions/periods may have data gaps
4. **Temporal lag**: Composite generation introduces delays

## License

MIT License - see LICENSE file for details.
