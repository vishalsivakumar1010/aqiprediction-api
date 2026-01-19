# Model Validation Metrics Summary

## Overall Performance (n = 50)

**1-hour forecast:**
- MAE: 5.6 AQI
- RMSE: 9.6 AQI
- Average bias: −2.0 AQI (slight under-prediction)

**3-hour forecast:**
- MAE: 6.1 AQI
- RMSE: 8.7 AQI
- Average bias: −1.0 AQI (slight under-prediction)

## Threshold-Based Metrics (AQI ≥ 50, Moderate+)

### 1-Hour Forecast
- **Recall: 85.7%** (caught 6 out of 7 actual cases)
- **Missed-Warning Rate: 14.3%** (1 missed out of 7 actual cases)
- **Precision: 85.7%** (6 of 7 predictions were correct)
- **False Alarm Rate: 1 false alarm**

**Interpretation**: Model catches 85.7% of Moderate+ conditions. 1 missed warning out of 7 actual cases.

### 3-Hour Forecast
- **Recall: 100.0%** (caught all 6 actual cases)
- **Missed-Warning Rate: 0.0%** (no missed warnings)
- **Precision: 100.0%** (all 6 predictions were correct)
- **False Alarm Rate: 0 false alarms**

**Interpretation**: Perfect recall - model catches all Moderate+ conditions with no missed warnings.

## Key Findings

1. **3h forecast has perfect recall** (100%) for AQI ≥ 50 threshold
2. **1h forecast has good recall** (85.7%) but 1 missed warning
3. **Slight under-prediction** exists (−2.0 AQI for 1h, −1.0 AQI for 3h)
4. **No cases of AQI ≥ 100** in this sample (need larger validation for this threshold)

## Interpretation

The fixes (rolling-feature correction + persistence ensemble) reduced the earlier systematic bias and produced more stable forecasts.

Most predictions fall within roughly ±10 AQI in typical conditions, but there are occasional large errors during rapid AQI changes (spikes).

**Because missed spikes are the most important safety risk**, threshold-based metrics (recall and missed-warning rate) are more critical for public health decisions than average error.

## Notes

- **50 validations is preliminary**; larger validation set (200+) being computed
- **Slight under-prediction exists**; we address this by focusing on category/threshold warnings and tracking missed alerts
- **Promising overall accuracy in typical conditions**, with known weakness on sudden spikes
- **For health warnings, over-prediction is safer** (false alarm) than under-prediction (missed warning)
- Current performance: Good recall (85.7-100%) for Moderate+ threshold

## Next Steps

1. Compute metrics on larger validation set (200+ samples)
2. Compute metrics for AQI ≥ 100 threshold when data is available
3. Analyze missed warnings to understand failure modes
4. Consider adjusting ensemble weights if missed-warning rate is too high
