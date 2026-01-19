#!/bin/bash

# Overnight Validation Study Script
# Runs AQI forecasts for 10 addresses every hour for 12 hours

# Define the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Configuration
ADDRESS_FILE="validation_addresses_10.txt"
API_KEY="C258449D-E52B-11F0-B596-4201AC1DC123"
HOURS=12
INTERVAL=60  # minutes (hourly)

# Create results directory if it doesn't exist
mkdir -p validation_results

# Generate a timestamp for the log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="validation_results/overnight_validation_${TIMESTAMP}.log"
PID_FILE="validation_results/overnight_validation.pid"

echo "==================================================================="
echo "STARTING OVERNIGHT VALIDATION STUDY"
echo "==================================================================="
echo "Started at: $(date)"
echo "Log file: $LOG_FILE"
echo "PID file: $PID_FILE"
echo "Address file: $ADDRESS_FILE"
echo "API Key: $API_KEY"
echo "Duration: $HOURS hours"
echo "Interval: $INTERVAL minutes (hourly)"
echo "Ensemble: 60% ML + 40% persistence"
echo "==================================================================="
echo ""

# Run the Python script in the background using nohup
# nohup prevents the process from being terminated when the shell exits
nohup python3 validation_study.py \
  --address-file "$ADDRESS_FILE" \
  --api-key "$API_KEY" \
  --hours "$HOURS" \
  --interval "$INTERVAL" \
  > "$LOG_FILE" 2>&1 &

# Save the Process ID (PID) to a file
echo $! > "$PID_FILE"

echo "✓ Validation study started with PID: $(cat "$PID_FILE")"
echo ""
echo "To monitor progress:"
echo "  tail -f $LOG_FILE"
echo ""
echo "To check status:"
echo "  ps -p $(cat "$PID_FILE")"
echo ""
echo "To stop the study:"
echo "  kill $(cat "$PID_FILE")"
echo ""
echo "Results will be saved to: validation_results/"
echo "  - predictions_*.csv: All forecast predictions"
echo "  - summary_*.json: Final summary statistics"
echo ""
echo "==================================================================="
