# Rolling Mean Feature Fix

## Issue Identified

**Problem**: Rolling mean features (`pm2_5_atm_rolling_mean_2`, etc.) were including the **current timestep** when calculating rolling statistics.

**Impact**: 
- When predicting at time t for time t+1, rolling mean included value at t (current)
- This created upward bias because rolling mean often > current value during increases
- Model heavily relies on rolling mean (55% importance), amplifying the bias

## Fix Applied

**Changed**: `feature_engineering.py` → `create_rolling_features()`

**Before** (WRONG):
```python
df.loc[sensor_mask, mean_col] = sensor_data[col].rolling(window=window, min_periods=1).mean().values
```
- Rolling mean at time t includes values at t and t-1
- For prediction, this leaks current information

**After** (CORRECT):
```python
shifted_values = sensor_data[col].shift(1)  # Shift by 1 to exclude current value
df.loc[sensor_mask, mean_col] = shifted_values.rolling(window=window, min_periods=1).mean().values
```
- Rolling mean at time t uses values at t-1, t-2, ..., t-window
- For prediction, uses only past values (no leakage)

## Example

**At time t=2 (PM2.5 = 14):**

**Before (Wrong)**:
- Rolling mean = mean(14, 12) = 13.0 (includes current value 14)

**After (Fixed)**:
- Rolling mean = mean(12, 10) = 11.0 (uses only past values)

## Verification

Fix verified with test data:
- Rolling mean now uses only past values (t-1, t-2, ...)
- No current value included
- Correctly excludes current timestep for prediction

## Next Steps

1. ✅ **Fix applied** to `feature_engineering.py`
2. ⏳ **Retraining** models with corrected features
3. 📊 **Re-evaluate bias** after retraining
4. 🔧 **Implement ensemble** (60% ML + 40% persistence)

## Expected Impact

After retraining with fixed rolling mean:
- Rolling mean feature will use only past values
- Should reduce upward bias in predictions
- Model should learn more accurate patterns
- Ensemble will further smooth predictions
