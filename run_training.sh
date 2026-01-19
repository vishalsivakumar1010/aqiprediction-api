#!/bin/bash
# Wrapper script to run training with explicit output

cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

echo "========================================"
echo "Starting AQI Model Training"
echo "========================================"
echo "Date: $(date)"
echo ""

# Install dependencies if needed
echo "Checking dependencies..."
python3 -m pip install -q meteostat scikit-learn pandas numpy scipy 2>&1 | grep -E "(Successfully|Requirement|ERROR)" || echo "Dependencies OK"

echo ""
echo "Running training script..."
echo ""

# Run training script with output to file
python3 train_with_checks.py 2>&1 | tee training_output_full.log

echo ""
echo "========================================"
echo "Training completed!"
echo "========================================"
echo "Check training_output_full.log for details"

