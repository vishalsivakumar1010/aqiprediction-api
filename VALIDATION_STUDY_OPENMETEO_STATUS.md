# 12-Hour Validation Study with New Models (Open-Meteo)

## ✅ Study Started!

**Start Time**: Running now
**Duration**: 12 hours
**Interval**: 60 minutes (hourly measurements)
**Addresses**: 10 validation addresses
**Models**: New models trained with Open-Meteo data (100% wind coverage)

## Study Configuration

- **Addresses**: 10 addresses from validation_addresses_10.txt
- **API Key**: PurpleAir API (for current live data)
- **Hours**: 12 hours
- **Interval**: 60 minutes (hourly forecasts)
- **Rounds**: 12 rounds (one per hour)

## What the Study Does

1. **Hourly Forecasts**: Every hour, makes 1h and 3h forecasts for all 10 addresses
2. **Current Measurements**: Captures current PM2.5, AQI, and category from PurpleAir sensors
3. **Forecasts**: Generates 1h and 3h ahead predictions using new models
4. **Comparison**: After each forecast period (1h and 3h), fetches actual measurements to compare

## Expected Output Files

After completion, you'll have:
- `validation_results/predictions_YYYYMMDD_HHMMSS.csv` - All predictions
- `validation_results/actuals_YYYYMMDD_HHMMSS.csv` - Actual measurements
- `validation_results/summary_YYYYMMDD_HHMMSS.json` - Summary statistics
- `validation_study_openmeteo_YYYYMMDD_HHMMSS.log` - Full log file

## Monitor Progress

To check progress while it's running:

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

# Check if still running
ps aux | grep validation_study.py | grep -v grep

# View latest log
tail -f validation_study_openmeteo_*.log

# Check latest results
ls -lht validation_results/*.csv | head -5
```

## Expected Completion Time

- **Start**: Now
- **End**: ~12 hours from start
- **Total Rounds**: 12 (one per hour)

## Models Used

- **Training Data**: Open-Meteo CSV (1 year, 100% wind coverage)
- **Wind Coverage**: 100% (vs. potentially incomplete Meteostat)
- **Features**: 100 features (temporal, lagged, rolling, wind, spatial)

## Next Steps After Completion

1. **Analyze Results**: Compare forecasts vs actuals
2. **Calculate Metrics**: MAE, RMSE, R² for both 1h and 3h forecasts
3. **Compare with Previous**: Compare accuracy with previous validation study (Meteostat models)
4. **Assess Improvement**: Check if Open-Meteo training data improved predictions
