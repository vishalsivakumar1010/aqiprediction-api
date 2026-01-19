# Model Validation Summary (Corrected)

## Results (n = 50)

**1-hour forecast:**
- MAE: 5.6 AQI
- RMSE: 9.6 AQI
- Average bias: −2.0 AQI (slight under-prediction)

**3-hour forecast:**
- MAE: 6.1 AQI
- RMSE: 8.7 AQI
- Average bias: −1.0 AQI (slight under-prediction)

## Interpretation

The fixes (rolling-feature correction + persistence ensemble) reduced the earlier systematic bias and produced more stable forecasts.

Most predictions fall within roughly ±10 AQI in typical conditions, but there are occasional large errors during rapid AQI changes (spikes).

**Because missed spikes are the most important safety risk**, we also evaluate the model using AQI category accuracy and threshold-crossing metrics (e.g., how often it correctly flags conditions ≥50 or ≥100), not only average error.

## Threshold-Based Metrics

See detailed threshold metrics for:
- **Recall for AQI ≥ 50** (Moderate+): How often we catch "Moderate+" conditions when they actually occur
- **Missed-Warning Rate**: How often actual crosses threshold but predicted stays below (missed warnings)

These metrics are more critical for public health decisions than average error.

## Notes

- 50 validations is a preliminary check; larger validation set (200+) being computed
- Slight under-prediction exists; we address this by focusing on category/threshold warnings and tracking missed alerts
- Promising overall accuracy in typical conditions, with known weakness on sudden spikes
