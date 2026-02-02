# Diagnosis: 3-Hour Forecast Always Lower Than Current

## Problem Statement

**User Report**: In the deployed Lovable app, the 3-hour forecast is **always lower than current AQI**, regardless of trend. This indicates a logic bug, not a model issue.

## Code Analysis

### Location: `test_predictions.py` → `make_predictions()` function

### Issue #1: **Bias Correction Always Subtracts** (MOST LIKELY CULPRIT)

**Lines 1049-1058**:
```python
# Apply bias correction (Phase 2.1 Refinements: 3h only)
if horizon == '3h':
    if bias_correction_3h is None:
        estimated_3h_bias = 9.31
        correction_factor = 0.22
        bias_correction_3h = correction_factor * estimated_3h_bias  # Always ~2.05 μg/m³
    predicted_pm25 = max(0.1, predicted_pm25 - bias_correction_3h)  # ALWAYS SUBTRACTS
```

**Problem**: 
- Bias correction **always subtracts** ~2.05 μg/m³ from the 3h prediction
- This is applied **regardless of whether the prediction should go up or down**
- Even if ML predicts higher, ensemble + bias correction can bring it down to near/below current

**Example Scenario**:
- Current AQI: 50 (PM2.5: 12.1 μg/m³)
- ML predicts: 60 AQI (PM2.5: 15.4 μg/m³) - should go up
- Ensemble (30% ML, 70% persistence): 0.3 * 15.4 + 0.7 * 12.1 = 13.1 μg/m³ (≈ 54 AQI)
- Bias correction: 13.1 - 2.05 = 11.05 μg/m³ (≈ 46 AQI) ← **Below current!**

**Root Cause**: Bias correction was intended to correct for **over-prediction bias** (positive bias), but it's being applied **unconditionally**, even when the model predicts correctly or should predict higher.

### Issue #2: **Ensemble Weights May Be Too Conservative**

**Lines 970-971**:
```python
# Normal regime (Phase 2.1): 1h: 40% ML + 60% persistence, 3h: 30% ML + 70% persistence
ensemble_weights = {'1h': 0.4, '3h': 0.3}
```

**Problem**:
- 3h uses only **30% ML + 70% persistence**
- This means 70% of the prediction is just "current value"
- Combined with bias correction, this heavily biases toward current or lower

**Example**:
- Current: 50 AQI
- ML predicts: 70 AQI (should go up significantly)
- Ensemble: 0.3 * 70 + 0.7 * 50 = 21 + 35 = 56 AQI (only slightly above)
- Bias correction: 56 - 2.05 ≈ 54 AQI (barely above current)
- If ML predicts only slightly higher, result could be below current

### Issue #3: **Rate-of-Change Cap Logic** (Less Likely, But Check)

**Lines 1025-1032**:
```python
# Apply rate-of-change cap (Phase 2.1)
if current_pm25 > 0:
    hours_ahead = 1.0 if horizon == '1h' else 3.0
    max_allowed = current_pm25 * (1 + max_worsening_rate * hours_ahead)
    if predicted_pm25 > max_allowed:
        predicted_pm25 = max_allowed
```

**Analysis**: This logic looks correct - it only caps **worsening** (upward movement), not improvements. However, if `max_worsening_rate` is too small or incorrectly applied, it could limit upward movement.

**Lines 1034-1047** (Stricter 3h cap):
```python
# Apply stricter 3h rate-of-change cap (Phase 2.1 Refinements)
if horizon == '3h' and current_aqi is not None:
    if current_aqi < 100:
        max_aqi_allowed = current_aqi + 30  # Cap worsening to +30 AQI
        predicted_aqi_temp = pm25_to_aqi(predicted_pm25)
        if predicted_aqi_temp > max_aqi_allowed:
            predicted_pm25 = aqi_to_pm25(max_aqi_allowed)
```

**Analysis**: This also looks correct - it only caps upward movement. But if the prediction is already low due to bias correction, this won't help.

## Most Likely Root Cause

**Combination of Issues #1 and #2**:

1. **Bias correction always subtracts** ~2.05 μg/m³ (≈ 2-3 AQI)
2. **Ensemble is 70% persistence** (heavily weighted toward current)
3. **Result**: Even when ML predicts higher, the combination brings it down to near/below current

**Example Calculation**:
- Current: 50 AQI (12.1 μg/m³)
- ML predicts: 65 AQI (16.2 μg/m³) - should go up
- Ensemble: 0.3 * 16.2 + 0.7 * 12.1 = 4.86 + 8.47 = 13.33 μg/m³ (≈ 55 AQI)
- Bias correction: 13.33 - 2.05 = 11.28 μg/m³ (≈ 47 AQI) ← **Below current!**

## Recommended Fixes (In Priority Order)

### Fix #1: Make Bias Correction Conditional (CRITICAL)

**Current**: Always subtracts bias correction
**Should**: Only apply bias correction when prediction is **above** current (over-prediction)

```python
# Apply bias correction (Phase 2.1 Refinements: 3h only)
if horizon == '3h':
    if bias_correction_3h is None:
        estimated_3h_bias = 9.31
        correction_factor = 0.22
        bias_correction_3h = correction_factor * estimated_3h_bias
    
    # Only apply bias correction if prediction is above current (over-prediction)
    if current_pm25 is not None and predicted_pm25 > current_pm25:
        predicted_pm25 = max(0.1, predicted_pm25 - bias_correction_3h)
    # If prediction is below current, don't apply bias correction (no over-prediction to correct)
```

### Fix #2: Adjust Ensemble Weights for 3h (OPTIONAL)

**Current**: 30% ML + 70% persistence (very conservative)
**Consider**: 40% ML + 60% persistence (same as 1h) to allow more upward movement

### Fix #3: Add Diagnostic Logging (FOR DEBUGGING)

Add logging to track:
- Raw ML prediction
- Ensemble result (before bias correction)
- After bias correction
- Final returned value

This will help identify which step is causing the issue.

## Verification Steps

1. **Temporarily disable bias correction** and test
   - If 3h now goes above current → bias correction is the culprit
   
2. **Temporarily increase ML weight** (e.g., 50% ML + 50% persistence) and test
   - If 3h now goes above current → ensemble weights are too conservative

3. **Add diagnostic logging** to see actual values at each step
   - Compare ML prediction vs ensemble vs final

## Expected Behavior After Fix

- **3h forecast should**:
  - Sometimes go up (when conditions worsen)
  - Sometimes stay flat (when conditions stable)
  - Sometimes go down (when conditions improve)
  
- **Should NOT**:
  - Always be lower than current
  - Always be the same as current

## Next Steps

1. ✅ **Diagnosis complete** - Bias correction is most likely culprit
2. ⏳ **Wait for user approval** before making changes
3. 🔧 **Implement fix** - Make bias correction conditional
4. 🧪 **Test** - Verify 3h can go above current
5. 📊 **Add logging** - For future debugging
