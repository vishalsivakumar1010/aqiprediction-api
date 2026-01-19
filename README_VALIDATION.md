# Validation Study - Ready to Run

## ✅ Test Results

**All 10 addresses tested and working!**

The addresses work perfectly when business names are removed. The geocoding service works better with just the street addresses.

## 📋 Addresses for Validation Study

Use these cleaned addresses (comma-separated):

```
2523 Bishop Ave, Fremont, CA 94536,39400 Paseo Padre Pkwy, Fremont, CA 94538,4620 Mattos Dr, Fremont, CA 94536,5400 Mowry Ave, Fremont, CA 94538,36007 Pizarro Dr, Fremont, CA 94536,3377 Alder Ave, Fremont, CA 94536,34665 Allegheny Ct, Fremont, CA 94555,1251 Peralta Blvd, Fremont, CA 94536,40500 Paseo Padre Pkwy, Fremont, CA 94538,41800 Blacow Rd, Fremont, CA 94538
```

## 🚀 Ready to Run Validation Study

### Option 1: Using validation_study.py (Recommended)

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

python3 validation_study.py \
  --addresses "2523 Bishop Ave, Fremont, CA 94536,39400 Paseo Padre Pkwy, Fremont, CA 94538,4620 Mattos Dr, Fremont, CA 94536,5400 Mowry Ave, Fremont, CA 94538,36007 Pizarro Dr, Fremont, CA 94536,3377 Alder Ave, Fremont, CA 94536,34665 Allegheny Ct, Fremont, CA 94555,1251 Peralta Blvd, Fremont, CA 94536,40500 Paseo Padre Pkwy, Fremont, CA 94538,41800 Blacow Rd, Fremont, CA 94538" \
  --api-key "C258449D-E52B-11F0-B596-4201AC1DC123" \
  --hours 12 \
  --interval 60
```

### Option 2: One-time quick test (all addresses)

```bash
python3 test_cleaned_addresses.py
```

## 📊 What to Expect

- **Frequency**: Forecasts every 60 minutes for 12 hours
- **Total forecasts**: 10 addresses × 12 hours = 120 forecast sets
- **Each forecast includes**:
  - Current PM2.5 and AQI
  - 1-hour forecast (PM2.5, AQI, category)
  - 3-hour forecast (PM2.5, AQI, category)

## 📁 Output Files

Results will be saved to `validation_results/`:
- `predictions_TIMESTAMP.csv` - All forecasts
- `actuals_comparison_TIMESTAMP.csv` - Forecast vs actual (after times pass)
- `summary_TIMESTAMP.json` - Study metadata
- `report_TIMESTAMP.txt` - Error analysis

## ⏱️ Timeline

- **Start**: When you run the script
- **Forecasts complete**: After 12 hours
- **1h actuals available**: After 13 hours (1h after last forecast)
- **3h actuals available**: After 15 hours (3h after last forecast)
- **Report generated**: After fetching actuals

## 🎯 Success Criteria

All 10 addresses have been tested and are working:
1. ✓ Geocoding successful
2. ✓ Nearest sensors found
3. ✓ Predictions generated
4. ✓ All within reasonable distance from sensors

## 📝 Notes

- Business names are removed for geocoding (addresses work better)
- All sensors are within reasonable distance (< 5 km typically)
- The script will save results incrementally (safe to stop/resume)
- API rate limits should be fine (120 calls over 12 hours = ~10/hour)
