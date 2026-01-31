#!/bin/bash
# Phase 2 Pipeline - Run all steps sequentially

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Phase 2: P2-RouteFinder Pipeline"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"

# Step 1: Fetch sensor locations
echo "Step 1/6: Fetching sensor locations..."
python3 scripts/01_fetch_sensor_locations.py
echo ""

# Step 2: Ingest sensors
echo "Step 2/6: Ingesting sensor data..."
python3 scripts/02_ingest_sensors.py
echo ""

# Step 3: Quality control
echo "Step 3/6: Running quality control..."
python3 scripts/03_quality_control.py
echo ""

# Step 4: Merge weather data
echo "Step 4/6: Merging weather data..."
python3 scripts/04_merge_weather.py
echo ""

# Step 5: Feature engineering
echo "Step 5/6: Engineering features..."
python3 scripts/05_feature_engineering.py
echo ""

# Step 6: Train v2 model
echo "Step 6/6: Training v2 model..."
python3 scripts/06_train_model_v2.py
echo ""

echo "=========================================="
echo "Phase 2 Pipeline Complete!"
echo "=========================================="
echo ""
echo "Outputs:"
echo "  - QC reports: qc_reports/"
echo "  - Processed data: data/processed/"
echo "  - Trained models: models/v2/"
echo ""
