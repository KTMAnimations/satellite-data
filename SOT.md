# Satellite Imagery Migration & Activity Analysis Platform

## Complete Specification Document

**Project Name:** Exeter Astronomy
**Last Updated:** 2026-02-01
**Status:** Dockerless local-first implementation (SQLite + Earth Engine)

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

**Temporal Analysis:**
- Full Sentinel-2 archive (2015+)
- Granularity: Finest possible per data source (see table below)
- Seasonal comparisons (winter vs summer)

**Temporal Resolution by Metric (15 total):**
| Metric | Data Source (GEE Collection) | Resolution | Default Granularity | Supported | Notes |
|--------|------------------------------|------------|---------------------|-----------|-------|
| NDVI | Sentinel-2 + MODIS fill | 10m | Weekly | weekly, monthly | Vegetation health |
| Nightlights | VIIRS Black Marble / NOAA monthly | 375m | Monthly | daily, monthly | Activity proxy |
| Urban Density | GHSL SMOD | 10m | Monthly | monthly | Built-up fraction |
| Parking | Sentinel-2 (NDBI) | 10m | Weekly | weekly, monthly | Occupancy proxy |
| Land Cover | Dynamic World | 10m | Weekly | weekly, monthly | Built-up probability |
| Surface Water | JRC GSW | 30m | Monthly | monthly | Water extent |
| NO2 | Sentinel-5P | 7km | Daily | daily, monthly | Air quality |
| Temperature | ERA5-Land Daily Agg | 11km | Daily | daily, monthly | 2m air temperature |
| Precipitation | CHIRPS Daily | ~5km | Daily | daily, monthly | Rainfall |
| Aerosol | Sentinel-5P | 7km | Daily | daily, monthly | UV aerosol index |
| Cropland | ESA WorldCover | 10m | Monthly | monthly | Cropland fraction (global) |
| Evapotranspiration | MODIS MOD16A2GF | ~500m | Monthly | monthly | Water use (global) |
| Soil Moisture | SMAP L4 | ~11km | Weekly | weekly, monthly | Root-zone moisture (m³/m³) |
| Impervious | GAIA | 30m | Monthly | monthly | Urban footprint |
| Canopy Height | GEDI / Simard | 1km | Monthly | monthly | Forest structure (static dataset) |

See `docs/GEE_DATASETS.md` for detailed dataset specifications.

**Visualization Outputs:**
- Interactive heatmaps (zoomable, time-slider)
- Time-lapse animations (GIF export)
- Comparative charts (line/bar/scatter)
- Downloadable reports (PDF)

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
| Frontend | React + TypeScript (Vite) |
| Maps | Leaflet (open source, free) |
| Charts | D3.js |
| State Management | Zustand |
| Backend | FastAPI (Python, fully async) |
| Database | SQLite (aiosqlite) |
| Region Storage | GeoJSON in SQLite TEXT columns |
| Satellite Compute | Google Earth Engine (server-side) |
| Auth | None (local/personal use) |
| Logging | Standard Python `logging` |
| Containers | None (dockerless, local-first) |
| Background Tasks | In-process (FastAPI BackgroundTasks) |
| Hosting | Local initially |
| Offline | Online only (no PWA) |

### 3.2 Data Sources (Google Earth Engine)

All satellite data is accessed exclusively through Google Earth Engine. GEE handles server-side compute, compositing, and tile generation — no local geospatial libraries (rasterio, GDAL, etc.) are needed.

**Primary GEE Collections:**
| Source | Data Type | Spatial Res | Temporal Res |
|--------|-----------|-------------|--------------|
| Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED) | Optical imagery (NDVI) | 10m | 5 days |
| MODIS (MODIS/061/MOD13A2) | NDVI fill layer | 1km | 16 days |
| VIIRS Black Marble (NASA/VIIRS/002/VNP46A2) | Daily nighttime lights | 375m | Daily |
| NOAA Monthly (NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG) | Monthly nightlight composites | 375m | Monthly |
| GHSL SMOD (JRC/GHSL/P2023A/GHS_SMOD_V1_0) | Built-up areas | 10m | Multi-year |
| Dynamic World (GOOGLE/DYNAMICWORLD/V1) | Land cover | 10m | Near real-time |
| JRC GSW (JRC/GSW1_4/MonthlyHistory) | Surface water | 30m | Monthly |
| Sentinel-5P (COPERNICUS/S5P/OFFL/L3_NO2) | NO2 pollution | 7km | Daily |
| ERA5-Land Daily (ECMWF/ERA5_LAND/DAILY_AGGR) | Temperature | 11km | Daily |
| CHIRPS (UCSB-CHG/CHIRPS/DAILY) | Precipitation | ~5km | Daily |
| Sentinel-5P (COPERNICUS/S5P/OFFL/L3_AER_AI) | Aerosol index | 7km | Daily |
| ESA WorldCover (ESA/WorldCover/v200) | Cropland fraction | 10m | Annual |
| MODIS (MODIS/061/MOD16A2GF) | Evapotranspiration | ~500m | 8-day |
| SMAP L4 (NASA/SMAP/SPL4SMGP/008) | Soil moisture | ~11km | 3-hourly |
| GAIA (Tsinghua/FROM-GLC/GAIA/v10) | Impervious surface | 30m | Annual |
| GEDI + Simard (NASA/JPL/global_forest_canopy_height_2005) | Canopy height | 1km | Static |

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
   └── Return results via API (stateless, no persistent storage)

6. VISUALIZATION
   ├── Generate tile layers for map
   ├── Compute chart data
   ├── Create animations
   └── Serve via API
```

### 4.3 Database Schema (SQLite via SQLAlchemy)

The backend uses SQLite with two tables managed by SQLAlchemy ORM (`backend/app/models.py`):

```python
# Region — stores predefined and custom regions
class Region:
    id: str (UUID, primary key)
    name: str
    description: str | None
    geometry: str  # GeoJSON text (Polygon)
    type: str      # 'predefined' | 'custom'
    country: str | None
    state_province: str | None
    category: str | None  # 'major_city' | 'megacity' | 'migration_hotspot'
    created_at: datetime
    updated_at: datetime

# ExportJob — tracks PDF/GIF export background tasks
class ExportJob:
    id: str (UUID, primary key)
    region_id: str (FK → Region)
    format: str         # 'pdf' | 'gif'
    status: str         # 'pending' | 'processing' | 'completed' | 'failed'
    progress: float | None
    message: str | None
    file_path: str | None
    file_size: int | None
    parameters: str | None  # JSON text
    created_at: datetime
    completed_at: datetime | None
```

There is no observations or analysis_results table — metric data is computed on-the-fly by Earth Engine and returned directly through the API.

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

# Metrics
GET    /api/v1/metrics/{region_id}        # Get time series data
GET    /api/v1/metrics/{region_id}/compare # Compare two periods

# Tiles (EE-generated, served via URL template)
GET    /api/v1/tiles/template             # Get EE tile URL for metric/date/granularity

# Exports
POST   /api/v1/exports/pdf                # Generate PDF report
POST   /api/v1/exports/animation          # Generate GIF time-lapse
GET    /api/v1/exports/{id}               # Check export status
GET    /api/v1/exports/{id}/download      # Download completed export

# Presets
GET    /api/v1/presets                    # List curated analysis presets
GET    /api/v1/presets/{id}               # Get preset details

# Health
GET    /api/v1/status                     # Health check
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

**5.2 Data Export (CSV)**
```
date,region,metric,value,unit
2023-01,phoenix,nightlights,58.2,nW/cm²/sr
2023-01,phoenix,ndvi,0.15,index
2023-01,phoenix,urban_density,0.82,ratio
2023-02,phoenix,nightlights,56.1,nW/cm²/sr
...
```

> Note: Interactive HTML reports and WebM video exports are not currently implemented. Only PDF and GIF exports are available.

---

### 7.2 Main Application Views

1. **Dashboard** - Overview with global map, quick stats, featured analyses
2. **Region Explorer** - Select/create regions, view details
3. **Analysis View** - Deep dive into metrics, charts, comparisons
4. **Animation Studio** - Create and export time-lapse animations
5. **Export Center** - Generate PDF reports, download data

### 7.3 Component Architecture

```
MapContainer (components/Map/MapContainer.tsx)
├── BaseMap (Leaflet + MapTiler OSM tiles)
├── CompositeTileLayer (EE-generated metric overlay)
├── HeatmapLegend (color scale + values)
├── MetricOverlay (metric raster via EE tile URLs)
├── FlowLayer (migration arrows/particles)
├── SplitScreenCompare (side-by-side temporal compare)
└── DrawControls (polygon drawing for custom regions)

Charts (components/Charts/)
├── TimeSeriesChart (multi-metric line chart, D3.js)
├── SeasonalBarChart (side-by-side comparison)
├── YearOverYearChart (horizontal bars)
├── RegionalRankingChart (sorted region comparison)
├── CorrelationScatter (scatter plot with R²)
├── SmallMultiples (grid of mini-charts)
└── TimeSlider (scrub through dates with playback)

Pages
├── Dashboard (overview with global map, quick stats)
├── RegionExplorer (select/create regions)
├── AnalysisView (deep dive: charts + map + granularity toggle)
├── MapPage (full-screen map with timeline)
├── AnimationStudio (GIF export with live preview)
├── CompareView (two-period comparison)
├── ExportCenter (PDF report generation)
└── (Presets are loaded via RegionExplorer/Dashboard)
```

---

## 8. Development Plan (Layer by Layer)

### Layer 1: Infrastructure
1. Initialize FastAPI project with SQLite + aiosqlite
2. Initialize React + TypeScript + Vite project
3. Set up GEE service account authentication
4. Seed predefined regions into SQLite
5. Configure GitHub Actions for deployment

### Layer 2: Data Pipeline (GEE Server-Side)
1. Implement GEE client with service account auth
2. Define all 17 metric computations in `gee.py`
3. Implement EE tile URL template generation
4. Add local tile caching layer (`data/cache/`)
5. Write tests for metric query params

### Layer 3: Feature Extraction (EE Compute)
1. Implement NDVI (Sentinel-2 + MODIS fill)
2. Implement nighttime light intensity (VIIRS)
3. Implement all Phase 1-4 metrics
4. Implement temporal aggregation (daily/weekly/monthly bucketing)
5. Tests for value ranges and units

### Layer 4: Analysis Engine
1. Implement seasonal change detection
2. Implement trend analysis
3. Implement period comparison (compare endpoint)
4. API endpoints for analysis results
5. Tests for analysis modules

### Layer 5: API Layer
1. Implement all REST endpoints (regions, metrics, tiles, exports, presets)
2. Implement EE tile URL template endpoint
3. Implement PDF and GIF export as background tasks
4. OpenAPI documentation (auto-generated by FastAPI)
5. API integration tests

### Layer 6: Frontend
1. Set up React project with Leaflet + Zustand
2. Implement map with EE tile overlay and legend
3. Add region explorer with drawing controls
4. Implement all chart types (time series, seasonal, YoY, scatter, rankings, small multiples)
5. Add Animation Studio with live preview and GIF export
6. Add granularity toggle for multi-granularity metrics
7. Polish UI/UX
8. E2E tests with Playwright

### Layer 7: Pre-computation & Launch
1. Script to seed predefined regions
2. Pre-cache tiles for common regions
3. Documentation (user guide, methodology, GEE datasets)
4. Final testing
5. Prepare for public access

---

## 9. Testing Strategy

### 9.1 Test Levels

| Level | Framework | Focus |
|-------|-----------|-------|
| Unit (backend) | pytest + pytest-asyncio | Individual functions, route handlers |
| Unit (frontend) | vitest | Components, utilities, services |
| E2E | Playwright | Full user flows |

### 9.2 Critical Test Cases

**Data Pipeline:**
- Cloud masking correctly removes cloudy pixels
- Multiple tiles mosaic without gaps
- Date range queries return expected data
- GEE queries return valid tile URLs

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
- Export jobs complete successfully

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
| Processing failed | "Analysis failed. Please try again." | ERROR |
| Invalid input | "Invalid region geometry. Please check your input." | INFO |
| GEE outage | "Satellite data temporarily unavailable. Please try again later." | ERROR |

### 10.2 Retry Strategy
- GEE tile requests: 3 retries with exponential backoff
- Export background tasks: 2 retries

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

See `backend/requirements.txt` for exact versions. Key dependencies:

```
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Storage
sqlalchemy>=2.0.0
aiosqlite>=0.20.0

# HTTP + exports
httpx>=0.26.0
pillow>=10.2.0
imageio>=2.33.0
reportlab>=4.0.0

# Satellite compute
earthengine-api>=0.1.380

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

### Frontend (Node.js)

See `frontend/package.json` for exact versions. Key dependencies:

```
react, react-dom, react-router-dom  # UI framework
leaflet, react-leaflet               # Interactive maps
d3                                   # Chart visualizations
zustand                              # State management
@tanstack/react-query                # Data fetching
@phosphor-icons/react                # Icons
```

---

## 13. Verification Plan

### 13.1 Milestone Checkpoints

**M1: Infrastructure Ready**
- [x] SQLite database initialized
- [x] API returns health check (`/api/v1/status`)
- [x] GEE service account authenticated

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
- **Data provider:** Google Earth Engine (sole provider)

### 14.3 Frontend Specifics
- **Date picker:** Both calendar picker + predefined presets (Last year, Winter 2023, etc.)
- **Animations:** Client-side JavaScript (instant preview)
- **Reports:** PDF export (GIF for animations)
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

- **`docs/GEE_DATASETS.md`** - Complete GEE dataset specifications, colormaps, value ranges, and implementation guide for all 15 metrics
- **`docs/METHODOLOGY.md`** - Technical methodology for proxy metrics and analysis
- **`docs/USER_GUIDE.md`** - End-user documentation for the platform

---

*This document serves as the source of truth for the Exeter Astronomy project. Update as requirements evolve.*
