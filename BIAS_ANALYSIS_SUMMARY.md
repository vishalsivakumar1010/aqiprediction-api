# Prediction Bias Analysis Summary

## Critical Finding

**The model is systematically over-predicting PM2.5 values.**

### Evidence

1. **100% of 1h PM2.5 predictions are HIGHER than current values**
2. **96.7% of 3h PM2.5 predictions are higher**
3. **Average bias**: +2.62 μg/m³ (1h), +4.04 μg/m³ (3h)
4. **Training data shows NO bias** - balanced (47.7% increases, 45.5% decreases)

### Root Cause Analysis

**Most Important Feature (55% importance): `pm2_5_atm_rolling_mean_2`**
- This is the rolling mean over the last 2 steps (1 hour)
- If this feature is systematically higher than current PM2.5, the model will predict higher
- The model is heavily relying on this feature (55% importance!)

**Second Most Important (29% importance): `pm25_nearby_sensors_avg`**
- Average PM2.5 from nearby sensors
- If nearby sensors are higher, model predicts higher

**Likely Mechanism:**
1. Rolling mean over last 2 steps includes recent values
2. If values were recently increasing, rolling mean > current
3. Model learned to predict based on rolling mean (55% weight!)
4. This creates systematic upward bias

### Why This Happens

**XGBoost Regression with Squared Error:**
- Squared error loss penalizes large errors more
- Model tends to predict towards mean of training distribution
- When the most important feature (rolling mean) is higher than current, model predicts higher
- No mechanism to correct for this bias

**Training Data Pattern:**
- Training data is balanced overall
- But by PM2.5 level, increases are more common:
  - Low PM2.5 (0-5): avg change +0.48 μg/m³
  - High PM2.5 (35-100): avg change +29.75 μg/m³
- Model learned that increases are more common at higher levels
- Applied this pattern too aggressively

## Solutions

### Solution 1: Adjust base_score (Quick Fix - Test First)

Set `base_score=0` in XGBRegressor to prevent starting from training mean:

```python
reg_model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    tree_method='hist',
    base_score=0.0  # Start from zero instead of mean
)
```

**Pros**: Quick to test, might reduce bias
**Cons**: May not solve underlying issue

### Solution 2: Post-Processing Bias Correction (Pragmatic)

Calculate average bias from validation results and subtract:

```python
# After prediction
predicted_pm25 = model.predict(X)[0]
bias_correction = -2.62  # Average bias from validation (1h)
corrected_pm25 = predicted_pm25 + bias_correction
```

**Pros**: Quick to implement, works immediately
**Cons**: Doesn't fix root cause, may vary by conditions

### Solution 3: Quantile Regression (Better Approach)

Use quantile regression to predict median instead of mean:

```python
reg_model = xgb.XGBRegressor(
    ...
    objective='reg:quantileerror',
    quantile_alpha=0.5  # Predict median (50th percentile)
)
```

**Pros**: More robust, less sensitive to outliers
**Cons**: Requires XGBoost 2.0+ and retraining

### Solution 4: Feature Engineering Fix (Address Root Cause)

The issue might be in how `rolling_mean_2` is calculated:
- Check if it includes current value (should exclude for prediction)
- Or calculate it correctly to exclude future values
- Or reduce weight of rolling features

### Solution 5: Ensemble with Persistence (Hybrid)

Weight predictions with persistence:

```python
# 70% persistence + 30% model prediction
predicted_pm25 = 0.7 * current_pm25 + 0.3 * model_prediction
```

**Pros**: Smooths predictions, reduces bias
**Cons**: Reduces model's contribution

### Solution 6: Different Loss Function (Fundamental)

Use Huber loss (combines absolute and squared error):
- Less sensitive to outliers
- More robust predictions
- But XGBoost doesn't support directly

## Recommended Approach

**Immediate (Before Validation Study Completes):**
1. Document the bias (done)
2. Wait for validation study to complete (12 hours)
3. Compare predictions vs actuals to quantify exact error

**Short-term (After Validation):**
1. **Try Solution 2** (bias correction) - Quick fix based on validation results
2. **Try Solution 1** (base_score=0) - Retrain with adjusted base_score
3. Compare performance with corrected predictions

**Long-term (For Next Training Run):**
1. **Solution 3** (quantile regression) - More robust approach
2. **Solution 4** (feature engineering fix) - Address root cause
3. **Solution 5** (ensemble) - Hybrid approach for stability

## Next Steps

1. ✅ **Bias identified**: 100% of predictions are higher
2. ⏳ **Wait for validation**: 12-hour study running now
3. 📊 **Analyze actuals**: Compare predictions vs actual measurements
4. 🔧 **Implement fix**: Choose solution based on validation results
5. 🔄 **Retrain if needed**: Retrain with adjusted parameters

## Feature Importance (1h Model)

1. `pm2_5_atm_rolling_mean_2`: 55.4% ⚠️ **DOMINATES** - This is the issue!
2. `pm25_nearby_sensors_avg`: 29.5%
3. `pm2_5_atm`: 10.4%
4. Other features: <1% each

**Insight**: The model is essentially predicting based on the 1-hour rolling mean, which tends to be higher than current when values were recently increasing. This creates systematic upward bias.
