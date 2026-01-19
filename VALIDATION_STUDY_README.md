# Validation Study Guide

This guide explains how to run a validation study comparing forecasts with actual measurements.

## Overview

The validation study will:
1. Run forecasts for 10 addresses every hour for 12 hours
2. Store all predictions with timestamps
3. Later fetch actual measurements at the forecast times
4. Compare predictions vs actuals and generate a report

## Quick Start

### Option 1: Using the Validation Script (Recommended)

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

python3 validation_study.py \
  --addresses "addr1,addr2,addr3,addr4,addr5,addr6,addr7,addr8,addr9,addr10" \
  --api-key "C258449D-E52B-11F0-B596-4201AC1DC123" \
  --hours 12 \
  --interval 60
```

### Option 2: Using the Simplified Wrapper

```bash
python3 run_validation.py \
  --addresses "addr1,addr2,addr3,..." \
  --api-key "YOUR_API_KEY" \
  --hours 12
```

### Option 3: Manual Approach (Most Reliable)

Create a simple bash script that calls `test_predictions.py` for each address:

```bash
#!/bin/bash
API_KEY="C258449D-E52B-11F0-B596-4201AC1DC123"
ADDRESSES=("addr1" "addr2" "addr3" "addr4" "addr5" "addr6" "addr7" "addr8" "addr9" "addr10")
RESULTS_DIR="validation_results"
mkdir -p "$RESULTS_DIR"

for round in {1..12}; do
  echo "Round $round/12 - $(date)"
  for addr in "${ADDRESSES[@]}"; do
    timestamp=$(date +%Y%m%d_%H%M%S)
    python3 test_predictions.py \
      --address "$addr" \
      --api-key "$API_KEY" \
      > "$RESULTS_DIR/round${round}_${addr// /_}_${timestamp}.txt" 2>&1
  done
  if [ $round -lt 12 ]; then
    echo "Waiting 60 minutes..."
    sleep 3600
  fi
done
```

## Example Address List

Here's a sample list of 10 Fremont addresses you can use:

```
"40000 Paseo Padre Pkwy, Fremont, CA 94538"
"2523 Bishop Avenue, Fremont"
"4620 Mattos Drive, Fremont"
"39149 Fremont Blvd, Fremont, CA 94538"
"34700 Ardenwood Blvd, Fremont, CA 94555"
"39155 Cedar Blvd, Fremont, CA 94538"
"39990 Mission Blvd, Fremont, CA 94539"
"45550 Fremont Blvd, Fremont, CA 94538"
"37250 Fremont Blvd, Fremont, CA 94536"
"34200 Fremont Blvd, Fremont, CA 94555"
```

## Output Files

Results will be saved to `validation_results/` directory:

- `predictions_TIMESTAMP.csv` - All predictions with timestamps
- `actuals_comparison_TIMESTAMP.csv` - Actual measurements compared to predictions
- `summary_TIMESTAMP.json` - Study summary metadata
- `report_TIMESTAMP.txt` - Detailed comparison report

## What Gets Measured

For each address and each hour:
- **Current PM2.5**: Measured at forecast time
- **1h Forecast**: Predicted PM2.5 for 1 hour ahead
- **3h Forecast**: Predicted PM2.5 for 3 hours ahead

Later (after forecast times pass):
- **Actual 1h**: Measured PM2.5 1 hour after forecast
- **Actual 3h**: Measured PM2.5 3 hours after forecast
- **Error**: Difference between forecast and actual

## Metrics Calculated

The report will include:
- Mean Absolute Error (MAE) for PM2.5 and AQI
- Root Mean Squared Error (RMSE)
- Error statistics by forecast horizon (1h vs 3h)
- Error statistics by address
- Comparison tables

## Tips

1. **Start during normal hours**: Better to start when sensors are actively reporting
2. **Monitor progress**: The script will save results incrementally, so you can stop and resume
3. **Check API limits**: PurpleAir API has rate limits - 10 addresses × 12 hours = 120 API calls, should be fine
4. **Allow time for comparison**: After 12 hours, wait an additional 3 hours for 3h forecasts to complete, then run comparison

## Troubleshooting

- **Import errors**: Make sure you're running from the correct directory
- **API errors**: Check your API key and network connection
- **Missing sensors**: Some addresses might not have nearby sensors - check the output
- **Time zone issues**: All timestamps are in UTC, convert to local time for readability

## Next Steps After Validation

1. Analyze the error patterns
2. Check if certain addresses or times have higher errors
3. Compare 1h vs 3h forecast accuracy
4. Use insights to improve the model if needed
