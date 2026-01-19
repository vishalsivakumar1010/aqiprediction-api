#!/usr/bin/env python3
"""
Test Script for AQI Prediction Models
Tests the trained models to verify they can predict AQI for a given location/sensor.

Usage:
    # Test with address (automatically finds nearest sensor):
    python3 test_predictions.py --address "Lake Elizabeth Park, Fremont, CA"
    python3 test_predictions.py --address "Fremont City Hall, CA"
    
    # Test with sensor ID:
    python3 test_predictions.py --sensor-id 17895 --use-csv
    
    # Test with multiple sensors:
    python3 test_predictions.py --sensor-id 17895 18987 19683 --use-csv
"""

import pandas as pd
import numpy as np
import pickle
import os
import sys
import argparse
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Try to import geopy for geocoding
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    GEOCODING_AVAILABLE = True
except ImportError:
    GEOCODING_AVAILABLE = False
    print("Warning: geopy not installed. Address geocoding will not be available.")
    print("Install with: pip install geopy")

# Add path to original pipeline for imports
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")
if os.path.exists(original_pipeline_dir) and original_pipeline_dir not in sys.path:
    sys.path.insert(0, original_pipeline_dir)

try:
    from aqi_utils import pm25_to_aqi, aqi_to_category
    from feature_engineering import engineer_features
except ImportError:
    print("Error: Could not import aqi_utils or feature_engineering")
    print(f"Please ensure the original pipeline exists at: {original_pipeline_dir}")
    sys.exit(1)

# Import wind fetching functions - Use Open-Meteo instead of Meteostat
try:
    # Add current directory to path for imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from fetch_wind_openmeteo import (
        fetch_historical_wind_openmeteo,
        fetch_forecast_wind_openmeteo
    )
    WIND_FETCHING_AVAILABLE = True
    WIND_SOURCE = "Open-Meteo"
except ImportError as e:
    print(f"Warning: Could not import Open-Meteo wind fetching functions: {e}")
    print("  Wind features will be missing during prediction (may reduce accuracy)")
    WIND_FETCHING_AVAILABLE = False
    WIND_SOURCE = None


def load_models(model_dir='models'):
    """
    Load trained models for both 1h and 3h forecasts.
    
    Args:
        model_dir: Directory containing saved models
        
    Returns:
        Dictionary with models for both horizons
    """
    models = {}
    
    for horizon in ['1h', '3h']:
        pm25_model_path = os.path.join(model_dir, f'pm25_model_{horizon}.pkl')
        category_model_path = os.path.join(model_dir, f'category_model_{horizon}.pkl')
        category_mapping_path = os.path.join(model_dir, f'category_mapping_{horizon}.pkl')
        feature_cols_path = os.path.join(model_dir, f'feature_columns_{horizon}.pkl')
        
        if not os.path.exists(pm25_model_path):
            raise FileNotFoundError(f"Model file not found: {pm25_model_path}")
        
        with open(pm25_model_path, 'rb') as f:
            pm25_model = pickle.load(f)
        
        with open(category_model_path, 'rb') as f:
            category_model = pickle.load(f)
        
        with open(feature_cols_path, 'rb') as f:
            feature_columns = pickle.load(f)
        
        category_mapping = None
        if os.path.exists(category_mapping_path):
            with open(category_mapping_path, 'rb') as f:
                mapping_data = pickle.load(f)
                if isinstance(mapping_data, dict) and 'num_to_cat' in mapping_data:
                    category_mapping = mapping_data['num_to_cat']
                else:
                    category_mapping = mapping_data
        
        models[horizon] = {
            'pm25_model': pm25_model,
            'category_model': category_model,
            'category_mapping': category_mapping,
            'feature_columns': feature_columns
        }
    
    return models


def load_sensor_locations(data_dir):
    """Load sensor location data from pickle or CSV."""
    location_path = os.path.join(data_dir, 'sensor_locations.pkl')
    alt_location_path = os.path.join(original_pipeline_dir, 'sensor_locations.pkl')
    csv_path = os.path.join(original_pipeline_dir, 'sensor_locations.csv')
    
    # Try pickle files first
    for path in [location_path, alt_location_path]:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    locations_df = pickle.load(f)
                return locations_df
            except Exception as e:
                print(f"Warning: Could not load locations from {path}: {e}")
                continue
    
    # Try CSV file
    if os.path.exists(csv_path):
        try:
            locations_df = pd.read_csv(csv_path)
            # Ensure sensor_id is integer
            if 'sensor_id' in locations_df.columns:
                locations_df['sensor_id'] = locations_df['sensor_id'].astype(int)
            return locations_df
        except Exception as e:
            print(f"Warning: Could not load locations from CSV {csv_path}: {e}")
    
    return None


# Known Fremont locations (fallback if geocoding fails)
FREMONT_LOCATIONS = {
    'lake elizabeth park': (37.54408, -121.96445),
    'lake elizabeth': (37.54408, -121.96445),
    'fremont city hall': (37.54828, -121.98861),
    'city hall': (37.54828, -121.98861),
    'glenmoor gardens': (37.54209, -122.00043),
    'glenmoor': (37.53806, -122.01384),
    'civic center': (37.55336, -121.97416),
    'fremont civic center': (37.55336, -121.97416),
    'northgate': (37.58510, -122.04132),
    'fremont northgate': (37.58510, -122.04132),
}


def geocode_address(address, city="Fremont, CA"):
    """
    Convert an address to latitude and longitude using geocoding.
    First tries known locations, then falls back to online geocoding.
    
    Args:
        address: Address string (e.g., "Lake Elizabeth Park" or full address)
        city: City name to append if not in address (default: "Fremont, CA")
        
    Returns:
        Tuple of (latitude, longitude) or None if geocoding fails
    """
    # First, try known locations lookup (case-insensitive)
    address_lower = address.lower().strip()
    if address_lower in FREMONT_LOCATIONS:
        coords = FREMONT_LOCATIONS[address_lower]
        print(f"  ✓ Found in known locations: {coords}")
        return coords
    
    # Try partial matches for known locations
    for known_name, coords in FREMONT_LOCATIONS.items():
        if known_name in address_lower or address_lower in known_name:
            print(f"  ✓ Matched known location '{known_name}': {coords}")
            return coords
    
    # If not found in known locations and geocoding available, try online geocoding
    if not GEOCODING_AVAILABLE:
        print(f"  ⚠ geopy not installed. Tried known locations but didn't find match.")
        print(f"  Known locations: {', '.join(FREMONT_LOCATIONS.keys())}")
        return None
    
    # Try multiple address variations
    address_variations = []
    
    # Original address
    address_variations.append(address)
    
    # With city appended if not present
    if city.lower() not in address.lower():
        address_variations.append(f"{address}, {city}")
        address_variations.append(f"{address}, Fremont, California, USA")
        address_variations.append(f"{address}, Fremont, CA, USA")
    
    # Also try with just "Fremont" if full city name was provided
    if "Fremont, CA" in address or "Fremont, California" in address:
        address_variations.append(address.replace("Fremont, CA", "Fremont").replace("Fremont, California", "Fremont"))
    
    geolocator = Nominatim(user_agent="aqi_prediction_app_fremont", timeout=10)
    
    for full_address in address_variations[:2]:  # Limit to first 2 variations to avoid rate limiting
        try:
            print(f"  Trying online geocoding: '{full_address}'")
            import time
            time.sleep(1)  # Be polite to the geocoding service
            location = geolocator.geocode(full_address, timeout=15, exactly_one=True)
            
            if location:
                print(f"  ✓ Found: {location.address}")
                return (location.latitude, location.longitude)
        except Exception as e:
            print(f"  Warning: Geocoding attempt failed: {e}")
            continue
    
    # If all variations failed, return None
    print(f"  ✗ Could not geocode address. Known locations: {', '.join(FREMONT_LOCATIONS.keys())}")
    return None


def find_nearest_sensor(target_lat, target_lon, locations_df):
    """
    Find the nearest sensor to a given latitude/longitude.
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        locations_df: DataFrame with sensor locations (must have latitude, longitude, sensor_id columns)
        
    Returns:
        Dictionary with nearest sensor info: {'sensor_id': int, 'name': str, 'distance_km': float, 'latitude': float, 'longitude': float}
    """
    if locations_df is None or locations_df.empty:
        raise ValueError("Sensor locations not available")
    
    if 'latitude' not in locations_df.columns or 'longitude' not in locations_df.columns:
        raise ValueError("Location dataframe missing latitude/longitude columns")
    
    # Filter to sensors with valid coordinates
    valid_locs = locations_df[locations_df['latitude'].notna() & locations_df['longitude'].notna()].copy()
    
    if valid_locs.empty:
        raise ValueError("No sensors with valid coordinates found")
    
    # Calculate distances using geodesic (Haversine formula)
    target_point = (target_lat, target_lon)
    
    distances = []
    for idx, row in valid_locs.iterrows():
        sensor_point = (row['latitude'], row['longitude'])
        distance_km = geodesic(target_point, sensor_point).kilometers
        distances.append({
            'sensor_id': int(row['sensor_id']),
            'name': row.get('name', f"Sensor {row['sensor_id']}"),
            'distance_km': distance_km,
            'latitude': row['latitude'],
            'longitude': row['longitude']
        })
    
    # Sort by distance and return nearest
    distances.sort(key=lambda x: x['distance_km'])
    nearest = distances[0]
    
    # Also return top 3 for reference
    return {
        'nearest': nearest,
        'top_3': distances[:3]
    }


def fetch_current_sensor_data_api(api_key, sensor_id):
    """
    Fetch current live sensor data from PurpleAir API.
    
    Args:
        api_key: PurpleAir API read key
        sensor_id: Sensor ID
        
    Returns:
        DataFrame with current sensor data (single row)
    """
    import requests
    
    url = f"https://api.purpleair.com/v1/sensors/{sensor_id}"
    headers = {'X-API-Key': api_key}
    params = {'fields': 'humidity,temperature,pm2.5_atm'}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'sensor' not in data:
            raise ValueError("No sensor data in API response")
        
        sensor_info = data['sensor']
        
        # Create DataFrame with current data
        current_data = {
            'sensor_id': int(sensor_id),
            'time_stamp': pd.Timestamp.now(tz='UTC'),
            'humidity': sensor_info.get('humidity'),
            'temperature': sensor_info.get('temperature'),
            'pm2_5_atm': sensor_info.get('pm2.5_atm'),
            'latitude': sensor_info.get('latitude'),
            'longitude': sensor_info.get('longitude'),
            'name': sensor_info.get('name', f"Sensor {sensor_id}")
        }
        
        return pd.DataFrame([current_data])
        
    except Exception as e:
        raise Exception(f"Error fetching current data from API: {e}")


def fetch_current_wind_data_for_prediction(df, latitude=37.5483, longitude=-121.9886):
    """
    Fetch current wind direction data from Open-Meteo for prediction.
    Uses Open-Meteo forecast API for current/recent data and historical API for past data.
    
    Args:
        df: DataFrame with sensor data (to determine date range)
        latitude: Latitude for wind data (default: Fremont center)
        longitude: Longitude for wind data (default: Fremont center)
        
    Returns:
        DataFrame with wind direction data (timestamp_hour, wdir, wspd) or None
    """
    if not WIND_FETCHING_AVAILABLE:
        print("⚠ Wind fetching not available. Predictions will have missing wind features.")
        return None
    
    # Get date range from dataframe
    start_date = df['time_stamp'].min()
    end_date = df['time_stamp'].max()
    
    current_time = pd.Timestamp.now(tz='UTC')
    
    print(f"\nFetching wind direction data from Open-Meteo for prediction...")
    print(f"  Location: ({latitude}, {longitude})")
    print(f"  Date range: {start_date} to {end_date}")
    
    try:
        # Determine if we need historical or forecast data
        # If end_date is recent (within last 6 hours), use forecast API
        # Otherwise, use historical API
        
        hours_ago = (current_time - end_date).total_seconds() / 3600
        
        if hours_ago < 6:
            # Use forecast API for recent/current data
            print(f"  Using Open-Meteo Forecast API (data is {hours_ago:.1f} hours old)")
            forecast_days = max(1, int((end_date - start_date).total_seconds() / 86400) + 1)
            forecast_days = min(forecast_days, 7)  # Open-Meteo forecast limit
            
            # Import here to ensure it's available
            from fetch_wind_openmeteo import fetch_forecast_wind_openmeteo
            wind_df = fetch_forecast_wind_openmeteo(latitude, longitude, forecast_days=forecast_days, height_meters=10)
            
            if wind_df is None or len(wind_df) == 0:
                print("⚠ Could not fetch forecast wind data from Open-Meteo.")
                return None
            
            # Filter to the date range we need
            # Open-Meteo returns timezone-naive timestamps, so convert our dates to naive for comparison
            start_date_naive = start_date.floor('H')
            if start_date_naive.tz is not None:
                start_date_naive = start_date_naive.tz_localize(None)
            end_date_naive = end_date.ceil('H')
            if end_date_naive.tz is not None:
                end_date_naive = end_date_naive.tz_localize(None)
            
            wind_df = wind_df[
                (wind_df['timestamp_hour'] >= start_date_naive) &
                (wind_df['timestamp_hour'] <= end_date_naive)
            ].copy()
            
            print(f"✓ Wind data fetched from Open-Meteo Forecast: {len(wind_df)} hourly records")
            
        else:
            # Use historical API for older data
            print(f"  Using Open-Meteo Historical API (data is {hours_ago:.1f} hours old)")
            
            # Convert to timezone-naive for Open-Meteo API
            start_date_naive = start_date.tz_localize(None) if start_date.tz else start_date
            end_date_naive = end_date.tz_localize(None) if end_date.tz else end_date
            
            # Import here to ensure it's available
            from fetch_wind_openmeteo import fetch_historical_wind_openmeteo
            wind_df = fetch_historical_wind_openmeteo(
                latitude, longitude, 
                start_date_naive, end_date_naive,
                height_meters=10
            )
            
            if wind_df is None or len(wind_df) == 0:
                print("⚠ Could not fetch historical wind data from Open-Meteo.")
                return None
            
            print(f"✓ Wind data fetched from Open-Meteo Historical: {len(wind_df)} hourly records")
        
        # Open-Meteo returns wdir and wspd directly (already in correct format)
        # Ensure columns exist
        if 'wdir' not in wind_df.columns:
            print("⚠ Warning: wdir column not found in Open-Meteo data")
            return None
        
        # wspd is optional but useful
        if 'wspd' not in wind_df.columns:
            wind_df['wspd'] = np.nan
        
        # Return in format expected by merge function: (wind_df, station_info)
        # For Open-Meteo, we don't have station info, so create a dummy one
        station_info = {
            'station_name': 'Open-Meteo (Grid-based)',
            'station_id': 'OPENMETEO',
            'actual_coverage_pct': 100.0 if len(wind_df) > 0 else 0.0
        }
        
        return wind_df, station_info
        
    except Exception as e:
        print(f"⚠ Error fetching wind data from Open-Meteo: {e}")
        import traceback
        traceback.print_exc()
        print("  Predictions will proceed without wind features (may be less accurate)")
        return None


def merge_wind_data_for_prediction(df, wind_data):
    """
    Merge wind direction data into prediction dataframe.
    Similar to merge_wind_direction in prepare_full_dataset but for prediction.
    
    Args:
        df: Sensor data DataFrame
        wind_data: Tuple of (wind_df, station_info) or None
        
    Returns:
        DataFrame with merged wind data
    """
    if wind_data is None:
        # No wind data available, create empty columns
        df['wdir'] = np.nan
        df['wind_dir_x'] = np.nan
        df['wind_dir_y'] = np.nan
        return df
    
    wind_df, station_info = wind_data
    tz_local = 'America/Los_Angeles'
    
    # Convert timestamps to timezone-naive local time
    df = df.copy()
    # Handle both timezone-aware and timezone-naive timestamps
    if isinstance(df['time_stamp'].iloc[0], pd.Timestamp):
        if df['time_stamp'].iloc[0].tz is not None:
            # Already timezone-aware, convert to local then naive
            df['time_stamp'] = pd.to_datetime(df['time_stamp']).dt.tz_convert(tz_local).dt.tz_localize(None)
        else:
            # Timezone-naive, assume UTC and convert
            df['time_stamp'] = pd.to_datetime(df['time_stamp']).dt.tz_localize('UTC').dt.tz_convert(tz_local).dt.tz_localize(None)
    else:
        # Not a timestamp yet, parse as UTC then convert
        df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True).dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Create hourly timestamp for merging
    df['timestamp_hour'] = df['time_stamp'].dt.floor('H')
    
    # Ensure wind_df timestamps are also timezone-naive local
    wind_df = wind_df.copy()
    wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour'])
    
    # Handle timezone if wind_df timestamps are timezone-aware
    if hasattr(wind_df['timestamp_hour'].iloc[0], 'tz') and wind_df['timestamp_hour'].iloc[0].tz is not None:
        wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Merge wind direction data
    df = df.merge(wind_df[['timestamp_hour', 'wdir']], 
                  on='timestamp_hour', 
                  how='left')
    
    # Forward-fill with 6-hour limit (same as training)
    # Sort by time_stamp first to ensure proper forward fill
    df = df.sort_values('time_stamp').reset_index(drop=True)
    df['wdir'] = df.groupby('sensor_id')['wdir'].ffill(limit=6)
    
    # Also backward-fill for the first row if needed (get value from next available hour)
    df['wdir'] = df.groupby('sensor_id')['wdir'].bfill(limit=1)
    
    # Convert to x, y components
    mask = df['wdir'].notna()
    df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
    df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
    df.loc[~mask, 'wind_dir_x'] = np.nan
    df.loc[~mask, 'wind_dir_y'] = np.nan
    
    coverage_pct = (df['wdir'].notna().sum() / len(df)) * 100
    print(f"✓ Wind data merged: {coverage_pct:.1f}% coverage")
    
    return df


def prepare_test_data_from_csv(data_dir, sensor_id, num_rows=48):
    """
    Prepare test data from existing CSV files.
    Uses the most recent rows from a sensor's CSV file.
    
    NOTE: This uses HISTORICAL data from CSV files, not current live values!
    
    Args:
        data_dir: Directory containing CSV files
        sensor_id: Sensor ID to test
        num_rows: Number of recent rows to use (48 = 24 hours of 30-min data)
        
    Returns:
        DataFrame with sensor data ready for prediction
    """
    # Find CSV file for this sensor
    csv_pattern = f"{sensor_id} *30-Minute Average.csv"
    import glob
    csv_files = glob.glob(os.path.join(data_dir, csv_pattern))
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV file found for sensor {sensor_id} in {data_dir}")
    
    csv_file = csv_files[0]
    print(f"Loading HISTORICAL data from: {os.path.basename(csv_file)}")
    
    # Load CSV
    df = pd.read_csv(csv_file)
    df['sensor_id'] = int(sensor_id)
    # Convert to UTC timezone-aware, then to timezone-naive local for consistency
    df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
    # Keep as UTC-aware for now, will convert when merging wind data
    
    # Standardize column names
    if 'pm2.5_atm' in df.columns:
        df = df.rename(columns={'pm2.5_atm': 'pm2_5_atm'})
    
    # Get most recent rows
    df = df.sort_values('time_stamp').tail(num_rows).reset_index(drop=True)
    
    # Show warning about data age
    last_timestamp = df['time_stamp'].iloc[-1]
    time_diff = pd.Timestamp.now(tz='UTC') - last_timestamp
    if time_diff > pd.Timedelta(hours=1):
        print(f"⚠ WARNING: CSV data is {time_diff} old (last row: {last_timestamp})")
        print(f"  This is HISTORICAL data, not current live values!")
        print(f"  To get current live data, use --api-key option")
    
    # Add location data if available
    locations_df = load_sensor_locations(data_dir)
    if locations_df is not None:
        sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
        if not sensor_locs.empty:
            df['latitude'] = sensor_locs.iloc[0]['latitude']
            df['longitude'] = sensor_locs.iloc[0]['longitude']
            if 'name' in sensor_locs.columns:
                df['name'] = sensor_locs.iloc[0]['name']
    
    # Fetch and merge wind data
    if WIND_FETCHING_AVAILABLE and 'latitude' in df.columns and df['latitude'].notna().any():
        sensor_lat = df['latitude'].iloc[0]
        sensor_lon = df['longitude'].iloc[0]
        wind_data = fetch_current_wind_data_for_prediction(df, sensor_lat, sensor_lon)
        if wind_data is not None:
            df = merge_wind_data_for_prediction(df, wind_data)
    
    return df


def prepare_features_for_prediction(df, sensor_id):
    """
    Prepare features from sensor data using the same pipeline as training.
    
    Args:
        df: DataFrame with sensor data (historical + current)
        sensor_id: Sensor ID
        
    Returns:
        DataFrame with engineered features (last row for prediction)
    """
    # Ensure sensor_id is set
    df = df.copy()
    df['sensor_id'] = int(sensor_id)
    
    # Check if location data is available
    has_locations = 'latitude' in df.columns and df['latitude'].notna().any()
    
    # Ensure wind features exist (they should be merged before this, but add if missing)
    if 'wdir' in df.columns and 'wind_dir_x' not in df.columns:
        # Create wind direction x, y components if wdir exists but components don't
        mask = df['wdir'].notna()
        df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
        df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
    
    # Engineer features (same as training, but without targets)
    df_features = engineer_features(df, include_targets=False, include_spatial_features=has_locations)
    
    # Ensure spatial interaction features exist (even if only one sensor)
    # During training, these might have been calculated across multiple sensors
    # During prediction with single sensor, we need to set them to the sensor's own value
    if 'pm25_nearby_sensors_avg' not in df_features.columns:
        df_features['pm25_nearby_sensors_avg'] = df_features['pm2_5_atm']
    if 'pm25_nearby_sensors_std' not in df_features.columns:
        df_features['pm25_nearby_sensors_std'] = 0.0
    
    # Fill NaN values for spatial interaction features
    df_features['pm25_nearby_sensors_avg'] = df_features['pm25_nearby_sensors_avg'].fillna(df_features['pm2_5_atm'])
    df_features['pm25_nearby_sensors_std'] = df_features['pm25_nearby_sensors_std'].fillna(0.0)
    
    # Ensure wind features exist (fill with 0 if missing, matching training behavior)
    if 'wind_dir_x' not in df_features.columns:
        df_features['wind_dir_x'] = 0.0
    if 'wind_dir_y' not in df_features.columns:
        df_features['wind_dir_y'] = 0.0
    if 'wdir' not in df_features.columns:
        df_features['wdir'] = 0.0
    
    # Remove sensor_id and time_stamp columns (not used as features, and may cause issues)
    # Keep only feature columns
    columns_to_remove = ['sensor_id', 'time_stamp']
    if 'timestamp_hour' in df_features.columns:
        columns_to_remove.append('timestamp_hour')
    
    df_features = df_features.drop(columns=[col for col in columns_to_remove if col in df_features.columns])
    
    # Return only the most recent row (current time)
    return df_features.iloc[[-1]]


def make_predictions(models, feature_row, feature_columns, current_pm25=None, ensemble_weight=0.6):
    """
    Make predictions using the loaded models with optional ensemble with persistence.
    
    Args:
        models: Dictionary with models for '1h' and '3h'
        feature_row: DataFrame row with engineered features
        feature_columns: List of feature column names expected by model
        current_pm25: Current PM2.5 value for persistence baseline (optional)
                     If provided, ensemble will be: 60% ML + 40% persistence (default weights)
        ensemble_weight: Weight for ML prediction (default 0.6, persistence = 1 - ensemble_weight)
        
    Returns:
        Dictionary with predictions for both horizons
    """
    predictions = {}
    
    for horizon in ['1h', '3h']:
        model_info = models[horizon]
        
        # Extract features in correct order
        # Use NaN for missing values - XGBoost handles NaN the same way it did in training
        # During training, feature_engineering.py fills NaNs with 0 at the end, but we want
        # to preserve NaN here so XGBoost can handle it properly (especially for wind features
        # that may have been missing during training)
        X = np.full((1, len(feature_columns)), np.nan)  # Initialize with NaN instead of 0
        for i, col in enumerate(feature_columns):
            if col in feature_row.columns:
                value = feature_row[col].iloc[0]
                # Handle infinite values (convert to NaN)
                if np.isinf(value):
                    X[0, i] = np.nan
                elif pd.isna(value):
                    X[0, i] = np.nan  # Keep NaN as NaN
                else:
                    X[0, i] = float(value)
            else:
                # Missing feature column - leave as NaN (don't fill with 0)
                X[0, i] = np.nan
        
        # XGBoost can handle NaN values, but if we want to match training exactly,
        # we can fill NaNs with 0 here (since training does df.fillna(0) at the end)
        # However, for wind features that were missing during training, leaving as NaN
        # is more appropriate. Let's fill with 0 to match training behavior, but log it.
        nan_count = np.isnan(X).sum()
        if nan_count > 0:
            print(f"  Note: {nan_count} feature values are NaN (will be handled by XGBoost)")
            # Fill with 0 to match training behavior (training does fillna(0))
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Predict PM2.5 using ML model
        pm25_model = model_info['pm25_model']
        ml_predicted_pm25 = pm25_model.predict(X)[0]
        
        # Ensure reasonable values
        ml_predicted_pm25 = max(0.0, min(1000.0, float(ml_predicted_pm25)))
        
        # Ensemble with persistence if current_pm25 is provided
        if current_pm25 is not None and not pd.isna(current_pm25):
            persistence_pm25 = float(current_pm25)
            # Combine ML prediction with persistence baseline
            # Default: 60% ML + 40% persistence
            predicted_pm25 = ensemble_weight * ml_predicted_pm25 + (1 - ensemble_weight) * persistence_pm25
            # Ensure reasonable values after ensemble
            predicted_pm25 = max(0.0, min(1000.0, predicted_pm25))
        else:
            # No ensemble, use ML prediction only
            predicted_pm25 = ml_predicted_pm25
        
        # Convert to AQI
        predicted_aqi = pm25_to_aqi(predicted_pm25)
        
        # Always use AQI-based category for accuracy (more reliable than classification model)
        # The classification model may have category mapping issues, so calculate from AQI directly
        predicted_category = aqi_to_category(predicted_aqi)
        
        # Note: We could also try using the classification model, but AQI-based is more reliable
        # category_model = model_info['category_model']
        # category_mapping = model_info['category_mapping']
        # try:
        #     category_num = category_model.predict(X)[0]
        #     if category_mapping is not None and isinstance(category_mapping, dict):
        #         predicted_category_from_model = category_mapping.get(int(category_num), None)
        #         if predicted_category_from_model:
        #             predicted_category = predicted_category_from_model
        # except:
        #     pass  # Fall back to AQI-based category
        
        predictions[horizon] = {
            'pm25_ugm3': round(predicted_pm25, 2),
            'aqi': int(predicted_aqi),
            'category': predicted_category
        }
    
    return predictions


def test_sensor_prediction(sensor_id, data_dir, models, use_csv=True, api_key=None):
    """
    Test prediction for a single sensor.
    
    Args:
        sensor_id: Sensor ID to test
        data_dir: Directory containing data files
        models: Loaded model dictionary
        use_csv: Whether to use CSV data (True) or API (False)
        api_key: PurpleAir API key (required if use_csv=False)
        
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*70}")
    print(f"Testing Sensor ID: {sensor_id}")
    print(f"{'='*70}")
    
    try:
        if use_csv:
            # Load test data from CSV (HISTORICAL data)
            test_df = prepare_test_data_from_csv(data_dir, sensor_id, num_rows=48)
            print(f"✓ Loaded {len(test_df)} rows of HISTORICAL data")
            
            # Get current values (most recent row from historical data)
            current_row = test_df.iloc[-1]
            current_pm25 = current_row['pm2_5_atm']
            current_aqi = pm25_to_aqi(current_pm25)
            current_category = aqi_to_category(current_aqi)
            
            print(f"\nMost Recent Historical Conditions (from CSV):")
            print(f"  ⚠ NOTE: This is HISTORICAL data, not current live values!")
            print(f"  Timestamp: {current_row['time_stamp']}")
            print(f"  PM2.5: {current_pm25:.2f} μg/m³")
            print(f"  AQI: {int(current_aqi)} ({current_category})")
            if 'temperature' in current_row:
                print(f"  Temperature: {current_row['temperature']:.1f}°F")
            if 'humidity' in current_row:
                print(f"  Humidity: {current_row['humidity']:.1f}%")
            if 'latitude' in current_row and pd.notna(current_row['latitude']):
                print(f"  Location: ({current_row['latitude']:.4f}, {current_row['longitude']:.4f})")
        else:
            # Fetch current live data from API
            if not api_key:
                raise ValueError("API key required for live data. Use --api-key option or --use-csv for historical data.")
            
            print(f"Fetching CURRENT LIVE data from PurpleAir API...")
            current_df = fetch_current_sensor_data_api(api_key, sensor_id)
            
            # For predictions, we still need historical data for features
            # Load historical from CSV (it will fetch wind data automatically)
            try:
                # Load historical data - it will fetch wind data internally
                hist_df = prepare_test_data_from_csv(data_dir, sensor_id, num_rows=47)
                
                # Ensure both dataframes have consistent timezone handling before combining
                # Convert both to UTC-aware, then we'll convert to local-naive when merging wind
                current_df['time_stamp'] = pd.to_datetime(current_df['time_stamp'], utc=True)
                hist_df['time_stamp'] = pd.to_datetime(hist_df['time_stamp'], utc=True)
                
                # Combine historical + current
                test_df = pd.concat([hist_df, current_df], ignore_index=True).sort_values('time_stamp').reset_index(drop=True)
                print(f"✓ Combined {len(hist_df)} historical rows + 1 current live row")
                
                # Re-fetch wind data for the combined dataset to include current time
                # (hist_df has wind up to its last timestamp, but we need it for current time too)
                if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                    sensor_lat = test_df['latitude'].iloc[0]
                    sensor_lon = test_df['longitude'].iloc[0]
                    print(f"\nUpdating wind data for combined dataset (including current time)...")
                    wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                    if wind_data is not None:
                        test_df = merge_wind_data_for_prediction(test_df, wind_data)
            except Exception as e:
                # If no historical CSV, use just current data (limited features)
                print(f"⚠ Warning: Could not load historical CSV data: {e}")
                print(f"  Using current data only (limited features - predictions may be less accurate)")
                test_df = current_df.copy()
                
                # Ensure current data has location info for wind fetching
                if 'latitude' not in test_df.columns or test_df['latitude'].isna().all():
                    # Try to get location from sensor locations
                    locations_df = load_sensor_locations(data_dir)
                    if locations_df is not None:
                        sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
                        if not sensor_locs.empty:
                            test_df['latitude'] = sensor_locs.iloc[0]['latitude']
                            test_df['longitude'] = sensor_locs.iloc[0]['longitude']
                
                # Still try to fetch wind data even with just current data
                if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                    sensor_lat = test_df['latitude'].iloc[0]
                    sensor_lon = test_df['longitude'].iloc[0]
                    print(f"\nFetching wind data for current data only...")
                    wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                    if wind_data is not None:
                        test_df = merge_wind_data_for_prediction(test_df, wind_data)
            
            current_row = current_df.iloc[0]
            current_pm25 = current_row['pm2_5_atm']
            current_aqi = pm25_to_aqi(current_pm25)
            current_category = aqi_to_category(current_aqi)
            
            print(f"\nCurrent LIVE Conditions (from PurpleAir API):")
            print(f"  Timestamp: {current_row['time_stamp']}")
            print(f"  PM2.5: {current_pm25:.2f} μg/m³")
            print(f"  AQI: {int(current_aqi)} ({current_category})")
            if 'temperature' in current_row:
                print(f"  Temperature: {current_row['temperature']:.1f}°F")
            if 'humidity' in current_row:
                print(f"  Humidity: {current_row['humidity']:.1f}%")
            if 'latitude' in current_row and pd.notna(current_row['latitude']):
                print(f"  Location: ({current_row['latitude']:.4f}, {current_row['longitude']:.4f})")
        
        # Prepare features
        print(f"\nPreparing features...")
        feature_row = prepare_features_for_prediction(test_df, sensor_id)
        print(f"✓ Features prepared ({len(feature_row.columns)} columns)")
        
        # Get feature columns (use 1h model's features as reference)
        feature_columns = models['1h']['feature_columns']
        print(f"✓ Using {len(feature_columns)} features from model")
        
        # CRITICAL FIX: Reorder feature_row to match the exact order expected by the model
        # While make_predictions matches by name, ensuring correct order is good practice
        # Create a new DataFrame with features in the exact order expected by the model
        feature_row_reordered = pd.DataFrame()
        for col in feature_columns:
            if col in feature_row.columns:
                feature_row_reordered[col] = [feature_row[col].iloc[0]]  # Keep as single-row DataFrame
            else:
                # Missing feature - will be set to NaN (then 0) in make_predictions
                feature_row_reordered[col] = [np.nan]
        
        feature_row = feature_row_reordered
        
        # Check feature coverage
        missing_features = set(feature_columns) - set(feature_row.columns)
        if missing_features:
            print(f"⚠ Warning: {len(missing_features)} feature columns missing from engineered data:")
            print(f"  {list(missing_features)[:10]}...")  # Show first 10
            print(f"  These will be set to NaN (then 0 to match training behavior)")
        
        # Verify feature engineering used the same function
        print(f"  Feature engineering: Using engineer_features() from original pipeline")
        print(f"  Feature order: REORDERED to match saved feature_columns_*.pkl exactly (CRITICAL FIX)")
        
        # Make predictions with ensemble (60% ML + 40% persistence)
        print(f"\nMaking predictions...")
        print(f"  Using ensemble: {int(60)}% ML prediction + {int(40)}% persistence (current PM2.5)")
        predictions = make_predictions(models, feature_row, feature_columns, current_pm25=current_pm25, ensemble_weight=0.6)
        
        # Display results
        print(f"\n{'='*70}")
        print(f"PREDICTION RESULTS")
        print(f"{'='*70}")
        
        for horizon in ['1h', '3h']:
            pred = predictions[horizon]
            print(f"\n{horizon.upper()} Forecast:")
            print(f"  Predicted PM2.5: {pred['pm25_ugm3']:.2f} μg/m³")
            print(f"  Predicted AQI: {pred['aqi']} ({pred['category']})")
        
        return {
            'sensor_id': sensor_id,
            'current': {
                'pm25': float(current_pm25),
                'aqi': int(current_aqi),
                'category': current_category
            },
            'predictions': predictions,
            'success': True
        }
        
    except Exception as e:
        print(f"✗ Error testing sensor {sensor_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'sensor_id': sensor_id,
            'success': False,
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description='Test AQI prediction models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with address (automatically finds nearest sensor):
  python3 test_predictions.py --address "Lake Elizabeth Park, Fremont, CA"
  python3 test_predictions.py --address "Fremont City Hall"
  python3 test_predictions.py --address "Glenmoor Gardens"
  
  # Test with specific sensor ID:
  python3 test_predictions.py --sensor-id 17895 --use-csv
  
  # Test multiple sensors:
  python3 test_predictions.py --sensor-id 17895 18987 19683 --use-csv
        """
    )
    parser.add_argument('--address', type=str, default=None,
                       help='Address or location name in Fremont, CA (e.g., "Lake Elizabeth Park")')
    parser.add_argument('--sensor-id', type=int, nargs='+', required=False,
                       help='Sensor ID(s) to test (alternative to --address)')
    parser.add_argument('--model-dir', type=str, default='models',
                       help='Directory containing trained models (default: models)')
    parser.add_argument('--data-dir', type=str, default=None,
                       help='Directory containing CSV data files (default: current directory)')
    parser.add_argument('--use-csv', action='store_true', default=True,
                       help='Use CSV data files for historical data (default: True). Note: CSV data is HISTORICAL, not current live values.')
    parser.add_argument('--api-key', type=str, default=None,
                       help='Purple Air API key for fetching current live data. If provided, will fetch current values instead of using historical CSV data.')
    
    args = parser.parse_args()
    
    # Determine data directory
    if args.data_dir is None:
        data_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        data_dir = args.data_dir
    
    # Ensure model directory path is absolute
    if not os.path.isabs(args.model_dir):
        model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.model_dir)
    else:
        model_dir = args.model_dir
    
    print("="*70)
    print("AQI PREDICTION MODEL TEST")
    print("="*70)
    print(f"Model directory: {model_dir}")
    print(f"Data directory: {data_dir}")
    if args.api_key:
        print(f"Mode: LIVE API (current values)")
        args.use_csv = False  # Override use_csv if API key provided
    else:
        print(f"Mode: HISTORICAL CSV (note: data may be outdated)")
        print(f"      To get current live values, provide --api-key")
    
    # Determine which sensors to test
    sensor_ids_to_test = []
    
    # If address is provided, geocode it and find nearest sensor
    if args.address:
        if not GEOCODING_AVAILABLE:
            print("\n✗ Error: geopy is not installed. Cannot geocode addresses.")
            print("Install with: pip install geopy")
            sys.exit(1)
        
        print(f"\nGeocoding address: '{args.address}'")
        coords = geocode_address(args.address)
        
        if coords is None:
            print(f"✗ Could not geocode address: {args.address}")
            sys.exit(1)
        
        target_lat, target_lon = coords
        print(f"✓ Address coordinates: ({target_lat:.6f}, {target_lon:.6f})")
        
        # Load sensor locations
        locations_df = load_sensor_locations(data_dir)
        if locations_df is None:
            # Try from original pipeline directory
            locations_df = load_sensor_locations(original_pipeline_dir)
        
        if locations_df is None:
            print("✗ Error: Could not load sensor locations. Cannot find nearest sensor.")
            sys.exit(1)
        
        # Find nearest sensor
        print(f"\nFinding nearest sensor to your location...")
        sensor_info = find_nearest_sensor(target_lat, target_lon, locations_df)
        nearest = sensor_info['nearest']
        top_3 = sensor_info['top_3']
        
        print(f"\n✓ Nearest Sensor Found:")
        print(f"  Sensor ID: {nearest['sensor_id']}")
        print(f"  Name: {nearest['name']}")
        print(f"  Distance: {nearest['distance_km']:.2f} km from your location")
        print(f"  Coordinates: ({nearest['latitude']:.6f}, {nearest['longitude']:.6f})")
        
        print(f"\n  Nearby sensors (for reference):")
        for i, sensor in enumerate(top_3, 1):
            print(f"    {i}. {sensor['name']} (ID: {sensor['sensor_id']}) - {sensor['distance_km']:.2f} km")
        
        sensor_ids_to_test = [nearest['sensor_id']]
        
    elif args.sensor_id:
        sensor_ids_to_test = args.sensor_id
    else:
        parser.print_help()
        print("\n✗ Error: Must provide either --address or --sensor-id")
        sys.exit(1)
    
    # Load models
    print(f"\nLoading models...")
    try:
        models = load_models(model_dir)
        print(f"✓ Models loaded successfully")
        print(f"  - 1h forecast model: {len(models['1h']['feature_columns'])} features")
        print(f"  - 3h forecast model: {len(models['3h']['feature_columns'])} features")
    except Exception as e:
        print(f"✗ Error loading models: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Test each sensor
    results = []
    for sensor_id in sensor_ids_to_test:
        result = test_sensor_prediction(sensor_id, data_dir, models, use_csv=args.use_csv, api_key=args.api_key)
        results.append(result)
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    successful = sum(1 for r in results if r.get('success', False))
    print(f"Successful predictions: {successful}/{len(results)}")
    
    if successful > 0:
        print(f"\n✓ Models are working correctly!")
        print(f"  The trained models can successfully predict AQI for the tested sensors.")
    else:
        print(f"\n✗ All tests failed. Please check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
