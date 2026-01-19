# Training Script Summary

## Script: `train_with_checks.py`

This comprehensive training script implements all requirements:

### ✅ Checks Before Training:

1. **Data Leakage Verification**:
   - Verifies lag/rolling features use only past rows within each sensor_id group
   - Confirms targets are shifted forward (+2 steps for 1h, +6 steps for 3h)
   - Checks that targets don't leak into features

2. **Time-Based Split Verification**:
   - Prints train start/end dates: 2025-01-01 to 2025-11-01
   - Prints test start/end dates: 2025-11-01 to 2026-01-08
   - Verifies no shuffle (temporal order preserved)
   - Confirms no overlap between train and test

3. **Wind Direction Merge Verification**:
   - Prints % missing wdir values
   - Confirms forward-fill worked (30-min rows inherit hourly values)
   - Verifies wind_dir_x and wind_dir_y components are correct

### ✅ Models Trained:

1. **Baseline Persistence Models**:
   - Value baseline: Uses current PM2.5 as prediction (no model)
   - Category baseline: Predicts current category for future
   - Provides baseline metrics for comparison

2. **Main Models** (XGBoost or HistGradientBoosting fallback):
   - **AQI Regression** (1h, 3h): Predicts PM2.5 → Converts to AQI
   - **AQI Category Classification** (1h, 3h): Directly predicts category

### ✅ Metrics Reported:

**Regression Metrics** (vs baseline):
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- R² score
- Improvement % over baseline

**Classification Metrics** (vs baseline):
- Accuracy
- Macro F1 score
- Confusion matrix
- Improvement % over baseline

### ✅ Models Saved:

- `pm25_model_1h.pkl` - Regression model for 1-hour forecast
- `pm25_model_3h.pkl` - Regression model for 3-hour forecast
- `category_model_1h.pkl` - Classification model for 1-hour forecast
- `category_model_3h.pkl` - Classification model for 3-hour forecast
- `category_mapping_1h.pkl` - Category mapping for 1h
- `category_mapping_3h.pkl` - Category mapping for 3h
- `feature_columns_1h.pkl` - Feature list for 1h
- `feature_columns_3h.pkl` - Feature list for 3h

### ✅ Next Steps After Training:

1. Generate `predict.py` script that:
   - Loads saved models
   - Loads feature list
   - Prepares features from latest window
   - Predicts +1h and +3h AQI and category

---

## Ready to Start Training!

Run:
```bash
python3 train_with_checks.py
```

This will:
1. Load full 2025 dataset (10 sensors)
2. Fetch historical wind direction from Meteostat
3. Merge wind direction with PurpleAir data
4. Engineer all features
5. Run comprehensive checks
6. Train baseline and main models
7. Report metrics vs baseline
8. Save models to disk

Estimated time: 15-30 minutes (depending on dataset size and system)

