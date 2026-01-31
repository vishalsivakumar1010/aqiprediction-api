#!/bin/bash
# Run historical validation for v2 model on 5 sensors (same as v1 validation)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/validation_results"

mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Phase 2: Historical Validation (5 Sensors)"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"

# Sensors used in v1 validation
SENSORS=(17895 18987 19683 193337 71443)
START_DATE="2025-06-01"
END_DATE="2025-12-31"
NUM_TESTS=200

for sensor_id in "${SENSORS[@]}"; do
    echo "=========================================="
    echo "Validating sensor $sensor_id..."
    echo "=========================================="
    
    python3 scripts/07_validate_historic_v2.py \
        --sensor-id "$sensor_id" \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --num-tests "$NUM_TESTS" \
        --output "$OUTPUT_DIR/validation_v2_${sensor_id}_200samples.csv"
    
    echo ""
done

echo "=========================================="
echo "Validation Complete!"
echo "=========================================="
echo ""
echo "Results saved to: $OUTPUT_DIR/"
echo ""
ls -lh "$OUTPUT_DIR"/validation_v2_*.csv
