# Debug Field Reference for UI Diagnosis

## Overview

A temporary `debug` field has been added to the API response to help diagnose whether the "3h always lower" issue is UI-side or API-side.

## Debug Field Structure

The `debug` field is now included in every API response (optional, won't break existing clients):

```json
{
  "success": true,
  "current_aqi": { ... },
  "forecast_1h": { ... },
  "forecast_3h": { ... },
  "debug": {
    "selected_sensor_id": 19683,
    "distance_km": 0.523,
    "current_pm25": 28.700,
    "current_aqi": 88,
    "pred_1h_pm25": 26.300,
    "pred_1h_aqi": 81,
    "pred_3h_pm25": 30.500,
    "pred_3h_aqi": 92,
    "comparison": {
      "current_vs_1h": {
        "pm25_diff": -2.400,
        "aqi_diff": -7,
        "direction": "improving"
      },
      "current_vs_3h": {
        "pm25_diff": 1.800,
        "aqi_diff": 4,
        "direction": "worsening"
      }
    }
  }
}
```

## Debug Field Fields

| Field | Type | Description |
|-------|------|-------------|
| `selected_sensor_id` | integer | ID of the PurpleAir sensor used for prediction |
| `distance_km` | float | Distance from address to sensor (3 decimal precision) |
| `current_pm25` | float | Current PM2.5 value (3 decimal precision) |
| `current_aqi` | integer | Current AQI (calculated from current_pm25) |
| `pred_1h_pm25` | float | 1-hour forecast PM2.5 (3 decimal precision) |
| `pred_1h_aqi` | integer | 1-hour forecast AQI (calculated from pred_1h_pm25) |
| `pred_3h_pm25` | float | 3-hour forecast PM2.5 (3 decimal precision) |
| `pred_3h_aqi` | integer | 3-hour forecast AQI (calculated from pred_3h_pm25) |
| `comparison.current_vs_1h.pm25_diff` | float | Difference: pred_1h_pm25 - current_pm25 |
| `comparison.current_vs_1h.aqi_diff` | integer | Difference: pred_1h_aqi - current_aqi |
| `comparison.current_vs_1h.direction` | string | "improving", "worsening", or "flat" |
| `comparison.current_vs_3h.pm25_diff` | float | Difference: pred_3h_pm25 - current_pm25 |
| `comparison.current_vs_3h.aqi_diff` | integer | Difference: pred_3h_aqi - current_aqi |
| `comparison.current_vs_3h.direction` | string | "improving", "worsening", or "flat" |

## Testing Instructions

### Step 1: Log Full API Response

For each of the 5 test addresses below, log the **complete API response** (including the `debug` field):

1. `2523 Bishop Ave, Fremont, CA 94536`
2. `41800 Blacow Rd, Fremont, CA 94538`
3. `43900 Ice House Terrace, Fremont, CA 94538`
4. `5400 Mowry Ave, Fremont, CA 94538`
5. `39400 Paseo Padre Pkwy, Fremont, CA 94538`

### Step 2: Compare Debug Values with UI Display

For each address, verify:

#### Sensor Information
- [ ] UI shows same `selected_sensor_id` as `debug.selected_sensor_id`
- [ ] UI shows same `distance_km` as `debug.distance_km` (within rounding)

#### Current Values
- [ ] UI shows same `current_pm25` as `debug.current_pm25` (within rounding)
- [ ] UI shows same `current_aqi` as `debug.current_aqi`

#### 1-Hour Forecast
- [ ] UI shows same `pred_1h_pm25` as `debug.pred_1h_pm25` (within rounding)
- [ ] UI shows same `pred_1h_aqi` as `debug.pred_1h_aqi`
- [ ] UI shows correct direction: `debug.comparison.current_vs_1h.direction`

#### 3-Hour Forecast
- [ ] UI shows same `pred_3h_pm25` as `debug.pred_3h_pm25` (within rounding)
- [ ] UI shows same `pred_3h_aqi` as `debug.pred_3h_aqi`
- [ ] UI shows correct direction: `debug.comparison.current_vs_3h.direction`

### Step 3: Check for Common UI Issues

#### Value Swapping
- [ ] 1h values are NOT swapped with 3h values
- [ ] PM2.5 values are NOT swapped with AQI values

#### Logic Issues
- [ ] No `min()` or `max()` logic applied to forecasts
- [ ] No floor/ceiling applied to forecasts
- [ ] No conditional logic that forces 3h < current

#### Unit Mismatch
- [ ] PM2.5 values are displayed as PM2.5 (not converted to AQI)
- [ ] AQI values are displayed as AQI (not converted to PM2.5)
- [ ] No unit conversion errors

#### Rounding/Flooring Artifacts
- [ ] Rounding is consistent (e.g., 2 decimal places for PM2.5, integer for AQI)
- [ ] No unexpected floor values (e.g., 0.1, 0.0)
- [ ] No unexpected ceiling values

## Diagnosis

### Scenario 1: Debug Shows 3h > Current, UI Shows 3h < Current
**Conclusion:** Issue is in **frontend mapping/formatting**
- Check UI code for:
  - Value swapping (1h/3h or PM2.5/AQI)
  - `min()` logic applied to 3h forecast
  - Conditional logic forcing 3h < current
  - Unit conversion errors

### Scenario 2: Debug Shows 3h < Current, UI Shows 3h < Current
**Conclusion:** Issue is in **API/model logic** (already fixed with Phase 2.1.5)
- The API is correctly predicting improvement
- This is expected behavior when conditions are improving
- No UI issue

### Scenario 3: Debug Shows 3h > Current, UI Shows 3h > Current
**Conclusion:** No issue - both API and UI are correct
- The API is correctly predicting worsening
- The UI is correctly displaying it

## Example Comparison

### API Response (Debug)
```json
{
  "debug": {
    "current_pm25": 28.700,
    "current_aqi": 88,
    "pred_3h_pm25": 30.500,
    "pred_3h_aqi": 92,
    "comparison": {
      "current_vs_3h": {
        "direction": "worsening"
      }
    }
  }
}
```

### Expected UI Display
- Current AQI: **88**
- 3h Forecast AQI: **92** (higher than current)
- Direction: **Worsening** (or upward arrow)

### If UI Shows
- Current AQI: **88**
- 3h Forecast AQI: **81** (lower than current) ❌
- Direction: **Improving** ❌

**Then:** UI is incorrectly displaying the values (check for swapping, min() logic, etc.)

## Notes

- The `debug` field is **temporary** and can be removed after diagnosis
- All values in `debug` use higher precision (3 decimals for PM2.5) to avoid rounding artifacts
- The `comparison` object provides pre-calculated differences and direction for easy checking
- If any discrepancies are found, log both the API response and the UI display for comparison
