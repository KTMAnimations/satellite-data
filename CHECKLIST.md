# Shipping Checklist

**Last Updated:** 2026-01-26
**MVP Goal:** End-to-end working platform with 5 key regions
**Overall Status:** ~85% complete

---

## Quick Status

| Component | Status | Blockers |
|-----------|--------|----------|
| Frontend | **Ready** | None - all 6 views working, 17 metrics |
| Backend API | **Ready** | None - all endpoints implemented |
| Database | **Ready** | Migrations complete, schema verified |
| Docker | **Ready** | All services defined, health checks configured |
| Data | **Partial** | Need tile data for 5 key regions |
| Testing | **Minimal** | No automated tests yet |

---

## MVP Definition

The platform is shippable when:
1. Docker Compose starts all services successfully
2. 5 key regions have precomputed tile data (12+ months each)
3. User can select region → view charts → export CSV
4. Snowbird pattern visible in Phoenix (higher winter activity)

**5 Key Regions:**
- Phoenix, AZ (primary demo - snowbird migration)
- Miami, FL (migration hotspot)
- Las Vegas, NV (tourism patterns)
- New York, NY (baseline comparison)
- Los Angeles, CA (urban density)

---

## Phase 1: Infrastructure (COMPLETE)

### Docker Services
- [x] PostgreSQL 16 + PostGIS 3.4 container
- [x] Redis 7 container
- [x] FastAPI backend container
- [x] Celery worker container
- [x] React frontend container
- [x] Health checks configured
- [x] Volume mounts for data persistence

### Database
- [x] Alembic migrations created
- [x] Region model with PostGIS geometry
- [x] Observation model for time series
- [x] AnalysisResult model for cached analyses
- [x] APIKey model for authentication

### Backend Core
- [x] FastAPI app with lifespan handlers
- [x] CORS middleware configured
- [x] Rate limiting middleware (100/1000 req/min)
- [x] Global error handlers
- [x] Structured logging

---

## Phase 2: API Endpoints (COMPLETE)

### Region Management
- [x] `GET /api/v1/regions` - List with filtering
- [x] `POST /api/v1/regions` - Create custom region
- [x] `GET /api/v1/regions/{id}` - Get single region
- [x] `DELETE /api/v1/regions/{id}` - Delete custom region

### Metrics & Analysis
- [x] `GET /api/v1/metrics/{region_id}` - Time series data
- [x] `POST /api/v1/analysis` - Request new analysis
- [x] `GET /api/v1/analysis/{id}/status` - Check status
- [x] `POST /api/v1/analysis/compare` - Period comparison

### Tiles
- [x] `GET /api/v1/tiles/us/{metric}/{date}/{z}/{x}/{y}.png` - US-wide tiles
- [x] `GET /api/v1/tiles/{region_id}/{metric}/{z}/{x}/{y}.png` - Region tiles
- [x] 17 metrics supported with colormaps and value ranges

### Exports
- [x] `POST /api/v1/exports/pdf` - PDF generation
- [x] `POST /api/v1/exports/csv` - CSV export
- [x] `POST /api/v1/exports/animation` - GIF/WebM generation

### Data Collection
- [x] `POST /api/v1/collect/{region_id}` - Collect satellite data
- [x] Background collection support

### Auth & Health
- [x] `POST /api/v1/auth/keys` - Generate API key
- [x] `GET /health` - Health check with service status

---

## Phase 3: Frontend (COMPLETE)

### Views Implemented
- [x] Dashboard - Featured analyses, quick stats, navigation
- [x] Region Explorer - Browse/search/create regions
- [x] Analysis View - Time series charts, metrics overlay
- [x] Animation Studio - Time-lapse generation
- [x] Compare View - Side-by-side period comparison
- [x] Export Center - PDF/CSV/animation export
- [x] Gallery - 5 preset analyses with deep-linking

### Map Components
- [x] Leaflet base map with OSM tiles
- [x] CompositeTileLayer for metric overlays
- [x] GeoJSON region boundaries
- [x] FlowLayer for migration visualization
- [x] Draw controls for custom regions
- [x] GeoJSON upload support

### Metrics Support
- [x] All 17 metrics in dropdowns and selectors
- [x] Correct granularity badges (daily/weekly/monthly/yearly/static)
- [x] Appropriate colormaps per metric

---

## Phase 4: Data Pipeline (PARTIAL)

### GEE Integration
- [x] GEEClient with Sentinel-2 support
- [x] VIIRSClient for nighttime lights
- [x] USDataService with 17 get_* methods
- [x] computePixels() for tile generation

### Feature Extractors
- [x] NDVI extractor (Sentinel-2)
- [x] Nightlights extractor (VIIRS)
- [x] Urban density extractor (GHSL)
- [x] Parking detector (NDBI)
- [x] 13 additional metrics (land_cover, surface_water, etc.)

### Tile Generation
- [x] USTileGenerator with colormaps
- [x] VALUE_RANGES for all 17 metrics
- [x] Zoom level 11 native tiles
- [ ] **NEEDED:** Precompute tiles for 5 key regions

---

## Phase 5: Pre-computed Data (NEEDED)

### Tile Generation Tasks

| Region | Metric | Date Range | Status |
|--------|--------|------------|--------|
| Phoenix, AZ | nightlights | 2023-01 to 2024-12 | [ ] |
| Phoenix, AZ | ndvi | 2023-01 to 2024-12 | [ ] |
| Miami, FL | nightlights | 2023-01 to 2024-12 | [ ] |
| Miami, FL | ndvi | 2023-01 to 2024-12 | [ ] |
| Las Vegas, NV | nightlights | 2023-01 to 2024-12 | [ ] |
| New York, NY | nightlights | 2023-01 to 2024-12 | [ ] |
| Los Angeles, CA | nightlights | 2023-01 to 2024-12 | [ ] |

**Command:**
```bash
# Seed regions first
docker exec satellite-api python scripts/seed_regions.py

# Collect data for Phoenix
docker exec satellite-api python scripts/collect_archive.py \
  --region "Phoenix, AZ" \
  --start 2023-01-01 --end 2024-12-31 \
  --metrics nightlights ndvi
```

### Region Seeding
- [ ] Run `scripts/seed_regions.py` to create predefined regions
- [ ] Verify 30+ regions exist via API

---

## Phase 6: Verification (NEEDED)

### Manual Testing
- [ ] Start all Docker services
- [ ] Open frontend at localhost:5173
- [ ] Select Phoenix from region explorer
- [ ] View nightlights time series chart
- [ ] Verify winter values > summer values (snowbird pattern)
- [ ] Export CSV and verify data
- [ ] Generate animation and verify playback

### API Testing
```bash
# Health check
curl http://localhost:8000/health | jq

# List regions
curl http://localhost:8000/api/v1/regions | jq '.total'

# Get Phoenix metrics
curl "http://localhost:8000/api/v1/metrics/{PHOENIX_ID}?start_date=2023-01-01" | jq

# Verify tile generation
curl -I "http://localhost:8000/api/v1/tiles/us/nightlights/2024-01/11/512/768.png"
```

---

## Phase 7: Production Hardening (OPTIONAL)

### Authentication
- [ ] Implement API key validation middleware
- [ ] Add rate limit headers to responses

### Caching
- [ ] Configure Redis caching for tiles
- [ ] Add cache headers to tile responses

### Monitoring
- [ ] Structured logging to files
- [ ] Prometheus metrics endpoint
- [ ] Error alerting

### Documentation
- [x] User guide complete
- [x] Methodology document complete
- [x] API docs via Swagger UI
- [ ] Deployment guide

---

## Startup Commands

```bash
# 1. Start all services
docker-compose up -d

# 2. Check services are healthy
docker-compose ps
curl http://localhost:8000/health

# 3. Run database migrations
docker exec satellite-api alembic upgrade head

# 4. Seed predefined regions
docker exec satellite-api python scripts/seed_regions.py

# 5. Collect data for demo regions (this takes time due to GEE rate limits)
docker exec satellite-api python scripts/collect_archive.py \
  --region "Phoenix, AZ" --start 2023-01-01 --end 2024-12-31 --metrics nightlights ndvi

# 6. Verify via API
curl http://localhost:8000/api/v1/regions | jq '.total'

# 7. Open frontend
open http://localhost:5173
```

---

## Known Issues

1. **Worker volume mount** - May need adjustment if worker fails to start
2. **GEE authentication** - Requires service account credentials or gcloud auth
3. **Tile generation time** - First request for new tiles takes 10-30 seconds
4. **Large exports** - Animation generation can timeout for long date ranges

---

## Files Changed Since Last Update

| File | Change |
|------|--------|
| `SOT.md` | Updated status, metrics list, removed Section 18 |
| `docs/GEE_DATASETS.md` | New - consolidated GEE documentation |
| `CHECKLIST.md` | New - this file |
| Deleted: `MVP_CHECKLIST.md` | Consolidated into CHECKLIST.md |
| Deleted: `docs/SHIPPING_CHECKLIST.md` | Consolidated into CHECKLIST.md |
| Deleted: `docs/GEE_DATASET_TEST_MATRIX.md` | Merged into GEE_DATASETS.md |

---

## Remaining Work Estimate

| Task | Effort | Dependency |
|------|--------|------------|
| Start Docker services | 5 min | None |
| Seed regions | 5 min | Docker running |
| Collect Phoenix data | 2-4 hours | GEE credentials |
| Collect other 4 regions | 4-8 hours | GEE rate limits |
| Manual verification | 30 min | Data collected |
| **Total** | **~1 day** | |

---

*This checklist replaces MVP_CHECKLIST.md and docs/SHIPPING_CHECKLIST.md*
