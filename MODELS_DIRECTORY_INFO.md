# Models Directory Location

## Where Models Will Be Saved:

**Directory Path:**
```
/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models/
```

**Relative Path (from script directory):**
```
./models/
```

## Current Status:

❌ **The models directory does NOT exist yet** because training failed due to XGBoost/OpenMP issue.

The directory will be automatically created when training runs successfully.

## What Will Be Saved There:

After successful training, the `models/` directory will contain:

### 1-Hour Forecast Models:
- `pm25_model_1h.pkl` - Regression model for PM2.5 prediction (1 hour ahead)
- `category_model_1h.pkl` - Classification model for AQI category (1 hour ahead)
- `category_mapping_1h.pkl` - Category mapping (num_to_cat, cat_to_num)
- `feature_columns_1h.pkl` - List of feature columns used

### 3-Hour Forecast Models:
- `pm25_model_3h.pkl` - Regression model for PM2.5 prediction (3 hours ahead)
- `category_model_3h.pkl` - Classification model for AQI category (3 hours ahead)
- `category_mapping_3h.pkl` - Category mapping (num_to_cat, cat_to_num)
- `feature_columns_3h.pkl` - List of feature columns used

## To Create Directory Now:

You can create it manually:
```bash
mkdir -p "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models"
```

Or the training script will create it automatically when it runs.

## Next Steps:

1. The XGBoost issue has been fixed - script will use HistGradientBoosting as fallback
2. Run training again: `python3 train_with_checks.py`
3. Models will be saved to the directory above once training completes

