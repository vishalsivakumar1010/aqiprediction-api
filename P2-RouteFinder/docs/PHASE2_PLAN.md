# Phase 2: P2-RouteFinder - Implementation Plan

## Overview

Phase 2 improves forecast accuracy, robustness, and spatial usefulness of BreatheSmart AI by:
- Expanding sensor coverage from ~10 to ~40 sensors
- Implementing systematic data quality control
- Standardizing weather inputs (Open-Meteo)
- Retraining models with improved data pipeline

## Directory Structure

```
P2-RouteFinder/
├── data/
│   ├── raw/              # Original sensor CSVs (read-only reference)
│   ├── processed/        # QC'd and merged data
│   └── sensor_locations/ # Location data for all sensors
├── scripts/
│   ├── 01_fetch_sensor_locations.py
│   ├── 02_ingest_sensors.py
│   ├── 03_quality_control.py
│   ├── 04_merge_weather.py
│   ├── 05_feature_engineering.py
│   └── 06_train_model_v2.py
├── models/
│   └── v2/               # New model versions
├── qc_reports/           # QC summaries and logs
└── docs/
    └── PHASE2_PLAN.md
```

## Implementation Steps

### Step 1: Fetch Sensor Locations
**Script:** `01_fetch_sensor_locations.py`

- Fetches latitude/longitude for all 42 sensors from PurpleAir API
- Saves to `sensor_locations.csv` and `sensor_locations.pkl`
- Required for spatial features and RouteFinder

### Step 2: Ingest Sensors
**Script:** `02_ingest_sensors.py`

- Loads all 42 sensor CSV files from PurpleAir directory
- Combines into unified dataset
- Adds sensor locations if available
- Saves raw combined data

### Step 3: Quality Control
**Script:** `03_quality_control.py`

**Sample-level filtering:**
- Remove PM2.5 < 0 or > 500 μg/m³

**Spike detection (two-stage):**
- Stage 1: Auto-remove single-point blowups (>10× previous AND >200, returns to baseline within 1-2 readings)
- Stage 2: Flag suspicious spikes (>5× previous AND >100) but keep them

**Stuck sensor detection:**
- Remove segments with std < 1.0 AND range < 2.0 over 12-hour windows
- Drop entire sensor if >30% of rows removed

**Coverage thresholds:**
- Keep sensor if: `total_samples >= 1000 AND (coverage_days >= 90 OR total_samples >= 5000)`

**Output:** QC report with statistics and cleaned dataset

### Step 4: Merge Weather Data
**Script:** `04_merge_weather.py`

- Loads Open-Meteo hourly weather data (single Fremont point)
- Merges with 30-minute PM2.5 data using last-known-hour forward fill
- Validates timestamp alignment (:00/:30)
- Forward-fills weather up to 2 hours, then drops rows
- Calculates wind direction components (x, y)

**Weather variables:**
- `temperature_2m` (replaces PurpleAir temperature)
- `relative_humidity_2m` (replaces PurpleAir humidity)
- `wind_speed_10m`
- `wind_direction_10m` → `wind_dir_x`, `wind_dir_y`, `wdir`

### Step 5: Feature Engineering
**Script:** `05_feature_engineering.py`

Creates features using Open-Meteo weather data:

**Time features:**
- hour, day_of_week, month, day_of_year
- Cyclical encoding (sin/cos)

**Lag features:**
- PM2.5, relative_humidity_2m, temperature_2m
- Lags: 1, 2, 3, 4, 6, 12 steps (30 min to 6 hours)
- Difference features

**Rolling statistics:**
- Windows: 2, 4, 6, 12, 24 steps (1h to 12h)
- Mean, std, min, max
- **Critical:** Uses only past values (shifted by 1) to avoid data leakage

**Spatial features:**
- Latitude, longitude, distance from center
- Normalized coordinates
- Spatial interactions (nearby sensors PM2.5 average/std)

**Wind features:**
- `wind_dir_x`, `wind_dir_y` (sine/cosine encoding)

**Targets:**
- `pm2_5_atm_target_2h` (1-hour forecast)
- `pm2_5_atm_target_6h` (3-hour forecast)

### Step 6: Train v2 Model
**Script:** `06_train_model_v2.py`

**Time-based splits:**
- Train: 2024-01-01 → 2025-09-30
- Validation: 2025-10-01 → 2025-11-30
- Test: 2025-12-01 → 2026-01-10

**Models trained:**
- XGBoost Regressor (PM2.5 prediction) for 1h and 3h horizons
- XGBoost Classifier (AQI category) for 1h and 3h horizons

**Evaluation metrics:**
- MAE, RMSE, R² for PM2.5
- AQI MAE
- Category accuracy
- AQI ≥ 50 recall (to be added in evaluation script)

## Data Sources

**PurpleAir Sensors:**
- Directory: `/Users/vishalsivakumar/Library/Application Support/com.purpleair.data-download-tool/PurpleAir Download 1-25-2026-Fullset`
- 42 sensors, 30-minute resolution
- Date range: 2024-01-01 to 2026-01-10 (mixed history lengths)

**Open-Meteo Weather:**
- File: `/Users/vishalsivakumar/Downloads/open-meteo-37.50N122.00W18m-FinalSet.csv`
- Single Fremont point (37.50439°N, 121.997345°W)
- Hourly resolution
- Variables: temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m

## QC Parameters

All QC parameters are configurable in `03_quality_control.py`:

```python
QC_CONFIG = {
    'pm25_min': 0,
    'pm25_max': 500,
    'spike_multiplier': 10,
    'spike_min_value': 200,
    'spike_check_window': 2,
    'spike_return_threshold': 0.2,
    'spike_flag_multiplier': 5,
    'spike_flag_min_value': 100,
    'stuck_window_hours': 12,
    'stuck_std_threshold': 1.0,
    'stuck_range_threshold': 2.0,
    'min_samples': 1000,
    'min_coverage_days': 90,
    'min_samples_alt': 5000,
    'sensor_drop_threshold': 0.30
}
```

## Next Steps

1. **Evaluation Script** (`07_evaluate_v2.py`):
   - Compare v2 vs original v1 on same test window
   - Compute AQI ≥ 50 recall and missed-warning rate
   - Generate comparison report

2. **v1_retrained Model** (optional):
   - Retrain v1-style model on new dataset without QC/Open-Meteo
   - Compare v1_retrained vs v2 to isolate Phase 2 improvements

3. **RouteFinder Integration** (Phase 2.5):
   - Spatial interpolation (IDW)
   - Route AQI scoring
   - Map overlay visualization

## Notes

- All scripts are designed to be run sequentially
- Each script saves intermediate outputs for debugging
- QC reports are saved with timestamps
- Models are versioned (v2) for comparison
- Backward compatibility maintained with existing API
