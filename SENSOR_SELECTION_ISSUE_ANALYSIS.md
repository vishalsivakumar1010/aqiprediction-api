# Sensor Selection Issue Analysis

## Problem Report

**User Report**: For address "43900 Ice House Terrace, Fremont, CA 94538", the system selected Lake Elizabeth sensor which is 3.95 miles away, even though there are several PurpleAir sensors nearby.

## Investigation Results

### Address Details
- **Address**: 43900 Ice House Terrace, Fremont, CA 94538
- **Geocoded Coordinates**: (37.511081, -121.947585)

### Current API Behavior

**Sensors Loaded**: Only **10 sensors** from `sensor_locations.pkl` (Phase 1 dataset)

**Selected Sensor**: Lake Elizabeth (84117)
- **Distance**: 3.95 km = **2.46 miles** (not 3.95 miles as reported)
- **Rank**: #1 closest among the 10 sensors loaded

**All 10 Sensors (sorted by distance)**:
1. 84117 | Lake Elizabeth | 3.95 km (2.46 miles) ← **Selected**
2. 148483 | Fremont - Civic Center | 5.25 km (3.26 miles)
3. 193337 | Glen Moore-York Dr. | 5.65 km (3.51 miles)
4. 19683 | Glenmoor Gardens | 5.80 km (3.61 miles)
5. 17895 | Glenmoor | 6.58 km (4.09 miles)
6. 71443 | MoonRiver | 6.79 km (4.22 miles)
7. 286506 | 405 L Street | 7.29 km (4.53 miles)
8. 114889 | Washburn court | 8.12 km (5.04 miles)
9. 18987 | Fremont: Cabrillo | 9.12 km (5.67 miles)
10. 56275 | Fremont (Northgate) | 11.67 km (7.25 miles)

### Phase 2 Sensor Analysis

**Sensors Available**: **42 sensors** in Phase 2 dataset (`P2-RouteFinder/data/sensor_locations/sensor_locations.pkl`)

**Top 15 Closest Phase 2 Sensors**:
1. **200231 | UG FRE01 BLS SQA** | **0.72 km (0.44 miles)** ← **Much closer!**
2. 80679 | Camellia Ct | 1.02 km (0.64 miles)
3. 289878 | 1005 | 1.31 km (0.82 miles)
4. 52853 | Westbourne Park | 1.34 km (0.83 miles)
5. 62183 | Laurel Glen | 2.69 km (1.67 miles)
6. 289208 | CZT hallway timeclock area | 2.79 km (1.73 miles)
7. 289204 | CZT Lunchroom | 2.80 km (1.74 miles)
8. 289206 | Chris's office | 2.81 km (1.74 miles)
9. 204577 | Mission Hollow | 2.83 km (1.76 miles)
10. 65547 | Dollar | 3.03 km (1.89 miles)
11. 65447 | PaseoAtDriscoll | 3.67 km (2.28 miles)
12. 77725 | South Mission | 3.68 km (2.29 miles)
13. 145924 | RHiguera | 3.87 km (2.40 miles)
14. 22471 | Zapotec | 3.92 km (2.44 miles)
15. **84117 | Lake Elizabeth** | **3.95 km (2.46 miles)** ← Current selection

## Root Cause

### Issue 1: Wrong Sensor File Loaded

**Problem**: The API server is loading `sensor_locations.pkl` from the current directory, which contains only **10 sensors** from Phase 1.

**Expected**: The API should load Phase 2's sensor file with **42 sensors** from `P2-RouteFinder/data/sensor_locations/sensor_locations.pkl`.

**Impact**: 
- Missing 32 sensors from Phase 2
- Selecting sensors that are 3-5x farther away than necessary
- Example: Selecting Lake Elizabeth at 3.95 km instead of UG FRE01 BLS SQA at 0.72 km

### Issue 2: Unit Confusion (Possible)

**User Reported**: "3.95 miles away"

**Actual Distance**: 3.95 km = 2.46 miles

**Possible Causes**:
1. API response shows `distance_km: 3.95` and Lovable UI displays it as "3.95 miles" (missing unit conversion)
2. User misread the value
3. API response format issue

**API Response Format** (from `aqi_api_server.py`):
```python
sensor_info={
    "sensor_id": sensor_id,
    "sensor_name": sensor_name,
    "distance_km": round(distance_km, 2),  # ← Returns in km
    "latitude": nearest['latitude'],
    "longitude": nearest['longitude']
}
```

**Note**: The API correctly returns `distance_km`, but if Lovable displays it without the "km" unit, users might interpret it as miles.

## Comparison

| Metric | Current API (10 sensors) | Phase 2 (42 sensors) | Difference |
|--------|-------------------------|---------------------|------------|
| **Closest Sensor** | Lake Elizabeth (84117) | UG FRE01 BLS SQA (200231) | - |
| **Distance** | 3.95 km (2.46 miles) | 0.72 km (0.44 miles) | **3.23 km (2.01 miles) closer** |
| **Rank of Lake Elizabeth** | #1 (closest) | #15 | - |
| **Sensors within 2 km** | 0 | 4 | - |
| **Sensors within 3 km** | 0 | 10 | - |

## Impact

### Accuracy Impact

**Current Selection (Lake Elizabeth at 3.95 km)**:
- Sensor is 3.95 km away from address
- May not be representative of local conditions
- Warning message should trigger (>3.0 km threshold)

**Optimal Selection (UG FRE01 BLS SQA at 0.72 km)**:
- Sensor is only 0.72 km away (0.44 miles)
- Much more representative of local conditions
- No warning needed (<2.0 km threshold)

### User Experience Impact

- Users see "3.95" and may think it's miles (confusing)
- Sensor is unnecessarily far away
- Forecast accuracy may be reduced due to distance
- Warning message may appear unnecessarily

## Technical Details

### Current Sensor Loading Logic

**File**: `test_predictions.py` → `load_sensor_locations()`

**Search Order**:
1. `{data_dir}/sensor_locations.pkl` ← **Currently loading from here (10 sensors)**
2. `~/Downloads/PAIC Data 2 Months/sensor_locations.pkl`
3. `~/Downloads/PAIC Data 2 Months/sensor_locations.csv`

**Missing**: Phase 2 sensor file path not checked!

### Phase 2 Sensor File Location

- **Path**: `P2-RouteFinder/data/sensor_locations/sensor_locations.pkl`
- **Sensors**: 42 sensors
- **Status**: Exists but not being loaded by API

## Recommendations

### Fix 1: Update Sensor Loading to Include Phase 2

**Action**: Modify `load_sensor_locations()` to check Phase 2 sensor file first (or merge both).

**Priority**: High - This will immediately improve sensor selection for all addresses.

### Fix 2: Clarify Distance Units in API Response

**Action**: Ensure API response clearly indicates units (km) and/or add distance in miles.

**Priority**: Medium - Improves user understanding.

### Fix 3: Update API Documentation

**Action**: Document that Phase 2 sensors (42) should be used, not Phase 1 (10).

**Priority**: Low - Documentation only.

## Files to Modify

1. **`test_predictions.py`**:
   - Update `load_sensor_locations()` to check Phase 2 sensor file
   - Priority: Check Phase 2 file first, fallback to Phase 1

2. **`aqi_api_server.py`** (optional):
   - Add `distance_miles` to response for clarity
   - Ensure units are clear in response

## Expected Outcome After Fix

- **Closest sensor**: UG FRE01 BLS SQA (200231) at 0.72 km (0.44 miles)
- **Improvement**: 3.23 km (2.01 miles) closer
- **Better accuracy**: Sensor much closer to address
- **No warning**: Distance < 2.0 km threshold
