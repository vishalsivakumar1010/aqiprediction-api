# How Wind Direction Data is Fetched

## The Issue You Found

When you check Meteostat directly using Point-based queries (latitude/longitude), you may not see wind direction data. However, the code **does** successfully fetch wind direction data for training and inference. Here's why:

## How the Code Actually Works

### 1. Station-Based Selection (Not Point-Based)

The code does **NOT** use Point-based queries like:
```python
# This might NOT work or return incomplete data:
data = Hourly(Point(latitude, longitude), start=start, end=end).fetch()
```

Instead, it uses a **station-selection algorithm**:

### 2. Station Selection Process

1. **Find Nearby Stations**: Uses `stations.nearby(Point(lat, lon), radius=50km)` to find actual weather stations
2. **Test Each Station**: For each station, tests wind direction coverage using a sample window (June 1-7, 2025)
3. **Select Best Station**: Chooses stations with ≥80% coverage (preferred) or ≥50% (minimum)
4. **Fetch from Station ID**: Uses `hourly(station_id, start=start, end=end).fetch()` to get data from the selected station

### 3. Stations Used

Based on the cache file, these stations have 100% wind direction coverage:
- **74509** (Moffett Field) - 14.45 km from Fremont
- KPAO0 (Palo Alto)
- 72585 (Hayward / Russell City)
- KSJC0 (San Jose)
- KLVK0 (Livermore)
- And others...

### 4. Verification

I tested station 74509 (Moffett Field) directly:
```python
from meteostat import hourly
from datetime import datetime

station_id = '74509'
start = datetime(2025, 6, 1)
end = datetime(2025, 6, 7)

data = hourly(station_id, start=start, end=end).fetch()
# Result: 145 rows, 100% wdir coverage, values: [340, 340, 340, 330, 340, ...]
```

**✓ Station 74509 DOES have wind direction data!**

## Why Point-Based Queries Might Not Work

1. **No Direct Station Mapping**: Point-based queries may interpolate from multiple stations or fail to find a good match
2. **Missing Data**: Some stations near a point might not have wind direction data
3. **Coverage Issues**: The nearest station to a point might have poor wind direction coverage

## What the Code Does Differently

1. **Explicit Station Selection**: Tests multiple nearby stations to find ones with good coverage
2. **Coverage Testing**: Uses a test window to verify wind direction availability before selection
3. **Caching**: Caches coverage results to avoid repeated testing
4. **Fallback Logic**: Expands search radius (50km → 100km) if needed

## For Training

The code:
1. Finds nearby stations (within 50km of Fremont center: 37.5483, -121.9886)
2. Tests each station's wind direction coverage (June 1-7, 2025 sample window)
3. Selects station 74509 (Moffett Field) - 100% coverage, 14.45 km away
4. Fetches full historical data from station 74509 for the training period (2025-01-01 to 2026-01-08)
5. Merges wind data with PurpleAir data (hourly → 30-minute via forward-fill)

## For Inference/Prediction

The code:
1. Uses the same station selection logic
2. Fetches recent wind data from the selected station
3. Merges with current sensor data for predictions

## Summary

- **Station-Based Approach**: Uses specific weather station IDs (like '74509')
- **Coverage Testing**: Verifies wind direction data exists before using
- **Not Point-Based**: Does NOT rely on Point(lat, lon) queries
- **Real Data**: Station 74509 (Moffett Field) has 100% wind direction coverage

The reason it works in the code but you don't see it when checking directly is likely because:
1. You're using Point-based queries instead of station IDs
2. You're checking stations that don't have wind direction data
3. The code specifically selects stations WITH wind direction data (like 74509)

## To Verify Yourself

```python
from meteostat import hourly
from datetime import datetime

# Use the specific station ID that the code uses:
station_id = '74509'  # Moffett Field
start = datetime(2025, 6, 1)
end = datetime(2025, 6, 7)

data = hourly(station_id, start=start, end=end).fetch()
print(f"Wind direction data: {data['wdir'].notna().sum()}/{len(data)} rows")
print(f"Sample values: {data['wdir'].dropna().head(10).tolist()}")
```

You should see wind direction values like [340, 340, 330, 340, ...] (degrees 0-360).
