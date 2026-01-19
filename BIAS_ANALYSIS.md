# Prediction Bias Analysis

## Observed Bias

From validation study logs (as of latest run):

**1-Hour Forecast:**
- 90% of predictions are **higher** than current AQI
- Average difference: +6.6 AQI points
- Median difference: +2.0 AQI points
- 0% of predictions are lower than current

**3-Hour Forecast:**
- 96.7% of predictions are **higher** than current AQI
- Average difference: +11.1 AQI points
- Median difference: +9.0 AQI points
- 86.7% of 3h predictions are higher than 1h predictions

## Training Data Analysis

**Surprisingly, training data shows NO bias:**
- 1h future: 47.7% increases, 45.5% decreases (balanced)
- 3h future: 50.2% increases, 46.3% decreases (balanced)
- Average change: -0.00 μg/m³ (1h), -0.01 μg/m³ (3h)
- Median change: 0.00 μg/m³ (1h), 0.10 μg/m³ (3h)

**Conclusion**: Training data is balanced, but model consistently predicts increases. This suggests the model learned a pattern that doesn't exist in the data, or there's an issue in prediction pipeline.

## Potential Causes

### 1. **XGBoost Base Score**
- XGBoost regression models have a `base_score` parameter
- Default is 0.5 (for classification) or mean of training labels (for regression)
- If model is predicting from a base that's higher than actual, it could create bias

### 2. **Loss Function Issue**
- XGBoost uses squared error loss by default
- Squared error penalizes large errors more, which might lead model to predict conservatively higher
- No explicit handling of negative errors vs positive errors

### 3. **Feature Engineering Bias**
- Some features might correlate with increases (e.g., time of day patterns)
- Rolling statistics might capture upward trends
- Spatial features might suggest increases

### 4. **AQI Conversion Nonlinearity**
- PM2.5 to AQI conversion is nonlinear
- Small PM2.5 increases can create larger AQI increases at certain ranges
- Model might predict PM2.5 correctly, but AQI conversion amplifies errors

### 5. **Temporal Patterns**
- Model might have learned that PM2.5 increases at certain times
- Rush hour patterns, daily cycles might suggest increases
- Weather patterns might suggest increases

### 6. **Regression vs Classification Mismatch**
- Regression model predicts PM2.5, then converts to AQI
- Classification model predicts category directly
- If using regression output, the conversion might introduce bias

## Next Steps to Investigate

1. **Check actual PM2.5 predictions** (not just AQI) to see if bias is in PM2.5 or AQI conversion
2. **Check model base_score** and see if it's causing bias
3. **Analyze predictions by time of day** to see if there's a temporal pattern
4. **Compare with actual measurements** from validation study to quantify error
5. **Check feature importance** to see which features are driving predictions
6. **Examine residuals** to see if errors are systematic or random

## Possible Solutions

1. **Adjust base_score**: Set base_score to match expected mean of predictions
2. **Use quantile regression**: Predict median instead of mean (less sensitive to outliers)
3. **Post-processing correction**: Apply bias correction based on validation results
4. **Different loss function**: Use absolute error instead of squared error
5. **Ensemble with persistence**: Weight predictions with persistence model
6. **Retrain with balanced sampling**: Sample more decreases to balance training data
