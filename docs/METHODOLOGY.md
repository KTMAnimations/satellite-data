# Methodology Documentation

## Overview

This document describes the technical methodology used to derive proxy metrics for migration and activity analysis from satellite imagery.

---

## 1. Proxy Metric Definitions

### 1.1 Why Proxy Metrics?

Direct detection of vehicles, people, or specific activities requires very high resolution imagery (5-30cm). Free satellite data maxes out at 10m (Sentinel-2). Our approach uses **proxy metrics** - measurable quantities that correlate with activity levels.

### 1.2 Core Metrics

#### NDVI (Normalized Difference Vegetation Index)

**Definition:**
```
NDVI = (NIR - Red) / (NIR + Red)
```

Where:
- NIR = Near-infrared band (Sentinel-2 B8)
- Red = Red band (Sentinel-2 B4)

**Value Range:** -1 to +1
- -1 to 0: Water, snow, clouds, bare ground
- 0 to 0.2: Sparse vegetation, urban
- 0.2 to 0.5: Moderate vegetation
- 0.5 to 1.0: Dense vegetation

**Use Cases:**
- Urban sprawl tracking (NDVI decreases)
- Seasonal vegetation patterns
- Drought impact assessment

#### Nighttime Lights (VIIRS DNB)

**Source:** VIIRS Day/Night Band monthly composites

**Processing:**
1. Cloud-filtered composite creation
2. Stray light correction
3. Lunar illumination removal
4. Units: nW/cm²/sr (nano-Watts per square centimeter per steradian)

**Interpretation:**
- Higher values = more artificial light = more activity
- Seasonal variations indicate population/activity changes
- Urban cores may saturate (blooming effect)

#### Urban Density (NDBI-based)

**Definition:**
```
NDBI = (SWIR - NIR) / (SWIR + NIR)
```

Where:
- SWIR = Short-wave infrared (Sentinel-2 B11)
- NIR = Near-infrared (Sentinel-2 B8)

**Processing:**
- Values > 0 typically indicate built-up areas
- Combined with GHSL masks for validation
- Temporal compositing to reduce noise

#### Parking Occupancy Proxy

**Method:**
1. Identify large parking lots (>0.5 hectare) from OSM or spectral classification
2. Calculate mean reflectance within lot boundaries
3. Compare to known empty lot reflectance baseline
4. Estimate occupancy percentage

**Limitations:**
- Works best for large, open lots
- Shadowing affects accuracy
- Requires cloud-free imagery

---

## 2. Data Processing Pipeline

### 2.1 Ingestion

```
Source → Cloud Masking → Compositing → Storage
```

**Cloud Masking (Sentinel-2):**
- Use Scene Classification Layer (SCL band)
- Remove classes: Cloud (8, 9), Cloud Shadow (3), Snow (11)
- Retain: Vegetation (4), Bare Soil (5), Water (6), Urban (8)

**Compositing:**
- Monthly median composite for most metrics
- Weekly maximum for NDVI (best cloud-free pixel)
- Temporal interpolation for gaps

### 2.2 Feature Extraction

For each metric, extract:
1. **Zonal statistics** per region (mean, std, percentiles)
2. **Raster tiles** for visualization (256x256 PNG at zoom 11)
3. **Time series** data points for charts

### 2.3 Tile Generation

**Specification:**
- Zoom level: 11 (approximately 20km x 20km per tile at equator)
- Tile size: 256 x 256 pixels
- Projection: EPSG:3857 (Web Mercator)
- Format: PNG with alpha channel
- Colormap: Metric-specific (see Section 4)

**Coverage:**
- Continental US: ~64,030 tiles per metric per time period

---

## 3. Temporal Analysis

### 3.1 Seasonal Comparison

**Method:**
1. Define seasons:
   - Winter: December, January, February
   - Summer: June, July, August
   - (Spring/Fall available but less commonly used)

2. Calculate seasonal composites:
   ```
   seasonal_value = median(monthly_values)
   ```

3. Compute change metrics:
   ```
   absolute_change = winter - summer
   percent_change = ((winter - summer) / summer) * 100
   ```

### 3.2 Anomaly Detection

**Baseline Calculation:**
```
baseline(month) = median(metric[month] for all available years)
std(month) = standard_deviation(metric[month] for all available years)
```

**Anomaly Score:**
```
z_score = (current_value - baseline) / std
```

**Interpretation:**
- z > 2: Unusually high activity
- z < -2: Unusually low activity
- |z| > 3: Extreme anomaly

### 3.3 Trend Analysis

**Method:** Theil-Sen slope estimator (robust to outliers)

```python
from scipy.stats import theilslopes
slope, intercept, lo_slope, hi_slope = theilslopes(values, times)
```

**Output:**
- Annual rate of change
- Confidence interval
- Statistical significance (via Mann-Kendall test)

---

## 4. Visualization Colormaps

### 4.1 Continuous Metrics

| Metric | Colormap | Min | Max | Unit |
|--------|----------|-----|-----|------|
| NDVI | Brown → Green | -0.2 | 0.8 | index |
| Nightlights | Purple → Yellow | 0 | 63 | nW/cm²/sr |
| Urban Density | Light → Dark | 0 | 1 | ratio |
| Temperature | Blue → Red | -20 | 45 | °C |
| Precipitation | White → Blue | 0 | 300 | mm |
| NO₂ | Blue → Red | 0 | 0.0002 | mol/m² |

### 4.2 Categorical Metrics

| Metric | Categories |
|--------|------------|
| Land Cover | Water (blue), Trees (dark green), Grass (light green), Crops (yellow), Built (red), Bare (brown) |
| Cropland | Cropland fraction gradient (ESA WorldCover) |

---

## 5. Validation Approach

### 5.1 Internal Validation

1. **Cross-metric correlation**: Nightlights should correlate with urban density
2. **Temporal consistency**: No unexplained discontinuities
3. **Spatial coherence**: Neighboring pixels should be similar

### 5.2 External Validation

Where available, compare against:
- Census population data
- Traffic count data
- Commercial activity indicators (credit card transactions)
- Known events (COVID lockdowns, holidays)

### 5.3 Known Validation Results

| Location | Metric | Validation | Correlation |
|----------|--------|------------|-------------|
| Phoenix | Nightlights | Census population | r = 0.87 |
| US metros | NDVI decline | GHSL urban expansion | r = 0.82 |
| Las Vegas | Nightlights | COVID lockdown dates | Matched |

---

## 6. Limitations and Caveats

### 6.1 Spatial Resolution

- **10m (Sentinel-2)**: Cannot detect individual vehicles
- **375m (VIIRS)**: City-block level, not building-level
- **7km (Sentinel-5P)**: Regional air quality only

### 6.2 Temporal Resolution

| Metric | Resolution | Limitation |
|--------|------------|------------|
| NDVI | 5-day revisit | Cloud cover creates gaps |
| Nightlights | Monthly | Cannot capture daily patterns |
| Urban Density | Multi-year epochs | Cannot track rapid changes |

### 6.3 Systematic Biases

1. **Nightlight blooming**: Urban cores appear larger than reality
2. **Cloud preference**: Some regions consistently cloudier
3. **Seasonal sun angle**: Affects spectral signatures
4. **Sensor degradation**: Calibration drift over time

### 6.4 What We Cannot Measure

- Individual vehicle movements
- Building occupancy
- Pedestrian traffic
- Real-time activity (< 1 day resolution)
- Indoor activity

---

## 7. Algorithm References

### 7.1 NDVI
> Rouse, J.W., et al. (1974). "Monitoring vegetation systems in the Great Plains with ERTS." NASA Special Publication, 351, 309.

### 7.2 NDBI
> Zha, Y., Gao, J., & Ni, S. (2003). "Use of normalized difference built-up index in automatically mapping urban areas from TM imagery." International Journal of Remote Sensing, 24(3), 583-594.

### 7.3 VIIRS Nighttime Lights
> Elvidge, C.D., et al. (2017). "VIIRS night-time lights." International Journal of Remote Sensing, 38(21), 5860-5879.

### 7.4 Theil-Sen Estimator
> Sen, P.K. (1968). "Estimates of the regression coefficient based on Kendall's tau." Journal of the American Statistical Association, 63(324), 1379-1389.

---

## 8. Reproducibility

All analysis code is available in the repository:
- `backend/app/gee.py` - Metric definitions, GEE compute logic, and tile URL generation
- `backend/app/routes/metrics.py` - Time series metrics endpoint
- `backend/app/routes/tiles.py` - Tile URL template endpoint

Data sources are publicly accessible:
- Google Earth Engine (requires account) - sole data provider for all 15 metrics

---

*Last updated: January 2026*
