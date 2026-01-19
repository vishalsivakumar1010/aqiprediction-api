# Ensemble Implementation (60% ML + 40% Persistence)

## Overview

Implemented ensemble approach combining ML prediction with persistence baseline to reduce systematic bias and improve forecast stability.

## Implementation Details

### Changes Made

**File**: `test_predictions.py`

**Function**: `make_predictions()`

**New Parameters**:
- `current_pm25`: Current PM2.5 value for persistence baseline (optional)
- `ensemble_weight`: Weight for ML prediction (default 0.6)

**Ensemble Formula**:
```python
final_prediction = 0.6 * ML_prediction + 0.4 * current_pm25
```

### How It Works

1. **ML Prediction**: Model predicts PM2.5 using XGBoost regression (same as before)

2. **Persistence Baseline**: Uses current PM2.5 value as baseline (assumes no change)

3. **Ensemble Combination**: 
   - 60% weight on ML prediction (captures trends and patterns)
   - 40% weight on persistence (reduces over-reaction to short-term fluctuations)

4. **Final Prediction**: Weighted average of ML and persistence

### Why This Works

**Benefits**:
- **Reduces Systematic Bias**: Persistence baseline provides stability, preventing over-reaction
- **Maintains Trend Awareness**: ML component (60%) still captures directional patterns
- **Defensible Approach**: Standard practice in time-series forecasting
- **Easy to Explain**: Clear, interpretable methodology

**Trade-offs**:
- Slightly less aggressive predictions (may miss rapid changes)
- More stable forecasts (better for planning)
- Balanced approach (combines benefits of both methods)

## Usage

The ensemble is automatically applied when `current_pm25` is provided:

```python
predictions = make_predictions(
    models, 
    feature_row, 
    feature_columns,
    current_pm25=current_pm25,  # Enables ensemble
    ensemble_weight=0.6  # 60% ML, 40% persistence (default)
)
```

If `current_pm25` is `None`, predictions use ML only (no ensemble).

## Expected Impact

**Before (ML Only)**:
- Systematic upward bias in predictions
- Over-reaction to short-term trends
- Higher variance in forecasts

**After (Ensemble)**:
- Reduced systematic bias
- More stable predictions
- Better balance between trend awareness and stability
- Improved forecast reliability

## Next Steps

1. ✅ **Rolling mean fixed** (uses only past values)
2. ✅ **Model retrained** with corrected features
3. ✅ **Ensemble implemented** (60% ML + 40% persistence)
4. ⏳ **Re-evaluate bias** after ensemble implementation

## Notes

- Ensemble weights (60/40) are based on standard time-series forecasting practice
- Can be adjusted if needed (e.g., 70/30 or 50/50) based on validation results
- Focus should shift to AQI category accuracy and threshold crossings (as recommended)
