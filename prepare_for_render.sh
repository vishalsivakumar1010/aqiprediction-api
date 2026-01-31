#!/bin/bash
# Script to prepare the repository for Render deployment
# This ensures all necessary files are in place

set -e

echo "=========================================="
echo "Preparing for Render Deployment"
echo "=========================================="

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "1. Checking required files..."

# Check for API server
if [ ! -f "aqi_api_server.py" ]; then
    echo "❌ ERROR: aqi_api_server.py not found"
    exit 1
fi
echo "✓ aqi_api_server.py found"

# Check for test_predictions.py
if [ ! -f "test_predictions.py" ]; then
    echo "❌ ERROR: test_predictions.py not found"
    exit 1
fi
echo "✓ test_predictions.py found"

# Check for aqi_utils.py
if [ ! -f "aqi_utils.py" ]; then
    echo "⚠️  WARNING: aqi_utils.py not found in current directory"
    echo "   Checking original pipeline directory..."
    ORIGINAL_DIR="$HOME/Downloads/PAIC Data 2 Months"
    if [ -f "$ORIGINAL_DIR/aqi_utils.py" ]; then
        echo "   Copying aqi_utils.py from original pipeline..."
        cp "$ORIGINAL_DIR/aqi_utils.py" .
        echo "✓ aqi_utils.py copied"
    else
        echo "❌ ERROR: aqi_utils.py not found anywhere"
        exit 1
    fi
else
    echo "✓ aqi_utils.py found"
fi

# Check for feature_engineering.py
if [ ! -f "feature_engineering.py" ]; then
    echo "⚠️  WARNING: feature_engineering.py not found in current directory"
    echo "   Checking original pipeline directory..."
    ORIGINAL_DIR="$HOME/Downloads/PAIC Data 2 Months"
    if [ -f "$ORIGINAL_DIR/feature_engineering.py" ]; then
        echo "   Copying feature_engineering.py from original pipeline..."
        cp "$ORIGINAL_DIR/feature_engineering.py" .
        echo "✓ feature_engineering.py copied"
    else
        echo "❌ ERROR: feature_engineering.py not found anywhere"
        exit 1
    fi
else
    echo "✓ feature_engineering.py found"
fi

# Check for models directory
if [ ! -d "models" ]; then
    echo "❌ ERROR: models/ directory not found"
    exit 1
fi
echo "✓ models/ directory found"

# Check for required model files
REQUIRED_MODELS=(
    "models/pm25_model_1h.pkl"
    "models/pm25_model_3h.pkl"
    "models/category_model_1h.pkl"
    "models/category_model_3h.pkl"
    "models/category_mapping_1h.pkl"
    "models/category_mapping_3h.pkl"
    "models/feature_columns_1h.pkl"
    "models/feature_columns_3h.pkl"
)

echo ""
echo "2. Checking model files..."
for model in "${REQUIRED_MODELS[@]}"; do
    if [ ! -f "$model" ]; then
        echo "❌ ERROR: $model not found"
        exit 1
    fi
    echo "✓ $(basename $model) found"
done

# Check for sensor_locations
if [ ! -f "sensor_locations.pkl" ] && [ ! -f "sensor_locations.csv" ]; then
    echo "⚠️  WARNING: sensor_locations.pkl or .csv not found"
    echo "   Checking original pipeline directory..."
    ORIGINAL_DIR="$HOME/Downloads/PAIC Data 2 Months"
    if [ -f "$ORIGINAL_DIR/sensor_locations.pkl" ]; then
        echo "   Copying sensor_locations.pkl from original pipeline..."
        cp "$ORIGINAL_DIR/sensor_locations.pkl" .
        echo "✓ sensor_locations.pkl copied"
    elif [ -f "$ORIGINAL_DIR/sensor_locations.csv" ]; then
        echo "   Copying sensor_locations.csv from original pipeline..."
        cp "$ORIGINAL_DIR/sensor_locations.csv" .
        echo "✓ sensor_locations.csv copied"
    else
        echo "❌ ERROR: sensor_locations file not found anywhere"
        exit 1
    fi
else
    echo "✓ sensor_locations file found"
fi

# Check for requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo "⚠️  WARNING: requirements.txt not found"
    if [ -f "api_requirements.txt" ]; then
        echo "   Using api_requirements.txt as requirements.txt..."
        cp api_requirements.txt requirements.txt
        echo "✓ requirements.txt created from api_requirements.txt"
    else
        echo "❌ ERROR: No requirements file found"
        exit 1
    fi
else
    echo "✓ requirements.txt found"
fi

# Check for render.yaml
if [ ! -f "render.yaml" ]; then
    echo "⚠️  WARNING: render.yaml not found (optional but recommended)"
else
    echo "✓ render.yaml found"
fi

echo ""
echo "3. Verifying file sizes..."
MODEL_SIZE=$(du -sh models/ | cut -f1)
echo "   Models directory size: $MODEL_SIZE"

echo ""
echo "4. Checking for hardcoded paths in aqi_api_server.py..."
if grep -q "~/Downloads/PAIC Data 2 Months" aqi_api_server.py; then
    echo "⚠️  WARNING: Hardcoded path found in aqi_api_server.py"
    echo "   This may cause issues on Render. Consider updating to use relative paths."
    echo "   See RENDER_DEPLOYMENT.md for details."
else
    echo "✓ No hardcoded paths found"
fi

echo ""
echo "=========================================="
echo "Preparation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review and update aqi_api_server.py if needed (remove hardcoded paths)"
echo "2. Commit all files to Git:"
echo "   git add ."
echo "   git commit -m 'Prepare for Render deployment'"
echo "3. Push to GitHub:"
echo "   git push origin main"
echo "4. Follow RENDER_DEPLOYMENT.md for deployment instructions"
echo ""
