# AQI Prediction Logic & Process

## Quick Summary

**Model Type**: XGBoost (Gradient Boosting Ensemble)
- **Regression Model**: Predicts PM2.5 → Converts to AQI
- **Classification Model**: Directly predicts AQI category

**Why XGBoost?**
- Handles complex non-linear relationships
- Captures temporal patterns (seasonal, daily, hourly)
- Works with 100+ features effectively
- Fast training and inference
- Provides feature importance for interpretability

## How We Predict AQI

### 1. Understanding the Problem

AQI depends on:
- **Historical air quality** (persistence - air quality doesn't change instantly)
- **Time of day** (rush hours have more traffic → higher PM2.5)
- **Day of week** (weekends have less traffic → lower PM2.5)
- **Season/Month** (winter inversions trap pollutants, summer dispersion clears them)
- **Weather conditions** (humidity, temperature affect particle behavior)
- **Location** (proximity to highways, parks, industrial areas)
- **Wind direction** (pollutants blow from source areas to sensor locations)

### 2. The Prediction Process

```
Current Conditions → Features → Model → Future AQI
```

**Step-by-Step:**

1. **Get Current Data** (from Purple Air API):
   - PM2.5, humidity, temperature
   - Historical values (last 24-48 hours)

2. **Get Wind Direction** (from Meteostat):
   - Current wind direction
   - Historical wind patterns

3. **Engineer Features** (100+ features):
   - **Time Features**: Hour, day, month with cyclical encoding
   - **Lagged Features**: Previous PM2.5, humidity, temp (30 min ago, 1h ago, etc.)
   - **Rolling Stats**: Recent averages, trends, volatility
   - **Spatial Features**: Sensor location, nearby sensor averages
   - **Wind Features**: Direction (x, y components)

4. **Model Prediction**:
   - Input: 100+ engineered features
   - Output: PM2.5 value 1h or 3h in future
   - Convert PM2.5 → AQI using EPA formula
   - Predict category (Good, Moderate, Unhealthy, etc.)

5. **Return Results**:
   - Current AQI and category
   - 1-hour forecast: AQI, category, recommendation
   - 3-hour forecast: AQI, category, recommendation

## Feature Categories Explained

### A. Temporal Features (Time-Based Patterns)

**Why Important:**
- **Seasonal Patterns**: Winter has higher PM2.5 (inversions), summer has lower (dispersion)
- **Daily Patterns**: Rush hours (7-9 AM, 5-7 PM) have higher PM2.5
- **Weekly Patterns**: Weekends have less traffic → lower PM2.5

**Features:**
- Hour of day (sin/cos encoding: 0° = midnight, 90° = 6 AM, 180° = noon, 270° = 6 PM)
- Day of week (sin/cos encoding: Mon-Sun cycle)
- Month (sin/cos encoding: Jan-Dec cycle)
- Is rush hour? (binary: 7-9 AM or 5-7 PM)
- Is weekend? (binary: Sat-Sun)

**Example Pattern Learned:**
- 8 AM on Monday in January → Higher PM2.5 (rush hour + winter)
- 2 PM on Saturday in July → Lower PM2.5 (no rush hour + summer dispersion)

### B. Lagged Features (Historical Context)

**Why Important:**
- Air quality has **persistence** - if PM2.5 is high now, it's likely still high in 30 minutes
- **Trend detection** - Is PM2.5 increasing or decreasing?

**Features:**
- PM2.5 30 min ago (immediate past)
- PM2.5 1 hour ago (recent trend)
- PM2.5 3 hours ago (medium-term baseline)
- PM2.5 24 hours ago (yesterday same time - daily cycle)
- Change from previous step (detects sudden changes)
- Change from 24h ago (detects anomalies)

**Example Pattern Learned:**
- PM2.5 was 50, 55, 60 in last 3 readings → Increasing trend → Predict higher future value
- PM2.5 was 50, 45, 40 in last 3 readings → Decreasing trend → Predict lower future value

### C. Rolling Statistics (Local Patterns)

**Why Important:**
- Captures **local patterns** and **volatility**
- Recent average gives baseline
- Standard deviation shows variability

**Features:**
- Rolling mean (1h, 2h, 3h, 6h, 12h, 24h windows)
- Rolling std (variability/volatility)
- Rolling min/max (range/extremes)

**Example Pattern Learned:**
- High mean + high std → Unstable, variable PM2.5 → Harder to predict
- High mean + low std → Consistently high PM2.5 → Predict high value
- Low mean + low std → Consistently low PM2.5 → Predict low value

### D. Spatial Features (Location Context)

**Why Important:**
- Sensors near highways → Higher baseline PM2.5
- Sensors in parks → Lower baseline PM2.5
- Nearby sensors often have similar values (spatial correlation)

**Features:**
- Latitude/longitude (absolute position)
- Distance from geographic center (relative position)
- Average PM2.5 from nearby sensors (within 5km)
- Standard deviation from nearby sensors (spatial variability)

**Example Pattern Learned:**
- Sensor 84117 (Lake Elizabeth - park) → Lower baseline PM2.5
- Sensor near highway → Higher baseline PM2.5
- Nearby sensors all showing high PM2.5 → Likely regional issue → Predict high value

### E. Wind Direction Features (NEW - Critical!)

**Why Important:**
- **Determines pollutant transport direction**
- Wind from industrial area → Higher PM2.5 expected
- Wind from ocean → Lower PM2.5 (cleaner air)
- Calm conditions → Pollutants accumulate locally

**Features:**
- Wind direction (degrees 0-360)
- Wind direction x-component (cos - east-west direction)
- Wind direction y-component (sin - north-south direction)

**Wind Direction Logic:**
- **0° (North)**: Wind blowing FROM north → Pollutants move SOUTH
- **90° (East)**: Wind blowing FROM east → Pollutants move WEST
- **180° (South)**: Wind blowing FROM south → Pollutants move NORTH
- **270° (West)**: Wind blowing FROM west → Pollutants move EAST

**Combined with Spatial Features:**
- Wind from West + Sensor is East of pollution source → High PM2.5
- Wind from North + Sensor is South of pollution source → High PM2.5
- Wind from Ocean (West) → Lower PM2.5 (cleaner air)
- Calm conditions → Higher PM2.5 (pollutants accumulate)

**Example Pattern Learned:**
- 8 AM, wind from West, sensor 84117 (Lake Elizabeth, east of highways) → Higher PM2.5
- 2 PM, wind from Ocean, all sensors → Lower PM2.5 (clean air blowing in)

### F. Weather Features (Existing)

**Humidity:**
- High humidity → Particles absorb water, become heavier, settle faster → Lower PM2.5
- Low humidity → Particles stay airborne longer → Higher PM2.5

**Temperature:**
- High temperature → Better atmospheric mixing, dispersion → Lower PM2.5
- Low temperature → Temperature inversions trap pollutants → Higher PM2.5

**Combined Effect:**
- Low temp + High humidity → Winter inversion → Highest PM2.5
- High temp + Low humidity → Summer dispersion → Lowest PM2.5

## User Location → Nearest Sensor Matching

**Process:**

1. **User Input**: "Lake Elizabeth Park, Fremont" or lat/lon

2. **Geocoding** (if address):
   ```
   "Lake Elizabeth Park, Fremont" → (37.54408, -121.96445)
   ```

3. **Find Nearest Sensor**:
   ```
   Calculate distance to all 10 sensors:
   - Sensor 84117 (Lake Elizabeth): 0.0 km ✓ (exact match!)
   - Sensor 19683 (Glenmoor Gardens): 3.2 km
   - Sensor 17895 (Glenmoor): 4.1 km
   - ...
   
   Select: Sensor 84117 (nearest)
   ```

4. **Use Sensor's Pattern**:
   - Use Sensor 84117's historical data for training context
   - Use its spatial features (park location, nearby sensors)
   - Predict based on its patterns

**Fallback**: If no exact match, use weighted average of nearest 3 sensors

## Model Training Logic

**What the Model Learns:**

1. **Seasonal Patterns**:
   - Winter (Dec-Feb): Higher PM2.5 due to inversions
   - Summer (Jun-Aug): Lower PM2.5 due to better dispersion
   - Spring/Fall: Moderate patterns

2. **Diurnal Patterns**:
   - Morning rush (7-9 AM): +10-20 μg/m³ increase
   - Afternoon (12-3 PM): Lower PM2.5 (dispersion)
   - Evening rush (5-7 PM): +10-20 μg/m³ increase
   - Night (10 PM-6 AM): Baseline lower

3. **Weather Patterns**:
   - Low temp + high humidity → Higher PM2.5
   - High temp + low humidity → Lower PM2.5

4. **Spatial Patterns**:
   - Sensors near highways: Higher baseline
   - Sensors in parks: Lower baseline
   - Nearby sensors: Similar values

5. **Wind Patterns**:
   - Wind from pollution source → Higher PM2.5
   - Wind from clean area → Lower PM2.5
   - Calm conditions → Accumulation → Higher PM2.5

6. **Temporal Persistence**:
   - If PM2.5 is high now → Likely still high in 1h
   - If PM2.5 is increasing → Predict higher value
   - If PM2.5 is decreasing → Predict lower value

## Prediction Example

**Scenario**: User wants to go to Lake Elizabeth Park at 3 PM today

**Current Conditions**:
- Time: 2 PM, Monday, January 2026
- Sensor 84117 (Lake Elizabeth): PM2.5 = 25 μg/m³, humidity = 60%, temp = 65°F
- Wind: From West (270°), 10 mph
- Recent trend: PM2.5 was 30, 28, 25 (decreasing)

**Features Created**:
- Time: hour_cos = -0.87 (2 PM), month_sin = -0.5 (January), is_rush_hour = 0 (no)
- Lagged: pm2.5_1h_ago = 28, pm2.5_3h_ago = 30, trend = -5 (decreasing)
- Rolling: mean_6h = 27, std_6h = 3 (moderate variability)
- Spatial: distance_from_center = 2.1 km, nearby_avg = 26
- Wind: wind_dir_x = 0 (West), wind_dir_y = -1 (South component)
- Weather: humidity = 60%, temp = 65°F

**Model Prediction**:
- 1-hour forecast: PM2.5 = 22 μg/m³ → AQI = 63 (Moderate)
- 3-hour forecast: PM2.5 = 20 μg/m³ → AQI = 58 (Moderate)

**Reasoning**:
- Decreasing trend → Lower future value
- Not rush hour → Less traffic pollution
- Wind from West (ocean) → Cleaner air blowing in
- Afternoon → Better dispersion
- Result: "Moderate" air quality - Good for outdoor activities!

## Model Performance Expectations

**With Full 2025 Dataset + All Features:**

**1-Hour Forecast:**
- MAE: ~3-5 μg/m³ (very good!)
- R²: > 0.85 (explains 85%+ of variance)
- Category Accuracy: > 85% (correctly predicts Good/Moderate/Unhealthy)

**3-Hour Forecast:**
- MAE: ~4-6 μg/m³ (good!)
- R²: > 0.75 (explains 75%+ of variance)
- Category Accuracy: > 80% (still very accurate)

**Why These Expectations?**
- Full year of data captures all seasonal patterns
- 100+ features capture complex relationships
- Wind direction adds critical pollutant transport information
- Spatial features capture location-specific patterns
- Time series features capture temporal dependencies

---

## Summary

**Model**: XGBoost Ensemble (Regression + Classification)

**Key Innovation**: 
- Wind direction + Spatial features = Understands **where pollutants are coming from** and **where they're going**

**Prediction Logic**:
1. Historical patterns (what was PM2.5 recently?)
2. Temporal patterns (what time/day/season is it?)
3. Weather patterns (how do conditions affect dispersion?)
4. Spatial patterns (where is the sensor located?)
5. Wind patterns (which direction are pollutants blowing?)
6. Combined → Predict future AQI

**Ready to train once you approve!**

