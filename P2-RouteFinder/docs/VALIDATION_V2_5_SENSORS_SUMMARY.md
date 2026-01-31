# Phase 2 v2 Model - Historical Validation Summary

## Overview

Validated v2 model predictions using historical data from 5 different sensors, with 200 samples each (total: 1,000 validation samples).

**Sensors tested:**
1. 17895 (Glenmoor)
2. 18987 (Fremont: Cabrillo)
3. 19683 (Glenmoor Gardens)
4. 193337 (Glen Moore-York Dr.)
5. 71443 (MoonRiver)

**Date range:** June 1, 2025 to December 31, 2025  
**Samples per sensor:** 200 timestamps (evenly distributed)  
**Total samples:** 1,000 validation points

---

## Results by Sensor

### Sensor 17895 (Glenmoor)
**1-Hour Forecast:**
- PM2.5 MAE: 2.71 μg/m³
- PM2.5 RMSE: 4.46 μg/m³
- PM2.5 Bias: +2.02 μg/m³ (slight over-prediction)
- AQI MAE: 8.80 AQI
- Category Accuracy: 87.0%

**3-Hour Forecast:**
- PM2.5 MAE: 2.98 μg/m³
- PM2.5 RMSE: 4.77 μg/m³
- PM2.5 Bias: +1.72 μg/m³ (slight over-prediction)
- AQI MAE: 10.06 AQI
- Category Accuracy: 89.5%

**Assessment:** Excellent performance, very low error and bias.

---

### Sensor 18987 (Fremont: Cabrillo)
**1-Hour Forecast:**
- PM2.5 MAE: 2.47 μg/m³ ⭐ (best 1h MAE)
- PM2.5 RMSE: 3.84 μg/m³
- PM2.5 Bias: +1.88 μg/m³ (slight over-prediction)
- AQI MAE: 8.24 AQI
- Category Accuracy: 82.0%

**3-Hour Forecast:**
- PM2.5 MAE: 2.63 μg/m³ ⭐ (best 3h MAE)
- PM2.5 RMSE: 4.37 μg/m³
- PM2.5 Bias: +1.05 μg/m³ (slight over-prediction)
- AQI MAE: 8.88 AQI
- Category Accuracy: 90.5%

**Assessment:** Best overall performance - lowest MAE for both horizons.

---

### Sensor 19683 (Glenmoor Gardens)
**1-Hour Forecast:**
- PM2.5 MAE: 3.28 μg/m³
- PM2.5 RMSE: 4.85 μg/m³
- PM2.5 Bias: +1.91 μg/m³ (slight over-prediction)
- AQI MAE: 10.86 AQI
- Category Accuracy: 80.0%

**3-Hour Forecast:**
- PM2.5 MAE: 4.55 μg/m³
- PM2.5 RMSE: 7.60 μg/m³
- PM2.5 Bias: +1.85 μg/m³ (slight over-prediction)
- AQI MAE: 14.26 AQI
- Category Accuracy: 77.5%

**Assessment:** Good performance, but lower category accuracy than others.

---

### Sensor 193337 (Glen Moore-York Dr.)
**1-Hour Forecast:**
- PM2.5 MAE: 2.55 μg/m³
- PM2.5 RMSE: 4.10 μg/m³
- PM2.5 Bias: +2.06 μg/m³ (slight over-prediction)
- AQI MAE: 8.93 AQI
- Category Accuracy: 87.5%

**3-Hour Forecast:**
- PM2.5 MAE: 2.50 μg/m³
- PM2.5 RMSE: 3.81 μg/m³
- PM2.5 Bias: +1.71 μg/m³ (slight over-prediction)
- AQI MAE: 8.91 AQI
- Category Accuracy: 91.5%

**Assessment:** Excellent performance, very consistent across horizons.

---

### Sensor 71443 (MoonRiver)
**1-Hour Forecast:**
- PM2.5 MAE: 16.13 μg/m³ ⚠️ (outlier)
- PM2.5 RMSE: 22.88 μg/m³
- PM2.5 Bias: +15.34 μg/m³ (significant over-prediction)
- AQI MAE: 12.21 AQI
- Category Accuracy: 68.5%

**3-Hour Forecast:**
- PM2.5 MAE: 6.24 μg/m³
- PM2.5 RMSE: 9.28 μg/m³
- PM2.5 Bias: -1.80 μg/m³ (slight under-prediction)
- AQI MAE: 5.53 AQI
- Category Accuracy: 97.5% ⭐ (best category accuracy)

**Assessment:** Unusual pattern - poor 1h performance but excellent 3h performance. May indicate sensor-specific data quality issues or model behavior.

---

## Overall Average (across 5 sensors)

### 1-Hour Forecast
- **PM2.5 MAE:** 5.43 μg/m³
- **PM2.5 RMSE:** 8.02 μg/m³
- **PM2.5 Bias:** +4.64 μg/m³ (over-prediction)
- **AQI MAE:** 9.81 AQI
- **Category Accuracy:** 81.0%

### 3-Hour Forecast
- **PM2.5 MAE:** 3.78 μg/m³ ⭐ (better than 1h)
- **PM2.5 RMSE:** 5.96 μg/m³
- **PM2.5 Bias:** +0.90 μg/m³ (nearly unbiased)
- **AQI MAE:** 9.53 AQI
- **Category Accuracy:** 89.3% ⭐ (better than 1h)

---

## Key Findings

1. **3-hour forecast performs better than 1-hour** on average (lower MAE, higher category accuracy)
2. **Sensor 71443 shows unusual behavior** - very high 1h error but excellent 3h performance
3. **Overall bias is small** for 3h forecast (+0.90 μg/m³), but higher for 1h (+4.64 μg/m³)
4. **Category accuracy is strong** (81.0% for 1h, 89.3% for 3h)
5. **Best performing sensors:** 18987 and 193337 show consistently low error across both horizons

---

## Comparison with v1 Model

(To be added after v1 comparison analysis)

---

## Notes

- Validation uses historical data from June-December 2025
- All predictions use Open-Meteo weather data (standardized across sensors)
- Feature engineering uses Phase 2 pipeline (QC'd data, Open-Meteo weather)
- Results saved to: `validation_results/validation_v2_*_200samples.csv`

---

## Next Steps

1. Investigate sensor 71443 1h forecast performance
2. Compare with v1 model on same test set
3. Compute threshold-based metrics (AQI ≥ 50 recall, missed-warning rate)
4. Analyze bias patterns across sensors
