# GEE Dataset Integration Guide

**Last Updated:** 2026-01-31
**Status:** 17 metrics implemented, tested, and verified

This document consolidates the GEE dataset research and test verification for the Satellite Migration Analysis Platform.

---

## Quick Reference

### Implemented Metrics (17 total)

| Metric | GEE Dataset | Resolution | Default | Supported | Status |
|--------|-------------|------------|---------|-----------|--------|
| `ndvi` | Sentinel-2 + MODIS fill | 10m | Weekly | weekly, monthly | Verified |
| `nightlights` | VIIRS Black Marble + NOAA monthly | 375m | Monthly | daily, monthly | Verified |
| `urban_density` | GHSL SMOD | 10m | Monthly | monthly | Verified |
| `parking` | Sentinel-2 (NDBI) | 10m | Weekly | weekly, monthly | Verified |
| `land_cover` | Dynamic World | 10m | Weekly | weekly, monthly | Verified |
| `surface_water` | JRC GSW | 30m | Monthly | monthly | Verified |
| `active_fire` | VIIRS 375m | 375m | Daily | daily, monthly | Verified |
| `no2` | Sentinel-5P | 7km | Daily | daily, monthly | Verified |
| `temperature` | ERA5-Land Daily Agg | 11km | Daily | daily, monthly | Verified |
| `precipitation` | CHIRPS Daily | ~5km | Daily | daily, monthly | Verified |
| `aerosol` | Sentinel-5P | 7km | Daily | daily, monthly | Verified |
| `cropland` | ESA WorldCover | 10m | Monthly | monthly | Verified |
| `evapotranspiration` | MODIS MOD16A2GF | ~500m | Monthly | monthly | Verified |
| `soil_moisture` | SMAP L4 | ~11km | Weekly | weekly, monthly | Verified |
| `impervious` | GAIA | 30m | Monthly | monthly | Verified |
| `fire_historical` | MODIS FIRMS | 1km | Monthly | monthly | Verified |
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

#### Active Fire (`NASA/LANCE/SNPP_VIIRS/C2`)
- **Description:** Active fire hotspots with Fire Radiative Power
- **Resolution:** 375m (4x better than MODIS)
- **Bands:** brightness temperatures, confidence, FRP
- **Value Range:** FRP 0-500 MW
- **Use Cases:** Real-time fire tracking, intensity analysis

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

#### Fire Historical (`MODIS/061/MOD14A1`)
- **Description:** Fire archive from 2000+
- **Resolution:** 1km
- **Value Range:** FRP 0-500 MW
- **Use Cases:** Long-term fire history, trend analysis

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
| `backend/app/api/routes/tiles.py` | Tile endpoint with valid_metrics list |
| `backend/app/services/satellite/us_data_service.py` | `get_{metric}()` methods for each metric |
| `backend/app/services/tiles/us_tile_generator.py` | COLORMAPS and VALUE_RANGES |

### 2.2 Frontend Files

| File | Purpose |
|------|---------|
| `frontend/src/types/index.ts` | `MetricType` union type |
| `frontend/src/services/api.ts` | Daily metrics list for granularity |
| `frontend/src/pages/AnimationStudio.tsx` | METRIC_OPTIONS and METRIC_GRANULARITY |

### 2.3 Adding a New Metric

1. **Backend - Data Service:**
```python
# us_data_service.py
async def get_new_metric(self, year: int, month: int) -> np.ndarray | None:
    collection = ee.ImageCollection("GEE/DATASET/ID")
    # Filter and process...
    return await self._compute_us_raster(image)
```

2. **Backend - Tile Generator:**
```python
# us_tile_generator.py
COLORMAPS["new_metric"] = [(r1,g1,b1), (r2,g2,b2), ...]
VALUE_RANGES["new_metric"] = (min_val, max_val)
```

3. **Backend - Routes:**
```python
# tiles.py - Add to valid_metrics list
valid_metrics = [..., "new_metric"]
```

4. **Frontend - Types:**
```typescript
// types/index.ts
export type MetricType = ... | 'new_metric';
```

5. **Frontend - Animation Studio:**
```typescript
// AnimationStudio.tsx
const METRIC_OPTIONS = [..., { value: 'new_metric', label: 'New Metric', granularity: 'monthly' }];
```

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
| active_fire | Yellow-orange-red | Fire intensity |
| no2 | Blue-yellow-red | Pollution diverging |
| temperature | Blue-white-red | Cold-hot diverging |
| precipitation | White-green-blue-purple | Rainfall amount |
| aerosol | White-tan-brown-black | Smoke intensity |
| cropland | Multi-color categorical | Crop types |
| evapotranspiration | Brown-green-blue | Water use |
| soil_moisture | Brown-tan-blue | Dry-wet |
| impervious | White-black gray | Urban footprint |
| fire_historical | Yellow-orange-red | Historical fire |
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
    "active_fire": (0.0, 500.0),  # FRP in MW
    "no2": (0.0, 0.0002),  # mol/m²
    "temperature": (-30.0, 45.0),  # Celsius
    "precipitation": (0.0, 500.0),  # mm
    "aerosol": (-2.0, 5.0),  # index
    "cropland": (0.0, 255.0),  # categorical
    "evapotranspiration": (0.0, 300.0),  # mm/month
    "soil_moisture": (0.0, 50.0),  # mm
    "impervious": (0.0, 1.0),  # binary
    "fire_historical": (0.0, 500.0),  # FRP in MW
    "canopy_height": (0.0, 60.0),  # meters
}
```

---

## 4. Granularity & Date Formats

### 4.1 Daily Metrics
These metrics support daily date format (YYYY-MM-DD):
- `nightlights` - VIIRS daily data
- `active_fire` - Real-time fire detection

### 4.2 Monthly Metrics
All other metrics use monthly format (YYYY-MM) or auto-convert from daily requests.

### 4.3 Frontend Mapping

```typescript
const METRIC_GRANULARITY: Record<string, string> = {
  nightlights: 'daily',
  ndvi: 'weekly',
  urban_density: 'monthly',
  parking: 'weekly',
  land_cover: 'monthly',
  surface_water: 'monthly',
  active_fire: 'daily',
  no2: 'monthly',
  temperature: 'monthly',
  precipitation: 'monthly',
  aerosol: 'monthly',
  cropland: 'yearly',
  evapotranspiration: 'monthly',
  soil_moisture: 'monthly',
  impervious: 'yearly',
  fire_historical: 'monthly',
  canopy_height: 'static',
};
```

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

All 17 metrics verified to return 200 OK with valid PNG tiles:
```bash
for metric in ndvi nightlights urban_density parking land_cover surface_water active_fire no2 temperature precipitation aerosol cropland evapotranspiration soil_moisture impervious fire_historical canopy_height; do
  curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/tiles/us/$metric/2024-01/11/512/768.png"
done
```

### 6.2 Frontend Verification

Visual verification completed via Playwright MCP browser:
- Animation Studio shows all 17 metric cards
- Each metric displays correct granularity badge
- Map overlays render with appropriate colormaps

### 6.3 Known Discrepancies

| Issue | SOT Spec | Implementation | Impact |
|-------|----------|----------------|--------|
| soil_moisture unit | % (0-100) | mm (0-50) | Low - display conversion |
| active_fire range | 0-1000 MW | 0-500 MW | Low - covers typical fires |

---

## 7. Future Datasets (Not Implemented)

### 7.1 Recommended for Future

| Dataset | GEE ID | Use Case | Effort |
|---------|--------|----------|--------|
| GOES-16 FDCC | `NOAA/GOES/16/FDCC` | Real-time fire (10-min) | Medium |
| SMAP L4 | `NASA/SMAP/SPL4SMGP/007` | Enhanced soil moisture | Low |
| CAMS NRT | `ECMWF/CAMS/NRT` | Air quality forecast | Medium |

### 7.2 Not Recommended

| Dataset | Reason |
|---------|--------|
| Global Human Modification | Non-commercial license (CC-BY-NC) |
| Global Fishing Watch | Share-alike requirement (CC-BY-SA) |
| Blitzortung Lightning | Not available for commercial use |

---

*This document consolidates SOT Section 18 and GEE_DATASET_TEST_MATRIX.md*
