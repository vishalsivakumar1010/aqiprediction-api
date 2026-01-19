# Lovable Integration Update Guide

## Overview

After retraining the models with the rolling mean fix and implementing the ensemble approach, you need to update the Lovable integration. The good news is that **very little needs to change** - the API endpoints remain the same, and the model files just need to be copied to the API server directory.

---

## What Changed in the New Model

1. **Rolling Mean Fix**: Rolling features now use strictly past-only values (no data leakage)
2. **Ensemble Approach**: Predictions now use 60% ML + 40% persistence baseline
3. **Retrained Models**: All model files have been retrained with corrected features

**Model Files (All Updated):**
- `pm25_model_1h.pkl` - 1-hour PM2.5 regression model
- `pm25_model_3h.pkl` - 3-hour PM2.5 regression model
- `category_model_1h.pkl` - 1-hour AQI category classification model
- `category_model_3h.pkl` - 3-hour AQI category classification model
- `category_mapping_1h.pkl` - Category mappings
- `category_mapping_3h.pkl` - Category mappings
- `feature_columns_1h.pkl` - Feature column list (100 features)
- `feature_columns_3h.pkl` - Feature column list (100 features)

---

## Steps to Update Lovable Integration

### Step 1: Copy New Model Files to API Directory

The API server loads models from `~/Documents/aqi_api/models/`. Copy the newly trained models:

```bash
# Navigate to the model directory
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

# Copy all model files to the API directory
cp models/*.pkl ~/Documents/aqi_api/models/
```

**Verify the copy:**
```bash
ls -lh ~/Documents/aqi_api/models/*.pkl
```

You should see 8 files with recent timestamps (from when the models were retrained).

---

### Step 2: Update API Server Code ✅ (ALREADY DONE)

**The API server code has been updated** to use the ensemble approach!

The API server (`aqi_api_server.py`) now calls `make_predictions()` with the `current_pm25` parameter:

```python
predictions = make_predictions(
    models, 
    feature_row, 
    feature_columns,
    current_pm25=current_pm25,  # This enables ensemble
    ensemble_weight=0.6  # 60% ML + 40% persistence
)
```

**No code changes needed** - the API server is already configured to use the ensemble approach.

---

### Step 3: Restart the API Server

After copying the new model files:

1. **Stop the current API server** (if running):
   ```bash
   # Find the process
   ps aux | grep aqi_api_server
   
   # Kill it (replace PID with actual process ID)
   kill <PID>
   ```

2. **Start the API server**:
   ```bash
   cd ~/Documents/aqi_api
   ./start_api.sh
   # Or:
   python3 aqi_api_server.py
   ```

3. **Verify it's running**:
   ```bash
   curl http://localhost:8000/health
   ```

---

### Step 4: Test the API

Test that the new models are working:

```bash
# Test with an address
curl -X GET "http://localhost:8000/predict/address?address=2523%20Bishop%20Ave,%20Fremont,%20CA%2094536&api_key=YOUR_API_KEY"

# Or test with coordinates
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.5483,
    "longitude": -121.9886,
    "api_key": "YOUR_API_KEY"
  }'
```

**Expected Response:**
- Predictions should be slightly different from the old model (due to rolling mean fix and ensemble)
- Response format should be identical (no API changes)

---

## What Doesn't Need to Change

✅ **API Endpoints**: All endpoints remain the same (`/health`, `/predict/address`, `/predict`)  
✅ **Request/Response Format**: JSON structure is identical  
✅ **Lovable UI Code**: No changes needed to the frontend  
✅ **API Parameters**: All parameters remain the same  

---

## Verification Checklist

- [ ] Copied all 8 `.pkl` files from `models/` to `~/Documents/aqi_api/models/`
- [ ] Verified file sizes match (models should be ~0.68-3.42 MB each)
- [ ] Verified API server code uses `make_predictions()` with `current_pm25` parameter
- [ ] Restarted API server
- [ ] Tested `/health` endpoint
- [ ] Tested `/predict/address` endpoint with a known address
- [ ] Verified predictions are generated correctly
- [ ] Confirmed Lovable UI can connect and get predictions

---

## Troubleshooting

### Issue: API Server Can't Load Models

**Error**: `FileNotFoundError: models/pm25_model_1h.pkl`

**Solution**: 
- Check that files were copied to `~/Documents/aqi_api/models/`
- Verify file permissions: `chmod 644 ~/Documents/aqi_api/models/*.pkl`

### Issue: Predictions Seem Wrong

**Solution**:
- Verify the API server is using the latest `test_predictions.py` code
- Check that `make_predictions()` is called with `current_pm25` parameter
- Ensure the API server is loading models from the correct directory

### Issue: Import Errors

**Error**: `ModuleNotFoundError: cannot import name 'make_predictions'`

**Solution**:
- Ensure `test_predictions.py` is in the correct location
- Check that the API server's import paths are correct
- The API server should import from the original pipeline directory

---

## Summary

**Quick Update Steps:**
1. Copy model files: `cp models/*.pkl ~/Documents/aqi_api/models/`
2. Verify API server code uses ensemble (check `make_predictions()` call)
3. Restart API server
4. Test endpoints

**That's it!** The API interface hasn't changed, so Lovable should continue working seamlessly with the improved models.

---

## Model File Locations

**Source (New Models):**
```
/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models/
```

**Destination (API Server):**
```
~/Documents/aqi_api/models/
```

**Model Files to Copy:**
- `pm25_model_1h.pkl`
- `pm25_model_3h.pkl`
- `category_model_1h.pkl`
- `category_model_3h.pkl`
- `category_mapping_1h.pkl`
- `category_mapping_3h.pkl`
- `feature_columns_1h.pkl`
- `feature_columns_3h.pkl`
