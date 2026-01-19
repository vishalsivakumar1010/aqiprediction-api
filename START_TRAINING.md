# Starting Training - Instructions

## Training Script: `train_with_checks.py`

The training script has been started, but I'm unable to see the terminal output here. Here's what's happening and how to monitor it:

## What the Training Script Does:

1. **Step 1**: Loads PurpleAir data (all 10 sensors, full 2025 dataset)
2. **Step 2**: Fetches historical wind direction from Meteostat (2025-01-01 to 2026-01-08)
3. **Step 3**: Merges wind direction with PurpleAir data
4. **Step 4**: Adds AQI calculations
5. **Step 5**: Engineers features (temporal, lagged, rolling, spatial, wind)
6. **Step 6**: Runs comprehensive checks:
   - Data leakage verification
   - Time-based split verification  
   - Wind direction merge verification
7. **Step 7**: Creates train/test split (train: 2025-01-01 to 2025-11-01, test: 2025-11-01 to 2026-01-08)
8. **Step 8**: Trains baseline persistence models
9. **Step 9**: Trains main XGBoost/HistGradientBoosting models
10. **Step 10**: Reports metrics vs baseline
11. **Step 11**: Saves all models to `models/` directory

## To Run Training Manually:

Open a terminal and run:

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
python3 train_with_checks.py
```

Or use the wrapper script:

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
./run_training.sh
```

## To Monitor Progress:

Check if training is running:
```bash
ps aux | grep train_with_checks
```

Check for output files:
```bash
ls -lht *.csv *.log models/ 2>/dev/null | head -20
```

Watch the log file (if created):
```bash
tail -f training_output_full.log
```

## Expected Output Files:

After training completes, you should see:
- `purpleair_complete_with_wind.csv` - Prepared dataset with wind direction
- `models/pm25_model_1h.pkl` - 1-hour forecast regression model
- `models/pm25_model_3h.pkl` - 3-hour forecast regression model
- `models/category_model_1h.pkl` - 1-hour forecast classification model
- `models/category_model_3h.pkl` - 3-hour forecast classification model
- `models/category_mapping_1h.pkl` - Category mapping for 1h
- `models/category_mapping_3h.pkl` - Category mapping for 3h
- `models/feature_columns_1h.pkl` - Feature list for 1h
- `models/feature_columns_3h.pkl` - Feature list for 3h

## Expected Training Time:

- Dataset preparation: 2-5 minutes
- Feature engineering: 5-10 minutes
- Model training: 5-15 minutes
- **Total: 15-30 minutes**

## Dependencies Required:

If you get import errors, install:
```bash
pip install meteostat scikit-learn pandas numpy scipy
```

For XGBoost (optional, will fallback to HistGradientBoosting if not available):
```bash
# On macOS, first install OpenMP:
brew install libomp

# Then install XGBoost:
pip install xgboost
```

## What to Expect:

The script will print:
1. Data loading progress
2. Wind direction fetching progress
3. Feature engineering progress
4. All verification checks (data leakage, time split, wind merge)
5. Training progress for baseline and main models
6. Final metrics comparing model vs baseline
7. Confusion matrices for category prediction

## Troubleshooting:

If training fails:
1. Check for missing dependencies: `pip install -r requirements.txt`
2. Check for meteostat API issues (might need internet connection)
3. Check disk space (dataset is ~163K rows)
4. Check Python version: `python3 --version` (should be 3.7+)

## Next Steps After Training:

Once training completes:
1. Review the metrics (MAE, RMSE, R², accuracy, F1)
2. Check the saved models in `models/` directory
3. Generate `predict.py` script (I'll create this after training completes)

---

**Training has been started! Check the terminal or log files for progress.**

