# Satellite Migration Analysis Platform - User Guide

## Overview

The Satellite Migration Analysis Platform enables analysis of seasonal migration patterns, urban growth, and activity changes using satellite-derived proxy metrics from free data sources.

**Key Capabilities:**
- Analyze 17 different satellite-derived metrics
- Compare time periods (seasonal, year-over-year)
- Create time-lapse animations
- Export reports (PDF) and animations (GIF)

---

## Getting Started

### 1. Dashboard

The Dashboard is your entry point to the platform. Here you'll find:

- **Featured Analyses**: Pre-built examples showcasing platform capabilities
- **Quick Stats**: Overview of available regions and data coverage
- **Quick Start Guide**: Step-by-step introduction to using the platform
- **Data Sources**: Information about satellite data used

### 2. Selecting a Region

Navigate to **Region Explorer** to:

1. **Browse Predefined Regions**: 50+ major US cities and migration hotspots
2. **Search**: Type a city name to find specific regions
3. **Draw Custom Regions**: Use the drawing tools to define your own area

### 3. Analyzing Metrics

In the **Analysis View**, you can:

1. Select which metrics to display (e.g., NDVI, Nightlights, Urban Density)
2. Choose a date range using the calendar or presets
3. Toggle granularity (e.g., Daily/Monthly) for metrics that support multiple cadences
4. View time series charts showing metric trends
5. See the metric overlay on the map (zoom in for best performance and detail)
6. Export your analysis

---

## Available Metrics

### Core Metrics

| Metric | Description | Resolution | Cadence |
|--------|-------------|------------|---------|
| **NDVI** | Vegetation health index | 10m | Weekly / Monthly |
| **Nightlights** | Nighttime light intensity (activity proxy) | 375m | Daily / Monthly |
| **Urban Density** | Built-up area estimation | 10m | Monthly |
| **Parking** | Parking lot occupancy proxy | 10m | Weekly / Monthly |

### Land & Water

| Metric | Description | Resolution | Cadence |
|--------|-------------|------------|---------|
| **Land Cover** | Dynamic land cover classification | 10m | Weekly / Monthly |
| **Surface Water** | Water extent mapping | 30m | Monthly |
| **Impervious** | Impervious surface extent (1985-2018) | 30m | Monthly |

### Fire & Air Quality

| Metric | Description | Resolution | Cadence |
|--------|-------------|------------|---------|
| **Active Fire** | Current fire hotspots | 375m | Daily / Monthly |
| **Fire Historical** | Historical fire archive (2000+) | 1km | Monthly |
| **NO₂** | Nitrogen dioxide (air quality) | 7km | Daily / Monthly |
| **Aerosol** | Aerosol index (smoke/dust) | 7km | Daily / Monthly |

### Weather & Agriculture

| Metric | Description | Resolution | Cadence |
|--------|-------------|------------|---------|
| **Temperature** | Surface temperature | 11km | Daily / Monthly |
| **Precipitation** | Rainfall amounts | ~5km | Daily / Monthly |
| **Cropland** | Cropland fraction (ESA WorldCover) | 10m | Monthly |
| **Evapotranspiration** | Water loss (MODIS global) | ~500m | Monthly |
| **Soil Moisture** | Surface moisture (SMAP L4) | ~11km | Weekly / Monthly |

### Vegetation Structure

| Metric | Description | Resolution | Cadence |
|--------|-------------|------------|---------|
| **Canopy Height** | Forest canopy height (LiDAR-derived) | 1km | Static |

---

## Feature Guide

### Animation Studio

Create time-lapse animations showing metric changes over time.

**Steps:**
1. Navigate to **Animation Studio**
2. Select a metric from the dropdown
3. Choose start and end dates
4. Use the playback controls:
   - **Play/Pause**: Start or stop animation
   - **Speed**: Adjust playback speed (0.5x - 4x)
   - **Timeline**: Scrub to specific dates
5. Export as GIF

**Tips:**
- Use longer date ranges for more frames
- NDVI shows vegetation seasonality best
- Nightlights reveal urban activity patterns

### Compare View

Compare two time periods side-by-side.

**Steps:**
1. Navigate to **Compare** (from Analysis View)
2. Select a metric to compare
3. Choose Period A and Period B dates
4. Use presets for common comparisons:
   - **Winter vs Summer**: Seasonal patterns
   - **COVID Impact**: 2019 vs 2020
   - **Year over Year**: Same period, different years

**What You'll See:**
- Split-screen map showing both periods
- Change percentage indicator
- Average values for each period
- Observation counts

### Export Center

Generate downloadable reports and data.

**PDF Reports Include:**
- Executive summary
- Embedded charts and maps
- Key metrics table
- Methodology notes

**Animation Exports:**
- GIF format (universal, shareable)

---

## Example Gallery

### Snowbird Migration Pattern

Tracks winter population shifts to Sun Belt cities.

- **Regions**: Phoenix, Miami, Tampa, Tucson
- **Comparison**: December-February vs June-August
- **Key Finding**: Phoenix shows +42% winter activity increase

### COVID-19 Impact Analysis

Examines urban activity collapse and recovery.

- **Regions**: New York, San Francisco, Las Vegas
- **Comparison**: 2019 vs 2020 vs 2021
- **Key Finding**: Las Vegas saw -45% activity drop in April 2020

### Urban Growth: Phoenix 2015-2024

Tracks one of America's fastest-growing cities.

- **Region**: Phoenix Metro
- **Timespan**: 2015-2024
- **Key Finding**: Built-up area increased 23% since 2015

### College Town Seasonality

Shows university impact on city activity.

- **Regions**: Austin TX, Ann Arbor MI, Boulder CO
- **Comparison**: Academic year vs Summer
- **Key Finding**: Ann Arbor shows -22% summer activity drop

### Tourist Destination Patterns

Analyzes tourism-driven activity fluctuations.

- **Regions**: Las Vegas, Orlando
- **Comparison**: Peak vs off-season
- **Key Finding**: Clear correlation with school holiday periods

---

## Understanding the Data

### What Are Proxy Metrics?

At 10-meter resolution (Sentinel-2), we cannot detect individual vehicles or people. Instead, we measure **proxy indicators** that correlate with activity:

- **Nighttime Lights**: Brighter areas indicate more human activity
- **NDVI (Vegetation)**: Less vegetation often means more urbanization
- **Parking Occupancy**: Reflectance patterns in large lots suggest usage
- **Urban Density**: Spectral signatures of built-up areas

### Limitations

1. **Resolution**: Cannot detect individual vehicles (need 30cm, we have 10m)
2. **Causation**: Metrics show correlation, not direct causation
3. **Cloud Cover**: Some periods may have data gaps
4. **Temporal Lag**: Composites introduce processing delays

### Data Sources

| Source | Type | Resolution | Provider |
|--------|------|------------|----------|
| Sentinel-2 | Optical imagery | 10m | ESA/Copernicus |
| VIIRS | Nighttime lights | 375m | NASA/NOAA |
| GHSL | Built-up areas | 10m | JRC |
| Sentinel-5P | Air quality | 7km | ESA/Copernicus |
| ERA5-Land | Weather | 11km | ECMWF |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play/Pause animation |
| `←` / `→` | Previous/Next frame |
| `+` / `-` | Zoom in/out on map |
| `Esc` | Close modal/dialog |

---

## Troubleshooting

### "No data available for this period"

- Try a different date range
- Some metrics have limited temporal coverage
- Check if the region is within the data extent (some metrics have regional coverage)

### Map tiles not loading

- Check your internet connection
- Try refreshing the page
- Zoom out and zoom back in
- If the metric overlay is hidden, zoom in (overlays appear at higher zoom levels)

### Export failed

- Ensure a region is selected
- Check that the date range is valid
- Try a smaller date range for animations

### Slow performance

- Reduce the date range
- Select fewer metrics
- Zoom in on the map before enabling overlays/animations
- Use Chrome or Firefox for best performance

---

## API Access

For programmatic access, see the API documentation at `/docs` (Swagger UI) or `/redoc` (ReDoc).

---

## Support

- **GitHub Issues**: Report bugs or request features
- **Documentation**: Full technical docs in the `/docs` directory
- **Methodology**: See `docs/methodology.md` for technical details

---

*Last updated: January 2026*
