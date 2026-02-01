#!/usr/bin/env python3
"""
AQI Prediction API Server
Exposes the AQI prediction model as a REST API for integration with Lovable UI.

Usage:
    python aqi_api_server.py --port 8000 --host 0.0.0.0
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add current directory and original pipeline to path (for backward compatibility)
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Try original pipeline directory as fallback (for local development)
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if os.path.exists(original_pipeline_dir) and original_pipeline_dir not in sys.path:
    sys.path.insert(0, original_pipeline_dir)

from test_predictions import (
    load_models, geocode_address, find_nearest_sensor,
    prepare_test_data_from_csv, prepare_features_for_prediction,
    make_predictions, load_sensor_locations,
    fetch_current_sensor_data_api
)
from aqi_utils import pm25_to_aqi, aqi_to_category

app = FastAPI(
    title="AQI Prediction API",
    description="API for predicting Air Quality Index (AQI) forecasts for Fremont, CA locations",
    version="1.0.0"
)

# Enable CORS for Lovable integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to Lovable's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models and config
models = None
data_dir = None
api_key = None

# Pydantic models for request/response
class PredictionRequest(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    api_key: Optional[str] = None

class PredictionResponse(BaseModel):
    success: bool
    timestamp: str
    location: dict
    current_aqi: dict
    forecast_1h: dict
    forecast_3h: dict
    sensor_info: dict
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    success: bool
    error: str
    message: str


def initialize_api(data_directory: str, model_directory: str, purpleair_api_key: str):
    """Initialize the API with models and configuration."""
    global models, data_dir, api_key
    
    data_dir = data_directory
    api_key = purpleair_api_key
    
    print("Loading models...")
    models = load_models(model_directory)
    print(f"✓ Models loaded: {len(models)} horizons")
    print("✓ API ready")


@app.get("/")
async def root():
    """API root endpoint with information."""
    return {
        "name": "AQI Prediction API",
        "version": "1.0.0",
        "description": "Predicts AQI forecasts (1h and 3h) for locations in Fremont, CA",
        "endpoints": {
            "/predict": "POST - Predict AQI for an address or coordinates",
            "/predict/address": "GET - Predict AQI for an address (query parameter)",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation (Swagger UI)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "models_loaded": models is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/predict/address", response_model=PredictionResponse)
async def predict_by_address(
    address: str = Query(..., description="Address in Fremont, CA (e.g., '2523 Bishop Ave, Fremont, CA 94536')"),
    api_key_param: Optional[str] = Query(None, alias="api-key", description="PurpleAir API key (optional if set at startup)")
):
    """
    Predict AQI for a given address.
    
    Example:
        GET /predict/address?address=2523+Bishop+Ave,+Fremont,+CA+94536
    """
    try:
        return await make_prediction(address=address, lat=None, lon=None, api_key_override=api_key_param)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Predict AQI for a given location (address or coordinates).
    
    Request body (JSON):
    {
        "address": "2523 Bishop Ave, Fremont, CA 94536",  // Optional if lat/lon provided
        "latitude": 37.563332,                            // Optional if address provided
        "longitude": -121.993722,                         // Optional if address provided
        "api_key": "YOUR_KEY"                             // Optional (uses server default)
    }
    """
    try:
        return await make_prediction(
            address=request.address,
            lat=request.latitude,
            lon=request.longitude,
            api_key_override=request.api_key or api_key
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def make_prediction(address: Optional[str] = None, lat: Optional[float] = None, 
                         lon: Optional[float] = None, api_key_override: Optional[str] = None):
    """Core prediction logic."""
    if models is None:
        raise HTTPException(status_code=503, detail="Models not loaded. API not initialized.")
    
    # Determine location
    if address:
        # Geocode address
        try:
            target_lat, target_lon = geocode_address(address)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not geocode address: {str(e)}")
    elif lat is not None and lon is not None:
        target_lat, target_lon = lat, lon
        address = f"Coordinates ({lat}, {lon})"
    else:
        raise HTTPException(status_code=400, detail="Either 'address' or 'latitude' and 'longitude' must be provided")
    
    # Find nearest sensor
    try:
        locations_df = load_sensor_locations(data_dir)
        if locations_df is None or locations_df.empty:
            raise HTTPException(status_code=500, detail="Sensor locations not available")
        
        sensor_info_dict = find_nearest_sensor(target_lat, target_lon, locations_df)
        nearest = sensor_info_dict['nearest']
        sensor_id = nearest['sensor_id']
        sensor_name = nearest['name']
        distance_km = nearest['distance_km']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not find nearest sensor: {str(e)}")
    
    # Fetch current data and make predictions
    try:
        # Use API key override if provided, otherwise use global
        use_api_key = api_key_override or api_key
        
        if not use_api_key:
            raise HTTPException(status_code=400, detail="PurpleAir API key required")
        
        # Fetch current live data
        current_df = fetch_current_sensor_data_api(use_api_key, sensor_id)
        if current_df is None or len(current_df) == 0:
            raise HTTPException(status_code=500, detail="Could not fetch current sensor data")
        
        current_row = current_df.iloc[0]
        current_pm25 = current_row['pm2_5_atm']
        
        # Validate current PM2.5 value
        if pd.isna(current_pm25) or current_pm25 is None:
            raise HTTPException(status_code=500, detail="Current sensor PM2.5 reading is missing or invalid")
        
        # Check for unrealistic values (sensor errors)
        if current_pm25 < 0 or current_pm25 > 500:
            raise HTTPException(status_code=500, detail=f"Current sensor PM2.5 reading appears invalid: {current_pm25} μg/m³")
        
        current_aqi = pm25_to_aqi(current_pm25)
        current_category = aqi_to_category(current_aqi)
        
        # Prepare historical data for features
        try:
            hist_df = prepare_test_data_from_csv(data_dir, sensor_id, num_rows=47)
            current_df['time_stamp'] = pd.to_datetime(current_df['time_stamp'], utc=True)
            if hist_df is not None and len(hist_df) > 0:
                hist_df['time_stamp'] = pd.to_datetime(hist_df['time_stamp'], utc=True)
                test_df = pd.concat([hist_df, current_df], ignore_index=True).sort_values('time_stamp').reset_index(drop=True)
            else:
                test_df = current_df.copy()
        except Exception as e:
            # If no historical CSV, use just current data
            test_df = current_df.copy()
        
        # Ensure wind columns exist BEFORE any operations (critical for feature engineering)
        # These columns must exist even if wind data is not available
        if 'wdir' not in test_df.columns:
            test_df['wdir'] = np.nan
        if 'wind_dir_x' not in test_df.columns:
            test_df['wind_dir_x'] = np.nan
        if 'wind_dir_y' not in test_df.columns:
            test_df['wind_dir_y'] = np.nan
        
        # Fetch wind data (if available) and merge it
        from test_predictions import fetch_current_wind_data_for_prediction, merge_wind_data_for_prediction, WIND_FETCHING_AVAILABLE
        
        if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
            try:
                sensor_lat = test_df['latitude'].iloc[0]
                sensor_lon = test_df['longitude'].iloc[0]
                wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                if wind_data is not None:
                    test_df = merge_wind_data_for_prediction(test_df, wind_data)
            except Exception as e:
                # Wind fetch failed, but columns already exist (filled with NaN above)
                print(f"Warning: Wind data fetch failed: {e}")
        
        # Prepare features
        feature_row = prepare_features_for_prediction(test_df, sensor_id)
        feature_columns = models['1h']['feature_columns']
        
        # Reorder features to match model order
        feature_row_reordered = pd.DataFrame()
        for col in feature_columns:
            if col in feature_row.columns:
                feature_row_reordered[col] = [feature_row[col].iloc[0]]
            else:
                feature_row_reordered[col] = [np.nan]
        feature_row = feature_row_reordered
        
        # Make predictions with ensemble (60% ML + 40% persistence)
        # Using current_pm25 for persistence baseline prevents unrealistic predictions
        predictions = make_predictions(models, feature_row, feature_columns, current_pm25=current_pm25)
        
        # Build response
        return PredictionResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            location={
                "address": address,
                "latitude": target_lat,
                "longitude": target_lon
            },
            current_aqi={
                "pm25_ugm3": round(float(current_pm25), 2),
                "aqi": int(current_aqi),
                "category": current_category,
                "temperature_f": float(current_row.get('temperature', 0)),
                "humidity_percent": float(current_row.get('humidity', 0))
            },
            forecast_1h={
                "pm25_ugm3": predictions['1h']['pm25_ugm3'],
                "aqi": predictions['1h']['aqi'],
                "category": predictions['1h']['category']
            },
            forecast_3h={
                "pm25_ugm3": predictions['3h']['pm25_ugm3'],
                "aqi": predictions['3h']['aqi'],
                "category": predictions['3h']['category']
            },
            sensor_info={
                "sensor_id": sensor_id,
                "sensor_name": sensor_name,
                "distance_km": round(distance_km, 2),
                "latitude": nearest['latitude'],
                "longitude": nearest['longitude']
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description='AQI Prediction API Server')
    # Get port from environment variable (Render sets PORT automatically) or default to 8000
    # Handle case where PORT might be empty string
    port_env = os.getenv('PORT', '')
    default_port = int(port_env) if port_env and port_env.strip() else 8000
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=default_port, help='Port to bind to (default: from PORT env var or 8000)')
    parser.add_argument('--data-dir', default=None, help='Data directory (default: script location)')
    parser.add_argument('--model-dir', default=None, help='Model directory (default: data_dir/models)')
    parser.add_argument('--api-key', default=None, help='PurpleAir API key (or set PURPLEAIR_API_KEY env var)')
    
    args = parser.parse_args()
    
    # Set defaults
    if args.data_dir is None:
        args.data_dir = Path(__file__).parent
    if args.model_dir is None:
        args.model_dir = Path(args.data_dir) / 'models'
    if args.api_key is None:
        args.api_key = os.getenv('PURPLEAIR_API_KEY', 'C258449D-E52B-11F0-B596-4201AC1DC123')
    
    # Initialize API
    initialize_api(str(args.data_dir), str(args.model_dir), args.api_key)
    
    # Start server
    print(f"\n{'='*70}")
    print(f"AQI Prediction API Server")
    print(f"{'='*70}")
    print(f"Server starting on http://{args.host}:{args.port}")
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/health")
    print(f"{'='*70}\n")
    
    uvicorn.run(app, host=args.host, port=args.port)
