# AQI Prediction Model - Testing Guide

## Quick Start

The `test_predictions.py` script allows you to test the trained models and verify they can predict AQI for given sensor locations.

### Basic Usage

**NEW: Predict by Address (Recommended)**

```bash
# Test with an address in Fremont - automatically finds nearest sensor
python3 test_predictions.py --address "Lake Elizabeth Park, Fremont, CA" --use-csv
python3 test_predictions.py --address "Fremont City Hall" --use-csv
python3 test_predictions.py --address "Glenmoor Gardens" --use-csv
python3 test_predictions.py --address "Civic Center" --use-csv
```

**Test by Sensor ID**

```bash
# Test a single sensor using CSV data
python3 test_predictions.py --sensor-id 17895 --use-csv

# Test multiple sensors
python3 test_predictions.py --sensor-id 17895 18987 19683 --use-csv

# Test with custom model/data directories
python3 test_predictions.py --sensor-id 17895 \
    --model-dir models \
    --data-dir "/path/to/data" \
    --use-csv
```

### Example Output (Address Input)

```
======================================================================
AQI PREDICTION MODEL TEST
======================================================================

Geocoding address: 'Lake Elizabeth Park'
  ✓ Found in known locations: (37.54408, -121.96445)
✓ Address coordinates: (37.544080, -121.964450)

Finding nearest sensor to your location...

✓ Nearest Sensor Found:
  Sensor ID: 84117
  Name: Lake Elizabeth
  Distance: 0.00 km from your location
  Coordinates: (37.544080, -121.964450)

  Nearby sensors (for reference):
    1. Lake Elizabeth (ID: 84117) - 0.00 km
    2. Fremont - Civic Center (ID: 148483) - 1.34 km
    3. MoonRiver (ID: 71443) - 3.06 km

Loading models...
✓ Models loaded successfully
  - 1h forecast model: 108 features
  - 3h forecast model: 108 features

======================================================================
Testing Sensor ID: 84117
======================================================================
Current Conditions (from data):
  PM2.5: 5.10 μg/m³
  AQI: 21 (Good)
  Temperature: 57.0°F
  Humidity: 65.0%

======================================================================
PREDICTION RESULTS
======================================================================

1H Forecast:
  Predicted PM2.5: 5.03 μg/m³
  Predicted AQI: 21 (Good)

3H Forecast:
  Predicted PM2.5: 4.05 μg/m³
  Predicted AQI: 17 (Good)
```

## What the Script Does

1. **Loads Trained Models**: Loads both 1-hour and 3-hour forecast models from the `models/` directory
2. **Loads Sensor Data**: Reads the most recent 48 rows (24 hours) of historical data from CSV files
3. **Engineers Features**: Creates the same 108 features used during training:
   - Temporal features (hour, day, month with cyclical encoding)
   - Lagged features (PM2.5, humidity, temp from 30min, 1h, 3h, 24h ago)
   - Rolling statistics (mean, std, min, max over various windows)
   - Spatial features (latitude, longitude, distance, nearby sensors)
4. **Makes Predictions**: Uses the models to predict PM2.5 and AQI category 1h and 3h ahead
5. **Displays Results**: Shows current conditions and predictions

## Address Input Feature

**Supported Address Formats:**
- Known Fremont locations (pre-configured, fast):
  - "Lake Elizabeth Park" or "Lake Elizabeth"
  - "Fremont City Hall" or "City Hall"
  - "Glenmoor Gardens" or "Glenmoor"
  - "Civic Center" or "Fremont Civic Center"
  - "Northgate" or "Fremont Northgate"
- Any address in Fremont, CA (will attempt online geocoding)

**How It Works:**
1. Enter an address in Fremont
2. Script geocodes the address to get coordinates
3. Finds the nearest PurpleAir sensor automatically
4. Uses that sensor's data to make predictions
5. Shows the distance to the sensor and nearby alternatives

## Available Sensors

The following sensors are available in the dataset:

| Sensor ID | Name | Location |
|-----------|------|----------|
| 17895 | Glenmoor | (37.5381, -122.0138) |
| 18987 | Fremont: Cabrillo | (37.5625, -122.0281) |
| 19683 | Glenmoor Gardens | (37.5421, -122.0004) |
| 56275 | Fremont (Northgate) | (37.5851, -122.0413) |
| 71443 | MoonRiver | (37.5612, -121.9915) |
| 84117 | Lake Elizabeth | (37.5441, -121.9645) |
| 114889 | Washburn court | (37.5768, -121.9879) |
| 148483 | Fremont - Civic Center | (37.5534, -121.9742) |
| 193337 | Glen Moore-York Dr. | (37.5338, -122.0048) |
| 286506 | 405 L Street | (37.5726, -121.9764) |

## Expected Warnings

You may see warnings about missing features:
```
⚠ Warning: 5 features missing from data:
  ['wind_dir_y', 'wdir', 'wind_dir_x', 'pm25_nearby_sensors_std', 'pm25_nearby_sensors_avg']
```

This is **expected and normal** because:
- Wind direction features are missing (Meteostat didn't return data during training)
- Nearby sensor features may be missing if spatial interaction couldn't be calculated
- The models handle missing features by filling them with 0, which is acceptable

## Testing with API (Future)

For real-time predictions using the Purple Air API, you'll need an API key:

```bash
python3 test_predictions.py --sensor-id 17895 --api-key YOUR_API_KEY
```

**Note**: API-based testing requires network connectivity and a valid Purple Air API key.

## Troubleshooting

### Models Not Found
```
FileNotFoundError: Model file not found: models/pm25_model_1h.pkl
```
**Solution**: Make sure you've run the training script and models are in the `models/` directory.

### CSV File Not Found
```
FileNotFoundError: No CSV file found for sensor 17895
```
**Solution**: Ensure the sensor CSV files are in the data directory. They should be named like:
`17895 2025-01-01 2026-01-08 30-Minute Average.csv`

### Feature Engineering Errors
```
Error: Required column pm2_5_atm not found
```
**Solution**: Check that CSV files have the correct columns: `time_stamp`, `humidity`, `temperature`, `pm2.5_atm`

## Model Performance

Based on training results:

**1-Hour Forecast:**
- R²: 0.7572
- Category Accuracy: 92.89%
- RMSE: 18.54 μg/m³

**3-Hour Forecast:**
- R²: 0.6845
- Category Accuracy: 83.17%
- RMSE: 21.14 μg/m³

## Next Steps

Once testing is successful, you can:
1. Integrate the prediction functions into your application
2. Set up scheduled predictions
3. Create a dashboard or API endpoint for predictions
4. Monitor prediction accuracy over time

## Questions?

If you encounter issues, check:
- Model files exist in `models/` directory
- CSV data files are present and readable
- Required Python packages are installed
- Sensor IDs are valid
