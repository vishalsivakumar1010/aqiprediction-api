# Prediction Bias Root Cause Analysis

## Summary

**Observed Bias:**
- **100%** of 1h PM2.5 predictions are HIGHER than current values
- **96.7%** of 3h PM2.5 predictions are higher
- Average 1h increase: +2.62 μg/m³
- Average 3h increase: +4.04 μg/m³

**Training Data:**
- NO bias in training data (47.7% increases, 45.5% decreases for 1h)
- Average change in training: -0.00 μg/m³ (balanced)

**Conclusion**: The bias is in the **PM2.5 predictions themselves**, not in AQI conversion.

## Root Cause Hypothesis

### Primary Hypothesis: XGBoost Regression Default Behavior

XGBoost regression models use **squared error loss** by default, which:
1. **Penalizes large errors more** (squared term)
2. **Tends to predict towards the mean** of the training distribution
3. **May over-predict** when the distribution has outliers or skew

If the training data has:
- Many small values (low PM2.5)
- Some large values (high PM2.5 events)
- The model learns to predict somewhere in between, which may be higher than current for low values

### Secondary Hypothesis: Feature-Based Pattern Learning

The model might have learned patterns from features that correlate with increases:
- **Rolling statistics** might capture upward trends
- **Temporal features** (hour, day) might suggest increases at certain times
- **Lagged features** might show patterns that suggest increases

### Tertiary Hypothesis: Training/Test Distribution Mismatch

If the test period (Nov 2025 - Jan 2026) has different characteristics than training:
- Different seasonal patterns
- Different average PM2.5 levels
- Model trained on summer/fall but tested on winter

## Evidence from Analysis

1. **100% prediction bias** - This is too consistent to be random
2. **Training data is balanced** - So the model learned something else
3. **Feature importance shows some features dominate** (Feature 55: 55% importance)
4. **PM2.5 level-dependent patterns** in training data:
   - Low PM2.5 (0-5): avg change +0.48 μg/m³
   - High PM2.5 (35-100): avg change +29.75 μg/m³
   - Model might be learning this pattern and applying it too aggressively

## Recommended Solutions

### Solution 1: Set base_score Explicitly (Quick Fix)

XGBoost regression uses mean of training labels as base_score. We could:
- Set `base_score=0` to start from zero
- Or set `base_score` to current PM2.5 (persistence-like baseline)

```python
reg_model = xgb.XGBRegressor(
    ...
    base_score=0.0,  # Start from zero instead of mean
)
```

### Solution 2: Use Quantile Regression (Better)

Predict median instead of mean:
- Less sensitive to outliers
- More robust to distribution shifts
- XGBoost supports quantile regression with `objective='reg:quantileerror'`

### Solution 3: Post-Processing Bias Correction (Pragmatic)

Apply correction based on validation results:
- Calculate average bias on validation set
- Subtract bias from predictions
- Or use a correction factor

### Solution 4: Ensemble with Persistence (Hybrid)

Weight predictions with persistence model:
- 50% persistence (current value)
- 50% model prediction
- Smooths predictions

### Solution 5: Different Loss Function (Fundamental)

Use absolute error instead of squared error:
- Less penalty on large errors
- More robust predictions
- XGBoost doesn't directly support this, but could use quantile regression

### Solution 6: Retrain with Balanced Sampling (Data-Level)

If certain conditions lead to increases, balance training:
- Oversample decrease cases
- Or undersample increase cases
- Ensure balanced learning

## Immediate Next Steps

1. **Check feature importance** to see which features drive predictions
2. **Examine predictions by condition** (time of day, current PM2.5 level)
3. **Compare with actual measurements** from validation study (once available)
4. **Try Solution 1 first** (base_score=0) - quick to test
5. **Consider Solution 3** (bias correction) - pragmatic fix

## Questions to Answer

1. Is the bias consistent across all conditions or specific to certain scenarios?
2. Which features are driving the predictions?
3. Does the bias correlate with time of day, current PM2.5 level, or weather?
4. How do actual measurements compare? (Need validation results)
