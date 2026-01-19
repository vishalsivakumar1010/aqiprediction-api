# AQI Prediction Model - Implementation Plan

## Dataset Overview
- **Full 2025 Data**: January 1, 2025 → January 8, 2026
- **Total Rows**: ~163,467 across 10 sensors
- **Frequency**: 30-minute intervals
- **Features**: PM2.5, humidity, temperature, time_stamp
- **Spatial Data**: Latitude/longitude for all 10 sensors (already fetched)
- **Location**: Fremont, CA area

## Prediction Architecture

### 1. Model Choice: XGBoost Ensemble

**Why XGBoost?**
- **Time Series Capability**: Excellent for sequential data with temporal dependencies
- **Feature Handling**: Automatically handles non-linear relationships between:
  - Temporal patterns (hour, day, season)
  - Weather conditions (humidity, temperature)
  - Spatial relationships (sensor proximity)
  - Wind patterns (direction affecting pollutant transport)
- **Interpretability**: Feature importance shows which factors matter most
- **Performance**: Fast training and inference, robust to overfitting
- **Categorical Targets**: Can predict both continuous AQI values and categories

**Dual Model Approach:**
1. **Regression Model**: Predicts PM2.5 (μg/m³) → Converted to AQI
2. **Classification Model**: Directly predicts AQI category (Good, Moderate, Unhealthy, etc.)

### 2. Feature Engineering Strategy

#### A. Temporal Features (Captures Seasonal & Time-of-Day Patterns)

**Cyclical Encoding** (sin/cos transformation preserves cyclical nature):
- **Hour**: Traffic patterns (rush hours 7-9 AM, 5-7 PM show higher PM2.5)
- **Day of Week**: Weekend vs weekday patterns (less traffic weekends)
- **Month/Season**: 
  - Winter: Lower dispersion, higher PM2.5 accumulation
  - Summer: Higher dispersion, wildfires possible
  - Spring/Fall: Moderate patterns

**Time Features:**
- Hour of day (0-23) → hour_sin, hour_cos
- Day of week (0-6) → day_of_week_sin, day_of_week_cos  
- Month (1-12) → month_sin, month_cos
- Day of year (1-365) → captures gradual seasonal changes
- Is weekend (binary)
- Is rush hour (binary: 7-9 AM, 5-7 PM)

#### B. Lagged Features (Historical Context)

**Purpose**: Capture persistence and trends in air quality

**Lags for PM2.5, humidity, temperature:**
- 1 step (30 min ago) - immediate past
- 2 steps (1 hour ago) - recent trend
- 4 steps (2 hours ago) - short-term pattern
- 6 steps (3 hours ago) - medium-term pattern
- 12 steps (6 hours ago) - longer-term baseline
- 24 steps (12 hours ago) - daily cycle reference
- 48 steps (24 hours ago) - yesterday's same time

**Differences:**
- Change from previous step (detects sudden changes)
- Change from 24h ago (detects daily anomalies)

#### C. Rolling Statistics (Captures Local Patterns)

**Windows:**
- 2 steps (1 hour) - recent average/trend
- 4 steps (2 hours) - short-term average
- 6 steps (3 hours) - medium-term average  
- 12 steps (6 hours) - half-day pattern
- 24 steps (12 hours) - day/night pattern
- 48 steps (24 hours) - full daily cycle

**Statistics per window:**
- Mean (trend direction)
- Std (volatility/variability)
- Min/Max (range/extremes)

#### D. Spatial Features (Geographic Context)

**Sensor Location Features:**
- Raw latitude/longitude (absolute position)
- Distance from geographic center (relative position)
- Normalized coordinates (lat/lon centered and scaled)

**Spatial Interactions:**
- Average PM2.5 from nearby sensors (within 5km)
- Standard deviation from nearby sensors (spatial variability)
- **Rationale**: Air quality is spatially correlated - nearby sensors should have similar values unless local sources exist

#### E. Wind Direction Features (NEW - Critical for Prediction)

**Purpose**: Wind direction determines:
- **Source direction**: Which direction pollutants are coming FROM
- **Transport patterns**: Where pollutants will move TO
- **Dispersion**: Wind affects how pollutants spread

**Features:**
- `wdir`: Wind direction in degrees (0-360)
  - 0° = North
  - 90° = East  
  - 180° = South
  - 270° = West
- `wind_dir_x`: cos(wdir_rad) - x-component of unit vector
- `wind_dir_y`: sin(wdir_rad) - y-component of unit vector

**Why Unit Vector (x, y)?**
- Preserves directional information without magnitude
- Model-friendly (continuous, bounded -1 to 1)
- Captures cyclical nature (0° and 360° are similar)

**Wind Direction Logic:**
- **North wind (0-45°, 315-360°)**: Pollutants move south
- **East wind (45-135°)**: Pollutants move west
- **South wind (135-225°)**: Pollutants move north
- **West wind (225-315°)**: Pollutants move east

**Combined with Spatial Features:**
- If wind from West and sensor is East of source → Higher PM2.5 expected
- If wind from South and sensor is North of source → Lower PM2.5 expected

#### F. Weather Features (Existing)

- **Humidity**: Affects particle formation and settling
- **Temperature**: Affects atmospheric stability and dispersion
- **Temperature-Humidity Interaction**: Combined effect on air quality

### 3. Target Variables (What We Predict)

**Forecast Horizons:**
1. **1-Hour Ahead** (2 steps forward)
2. **3-Hour Ahead** (6 steps forward)

**Targets:**
- `pm2_5_atm_target_2h`: PM2.5 value 1 hour in future
- `aqi_target_2h`: AQI value 1 hour in future (calculated from PM2.5)
- `category_target_2h`: AQI category 1 hour in future (Good, Moderate, etc.)
- Same for 3-hour horizon (6h)

### 4. User Location Input → Nearest Sensor Matching

**Process:**
1. **User Input**: Address or location name in Fremont area
2. **Geocoding**: Convert address → (lat, lon) using geocoding service
3. **Find Nearest Sensor**: Calculate distance to all 10 sensors
4. **Select Sensor**: Choose closest sensor based on:
   - Euclidean distance in lat/lon space
   - Or Haversine distance (more accurate for geographic)
5. **Use Sensor's Model**: Use that sensor's historical patterns and spatial features

**Fallback**: If exact sensor not available, use weighted average of nearest 3 sensors

### 5. Training Strategy

**Data Split (Time Series Aware):**
- **Training**: 2025-01-01 → 2025-10-31 (~10 months)
- **Validation**: 2025-11-01 → 2025-11-30 (1 month)
- **Test**: 2025-12-01 → 2026-01-08 (~5 weeks)

**Why This Split?**
- Preserves temporal order (no data leakage)
- Training includes all seasons except late fall/winter
- Validation tests on unseen seasonal patterns
- Test includes winter + early January patterns

**Cross-Validation:**
- Time Series Split (5 folds)
- Ensures model generalizes to future data
- Prevents overfitting to specific time periods

### 6. Model Training Process

**Step 1: Data Loading**
- Load all 10 sensor CSV files from full 2025 dataset
- Combine into single dataframe with sensor_id

**Step 2: Data Cleaning**
- Remove invalid values (negative PM2.5, unrealistic temps/humidity)
- Handle missing data (forward-fill, then backward-fill)

**Step 3: Add AQI Calculations**
- Convert PM2.5 to AQI using US EPA formula
- Calculate AQI categories

**Step 4: Add Spatial Features**
- Merge sensor locations (lat/lon)
- Calculate spatial features (distance from center, normalized coords)
- Calculate nearby sensor averages

**Step 5: Add Wind Direction (NEW)**
- Fetch hourly wind direction from Meteostat for Fremont center (37.5483, -121.9886)
- Date range: 2025-01-01 to 2026-01-08
- Merge on hourly timestamps (timestamp.floor("H"))
- Forward-fill to 30-minute rows
- Convert to x, y components

**Step 6: Feature Engineering**
- Create temporal features (cyclical encoding)
- Create lagged features (1, 2, 4, 6, 12, 24, 48 steps)
- Create rolling statistics (mean, std, min, max)
- Create difference features

**Step 7: Create Targets**
- Shift PM2.5 values forward by 2 steps (1h) and 6 steps (3h)
- Calculate AQI and categories for future timestamps

**Step 8: Train Models**
- Train separate models for 1h and 3h forecasts
- Each horizon: Regression (PM2.5) + Classification (Category)
- Use time series cross-validation
- Optimize hyperparameters if needed

**Step 9: Evaluate**
- Calculate MAE, RMSE, R² for PM2.5 predictions
- Calculate accuracy for category predictions
- Feature importance analysis

### 7. Prediction Workflow (Runtime)

**When User Requests Prediction:**

1. **Get User Location**
   - Input: "Lake Elizabeth Park, Fremont" or lat/lon
   - Geocode if needed
   - Find nearest sensor

2. **Fetch Current Data from Purple Air API**
   - Get current PM2.5, humidity, temperature for nearest sensor
   - Get recent historical data (last 24-48 hours) for feature engineering

3. **Get Current Wind Direction from Meteostat**
   - Fetch latest hourly wind direction
   - Use for current prediction

4. **Prepare Features**
   - Create all temporal features (current hour, day, month, etc.)
   - Create lagged features from historical data
   - Create rolling statistics
   - Add spatial features (sensor location)
   - Add wind direction features

5. **Make Predictions**
   - Use trained model for 1-hour forecast
   - Use trained model for 3-hour forecast
   - Get PM2.5 predictions → Convert to AQI
   - Get category predictions

6. **Return Results**
   - Current AQI and category
   - 1-hour forecast: AQI, category, recommendation
   - 3-hour forecast: AQI, category, recommendation

### 8. Key Insights the Model Will Learn

**Seasonal Patterns:**
- Winter (Dec-Feb): Higher PM2.5 due to inversion layers, lower dispersion
- Summer (Jun-Aug): Variable PM2.5 (wildfires, higher dispersion)
- Spring/Fall: Moderate patterns

**Diurnal Patterns:**
- Morning (7-9 AM): Peak PM2.5 due to rush hour traffic
- Afternoon (12-3 PM): Lower PM2.5 due to better dispersion, more mixing
- Evening (5-7 PM): Another peak due to evening rush hour
- Night (10 PM-6 AM): Lower baseline, less traffic

**Weather Effects:**
- High humidity + low temp → Higher PM2.5 (particles don't disperse)
- Low humidity + high temp → Lower PM2.5 (better dispersion)
- Temperature inversions → Trapped pollutants

**Spatial Effects:**
- Sensors near highways: Higher PM2.5
- Sensors in parks: Lower PM2.5
- Wind direction determines which sensors get upwind vs downwind pollution

**Wind Direction Effects:**
- Wind from industrial areas → Higher PM2.5
- Wind from ocean → Lower PM2.5 (cleaner air)
- Calm conditions → Pollutants accumulate locally

## Expected Model Performance

**Baseline (Simple persistence):** MAE ~5-8 μg/m³

**Expected with Full Features:**
- **1-Hour Forecast**: MAE ~3-5 μg/m³, R² > 0.85
- **3-Hour Forecast**: MAE ~4-6 μg/m³, R² > 0.75
- **Category Accuracy**: > 85% for 1h, > 80% for 3h

## Implementation Files

1. `train_model.py` - Main training script (updated for full dataset)
2. `add_wind_direction.py` - Add wind direction to dataset
3. `model_training.py` - Model training functions
4. `feature_engineering.py` - Feature creation
5. `predict.py` - Runtime prediction (with location matching)
6. `nearest_sensor.py` - Location → nearest sensor matching (NEW)

## Next Steps

1. ✅ Update data loading to use full 2025 dataset path
2. ✅ Add wind direction fetching and merging
3. ✅ Create location geocoding and nearest sensor matching
4. ✅ Update feature engineering to include all temporal/spatial/wind features
5. ✅ Train models with full dataset
6. ✅ Test predictions with real API data

## Advantages of This Approach

1. **Comprehensive Temporal Coverage**: Full year captures all seasonal patterns
2. **Spatial Awareness**: Uses location data for better regional predictions
3. **Wind Integration**: Understands pollutant transport direction
4. **Flexible Input**: Handles user location input → finds best sensor
5. **Dual Targets**: Predicts both AQI value and category
6. **Time Series Aware**: Respects temporal order, prevents data leakage
7. **Feature Rich**: 100+ engineered features capture complex patterns

---

**Ready to implement once you approve this plan!**

