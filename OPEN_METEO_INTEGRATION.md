# Open-Meteo Wind Data Integration

## Why Open-Meteo?

- ✅ **Reliable API**: Well-documented, free API
- ✅ **Historical Data**: CSV downloads available
- ✅ **Real-time Data**: API for current forecasts
- ✅ **10-meter Height**: Standard meteorological observation height (perfect for air quality)
- ✅ **Wind Direction + Speed**: Can use both
- ✅ **Fremont, CA Coverage**: Good coverage for the area

## Why 10 Meters Height?

- **Standard Height**: 10m is the standard height for surface weather observations
- **Relevant for AQI**: Surface-level wind (10m) is more relevant for ground-level air quality than 100m
- **Matches Meteostat**: Meteostat typically provides 10m wind data, so this is consistent
- **Model Compatibility**: The models were trained with surface-level wind data, so 10m matches best

## Integration Plan

### 1. For Historical Data (Training)

You can:
- **Option A**: Download CSV from Open-Meteo website for Fremont, CA (37.5483°N, -121.9886°W)
- **Option B**: Use Open-Meteo Historical API to fetch data programmatically

**CSV Format Needed:**
- Hourly timestamps
- Wind direction (degrees 0-360) at 10m
- Wind speed (optional, but useful) at 10m

**Integration:**
- Replace or supplement the Meteostat fetching function
- Use the same merge logic (hourly → 30-minute forward-fill)
- Convert to `wdir`, `wind_dir_x`, `wind_dir_y` (same format)

### 2. For Real-time Data (Inference/API)

- Use Open-Meteo Forecast API
- Fetch current wind direction at 10m
- Use same format as training data

## Benefits Over Meteostat

1. **More Reliable**: No station selection needed (grid-based data)
2. **Better Coverage**: Less likely to have missing data
3. **Consistent**: Same source for all locations
4. **Easier**: Direct API calls, no complex station selection
5. **Free**: Open API, no authentication needed

## Next Steps

1. **Test Open-Meteo API** with Fremont coordinates
2. **Create fetch function** for Open-Meteo wind data
3. **Update data preparation** to use Open-Meteo
4. **Update prediction code** to use Open-Meteo
5. **Retrain models** (optional, if using different data source)
6. **Update API server** to use Open-Meteo

## Open-Meteo API Details

**Historical API:**
```
https://archive-api.open-meteo.com/v1/archive?
latitude=37.5483
&longitude=-121.9886
&start_date=2025-01-01
&end_date=2026-01-08
&hourly=wind_direction_10m,wind_speed_10m
&timezone=America/Los_Angeles
```

**Forecast API:**
```
https://api.open-meteo.com/v1/forecast?
latitude=37.5483
&longitude=-121.9886
&hourly=wind_direction_10m,wind_speed_10m
&forecast_days=1
&timezone=America/Los_Angeles
```

## Data Format

Open-Meteo returns:
- `wind_direction_10m`: Wind direction in degrees (0-360°)
  - 0° = North, 90° = East, 180° = South, 270° = West
- `wind_speed_10m`: Wind speed in m/s (optional)

This matches the format we need (`wdir` in degrees 0-360).
