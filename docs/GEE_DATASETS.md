# GEE Dataset Integration Guide

**Last Updated:** 2026-02-01
**Status:** 15 metrics implemented, tested, and verified

This document consolidates the GEE dataset research and test verification for the Satellite Migration Analysis Platform.

---

## Quick Reference

### Implemented Metrics (15 total)

| Metric | GEE Dataset | Resolution | Default | Supported | Status |
|--------|-------------|------------|---------|-----------|--------|
| `ndvi` | Sentinel-2 + MODIS fill | 10m | Weekly | weekly, monthly | Verified |
| `nightlights` | VIIRS Black Marble + NOAA monthly | 375m | Monthly | daily, monthly | Verified |
| `urban_density` | GHSL SMOD | 10m | Monthly | monthly | Verified |
| `parking` | Sentinel-2 (NDBI) | 10m | Weekly | weekly, monthly | Verified |
| `land_cover` | Dynamic World | 10m | Weekly | weekly, monthly | Verified |
| `surface_water` | JRC GSW | 30m | Monthly | monthly | Verified |
| `no2` | Sentinel-5P | 7km | Daily | daily, monthly | Verified |
| `temperature` | ERA5-Land Daily Agg | 11km | Daily | daily, monthly | Verified |
| `precipitation` | CHIRPS Daily | ~5km | Daily | daily, monthly | Verified |
| `aerosol` | Sentinel-5P | 7km | Daily | daily, monthly | Verified |
| `cropland` | ESA WorldCover | 10m | Monthly | monthly | Verified |
| `evapotranspiration` | MODIS MOD16A2GF | ~500m | Monthly | monthly | Verified |
| `soil_moisture` | SMAP L4 | ~11km | Weekly | weekly, monthly | Verified |
| `impervious` | GAIA | 30m | Monthly | monthly | Verified |
| `canopy_height` | GEDI + Simard | 1km | Monthly | monthly | Verified |

---

## 1. Dataset Details

### 1.1 Original Core Metrics

#### NDVI (`COPERNICUS/S2_SR_HARMONIZED`)
- **Description:** Vegetation health index from Sentinel-2
- **Formula:** `(NIR - Red) / (NIR + Red)` using B8 and B4
- **Value Range:** -1 to +1
- **Use Cases:** Urban sprawl tracking, seasonal vegetation, drought assessment

#### Nightlights (`NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` + `NASA/VIIRS/002/VNP46A2`)
- **Description:** Artificial light intensity as activity proxy
- **Unit:** nW/cm²/sr
- **Value Range:** 0-100 (typical urban: 10-60)
- **Use Cases:** Population activity, migration patterns, economic indicators

#### Urban Density (`JRC/GHSL/P2023A/GHS_BUILT_S`)
- **Description:** Built-up area fraction from Global Human Settlement Layer
- **Value Range:** 0-1 (fraction of built-up area)
- **Use Cases:** Urbanization tracking, city boundary detection

#### Parking (`COPERNICUS/S2_SR_HARMONIZED` - NDBI)
- **Description:** Parking lot occupancy proxy using built-up index
- **Formula:** `(SWIR - NIR) / (SWIR + NIR)` using B11 and B8
- **Value Range:** 0-1
- **Use Cases:** Commercial activity proxy, event detection

### 1.2 Phase 1: Land & Water

#### Land Cover (`GOOGLE/DYNAMICWORLD/V1`)
- **Description:** Near real-time land cover probabilities
- **Classes:** water, trees, grass, flooded_vegetation, crops, shrub_and_scrub, built, bare, snow_and_ice
- **Value Range:** 0-1 per class (probabilities sum to 1)
- **License:** CC-BY 4.0
- **Use Cases:** Land use change detection, urban creep tracking

#### Surface Water (`JRC/GSW1_4/MonthlyHistory`)
- **Description:** Monthly water extent from 1984-2021
- **Resolution:** 30m
- **Value Range:** Binary (water/not-water)
- **Use Cases:** Reservoir monitoring, flood extent, drought tracking

### 1.3 Phase 2: Air Quality & Weather

#### NO2 (`COPERNICUS/S5P/OFFL/L3_NO2`)
- **Description:** Tropospheric nitrogen dioxide
- **Band:** `tropospheric_NO2_column_number_density`
- **Unit:** mol/m²
- **Value Range:** 0-0.0002
- **Use Cases:** Industrial activity, metro pollution, shipping lanes

#### Temperature (`ECMWF/ERA5_LAND/DAILY_AGGR`)
- **Description:** 2-meter air temperature from ERA5-Land daily aggregates
- **Band:** `temperature_2m`
- **Unit:** Celsius (after conversion from Kelvin)
- **Value Range:** -30 to +45°C
- **Use Cases:** Weather context, heatwave detection

#### Precipitation (`UCSB-CHG/CHIRPS/DAILY`)
- **Description:** Climate Hazards Group InfraRed Precipitation (CHIRPS) daily estimates
- **Band:** `precipitation`
- **Unit:** mm/day
- **Value Range:** 0-500mm
- **Use Cases:** Flood risk, drought context, agriculture

#### Aerosol (`COPERNICUS/S5P/OFFL/L3_AER_AI`)
- **Description:** Absorbing Aerosol Index (smoke/dust)
- **Value Range:** -2 to +5 (positive = absorbing aerosols like smoke)
- **Use Cases:** Wildfire smoke tracking, dust storms

### 1.4 Phase 3: Agriculture

#### Cropland (`ESA/WorldCover/v200`)
- **Description:** ESA WorldCover cropland fraction (global)
- **Resolution:** 10m
- **Value Range:** 0-1 (fraction of cropland within area)
- **Use Cases:** Cropland extent monitoring, agricultural land use

#### Evapotranspiration (`MODIS/061/MOD16A2GF`)
- **Description:** MODIS 8-day gap-filled evapotranspiration (global)
- **Band:** `ET`
- **Unit:** kg/m²/8day (scaled)
- **Value Range:** 0-300
- **Use Cases:** Water stress detection, irrigation monitoring

#### Soil Moisture (`NASA/SMAP/SPL4SMGP/008`)
- **Description:** SMAP L4 Global Positioning soil moisture
- **Band:** `sm_surface`
- **Unit:** m³/m³ (volumetric)
- **Value Range:** 0-0.5
- **Use Cases:** Drought onset, flood susceptibility

### 1.5 Phase 4: Historical & Specialized

#### Impervious (`Tsinghua/FROM-GLC/GAIA/v10`)
- **Description:** Year of urbanization (1985-2018)
- **Band:** `change_year_index`
- **Value Range:** 0-1 (binary mask for current implementation)
- **Use Cases:** Urban expansion animations, development timing

#### Canopy Height (`LARSE/GEDI/GRIDDEDVEG_002/V1/1KM`)
- **Description:** LiDAR-derived canopy height
- **Bands:** `mean`, `var`, `mode`
- **Unit:** meters
- **Value Range:** 0-60m
- **Use Cases:** Biomass estimation, forest structure

---

## 2. Implementation Architecture

### 2.1 Backend Files

| File | Purpose |
|------|---------|
| `backend/app/gee.py` | All metric definitions, EE compute logic, tile URL generation |
| `backend/app/routes/tiles.py` | Tile URL template endpoint |
| `backend/app/routes/metrics.py` | Time series metrics endpoint |

### 2.2 Frontend Files

| File | Purpose |
|------|---------|
| `frontend/src/types/index.ts` | `MetricType` and `Granularity` type definitions |
| `frontend/src/config/metrics.ts` | Default granularities, supported granularities, helpers |
| `frontend/src/components/Map/metricStyles.ts` | Palette and style definitions per metric |
| `frontend/src/pages/AnimationStudio.tsx` | METRIC_OPTIONS list |

### 2.3 Adding a New Metric

1. **Backend - gee.py:** Add a `MetricDefinition` entry to `METRICS`:
```python
# gee.py
"new_metric": MetricDefinition(
    collection="GEE/DATASET/ID",
    band="band_name",
    unit="unit",
    value_range=(min_val, max_val),
    palette=["#color1", "#color2", ...],
    default_granularity="monthly",
    supported_granularities={"monthly"},
    compute_fn=_compute_new_metric,  # optional custom function
)
```

2. **Frontend - types/index.ts:** Add to `MetricType` union and `SeasonalAverage`
3. **Frontend - config/metrics.ts:** Add to `METRIC_DEFAULT_GRANULARITY` and `METRIC_SUPPORTED_GRANULARITIES`
4. **Frontend - AnimationStudio.tsx:** Add to `METRIC_OPTIONS` array
5. **Frontend - AnalysisView.tsx & MapPage.tsx:** Add to their `METRIC_OPTIONS` arrays

---

## 3. Colormaps & Value Ranges

### 3.1 Colormaps by Metric

| Metric | Colormap Description | Visual |
|--------|---------------------|--------|
| ndvi | Red-brown-yellow-green | Vegetation gradient |
| nightlights | Black-purple-yellow-white | Light intensity |
| urban_density | Yellow-orange-brown | Density gradient |
| parking | Light-dark blue | Occupancy |
| land_cover | Purple gradient (built-up) | Built probability |
| surface_water | White-dark blue | Water presence |
| no2 | Blue-yellow-red | Pollution diverging |
| temperature | Blue-white-red | Cold-hot diverging |
| precipitation | White-green-blue-purple | Rainfall amount |
| aerosol | White-tan-brown-black | Smoke intensity |
| cropland | Multi-color categorical | Crop types |
| evapotranspiration | Brown-green-blue | Water use |
| soil_moisture | Brown-tan-blue | Dry-wet |
| impervious | White-black gray | Urban footprint |
| canopy_height | Light-dark green | Tree height |

### 3.2 Value Ranges

```python
VALUE_RANGES = {
    "ndvi": (-1.0, 1.0),
    "nightlights": (0.0, 100.0),
    "urban_density": (0.0, 1.0),
    "parking": (0.0, 1.0),
    "land_cover": (0.0, 1.0),
    "surface_water": (0.0, 1.0),
    "no2": (0.0, 0.0002),  # mol/m²
    "temperature": (-30.0, 45.0),  # Celsius
    "precipitation": (0.0, 500.0),  # mm
    "aerosol": (-2.0, 5.0),  # index
    "cropland": (0.0, 1.0),  # fraction (ESA WorldCover)
    "evapotranspiration": (0.0, 300.0),  # kg/m²/8day (MODIS)
    "soil_moisture": (0.0, 0.5),  # m³/m³ (SMAP L4)
    "impervious": (0.0, 1.0),  # binary
    "canopy_height": (0.0, 60.0),  # meters
}
```

---

## 4. Granularity & Date Formats

### 4.1 Multi-Granularity Metrics
These metrics support user-selectable granularity via a toggle in the UI:
- `nightlights` - daily (VIIRS Black Marble) or monthly (NOAA composites)
- `no2`, `temperature`, `precipitation`, `aerosol` - daily or monthly
- `ndvi`, `parking`, `land_cover`, `soil_moisture` - weekly or monthly

### 4.2 Single-Granularity Metrics
These metrics only support monthly: `urban_density`, `surface_water`, `cropland`, `evapotranspiration`, `impervious`, `canopy_height`.

### 4.3 Frontend Config

See `frontend/src/config/metrics.ts` for the canonical mapping:
- `METRIC_DEFAULT_GRANULARITY` — default granularity per metric
- `METRIC_SUPPORTED_GRANULARITIES` — all supported granularities per metric
- `getRecommendedGranularity()` — auto-selects finest granularity that fits within the backend's max time-series points

---

## 5. Licensing Summary

| License | Datasets | Commercial Use |
|---------|----------|----------------|
| CC-BY 4.0 | Dynamic World, GAIA, ESA WorldCover | Yes (attribution required) |
| Open/Public Domain | USDA CDL, ERA5, VIIRS, MODIS | Yes |
| Copernicus | Sentinel-2, Sentinel-5P | Yes |

**Note:** All implemented metrics are cleared for commercial use.

---

## 6. Test Verification

### 6.1 Backend API Tests

All 15 metrics verified to return 200 OK with valid PNG tiles:
```bash
for metric in ndvi nightlights urban_density parking land_cover surface_water no2 temperature precipitation aerosol cropland evapotranspiration soil_moisture impervious canopy_height; do
  curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/tiles/us/$metric/2024-01/11/512/768.png"
done
```

### 6.2 Frontend Verification

Visual verification completed via Playwright MCP browser:
- Animation Studio shows all 15 metric cards
- Each metric displays correct granularity badge
- Map overlays render with appropriate colormaps

### 6.3 Known Notes

All metrics are now consistent between SOT.md, this document, and the implementation.
Soil moisture uses SMAP L4 with m³/m³ units (range 0-0.5).

---

## 7. Future Datasets (Not Implemented)

### 7.1 Recommended for Future

| Dataset | GEE ID | Use Case | Effort |
|---------|--------|----------|--------|
| GOES-16 FDCC | `NOAA/GOES/16/FDCC` | Real-time fire (10-min) | Medium |
| USDA CDL | `USDA/NASS/CDL` | US-specific crop type classification | Low |
| CAMS NRT | `ECMWF/CAMS/NRT` | Air quality forecast | Medium |

### 7.2 Not Recommended

| Dataset | Reason |
|---------|--------|
| Global Human Modification | Non-commercial license (CC-BY-NC) |
| Global Fishing Watch | Share-alike requirement (CC-BY-SA) |
| Blitzortung Lightning | Not available for commercial use |

---

*This document consolidates SOT Section 18 and GEE_DATASET_TEST_MATRIX.md*
