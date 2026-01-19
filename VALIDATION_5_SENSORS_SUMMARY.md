# Historical Validation Summary - 5 Sensors (200 Samples Each)

## Overview

Validated predictions using historical data from 5 different sensors, with 200 samples each (total: 1000 validation samples).

**Sensors tested:**
1. 17895 (Fremont: Cabrillo)
2. 18987 (Fremont: Cabrillo)
3. 19683 (Glenmoor Gardens)
4. 193337 (Glen Moore-York Dr.)
5. 71443 (MoonRiver)

**Date range:** June 1, 2025 to December 31, 2025
**Samples per sensor:** 200 timestamps (evenly distributed)
**Total samples:** 1,000 validation points

---

## Results by Sensor

### Sensor 17895 (Fremont: Cabrillo)
**1-Hour Forecast:**
- MAE: 1.22 μg/m³
- RMSE: 1.86 μg/m³
- Bias: -0.21 μg/m³ (slight under-prediction)
- Category Accuracy: 97.5%

**3-Hour Forecast:**
- MAE: 2.11 μg/m³
- RMSE: 3.32 μg/m³
- Bias: +0.04 μg/m³ (nearly unbiased)
- Category Accuracy: 97.0%

**Assessment:** Excellent performance, very low error and bias.

---

### Sensor 18987 (Fremont: Cabrillo)
**1-Hour Forecast:**
- MAE: 1.13 μg/m³ ⭐ (best 1h MAE)
- RMSE: 2.06 μg/m³
- Bias: -0.26 μg/m³ (slight under-prediction)
- Category Accuracy: 95.0%

**3-Hour Forecast:**
- MAE: 2.33 μg/m³ ⭐ (best 3h MAE)
- RMSE: 4.45 μg/m³
- Bias: -0.25 μg/m³ (slight under-prediction)
- Category Accuracy: 94.5%

**Assessment:** Best overall performance - lowest MAE for both horizons.

---

### Sensor 19683 (Glenmoor Gardens)
**1-Hour Forecast:**
- MAE: 1.99 μg/m³
- RMSE: 3.28 μg/m³
- Bias: +0.02 μg/m³ (nearly unbiased)
- Category Accuracy: 89.0%

**3-Hour Forecast:**
- MAE: 3.30 μg/m³
- RMSE: 5.80 μg/m³
- Bias: -0.79 μg/m³ (slight under-prediction)
- Category Accuracy: 86.5%

**Assessment:** Good performance, but lower category accuracy than others.

---

### Sensor 193337 (Glen Moore-York Dr.)
**1-Hour Forecast:**
- MAE: 1.61 μg/m³
- RMSE: 2.84 μg/m³
- Bias: +0.21 μg/m³ (slight over-prediction)
- Category Accuracy: 96.5%

**3-Hour Forecast:**
- MAE: 2.62 μg/m³
- RMSE: 4.46 μg/m³
- Bias: +0.33 μg/m³ (slight over-prediction)
- Category Accuracy: 93.5%

**Assessment:** Very good performance, consistent across horizons.

---

### Sensor 71443 (MoonRiver)
**1-Hour Forecast:**
- MAE: 3.68 μg/m³
- RMSE: 8.15 μg/m³
- Bias: -2.46 μg/m³ (under-prediction)
- Category Accuracy: 99.5% ⭐ (best category accuracy for 1h)

**3-Hour Forecast:**
- MAE: 17.02 μg/m³ ⚠️
- RMSE: 52.96 μg/m³ ⚠️
- Bias: +13.78 μg/m³ ⚠️ (strong over-prediction)
- Category Accuracy: 91.0%

**Assessment:** 
- **1h forecast:** Good category accuracy but higher error
- **3h forecast:** Poor performance - very high MAE/RMSE and strong bias
- **Possible causes:** 
  - This sensor may experience different air quality patterns
  - May have more extreme values or spikes
  - Location-specific factors affecting predictability

---

## Overall Summary Statistics

### 1-Hour Forecast (Across All 5 Sensors)
- **Average MAE:** 1.92 μg/m³
- **Average RMSE:** 3.64 μg/m³
- **Average Bias:** -0.54 μg/m³ (slight under-prediction)
- **Average Category Accuracy:** 95.5%

### 3-Hour Forecast (Across All 5 Sensors)
- **Average MAE:** 5.48 μg/m³
- **Average RMSE:** 14.20 μg/m³
- **Average Bias:** +2.62 μg/m³ (over-prediction)
- **Average Category Accuracy:** 92.5%

**Note:** Sensor 71443's poor 3h performance significantly impacts overall averages.

---

## Key Observations

### 1. Performance Consistency
- **Best performers:** 17895 and 18987 show consistently excellent results
- **Most sensors** (4 out of 5) show good 1h forecast performance (MAE < 2.0)
- **Sensor 19683** has lower category accuracy but reasonable error metrics

### 2. Sensor 71443 Anomaly
- **1h forecast:** Acceptable (3.68 MAE, 99.5% category accuracy)
- **3h forecast:** Poor (17.02 MAE, 13.78 bias) - indicates challenges predicting this sensor's 3h future
- **Recommendation:** Investigate this sensor separately - may have location-specific characteristics

### 3. Bias Patterns
- **Most sensors** show slight under-prediction for 1h forecasts
- **Overall bias** is small (< 1.0 μg/m³) for 4 out of 5 sensors
- **Sensor 71443** shows strong over-prediction for 3h forecasts

### 4. Category Accuracy
- **Very high** (89-99.5%) across all sensors
- Model correctly identifies AQI categories in most cases
- This is the most important metric for public health applications

---

## Comparison with Previous Single-Sensor Validation

**Previous validation (Sensor 17895, 200 samples):**
- 1h MAE: 1.22 μg/m³ (same)
- 3h MAE: 2.11 μg/m³ (same)

**Multi-sensor average:**
- 1h MAE: 1.92 μg/m³ (slightly higher due to sensor 71443)
- 3h MAE: 5.48 μg/m³ (higher due to sensor 71443)

**Excluding sensor 71443 (4 sensors):**
- 1h MAE: 1.49 μg/m³ (still good)
- 3h MAE: 2.62 μg/m³ (very good)

---

## Recommendations

1. **Model Performance:** Overall excellent across 4 of 5 sensors
2. **Sensor 71443:** Requires further investigation - may need sensor-specific handling
3. **Category Accuracy:** Very high across all sensors (86.5-99.5%) - model is reliable for AQI category predictions
4. **Bias:** Generally small and acceptable, except for sensor 71443's 3h forecast

---

## Files Generated

- `validation_historic_17895_200samples.csv`
- `validation_historic_18987_200samples.csv`
- `validation_historic_19683_200samples.csv`
- `validation_historic_193337_200samples.csv`
- `validation_historic_71443_200samples.csv`

Each file contains 200 rows with detailed validation results for that sensor.
