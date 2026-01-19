# Corrected Training Workflow

## IMPORTANT: Historical Wind Data MUST be Fetched Before Training

You're absolutely right! We need to fetch historical wind direction data that matches the EXACT timestamps of the PM2.5, humidity, and temperature data BEFORE training the model.

## Correct Training Workflow

### Step 1: Prepare Dataset with Historical Wind Direction

**Script**: `prepare_full_dataset.py`

**What it does:**
1. Loads PurpleAir data (2025-01-01 to 2026-01-08)
2. **Fetches historical wind direction from Meteostat** for the EXACT same date range
3. Merges wind direction on hourly timestamps (matches 30-minute PurpleAir data)
4. Forward-fills wind direction to 30-minute rows (rows inherit hourly value)
5. Converts wind direction to x, y components
6. Adds sensor locations if available
7. Saves complete dataset

**Key Points:**
- Wind data fetched for: **2025-01-01 00:00:00 to 2026-01-08 23:59:59**
- Matches PurpleAir timestamps exactly
- Hourly wind data → Forward-filled to 30-minute rows
- Creates: `wdir`, `wind_dir_x`, `wind_dir_y` columns

### Step 2: Feature Engineering

**Script**: Uses `feature_engineering.py` (already handles wind features)

**What it does:**
1. Creates temporal features (hour, day, month with cyclical encoding)
2. Creates lagged features (PM2.5, humidity, temp from 30min, 1h, 3h, 24h ago)
3. Creates rolling statistics (mean, std, min, max over various windows)
4. Creates spatial features (latitude, longitude, distance, nearby sensors)
5. **Wind features are already included** (wdir, wind_dir_x, wind_dir_y from Step 1)
6. Creates target variables (PM2.5 1h and 3h in future)

**Note**: Wind features are already in the dataframe from Step 1, so they're automatically included in feature engineering.

### Step 3: Train Models

**Script**: `train_full_model.py` (or updated `train_model.py`)

**What it does:**
1. Loads prepared dataset (with wind direction already included)
2. Adds AQI calculations
3. Engineers all features (temporal, lagged, rolling, spatial, wind)
4. Trains XGBoost models for 1h and 3h forecasts
5. Saves models to `models/` directory

## Complete Training Process

```bash
# Step 1: Prepare dataset with historical wind direction
python3 prepare_full_dataset.py

# This creates: purpleair_complete_with_wind.csv

# Step 2: Train models (uses prepared dataset)
python3 train_full_model.py
```

Or use the integrated script that does everything:
```bash
python3 train_full_model.py
```

This script:
1. Prepares dataset with historical wind direction
2. Engineers features
3. Trains models

## Why This Order Matters

**WRONG Approach (prediction-time only):**
- Fetch wind direction only during prediction
- Model trained without wind features
- Model can't learn wind patterns
- Poor predictions

**CORRECT Approach (training-time + prediction-time):**
- Fetch historical wind direction for entire 2025 dataset
- Merge with PurpleAir data BEFORE training
- Model learns wind patterns during training
- During prediction, fetch current wind + use historical patterns
- Better predictions

## Dataset Structure After Preparation

**Columns:**
- `sensor_id`: Sensor ID
- `time_stamp`: Timestamp (30-minute intervals)
- `pm2_5_atm`: PM2.5 value
- `humidity`: Humidity
- `temperature`: Temperature
- `timestamp_hour`: Hourly timestamp (for merging)
- `wdir`: Wind direction in degrees (0-360) ✅ **FROM HISTORICAL METEOSTAT DATA**
- `wind_dir_x`: cos(wdir_rad) ✅ **FROM HISTORICAL METEOSTAT DATA**
- `wind_dir_y`: sin(wdir_rad) ✅ **FROM HISTORICAL METEOSTAT DATA**
- `latitude`: Sensor latitude (if available)
- `longitude`: Sensor longitude (if available)
- `name`: Sensor name (if available)

## Verification

After running `prepare_full_dataset.py`, verify:

1. **Wind Direction Coverage**:
   ```python
   df['wdir'].notna().sum() / len(df) * 100
   # Should be > 90%
   ```

2. **Date Range Alignment**:
   ```python
   print(f"PurpleAir range: {df['time_stamp'].min()} to {df['time_stamp'].max()}")
   print(f"Wind data range: {df[df['wdir'].notna()]['time_stamp'].min()} to {df[df['wdir'].notna()]['time_stamp'].max()}")
   # Should match!
   ```

3. **Sample Data**:
   ```python
   print(df[['time_stamp', 'pm2_5_atm', 'wdir', 'wind_dir_x', 'wind_dir_y']].head(10))
   # Should show wind direction values for most rows
   ```

## Example: What Gets Created

**Input (PurpleAir CSV):**
```csv
time_stamp,humidity,temperature,pm2.5_atm
2025-01-01T00:00:00-08:00,49,58,25.8
2025-01-01T00:30:00-08:00,49,57,27.3
2025-01-01T01:00:00-08:00,50,56,25.7
```

**Historical Wind Data from Meteostat:**
```csv
timestamp_hour,wdir
2025-01-01T00:00:00-08:00,270.0  # West wind
2025-01-01T01:00:00-08:00,275.0  # West-Northwest wind
```

**After Merging:**
```csv
time_stamp,pm2.5_atm,humidity,temp,wdir,wind_dir_x,wind_dir_y
2025-01-01T00:00:00-08:00,25.8,49,58,270.0,0.0,-1.0  # West wind (x=0, y=-1)
2025-01-01T00:30:00-08:00,27.3,49,57,270.0,0.0,-1.0  # Inherited from :00
2025-01-01T01:00:00-08:00,25.7,50,56,275.0,0.087,-0.996  # WNW wind
```

**After Feature Engineering:**
- All temporal features (hour, day, month, etc.)
- Lagged features (PM2.5 30min ago, 1h ago, etc.)
- Rolling statistics
- Spatial features
- **Wind features already included** (wdir, wind_dir_x, wind_dir_y)
- Target variables (PM2.5 1h ahead, 3h ahead)

## Next Steps

1. ✅ Run `prepare_full_dataset.py` to fetch historical wind direction
2. ✅ Verify wind data is properly merged
3. ✅ Run `train_full_model.py` to train models with wind features
4. ✅ Test predictions

---

**Ready to train with historical wind direction data!**

