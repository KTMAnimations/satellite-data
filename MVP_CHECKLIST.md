# MVP Checklist - Satellite Migration Analysis Platform

**Generated:** 2026-01-25
**Based on:** SOT.md Specification
**Current State:** ~75% complete

---

## Executive Summary

The platform has solid backend infrastructure with all core services implemented. The primary gaps are:
1. **Worker container not running** (volume mount issue)
2. **Insufficient data** (only 5 observations total)
3. **Predefined regions not seeded** (script exists but not run)
4. **Frontend needs data to display** (charts work but show "no data")

---

## Phase 1: Critical Fixes (Must Have for MVP)

### 1.1 Fix Worker Container
**Priority:** CRITICAL | **Effort:** 15 min | **SOT Ref:** Section 3.1

- [ ] Fix docker-compose.yml volume mount for workers
  - Current: `./workers:/workers` (wrong path)
  - Should be: `./workers:/app/workers` (to match Dockerfile)
- [ ] Verify worker starts: `docker-compose up -d worker`
- [ ] Verify worker connects to Redis: `docker logs satellite-worker`

**Test:** `docker ps` should show `satellite-worker` running

---

### 1.2 Seed Predefined Regions
**Priority:** CRITICAL | **Effort:** 5 min | **SOT Ref:** Section 5

- [ ] Run seed script inside API container:
  ```bash
  docker exec -it satellite-api python scripts/seed_regions.py
  ```
- [ ] Verify regions created:
  ```bash
  curl http://localhost:8000/api/v1/regions?type=predefined | jq '.total'
  ```
  - Expected: 30 regions (20 US cities + 10 global megacities)

**Test:** Frontend region explorer shows 30+ predefined regions

---

### 1.3 Collect Minimum Viable Data
**Priority:** CRITICAL | **Effort:** 2-4 hours (GEE rate limited) | **SOT Ref:** Section 4.1

Collect at least 12 months of data for 5 key regions:

- [ ] Phoenix, AZ (migration hotspot - primary demo)
- [ ] Miami, FL (migration hotspot)
- [ ] Las Vegas, NV (migration hotspot)
- [ ] New York, NY (comparison baseline)
- [ ] Tokyo, Japan (global megacity)

For each region:
```bash
python scripts/collect_archive.py --region "Phoenix, AZ" \
  --start 2023-01-01 --end 2024-12-31 \
  --metrics nightlights ndvi urban_density parking
```

**Minimum data requirements:**
- [ ] At least 24 monthly observations per metric per region
- [ ] Both winter (Dec-Feb) and summer (Jun-Aug) data present
- [ ] Total observations > 400

**Test:**
```bash
curl http://localhost:8000/api/v1/metrics/{phoenix_region_id} | jq '.metrics | keys'
```
Should return all 4 metrics with data

---

## Phase 2: Frontend Verification (Required for Demo)

### 2.1 Dashboard Page
**Priority:** HIGH | **Effort:** 30 min | **SOT Ref:** Section 7.2

- [ ] Map displays all predefined regions
- [ ] Stats show correct counts (regions, metrics)
- [ ] Featured analyses link to gallery
- [ ] "Explore Regions" button works

**Test:** Open http://localhost:5173 - no console errors, all sections render

---

### 2.2 Region Explorer
**Priority:** HIGH | **Effort:** 30 min | **SOT Ref:** Section 2.2

- [ ] Region list populates from API
- [ ] Filter by type (predefined/custom) works
- [ ] Filter by category (major_city, migration_hotspot, megacity) works
- [ ] Search by name works
- [ ] Click region navigates to analysis view
- [ ] Draw polygon tool creates custom region
- [ ] Delete custom region works

**Test:** Can create a custom region, see it listed, delete it

---

### 2.3 Analysis View
**Priority:** HIGH | **Effort:** 1 hour | **SOT Ref:** Section 7.1

- [ ] Region header displays correctly
- [ ] Map shows region boundary
- [ ] Date range picker functions
- [ ] Metric toggles update charts
- [ ] Time series chart renders with data
- [ ] Seasonal bar chart renders with data
- [ ] Stats cards show min/max/avg
- [ ] Seasonal change percentages display
- [ ] "Export" button links to export center

**Test:** Select Phoenix, view last 2 years - charts should show seasonal patterns

---

### 2.4 Export Center
**Priority:** HIGH | **Effort:** 30 min | **SOT Ref:** Section 6.1

- [ ] Region selector works
- [ ] Date range selection works
- [ ] CSV export generates and downloads
- [ ] PDF export generates and downloads
- [ ] Animation export generates and downloads (or shows meaningful error)
- [ ] Export status polling works

**Test:** Export CSV for Phoenix - file downloads with correct data

---

### 2.5 Gallery (Preset Analyses)
**Priority:** MEDIUM | **Effort:** 1 hour | **SOT Ref:** Section 5.4

- [ ] All 5 presets display
- [ ] Clicking preset shows analysis view
- [ ] Methodology section explains proxy metrics

**Note:** Presets are hardcoded - they work but need actual data to be meaningful

---

## Phase 3: API Completeness Verification

### 3.1 Core Endpoints
**SOT Ref:** Section 6.1

| Endpoint | Method | Status | Test |
|----------|--------|--------|------|
| `/api/v1/regions` | GET | [ ] | List returns regions |
| `/api/v1/regions` | POST | [ ] | Create custom region |
| `/api/v1/regions/{id}` | GET | [ ] | Get single region |
| `/api/v1/regions/{id}` | DELETE | [ ] | Delete custom region |
| `/api/v1/metrics/{region_id}` | GET | [ ] | Returns time series |
| `/api/v1/analysis/{region_id}` | GET | [ ] | Returns cached analyses |
| `/api/v1/analysis` | POST | [ ] | Triggers new analysis |
| `/api/v1/analysis/compare` | POST | [ ] | Compares two periods |
| `/api/v1/exports/csv` | POST | [ ] | Generates CSV |
| `/api/v1/exports/pdf` | POST | [ ] | Generates PDF |
| `/api/v1/exports/animation` | POST | [ ] | Generates animation |
| `/api/v1/tiles/{region}/{metric}/{z}/{x}/{y}.png` | GET | [ ] | Returns tile image |
| `/api/v1/auth/keys` | POST | [ ] | Generates API key |
| `/api/v1/collect/{region_id}` | POST | [ ] | Triggers data collection |

---

### 3.2 Data Collection Endpoints
**SOT Ref:** Section 4

- [ ] Collection for single metric works
- [ ] Collection for all metrics works
- [ ] Background collection with status polling works
- [ ] Existing observations are not duplicated

---

## Phase 4: Analysis Features Verification

### 4.1 Temporal Analysis
**SOT Ref:** Section 4.2

- [ ] Seasonal averages calculated correctly (winter vs summer)
- [ ] Southern hemisphere detection works (inverted seasons)
- [ ] Trend detection identifies increasing/decreasing patterns
- [ ] Anomaly detection flags unusual values

**Test:** Phoenix winter nightlights should be higher than summer

---

### 4.2 Change Detection
**SOT Ref:** Section 4.2

- [ ] Period comparison returns statistical difference
- [ ] COVID impact analysis (2020 vs 2019) shows drop

---

### 4.3 Migration Analysis
**SOT Ref:** Section 4.2

- [ ] Migration pattern classification works
- [ ] Phoenix classified as "winter destination"
- [ ] Flow data generated between correlated regions

---

## Phase 5: Visual Outputs (SOT Section 7)

### 5.1 Charts (D3.js)
- [ ] Multi-metric time series chart
- [ ] Seasonal comparison bar chart
- [ ] Stats summary cards

### 5.2 Maps (Leaflet)
- [ ] Region boundaries display
- [ ] Region selection works
- [ ] Zoom to region works
- [ ] Draw polygon tool works

### 5.3 Exports
- [ ] PDF report with embedded charts and tables
- [ ] CSV with proper headers and data
- [ ] Animation (GIF or WebM) - at minimum synthetic frames

---

## Phase 6: Data Quality Verification

### 6.1 Metric Value Ranges
**SOT Ref:** Section 2.2

| Metric | Expected Range | Phoenix Winter | Phoenix Summer |
|--------|----------------|----------------|----------------|
| NDVI | -1 to 1 | [ ] ~0.1-0.2 | [ ] ~0.15-0.25 |
| Nightlights | 0-200+ nW/cm²/sr | [ ] Higher | [ ] Lower |
| Urban Density | 0-1 | [ ] ~0.5 | [ ] ~0.5 |
| Parking | 0-1 | [ ] Higher | [ ] Lower |

---

### 6.2 Seasonal Patterns
- [ ] Phoenix shows higher winter activity (snowbird pattern)
- [ ] NDVI shows vegetation changes with seasons
- [ ] Patterns match known migration behavior

---

## Phase 7: Production Readiness (Nice to Have)

### 7.1 Status Tracking
- [ ] Switch from in-memory dict to Redis for export/analysis status
- [ ] Status survives API restart

### 7.2 Error Handling
- [ ] No cloud-free data returns friendly message
- [ ] Rate limit returns 429 with retry info
- [ ] Invalid geometry returns helpful error

### 7.3 Performance
- [ ] Metrics endpoint < 2s response
- [ ] Tile generation < 500ms
- [ ] Export generation completes within 5 min

---

## Phase 8: Documentation (Nice to Have)

### 8.1 User-Facing
- [ ] README.md with setup instructions
- [ ] API documentation accessible at /docs
- [ ] Methodology explanation in Gallery

### 8.2 Developer
- [ ] Environment variables documented in .env.example
- [ ] Docker setup instructions

---

## Quick Start Commands

```bash
# 1. Start all services
docker-compose up -d

# 2. Check all containers running
docker ps

# 3. Seed predefined regions
docker exec -it satellite-api python scripts/seed_regions.py

# 4. Collect data for Phoenix (primary demo region)
python scripts/collect_archive.py --region "Phoenix, AZ" \
  --start 2023-01-01 --end 2024-12-31 \
  --metrics nightlights ndvi

# 5. Verify data
curl http://localhost:8000/api/v1/regions | jq '.total'
curl "http://localhost:8000/api/v1/metrics/{PHOENIX_ID}?start_date=2023-01-01" | jq '.metrics | keys'

# 6. Open frontend
open http://localhost:5173
```

---

## MVP Definition of Done

The platform is MVP-ready when:

1. **Infrastructure:** All 5 Docker containers running (db, redis, api, worker, frontend)
2. **Data:** At least 5 regions with 12+ months of data each
3. **Frontend:** User can select region, view charts, export CSV
4. **API:** All core endpoints return valid responses
5. **Demo:** Can demonstrate snowbird pattern in Phoenix (higher winter activity)

---

## Estimated Total Effort

| Phase | Effort | Status |
|-------|--------|--------|
| Phase 1: Critical Fixes | 2-4 hours | Not Started |
| Phase 2: Frontend Verification | 2-3 hours | Not Started |
| Phase 3: API Verification | 1 hour | Not Started |
| Phase 4: Analysis Verification | 1 hour | Not Started |
| Phase 5: Visual Outputs | 30 min | Not Started |
| Phase 6: Data Quality | 30 min | Not Started |
| Phase 7: Production Ready | 2 hours | Optional |
| Phase 8: Documentation | 1 hour | Optional |

**Total MVP Effort:** ~8-12 hours (excluding data collection wait time)
