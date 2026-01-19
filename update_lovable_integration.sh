#!/bin/bash

# Script to update Lovable integration with new model files

echo "==================================================================="
echo "UPDATING LOVABLE INTEGRATION WITH NEW MODELS"
echo "==================================================================="
echo ""

# Source directory (new models)
SOURCE_DIR="/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC/models"

# Destination directory (API server)
DEST_DIR="$HOME/Documents/aqi_api/models"

echo "Source: $SOURCE_DIR"
echo "Destination: $DEST_DIR"
echo ""

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Check if destination directory exists
if [ ! -d "$DEST_DIR" ]; then
    echo "⚠ Warning: Destination directory does not exist. Creating it..."
    mkdir -p "$DEST_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ Error: Could not create destination directory: $DEST_DIR"
        exit 1
    fi
    echo "✓ Created destination directory"
fi

echo "Copying model files..."
echo ""

# Copy all .pkl files
cp "$SOURCE_DIR"/*.pkl "$DEST_DIR/"

if [ $? -eq 0 ]; then
    echo "✓ Successfully copied model files"
    echo ""
    echo "Copied files:"
    ls -lh "$DEST_DIR"/*.pkl | awk '{print "  - " $9 " (" $5 ")"}'
    echo ""
    echo "==================================================================="
    echo "✅ MODEL FILES UPDATED"
    echo "==================================================================="
    echo ""
    echo "Next steps:"
    echo "1. ✅ Model files copied (done)"
    echo "2. ✅ API server code updated to use ensemble (already done)"
    echo "3. ⏭  Restart the API server:"
    echo "   cd ~/Documents/aqi_api"
    echo "   ./start_api.sh"
    echo ""
    echo "Or stop current server and restart:"
    echo "   pkill -f aqi_api_server"
    echo "   cd ~/Documents/aqi_api && python3 aqi_api_server.py"
    echo ""
else
    echo "❌ Error: Failed to copy model files"
    exit 1
fi
