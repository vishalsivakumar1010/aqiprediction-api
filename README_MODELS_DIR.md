# Models Directory Location

## Answer: Where is the models directory?

**The models directory will be created at:**

```
/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models/
```

**Full absolute path:**
```
/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models/
```

**Relative to script:**
```
./models/
```

## Current Status:

❌ **The models directory does NOT exist yet** because training failed.

The directory will be automatically created by the training script when it runs successfully.

## What Will Be Saved There:

After successful training, these files will be saved in the `models/` directory:

### For 1-Hour Forecast:
- `pm25_model_1h.pkl` - Regression model
- `category_model_1h.pkl` - Classification model  
- `category_mapping_1h.pkl` - Category mappings
- `feature_columns_1h.pkl` - Feature list

### For 3-Hour Forecast:
- `pm25_model_3h.pkl` - Regression model
- `category_model_3h.pkl` - Classification model
- `category_mapping_3h.pkl` - Category mappings
- `feature_columns_3h.pkl` - Feature list

## To Check or Create:

You can create it manually now:
```bash
mkdir -p "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models"
```

Or it will be created automatically when you run:
```bash
python3 train_with_checks.py
```

