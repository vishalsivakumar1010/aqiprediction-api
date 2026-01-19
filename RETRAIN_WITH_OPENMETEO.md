# Retrain Models with Open-Meteo Wind Data

## Why Retrain with Open-Meteo?

Your validation study shows that predictions aren't matching actual values well:
- **1h forecasts**: Often higher than current AQI
- **3h forecasts**: Even higher, sometimes double
- **Pattern**: Model seems to over-predict

### Why Open-Meteo Could Help:

1. **Better Data Quality**: 100% coverage (no missing data)
2. **More Consistent**: Grid-based data, not station-dependent
3. **Better for Fremont**: Direct coverage for the area
4. **Same Format**: Wind direction 0-360° (compatible with existing models)

## Current Issues

From validation results:
- Predictions consistently higher than actuals
- 3h forecasts particularly off
- Suggests model may not be learning wind patterns correctly
- Or Meteostat data quality issues affecting training

## Retraining Plan

### Step 1: Update Data Preparation

Modify `prepare_full_dataset.py` to:
1. Load PurpleAir sensor data (same as before)
2. **Load Open-Meteo CSV** instead of fetching from Meteostat
3. Merge wind data (same logic)
4. Create complete dataset with wind features

### Step 2: Retrain Models

Run training with the new dataset:
1. Feature engineering (same as before)
2. Train XGBoost models
3. Evaluate on test set
4. Compare with previous model

### Step 3: Validate New Models

Test with validation study:
1. Use new models for predictions
2. Compare with actual measurements
3. Check if accuracy improved

## Implementation

I've created:
- ✅ `load_wind_openmeteo_csv.py` - Functions to load Open-Meteo CSV
- ✅ Tested and verified - CSV loads correctly!

## Next Steps

1. **Update `prepare_full_dataset.py`** to use Open-Meteo CSV
2. **Run data preparation** with Open-Meteo data
3. **Retrain models** with new dataset
4. **Test predictions** and compare accuracy

## Expected Improvements

- **Better Coverage**: 100% wind data coverage
- **More Accurate**: Consistent, high-quality wind data
- **Better Predictions**: Models trained on better data should perform better
- **Reduced Over-Prediction**: More accurate wind features may reduce forecast errors

## Recommendation

**Yes, retrain with Open-Meteo!** It's likely to improve accuracy because:
1. Better data quality (100% coverage)
2. More consistent source
3. Direct Fremont coverage
4. Validation shows current model needs improvement

The CSV you downloaded has a full year of data (2025-01-01 to 2026-01-08), which is perfect for retraining.
