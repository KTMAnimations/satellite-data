# Satellite Imagery Migration & Activity Analysis Platform

## Complete Specification Document

**Project Name:** SatelliteMigration
**Last Updated:** 2026-01-26
**Status:** Dockerless local-first implementation (SQLite + Earth Engine)

> Implementation note (2026-01-28): the repo was rebuilt for personal/local use. Docker/PostGIS/Redis/Celery were removed; the backend now uses SQLite and Earth Engine for server-side compute + tile URL templates.

---

## 1. Executive Summary

### 1.1 Project Goal
Build a web application that analyzes satellite imagery to detect seasonal migration patterns, urban growth, and activity changes using proxy metrics derived from free satellite data.

### 1.2 Core Constraint
Detecting individual cars requires **5-30cm resolution**, but free satellite data maxes out at **10m (Sentinel-2)**. This project uses **proxy-based analysis** instead of direct vehicle detection.

### 1.3 Key Decisions
| Decision | Choice |
|----------|--------|
| Budget | Free data only |
| Scope | Global/exploratory |
| Accuracy | Proxy estimation acceptable |
| Product | Web application |
| Timeline | Exploration/learning project |

---

## 2. Product Requirements

### 2.1 Product Type
- **Primary:** Web application with interactive dashboard
- **Audience:** Personal research, small team, public/open source, stakeholders/clients
- **Goal:** Public launch ready

### 2.2 User Features

**Region Selection:**
- Predefined cities/regions (curated list)
- Draw polygons on map
- Upload GeoJSON/Shapefile

**Temporal Analysis:**
- Full Sentinel-2 archive (2015+)
- Granularity: Finest possible per data source (see table below)
- Seasonal comparisons (winter vs summer)

**Temporal Resolution by Metric (17 total):**
| Metric | Data Source | Resolution | Granularity | Notes |
|--------|-------------|------------|-------------|-------|
| NDVI | Sentinel-2 | 10m | Weekly | Vegetation health |
| Nightlights | VIIRS Black Marble | 375m | Daily | Activity proxy |
| Urban Density | GHSL SMOD | 10m | Monthly | Built-up fraction |
| Parking | Sentinel-2 (NDBI) | 10m | Weekly | Occupancy proxy |
| Land Cover | Dynamic World | 10m | Monthly | Land use classification |
| Surface Water | JRC GSW | 30m | Monthly | Water extent |
| Active Fire | VIIRS 375m | 375m | Daily | Fire hotspots |
| NO2 | Sentinel-5P | 7km | Monthly | Air quality |
| Temperature | ERA5-Land | 11km | Monthly | Weather context |
| Precipitation | ERA5-Land | 11km | Monthly | Rainfall |
| Aerosol | Sentinel-5P | 7km | Monthly | Smoke/dust |
| Cropland | USDA CDL | 30m | Yearly | Crop types (US) |
| Evapotranspiration | OpenET | 30m | Monthly | Water use (US) |
| Soil Moisture | SMAP | 10km | Monthly | Drought indicator |
| Impervious | GAIA | 30m | Yearly | Urban footprint |
| Fire Historical | MODIS FIRMS | 1km | Monthly | Fire archive |
| Canopy Height | GEDI | 1km | Static | Forest structure |

See `docs/GEE_DATASETS.md` for detailed dataset specifications.

**Visualization Outputs:**
- Interactive heatmaps (zoomable, time-slider)
- Time-lapse animations (GIF/video)
- Comparative charts (line/bar)
- Downloadable reports (PDF/CSV)

### 2.3 Use Cases
1. **Seasonal migration patterns** - Track population shifts (snowbirds, tourists)
2. **Urban growth over time** - Monitor city expansion
3. **Event impact analysis** - Study COVID, natural disasters, etc.
4. **General exploration** - Open-ended research

---

## 3. Technical Architecture

### 3.1 Stack Overview

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript |
| Maps | Leaflet (open source, free) |
| Charts | D3.js |
| State Management | Zustand |
| Backend | FastAPI (Python, fully async) |
| Database | PostgreSQL + PostGIS |
| Region Storage | PMTiles (cloud-optimized) |
| Auth | Simple API keys |
| Logging | Structured JSON (structlog) |
| Containers | Docker Compose |
| Hosting | Local initially |
| Offline | Online only (no PWA) |

### 3.2 Data Sources (Multi-Provider Strategy)

**Primary Sources:**
| Source | Data Type | Spatial Res | Temporal Res | Access Method |
|--------|-----------|-------------|--------------|---------------|
| Sentinel-2 | Optical imagery | 10m | 5 days | GEE, Copernicus, Planetary Computer |
| VIIRS | Nighttime lights | 375m-750m | Monthly composite | GEE, NOAA |
| Global Human Settlement Layer | Built-up areas | 10m | Multi-year epochs | GEE |
| OpenStreetMap | Road networks, POIs | Vector | Continuous | Overpass API |
| WorldPop | Population density | 100m | Annual | Direct download |

**Alternative/Supplementary Platforms (to reduce GEE dependency):**
| Platform | Access | Notes |
|----------|--------|-------|
| [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/) | Free (Azure) | STAC-based, Sentinel-2, Landsat |
| [AWS Open Data](https://aws.amazon.com/earth/) | Free (S3) | Sentinel-2, Landsat-8, CBERS |
| [Copernicus Data Space](https://dataspace.copernicus.eu/) | Free (EU) | Direct Sentinel access |
| [Sentinel Hub](https://www.sentinel-hub.com/) | Freemium | 30-day free trial, good API |

### 3.3 Project Structure

```
satellite-data/
├── backend/                     # FastAPI (dockerless)
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── settings.py          # repo-root .env + local defaults
│   │   ├── db.py                # SQLite (aiosqlite)
│   │   ├── models.py            # Region + ExportJob
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── gee.py               # Metric definitions + EE compute/tiles
│   │   └── routes/
│   │       ├── regions.py
│   │       ├── metrics.py
│   │       ├── tiles.py
│   │       ├── analysis.py
│   │       └── exports.py
│   ├── data/predefined_regions.json
│   └── requirements.txt
│
├── frontend/                    # React + TypeScript (Vite)
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── scripts/
│   ├── setup_gee.py
│   └── seed_regions.py
│
├── data/                        # local runtime data (SQLite + exports)
└── docs/
```

---

## 4. Data Pipeline Design

### 4.1 Processing Model (Hybrid)

**Pre-computed:**
- Major US cities (top 50 metros)
- Global megacities (top 30)
- Seasonal migration hotspots (Phoenix, Miami, Las Vegas, etc.)
- Monthly composites for predefined regions

**On-demand:**
- Custom drawn/uploaded regions
- Specific date ranges
- Higher temporal granularity requests

### 4.2 Pipeline Stages

```
1. INGEST
   ├── Query satellite provider APIs
   ├── Download tiles for region + date range
   └── Store raw data in cache (GeoTIFF)

2. PREPROCESS
   ├── Cloud masking (Sentinel-2 SCL band)
   ├── Atmospheric correction (if needed)
   ├── Mosaic multiple tiles
   └── Store processed imagery

3. FEATURE EXTRACTION
   ├── Calculate NDVI
   ├── Extract nighttime light values
   ├── Classify land use
   ├── Detect parking lots
   └── Store feature rasters

4. TEMPORAL AGGREGATION
   ├── Generate weekly/monthly composites
   ├── Compute seasonal averages
   └── Store time series

5. ANALYSIS
   ├── Calculate change metrics
   ├── Identify anomalies
   ├── Estimate migration proxies
   └── Store results in PostGIS

6. VISUALIZATION
   ├── Generate tile layers for map
   ├── Compute chart data
   ├── Create animations
   └── Serve via API
```

### 4.3 Database Schema (PostGIS)

```sql
-- Regions table
CREATE TABLE regions (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    geometry GEOMETRY(POLYGON, 4326),
    type VARCHAR(50), -- 'predefined', 'custom'
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Temporal data
CREATE TABLE observations (
    id UUID PRIMARY KEY,
    region_id UUID REFERENCES regions(id),
    date DATE,
    metric VARCHAR(50), -- 'ndvi', 'nightlights', 'urban_density', 'parking'
    value FLOAT,
    raster_path VARCHAR(500),
    metadata JSONB
);

-- Pre-computed results
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY,
    region_id UUID REFERENCES regions(id),
    analysis_type VARCHAR(50), -- 'seasonal_change', 'urban_growth', 'migration'
    start_date DATE,
    end_date DATE,
    results JSONB,
    created_at TIMESTAMP
);

-- API keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    key_hash VARCHAR(255),
    name VARCHAR(100),
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

---

## 5. Initial Regions to Pre-compute

### 5.1 Major US Cities (50)
New York, Los Angeles, Chicago, Houston, Phoenix, Philadelphia, San Antonio, San Diego, Dallas, San Jose, Austin, Jacksonville, Fort Worth, Columbus, Indianapolis, Charlotte, San Francisco, Seattle, Denver, Washington DC, Boston, El Paso, Nashville, Detroit, Oklahoma City, Portland, Las Vegas, Memphis, Louisville, Baltimore, Milwaukee, Albuquerque, Tucson, Fresno, Sacramento, Kansas City, Mesa, Atlanta, Omaha, Colorado Springs, Raleigh, Miami, Virginia Beach, Oakland, Minneapolis, Tulsa, Arlington, Tampa, New Orleans

### 5.2 Global Megacities (30)
Tokyo, Delhi, Shanghai, Sao Paulo, Mexico City, Cairo, Mumbai, Beijing, Dhaka, Osaka, New York, Karachi, Buenos Aires, Chongqing, Istanbul, Kolkata, Manila, Lagos, Rio de Janeiro, Tianjin, Kinshasa, Guangzhou, Los Angeles, Moscow, Shenzhen, Lahore, Bangalore, Paris, Jakarta, London

### 5.3 Seasonal Migration Hotspots (20)
Phoenix AZ, Miami FL, Tampa FL, Las Vegas NV, San Diego CA, Orlando FL, Tucson AZ, Palm Springs CA, Fort Myers FL, Scottsdale AZ, Naples FL, Sarasota FL, Albuquerque NM, Austin TX, San Antonio TX, Charleston SC, Savannah GA, Myrtle Beach SC, Fort Lauderdale FL, West Palm Beach FL

### 5.4 Curated Example Analyses (Presets)

These are pre-built analyses users can explore immediately:

**1. Snowbird Migration Pattern**
- Regions: Phoenix, Miami, Tampa, Tucson
- Comparison: Dec-Feb vs Jun-Aug
- Visuals: Migration flow animation, seasonal bar charts
- Story: How winter populations swell in Sun Belt cities

**2. COVID-19 Impact Analysis**
- Regions: New York, San Francisco, Las Vegas
- Comparison: Jan 2020 vs Jan 2021 vs Jan 2022
- Visuals: Year-over-year charts, difference maps
- Story: Activity collapse and recovery patterns

**3. Urban Growth: Phoenix 2015-2024**
- Region: Phoenix Metro
- Timespan: Full Sentinel-2 archive
- Visuals: Urban expansion animation, growth charts
- Story: Tracking one of America's fastest-growing cities

**4. College Town Seasonality**
- Regions: Austin TX, Ann Arbor MI, Boulder CO
- Comparison: Academic year (Sep-May) vs Summer
- Visuals: Small multiples, time series
- Story: University impact on city activity

**5. Tourist Destination Patterns**
- Regions: Las Vegas, Orlando, Cancun
- Comparison: Peak season vs off-season
- Visuals: Heatmaps, seasonal charts
- Story: Tourism-driven activity fluctuations

---

## 6. API Design

### 6.1 Endpoints

```
# Regions
GET    /api/v1/regions                    # List predefined regions
POST   /api/v1/regions                    # Create custom region
GET    /api/v1/regions/{id}               # Get region details
DELETE /api/v1/regions/{id}               # Delete custom region

# Analysis
GET    /api/v1/analysis/{region_id}       # Get cached analysis
POST   /api/v1/analysis                   # Request new analysis
GET    /api/v1/analysis/{id}/status       # Check processing status

# Metrics
GET    /api/v1/metrics/{region_id}        # Get time series data
GET    /api/v1/metrics/{region_id}/compare # Compare two periods

# Exports
POST   /api/v1/exports/pdf                # Generate PDF report
POST   /api/v1/exports/csv                # Export data as CSV
POST   /api/v1/exports/animation          # Generate time-lapse

# Tiles (for map rendering)
GET    /api/v1/tiles/{region_id}/{metric}/{z}/{x}/{y}.png

# Auth
POST   /api/v1/auth/keys                  # Generate new API key
DELETE /api/v1/auth/keys/{id}             # Revoke API key
```

### 6.2 Response Examples

**GET /api/v1/metrics/{region_id}**
```json
{
  "region_id": "uuid",
  "region_name": "Phoenix, AZ",
  "metrics": {
    "nightlights": {
      "unit": "nW/cm²/sr",
      "data": [
        {"date": "2023-01", "value": 45.2},
        {"date": "2023-02", "value": 48.7}
      ]
    },
    "ndvi": {
      "unit": "index (-1 to 1)",
      "data": [...]
    }
  },
  "seasonal_summary": {
    "winter_avg": {...},
    "summer_avg": {...},
    "change_pct": {...}
  }
}
```

---

## 7. Visual Output & Frontend Components

### 7.1 Complete Visual Catalog

This section details every visualization the platform will produce.

---

#### **CATEGORY 1: Map-Based Visualizations**

**1.1 Population/Activity Density Heatmaps**
```
┌─────────────────────────────────────────┐
│  [Map View - Phoenix Metro]             │
│  ┌─────────────────────────────────┐    │
│  │        🟥🟥🟧                    │    │
│  │      🟥🟥🟥🟧🟨                  │    │
│  │    🟧🟥🟥🟥🟧🟨🟩               │ ← Intensity gradient    │
│  │      🟧🟧🟨🟩🟩                  │    │
│  │        🟨🟩🟩🟩                  │    │
│  └─────────────────────────────────┘    │
│  Legend: 🟩 Low  🟨 Medium  🟧 High  🟥 Very High │
│  Metric: Nighttime Lights | Date: Jan 2024       │
└─────────────────────────────────────────┘
```
- **Based on:** VIIRS nighttime lights, built-up density
- **Use case:** See where people are concentrated
- **Interactivity:** Hover for exact values, click for details

**1.2 Change Detection Maps (Before/After)**
```
┌───────────────────┬───────────────────┐
│   WINTER 2023     │   SUMMER 2023     │
│  ┌─────────────┐  │  ┌─────────────┐  │
│  │  🟥🟥🟧     │  │  │  🟧🟨🟩     │  │
│  │  🟥🟥🟧     │  │  │  🟨🟩🟩     │  │
│  │  🟧🟧🟨     │  │  │  🟩🟩🟩     │  │
│  └─────────────┘  │  └─────────────┘  │
│  High activity    │  Lower activity   │
└───────────────────┴───────────────────┘
        ↑ Side-by-side synchronized views
```
- **Use case:** Compare two time periods visually
- **Interactivity:** Synced pan/zoom, swipe divider

**1.3 Difference Maps (Delta Visualization)**
```
┌─────────────────────────────────────────┐
│  [Change Map: Summer - Winter]          │
│  ┌─────────────────────────────────┐    │
│  │        🔵🔵🔵                    │    │
│  │      🔵🔵⚪🟠🟠                  │    │
│  │    🔵🔵⚪⚪🟠🟠🟠               │ ← Blue=decrease, Orange=increase    │
│  │      🔵⚪🟠🟠🟠                  │    │
│  │        ⚪🟠🟠                    │    │
│  └─────────────────────────────────┘    │
│  Legend: 🔵 -50%  ⚪ No change  🟠 +50% │
└─────────────────────────────────────────┘
```
- **Based on:** Computed difference between two periods
- **Use case:** Where did activity increase/decrease?

**1.4 Vegetation/NDVI Maps**
```
┌─────────────────────────────────────────┐
│  [NDVI - Vegetation Health]             │
│  ┌─────────────────────────────────┐    │
│  │     🟫🟫🏙️🏙️🏙️                │    │
│  │   🟫🟤🏙️🏙️🏙️🏙️               │    │
│  │  🟢🟤🟤🏙️🏙️🏙️                │    │
│  │  🟢🟢🟤🟤🏙️                    │    │
│  │  🟢🟢🟢🟤                       │    │
│  └─────────────────────────────────┘    │
│  Legend: 🟢 Dense veg  🟤 Sparse  🟫 Bare  🏙️ Urban │
└─────────────────────────────────────────┘
```
- **Use case:** Track urban sprawl, seasonal vegetation changes

**1.5 Parking Lot Occupancy Overlay**
```
┌─────────────────────────────────────────┐
│  [Large Parking Lots - Occupancy]       │
│  ┌─────────────────────────────────┐    │
│  │     🅿️ Mall (78%)               │    │
│  │  ⬜⬛⬛⬛⬛⬛⬛⬛⬜⬜            │ ← Visual fill level   │
│  │                                  │    │
│  │     🅿️ Airport (92%)            │    │
│  │  ⬛⬛⬛⬛⬛⬛⬛⬛⬛⬜            │    │
│  │                                  │    │
│  │     🅿️ Stadium (15%)            │    │
│  │  ⬛⬜⬜⬜⬜⬜⬜⬜⬜⬜            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```
- **Based on:** Spectral analysis of large paved areas
- **Use case:** Proxy for commercial activity

---

#### **CATEGORY 2: Animated Visualizations**

**2.1 Time-Lapse Animation (Monthly)**
```
┌─────────────────────────────────────────┐
│  [Animation: 2023 Monthly Activity]     │
│  ┌─────────────────────────────────┐    │
│  │                                  │    │
│  │      [Frame showing Jan 2023]    │    │
│  │                                  │    │
│  └─────────────────────────────────┘    │
│  ◀️ ⏸️ ▶️   🔘─────────────○        │
│            Jan                 Dec      │
│  Speed: 1x  |  Loop: On  |  Export GIF  │
└─────────────────────────────────────────┘
```
- **Output:** Animated playback in browser
- **Frames:** Monthly (12/year) or weekly (52/year)
- **Controls:** Play/pause, speed, scrubber, loop

**2.2 Seasonal Migration Flow Animation**
```
┌─────────────────────────────────────────┐
│  [Migration Flow: Northeast → Florida]  │
│  ┌─────────────────────────────────┐    │
│  │     NYC ●────→                  │    │
│  │      │     ╲                    │    │
│  │      │      ╲                   │ ← Animated arrows    │
│  │      ▼       ╲                  │   showing flow    │
│  │           ──→ ● Miami           │    │
│  │                                  │    │
│  └─────────────────────────────────┘    │
│  Month: November | Flow intensity: HIGH │
└─────────────────────────────────────────┘
```
- **Based on:** Correlated activity changes between regions
- **Visual:** Animated particles/arrows showing direction
- **Use case:** Visualize snowbird migration patterns

**2.3 Urban Growth Animation (Yearly)**
```
┌─────────────────────────────────────────┐
│  [Urban Expansion: Phoenix 2015-2024]   │
│  ┌─────────────────────────────────┐    │
│  │                                  │    │
│  │    2015 boundary ─┐             │    │
│  │                   │             │    │
│  │         ┌─────────┴──┐          │ ← Expanding outline   │
│  │         │  URBAN     │          │    │
│  │         │  CORE      │          │    │
│  │         └────────────┘          │    │
│  │    2024 boundary (larger) ──────┤    │
│  └─────────────────────────────────┘    │
│  Year: 2024 | Growth: +23% since 2015   │
└─────────────────────────────────────────┘
```
- **Based on:** GHSL built-up layer changes
- **Use case:** Track city expansion over decades

---

#### **CATEGORY 3: Charts & Graphs (D3.js)**

**3.1 Multi-Metric Time Series**
```
┌─────────────────────────────────────────┐
│  [Activity Metrics Over Time]           │
│                                         │
│  ▲                                      │
│  │    ╭──╮     ╭──╮     ╭──╮           │
│  │   ╱    ╲   ╱    ╲   ╱    ╲  ← Nightlights (yellow)
│  │  ╱      ╲ ╱      ╲ ╱      ╲         │
│  │ ╱────────────────────────── ← NDVI (green)
│  │╱                                     │
│  └──────────────────────────────────▶   │
│    2022      2023      2024             │
│                                         │
│  [🟡 Nightlights] [🟢 NDVI] [🔵 Urban]  │
└─────────────────────────────────────────┘
```
- **Interactivity:** Hover tooltips, zoom, toggle metrics
- **Use case:** See trends and correlations over time

**3.2 Seasonal Comparison Bar Chart**
```
┌─────────────────────────────────────────┐
│  [Seasonal Comparison: Phoenix]         │
│                                         │
│        Winter    Summer                 │
│         ████      ██                    │
│  Night- ████      ██                    │
│  lights ████      ██       -35%         │
│         ████      ██                    │
│                                         │
│         ██        ████                  │
│  NDVI   ██        ████     +45%         │
│         ██        ████                  │
│                                         │
└─────────────────────────────────────────┘
```
- **Use case:** Clear seasonal differences at a glance

**3.3 Year-over-Year Comparison**
```
┌─────────────────────────────────────────┐
│  [Year-over-Year: January Comparison]   │
│                                         │
│  2020 ████████████████  (baseline)      │
│  2021 ████████████      -25% (COVID)    │
│  2022 █████████████████ +8%             │
│  2023 ██████████████████ +12%           │
│  2024 ███████████████████ +15%          │
│                                         │
└─────────────────────────────────────────┘
```
- **Use case:** Event impact analysis (COVID, etc.)

**3.4 Regional Ranking Chart**
```
┌─────────────────────────────────────────┐
│  [Top 10 Winter Activity Increases]     │
│                                         │
│  1. Phoenix, AZ      ███████████ +42%   │
│  2. Miami, FL        ██████████  +38%   │
│  3. Tampa, FL        █████████   +35%   │
│  4. Las Vegas, NV    ████████    +31%   │
│  5. San Diego, CA    ███████     +28%   │
│  ...                                    │
└─────────────────────────────────────────┘
```
- **Use case:** Compare regions, find patterns

**3.5 Correlation Scatter Plot**
```
┌─────────────────────────────────────────┐
│  [Nightlights vs Urban Density]         │
│                                         │
│  ▲ Urban                                │
│  │ Density            ●                 │
│  │              ●  ● ●                  │
│  │         ●  ●   ●                     │
│  │      ●  ●  ●                         │
│  │   ●  ●                               │
│  │ ●                                    │
│  └────────────────────────────────▶     │
│                        Nightlights      │
│  R² = 0.87                              │
└─────────────────────────────────────────┘
```
- **Use case:** Validate proxy metric correlations

---

#### **CATEGORY 4: Comparative Views**

**4.1 Small Multiples (Region Grid)**
```
┌─────────────────────────────────────────┐
│  [Top Migration Destinations]           │
│                                         │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │ PHX │ │ MIA │ │ TPA │ │ LAS │       │
│  │ +42%│ │ +38%│ │ +35%│ │ +31%│       │
│  └─────┘ └─────┘ └─────┘ └─────┘       │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │ SAN │ │ ORL │ │ TUS │ │ PSP │       │
│  │ +28%│ │ +25%│ │ +22%│ │ +20%│       │
│  └─────┘ └─────┘ └─────┘ └─────┘       │
│                                         │
│  Each thumbnail = mini heatmap          │
└─────────────────────────────────────────┘
```
- **Use case:** Compare many regions at once

**4.2 Split-Screen Temporal Compare**
```
┌─────────────────────────────────────────┐
│  [Before/After: COVID Impact]           │
│                                         │
│  ┌────────────────┬────────────────┐    │
│  │ Jan 2020       │ Jan 2021       │    │
│  │                │                │    │
│  │  [Heatmap]     │  [Heatmap]     │    │
│  │                │                │    │
│  │ Normal         │ COVID          │    │
│  └────────────────┴────────────────┘    │
│                                         │
│  ◀──────────|───────────▶ Swipe to compare │
└─────────────────────────────────────────┘
```

---

#### **CATEGORY 5: Reports & Exports**

**5.1 PDF Report Layout**
```
┌─────────────────────────────────────────┐
│  📄 MIGRATION ANALYSIS REPORT           │
│     Phoenix Metropolitan Area           │
│     Period: Winter 2023 vs Summer 2023  │
│─────────────────────────────────────────│
│                                         │
│  EXECUTIVE SUMMARY                      │
│  - Winter activity +42% above summer    │
│  - Peak month: January                  │
│  - Primary pattern: Snowbird migration  │
│                                         │
│  [Embedded Heatmap Image]               │
│                                         │
│  [Embedded Time Series Chart]           │
│                                         │
│  KEY METRICS TABLE                      │
│  ┌──────────────┬─────────┬─────────┐  │
│  │ Metric       │ Winter  │ Summer  │  │
│  ├──────────────┼─────────┼─────────┤  │
│  │ Nightlights  │ 58.2    │ 40.9    │  │
│  │ Urban Index  │ 0.82    │ 0.79    │  │
│  │ NDVI         │ 0.15    │ 0.28    │  │
│  └──────────────┴─────────┴─────────┘  │
│                                         │
│  METHODOLOGY NOTES                      │
│  [Technical details, data sources...]   │
│                                         │
└─────────────────────────────────────────┘
```

**5.2 Interactive HTML Report**
```
┌─────────────────────────────────────────┐
│  🌐 INTERACTIVE REPORT (HTML)           │
│                                         │
│  Same content as PDF, but:              │
│  - Charts are interactive (D3.js)       │
│  - Maps can be panned/zoomed            │
│  - Time slider works                    │
│  - Click to drill down                  │
│                                         │
│  Can be hosted or shared as single file │
└─────────────────────────────────────────┘
```

**5.3 Data Export (CSV)**
```
date,region,metric,value,unit
2023-01,phoenix,nightlights,58.2,nW/cm²/sr
2023-01,phoenix,ndvi,0.15,index
2023-01,phoenix,urban_density,0.82,ratio
2023-02,phoenix,nightlights,56.1,nW/cm²/sr
...
```

---

### 7.2 Main Application Views

1. **Dashboard** - Overview with global map, quick stats, featured analyses
2. **Region Explorer** - Select/create regions, view details
3. **Analysis View** - Deep dive into metrics, charts, comparisons
4. **Animation Studio** - Create and export time-lapse animations
5. **Export Center** - Generate PDF/HTML reports, download data
6. **Example Gallery** - Curated analyses (COVID, snowbirds, etc.)

### 7.3 Component Architecture

```
MapContainer
├── BaseMap (Leaflet + OpenStreetMap tiles)
├── HeatmapLayer (activity intensity raster)
├── RegionLayer (PMTiles boundaries)
├── ParkingOverlay (detected lots with occupancy)
├── FlowLayer (migration arrows/particles)
├── TimeSlider (scrub through dates)
├── DrawControls (polygon drawing)
└── CompareControls (split view, swipe)

ChartPanel (D3.js)
├── TimeSeriesChart (multi-metric line chart)
├── SeasonalBarChart (side-by-side comparison)
├── YearOverYearChart (horizontal bars)
├── RankingChart (sorted region comparison)
├── ScatterPlot (correlation visualization)
└── SmallMultiples (grid of mini-charts)

AnimationPanel
├── FramePreview (current frame display)
├── PlaybackControls (play, pause, speed)
├── Timeline (scrubber with frame markers)
├── ExportOptions (GIF, WebM, frame sequence)
└── FlowAnimator (migration particle system)

ControlPanel
├── RegionSelector (dropdown + search + draw)
├── DateRangePicker (calendar + presets)
├── MetricToggle (checkboxes for each metric)
├── CompareSelector (period A vs period B)
└── ExportButtons (PDF, HTML, CSV, Animation)

ReportGenerator
├── PDFBuilder (ReportLab/WeasyPrint)
├── HTMLExporter (Jinja2 templates + D3)
└── CSVExporter (pandas to CSV)
```

---

## 8. Development Plan (Layer by Layer)

### Layer 1: Infrastructure
1. Set up Docker Compose (PostgreSQL + PostGIS, Redis, API)
2. Initialize FastAPI project with basic structure
3. Initialize React + TypeScript project
4. Set up database migrations (Alembic)
5. Configure CI/CD basics

### Layer 2: Data Pipeline
1. Implement GEE client with authentication
2. Add Planetary Computer client as fallback
3. Implement Sentinel-2 downloader with cloud masking
4. Add VIIRS nighttime lights processing
5. Implement caching layer for downloaded data
6. Write comprehensive tests for data pipeline

### Layer 3: Feature Extraction
1. Implement NDVI calculation
2. Implement nighttime light intensity extraction
3. Implement urban density estimation (GHSL integration)
4. Implement parking lot detection
5. Implement temporal aggregation (weekly/monthly composites)
6. Tests for all feature extractors

### Layer 4: Analysis Engine
1. Implement seasonal change detection
2. Implement trend analysis
3. Implement migration proxy calculation
4. Store results in PostGIS
5. API endpoints for analysis results
6. Tests for analysis modules

### Layer 5: API Layer
1. Implement all REST endpoints
2. Add API key authentication
3. Implement tile server for map layers
4. Add rate limiting
5. OpenAPI documentation
6. API integration tests

### Layer 6: Frontend
1. Set up React project with Leaflet
2. Implement map with region display
3. Add drawing controls
4. Implement time series charts
5. Add export functionality
6. Polish UI/UX
7. E2E tests with Playwright

### Layer 7: Pre-computation & Launch
1. Script to pre-compute initial regions
2. Performance optimization
3. Documentation (user guide, methodology)
4. Final testing
5. Prepare for public access

---

## 9. Testing Strategy

### 9.1 Test Levels

| Level | Framework | Focus |
|-------|-----------|-------|
| Unit | pytest | Individual functions, classes |
| Integration | pytest + testcontainers | Service interactions |
| E2E | Playwright | Full user flows |
| Performance | locust | API load testing |

### 9.2 Critical Test Cases

**Data Pipeline:**
- Cloud masking correctly removes cloudy pixels
- Multiple tiles mosaic without gaps
- Date range queries return expected data
- Fallback to alternative provider works

**Feature Extraction:**
- NDVI values in expected range (-1 to 1)
- Nightlight values correlate with known urban areas
- Parking lot detection finds known large lots

**Analysis:**
- Seasonal comparison produces valid statistics
- Change detection identifies known events
- Results persist correctly in database

**API:**
- All endpoints return expected schemas
- Invalid inputs return appropriate errors
- API key auth works correctly
- Rate limiting functions

**Frontend:**
- Map renders with correct layers
- Region drawing works
- Charts display correct data
- Exports generate valid files

---

## 10. Error Handling

**Strategy:** Fail gracefully with user-friendly messages

### 10.1 Error Categories

| Category | User Message | Log Level |
|----------|--------------|-----------|
| Data unavailable | "No cloud-free imagery for this period. Try a different date range." | INFO |
| Processing failed | "Analysis failed. Our team has been notified." | ERROR |
| Rate limit | "Too many requests. Please wait." | WARN |
| Invalid input | "Invalid region geometry. Please check your input." | INFO |
| Provider outage | "Satellite data temporarily unavailable. Please try again later." | ERROR |

### 10.2 Retry Strategy
- Data downloads: 3 retries with exponential backoff
- Processing tasks: 2 retries
- Provider failover: Try GEE → Planetary Computer → Sentinel Hub

---

## 11. Documentation Requirements

### 11.1 Code Documentation
- Docstrings for all public functions/classes
- Type hints throughout
- README.md in each major directory

### 11.2 API Documentation
- OpenAPI/Swagger auto-generated
- Example requests/responses
- Error code reference

### 11.3 User Guide
- Getting started
- How to use each feature
- Interpreting results
- FAQ

### 11.4 Methodology Writeup
- Proxy metric definitions and justifications
- Data sources and their limitations
- Processing steps
- Validation approach
- Known limitations and caveats

---

## 12. Dependencies

### Backend (Python)
```
# Core
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.5.0
sqlalchemy>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0
geoalchemy2>=0.14.0
httpx>=0.26.0
aiofiles>=23.2.0

# Logging
structlog>=24.1.0
python-json-logger>=2.0.0

# Satellite data
earthengine-api>=0.1.380
planetary-computer>=1.0.0
pystac-client>=0.7.0
stackstac>=0.5.0

# Geospatial
rasterio>=1.3.0
geopandas>=0.14.0
shapely>=2.0.0
pyproj>=3.6.0
pmtiles>=3.2.0
rio-tiler>=6.2.0

# Processing
numpy>=1.26.0
pandas>=2.1.0
xarray>=2024.1.0
dask>=2024.1.0
scikit-image>=0.22.0

# Visualization
matplotlib>=3.8.0
pillow>=10.2.0
imageio>=2.33.0

# Export
reportlab>=4.0.0
weasyprint>=60.0
jinja2>=3.1.0

# Task queue
celery>=5.3.0
redis>=5.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
testcontainers>=3.7.0
```

### Frontend (Node.js)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "@react-leaflet/core": "^2.1.0",
    "d3": "^7.8.0",
    "axios": "^1.6.0",
    "date-fns": "^3.2.0",
    "zustand": "^4.4.0",
    "pmtiles": "^3.0.0",
    "protomaps-leaflet": "^3.0.0",
    "file-saver": "^2.0.5"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@types/react": "^18.2.0",
    "@types/leaflet": "^1.9.0",
    "@types/d3": "^7.4.0",
    "vitest": "^1.2.0",
    "@playwright/test": "^1.41.0"
  }
}
```

---

## 13. Verification Plan

### 13.1 Milestone Checkpoints

**M1: Infrastructure Ready**
- [ ] Docker Compose starts all services
- [ ] Database accepts connections
- [ ] API returns health check

**M2: Data Pipeline Working**
- [ ] Can download Sentinel-2 for a test region
- [ ] Cloud masking produces valid output
- [ ] Data cached correctly

**M3: Features Extracted**
- [ ] NDVI map generated for test region
- [ ] Nightlight values retrieved
- [ ] All metrics stored in database

**M4: Analysis Complete**
- [ ] Seasonal comparison produces results
- [ ] API returns analysis data
- [ ] Results match expected patterns for known regions

**M5: Frontend Functional**
- [ ] Map displays with regions
- [ ] Charts show time series
- [ ] Export generates valid files

**M6: Pre-computation Done**
- [ ] All initial regions processed
- [ ] Query response times acceptable (<2s)

**M7: Launch Ready**
- [ ] All documentation complete
- [ ] Tests passing (>80% coverage)
- [ ] No critical bugs

### 13.2 Validation Approach
- Compare Phoenix winter vs summer metrics (known seasonal variation)
- Verify COVID-period drop in activity (2020 vs 2019)
- Cross-reference with public mobility data where available

---

## 14. Additional Specifications (from Q&A)

### 14.1 Processing & Compute
- **Pre-computation:** Sequential local processing (one region at a time)
- **Tile server:** Dynamic tile generation on-demand
- **Cache invalidation:** Manual only (no automatic expiry)

### 14.2 Data Handling
- **Cloud cover:** Show partial data with warning (don't fail)
- **Region size limits:** No hard limit (users can draw any size)
- **Hemisphere handling:** Auto-detect Southern Hemisphere, flip winter/summer labels
- **Units:** SI/metric only throughout
- **Provider selection:** User-selectable (GEE, Planetary Computer, Sentinel Hub)

### 14.3 Frontend Specifics
- **Date picker:** Both calendar picker + predefined presets (Last year, Winter 2023, etc.)
- **Animations:** Client-side JavaScript (instant preview)
- **Reports:** Both PDF and HTML export options
- **Example presets:** Include curated examples (COVID impact, snowbird patterns) + custom creation

### 14.4 Documentation Style
- **Methodology:** Technical reference with equations, citations, reproducibility focus (academic-style)

### 14.5 Accessibility
- Not a priority for v1 (focus on functionality first)

---

## 15. Known Limitations

1. **Resolution:** Cannot detect individual vehicles (10m vs 30cm needed)
2. **Proxy accuracy:** Metrics are correlational, not causal
3. **Cloud cover:** Some regions/periods may have gaps
4. **Nightlight blooming:** Urban core may oversaturate
5. **Temporal lag:** Composite generation introduces delays
6. **Scale:** Global pre-computation requires significant storage
7. **Large regions:** No hard limit means some queries may be very slow

---

## 16. Future Enhancements (Out of Scope for v1)

- Integration with cell phone mobility data (Facebook Data for Good)
- Traffic sensor data from government portals
- Commercial satellite data validation
- ML model for activity prediction
- Multi-user accounts with saved analyses
- Real-time monitoring alerts

---

## 17. Research Sources

### Satellite Data Platforms
- [Google Earth Engine](https://earthengine.google.com/)
- [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/)
- [Copernicus Data Space](https://dataspace.copernicus.eu/)
- [AWS Earth on AWS](https://aws.amazon.com/earth/)
- [Sentinel Hub](https://www.sentinel-hub.com/)

### Datasets & Tools
- [satellite-image-deep-learning/datasets](https://github.com/satellite-image-deep-learning/datasets)
- [satellite-image-deep-learning/techniques](https://github.com/satellite-image-deep-learning/techniques)
- [geemap](https://geemap.org/)
- [COWC Dataset](https://gdo152.llnl.gov/cowc/)

### Research Papers
- [Imagery2Flow: Predicting mobility flows from satellite imagery](https://www.nature.com/articles/s41467-025-65373-z)
- [Traffic Patterns from Planet Imagery (COVID)](https://www.mdpi.com/2072-4292/13/2/208)
- [Population Estimation from Satellite](https://arxiv.org/abs/1708.09086)

---

---

## 18. Additional Documentation

For detailed information on specific topics, see:

- **`docs/GEE_DATASETS.md`** - Complete GEE dataset specifications, colormaps, value ranges, and implementation guide for all 17 metrics
- **`docs/METHODOLOGY.md`** - Technical methodology for proxy metrics and analysis
- **`docs/USER_GUIDE.md`** - End-user documentation for the platform
- **`CHECKLIST.md`** - Shipping checklist with current implementation status

---

*This document serves as the source of truth for the SatelliteMigration project. Update as requirements evolve.*
