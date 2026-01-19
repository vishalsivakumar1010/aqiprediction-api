# Model Validation Summary (n = 200)

## Overall Performance

**1-hour forecast:**
- MAE: 5.6 AQI, RMSE: 9.6 AQI
- Average bias: −2.0 AQI (slight under-prediction)

**3-hour forecast:**
- MAE: 6.1 AQI, RMSE: 8.7 AQI
- Average bias: −1.0 AQI (slight under-prediction)

## Threshold-Based Metrics (AQI ≥ 50, Moderate+)

### 1-Hour Forecast
- **Recall: 83.3%** (caught 25 out of 30 actual cases)
- **Missed-Warning Rate: 16.7%** (5 missed out of 30 actual cases)
- **Precision: 100.0%** (all predictions ≥ 50 were correct)
- **False Alarm Rate: 0.0%** (no false alarms)

### 3-Hour Forecast
- **Recall: 76.7%** (caught 23 out of 30 actual cases)
- **Missed-Warning Rate: 23.3%** (7 missed out of 30 actual cases)
- **Precision: 95.8%** (23 of 24 predictions were correct)
- **False Alarm Rate: 0.6%** (1 false alarm)

## Interpretation

The fixes (rolling-feature correction + persistence ensemble) reduced the earlier systematic bias and produced more stable forecasts.

Most predictions fall within roughly ±10 AQI in typical conditions, but there are occasional large errors during rapid AQI changes (spikes).

**Because missed spikes are the most important safety risk**, threshold-based metrics (recall and missed-warning rate) are more critical for public health decisions than average error.

**Slight under-prediction exists** (bias: −2.0 AQI for 1h, −1.0 AQI for 3h). We address this by:
1. Focusing on category/threshold warnings (not just point predictions)
2. Tracking missed alerts (recall and missed-warning rate)
3. Acknowledging that over-prediction is safer (false alarm) than under-prediction (missed warning) for health decisions

**Promising overall accuracy in typical conditions**, with known weakness on sudden spikes.

## Key Findings

1. **1h forecast recall: 83.3%** - catches most Moderate+ conditions, but 16.7% missed-warning rate
2. **3h forecast recall: 76.7%** - lower recall than 1h, with 23.3% missed-warning rate
3. **High precision** (95.8-100%) - when model predicts ≥ 50, it's usually correct
4. **Low false alarm rate** (0-0.6%) - very few false alarms
5. **Slight under-prediction** - model tends to predict slightly lower than actual (risky for health warnings)

## Recommendations

1. **For "safe to go outside" decisions**: Model has good recall (76.7-83.3%) but missed-warning rates (16.7-23.3%) mean some Moderate+ conditions are missed
2. **Consider conservative approach**: Since under-prediction is riskier than over-prediction, may want to adjust ensemble weights or add safety margin
3. **Monitor missed warnings**: Track when actual ≥ 50 but predicted < 50 to understand failure modes
4. **Larger validation**: Need more samples for AQI ≥ 100 threshold metrics

## Notes

- 200 validations provides more robust statistics than 50
- Threshold metrics (recall, missed-warning rate) are more relevant for health decisions than average error
- Model performance is promising but missed-warning rates should be monitored and potentially reduced
