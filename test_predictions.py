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

# All internal timestamps are America/Los_Angeles local time, timezone-naive.
# Never treat naive timestamps as UTC.

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

# Use root (script directory) for aqi_utils and feature_engineering - matches run_validation_jan_feb_2026
script_dir = os.path.dirname(os.path.abspath(__file__))
original_pipeline_dir = os.path.expanduser("~/Downloads/PAIC Data 2 Months")  # Fallback for sensor locations only
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from aqi_utils import pm25_to_aqi, aqi_to_category, aqi_to_pm25
    from feature_engineering import engineer_features
except ImportError:
    print("Error: Could not import aqi_utils or feature_engineering")
    print(f"Please ensure aqi_utils.py and feature_engineering.py exist in: {script_dir}")
    sys.exit(1)

# Import wind fetching functions - Use Open-Meteo instead of Meteostat
try:
    
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
        # Support both naming conventions: pm25_model_* (legacy) and xgboost_regressor_* (P2-RouteFinder 06_train_model_v2.py)
        pm25_model_path = os.path.join(model_dir, f'pm25_model_{horizon}.pkl')
        regressor_v2_path = os.path.join(model_dir, f'xgboost_regressor_{horizon}.pkl')
        if not os.path.exists(pm25_model_path) and os.path.exists(regressor_v2_path):
            pm25_model_path = regressor_v2_path
        category_model_path = os.path.join(model_dir, f'category_model_{horizon}.pkl')
        classifier_v2_path = os.path.join(model_dir, f'xgboost_classifier_{horizon}.pkl')
        if not os.path.exists(category_model_path) and os.path.exists(classifier_v2_path):
            category_model_path = classifier_v2_path
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
        # Diagnostic: log what we actually loaded (helps verify Render vs local pkl)
        sample = (feature_columns[:12] if len(feature_columns) >= 12 else feature_columns)
        humidity_like = [c for c in feature_columns if 'humidity' in str(c).lower() or 'relative_humidity' in str(c).lower()]
        print(f"[LOAD_MODEL] {horizon}: path={feature_cols_path}, n_features={len(feature_columns)}, sample={sample}, humidity_cols={humidity_like}")
        
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
    """
    Load sensor location data from pickle or CSV.
    Priority order:
    1. Phase 2 sensor file (filtered to 40 sensors used in training) - matches trained models
    2. Current directory sensor file
    3. Original pipeline directory sensor file
    4. CSV fallback
    
    Note: Phase 2 QC removed 2 sensors (17895, 165691), so we filter to only the 40 sensors
    that were actually used in model training.
    """
    # Phase 2 sensor file (highest priority - matches trained models)
    phase2_pkl = os.path.join(data_dir, 'P2-RouteFinder', 'data', 'sensor_locations', 'sensor_locations.pkl')
    phase2_csv = os.path.join(data_dir, 'P2-RouteFinder', 'data', 'sensor_locations', 'sensor_locations.csv')
    processed_file = os.path.join(data_dir, 'P2-RouteFinder', 'data', 'processed', 'purpleair_qc_cleaned.csv')
    
    # Current directory and original pipeline paths (fallback)
    location_path = os.path.join(data_dir, 'sensor_locations.pkl')
    alt_location_path = os.path.join(original_pipeline_dir, 'sensor_locations.pkl')
    csv_path = os.path.join(original_pipeline_dir, 'sensor_locations.csv')
    
    # Sensors that were dropped during QC (not used in training)
    # QC report shows: 17895 and 165691 were dropped
    dropped_sensors = {17895, 165691}
    
    # Try Phase 2 pickle file first - filter to only sensors used in training
    if os.path.exists(phase2_pkl):
        try:
            with open(phase2_pkl, 'rb') as f:
                locations_df = pickle.load(f)
            
            # Filter to only sensors that were actually used in training
            # Option 1: Use processed dataset to get exact sensor list
            if os.path.exists(processed_file):
                try:
                    processed_df = pd.read_csv(processed_file, usecols=['sensor_id'], nrows=1)
                    # Read just to get column, then get unique sensors
                    training_sensors = set(pd.read_csv(processed_file, usecols=['sensor_id'])['sensor_id'].unique())
                    locations_df = locations_df[locations_df['sensor_id'].isin(training_sensors)].copy()
                except Exception:
                    # Fallback: filter out known dropped sensors
                    locations_df = locations_df[~locations_df['sensor_id'].isin(dropped_sensors)].copy()
            else:
                # Fallback: filter out known dropped sensors
                locations_df = locations_df[~locations_df['sensor_id'].isin(dropped_sensors)].copy()
            
            print(f"Loaded Phase 2 sensor locations: {len(locations_df)} sensors (filtered from QC)")
            return locations_df
        except Exception as e:
            print(f"Warning: Could not load Phase 2 locations from {phase2_pkl}: {e}")
    
    # Try Phase 2 CSV file
    if os.path.exists(phase2_csv):
        try:
            locations_df = pd.read_csv(phase2_csv)
            if 'sensor_id' in locations_df.columns:
                locations_df['sensor_id'] = locations_df['sensor_id'].astype(int)
            
            # Filter to only sensors used in training
            if os.path.exists(processed_file):
                try:
                    training_sensors = set(pd.read_csv(processed_file, usecols=['sensor_id'])['sensor_id'].unique())
                    locations_df = locations_df[locations_df['sensor_id'].isin(training_sensors)].copy()
                except Exception:
                    locations_df = locations_df[~locations_df['sensor_id'].isin(dropped_sensors)].copy()
            else:
                locations_df = locations_df[~locations_df['sensor_id'].isin(dropped_sensors)].copy()
            
            print(f"Loaded Phase 2 sensor locations (CSV): {len(locations_df)} sensors (filtered from QC)")
            return locations_df
        except Exception as e:
            print(f"Warning: Could not load Phase 2 locations from CSV {phase2_csv}: {e}")
    
    # Try current directory pickle file
    if os.path.exists(location_path):
        try:
            with open(location_path, 'rb') as f:
                locations_df = pickle.load(f)
            print(f"Loaded sensor locations from current directory: {len(locations_df)} sensors")
            return locations_df
        except Exception as e:
            print(f"Warning: Could not load locations from {location_path}: {e}")
    
    # Try original pipeline directory pickle file
    if os.path.exists(alt_location_path):
        try:
            with open(alt_location_path, 'rb') as f:
                locations_df = pickle.load(f)
            print(f"Loaded sensor locations from original pipeline: {len(locations_df)} sensors")
            return locations_df
        except Exception as e:
            print(f"Warning: Could not load locations from {alt_location_path}: {e}")
    
    # Try CSV file as last resort
    if os.path.exists(csv_path):
        try:
            locations_df = pd.read_csv(csv_path)
            if 'sensor_id' in locations_df.columns:
                locations_df['sensor_id'] = locations_df['sensor_id'].astype(int)
            print(f"Loaded sensor locations from CSV: {len(locations_df)} sensors")
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


def fetch_historical_sensor_data_api(api_key, sensor_id, hours=24, average=30):
    """
    Fetch historical sensor data from PurpleAir API for the last N hours.
    
    Args:
        api_key: PurpleAir API read key
        sensor_id: Sensor ID
        hours: Number of hours of history to fetch (default: 24)
        average: Average period in minutes (default: 30 for 30-minute averages)
        
    Returns:
        DataFrame with historical sensor data, standardized to PST and resampled to 30-min intervals
    """
    import requests
    
    # Calculate time range
    end_time = pd.Timestamp.now(tz='UTC')
    start_time = end_time - pd.Timedelta(hours=hours)
    
    url = f"https://api.purpleair.com/v1/sensors/{sensor_id}/history"
    headers = {'X-API-Key': api_key}
    params = {
        'start_timestamp': int(start_time.timestamp()),
        'end_timestamp': int(end_time.timestamp()),
        'average': average,
        'fields': 'pm2.5_atm'  # PM2.5 only; temp/humidity from Open-Meteo (more reliable)
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'data' not in data or len(data['data']) == 0:
            print(f"⚠ No historical data returned from API for sensor {sensor_id}")
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(data['data'], columns=data['fields'])
        
        # Convert timestamp from Unix seconds to datetime
        df['time_stamp'] = pd.to_datetime(df['time_stamp'], unit='s', utc=True)
        
        # Standardize column names
        if 'pm2.5_atm' in df.columns:
            df = df.rename(columns={'pm2.5_atm': 'pm2_5_atm'})
        
        # Add sensor_id
        df['sensor_id'] = int(sensor_id)
        
        # Convert to PST (America/Los_Angeles) and make timezone-naive
        tz_pst = 'America/Los_Angeles'
        df['time_stamp'] = df['time_stamp'].dt.tz_convert(tz_pst).dt.tz_localize(None)
        
        # Resample to 30-minute intervals (:00/:30) if needed
        # PurpleAir API should already return 30-min averages, but we'll ensure alignment
        df = df.set_index('time_stamp')
        
        # Resample to 30-min intervals, taking the last value in each interval
        df_resampled = df.resample('30min', label='right', closed='right').last()
        
        # Forward fill any missing intervals (up to 2 hours)
        df_resampled = df_resampled.ffill(limit=4)
        
        # Reset index
        df_resampled = df_resampled.reset_index()
        df_resampled.rename(columns={'index': 'time_stamp'}, inplace=True)
        
        # Ensure timestamps are on :00 or :30 minutes
        df_resampled['time_stamp'] = df_resampled['time_stamp'].dt.floor('30min')
        
        # Sort by timestamp
        df_resampled = df_resampled.sort_values('time_stamp').reset_index(drop=True)
        
        print(f"✓ Fetched {len(df_resampled)} historical rows from API (last {hours} hours)")
        print(f"  Date range: {df_resampled['time_stamp'].min()} to {df_resampled['time_stamp'].max()}")
        
        return df_resampled
        
    except requests.exceptions.RequestException as e:
        print(f"⚠ Error fetching historical data from API: {e}")
        return None
    except Exception as e:
        print(f"⚠ Error processing historical data: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_current_sensor_data_api(api_key, sensor_id, max_retries=3):
    """
    Fetch current live sensor data from PurpleAir API with retry logic.
    
    Args:
        api_key: PurpleAir API read key
        sensor_id: Sensor ID
        max_retries: Maximum number of retry attempts (default: 3)
        
    Returns:
        DataFrame with current sensor data (single row), standardized to PST
    """
    import requests
    import time
    
    url = f"https://api.purpleair.com/v1/sensors/{sensor_id}"
    headers = {'X-API-Key': api_key}
    params = {'fields': 'pm2.5_atm'}  # PM2.5 only; temp/humidity from Open-Meteo
    
    # Increased timeout for paid Render account (network latency may be higher)
    timeout = 30  # Increased from 10 to 30 seconds
    
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            if 'sensor' not in data:
                raise ValueError("No sensor data in API response")
            
            sensor_info = data['sensor']
            
            # Get current time in PST
            tz_pst = 'America/Los_Angeles'
            current_time_pst = pd.Timestamp.now(tz='UTC').tz_convert(tz_pst).tz_localize(None)
            
            # Round to nearest 30-minute interval (:00 or :30)
            current_time_pst = current_time_pst.floor('30min')
            
            # Create DataFrame with current data
            current_data = {
                'sensor_id': int(sensor_id),
                'time_stamp': current_time_pst,
                'humidity': sensor_info.get('humidity'),
                'temperature': sensor_info.get('temperature'),
                'pm2_5_atm': sensor_info.get('pm2.5_atm'),
                'latitude': sensor_info.get('latitude'),
                'longitude': sensor_info.get('longitude'),
                'name': sensor_info.get('name', f"Sensor {sensor_id}")
            }
            
            return pd.DataFrame([current_data])
            
        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                print(f"⚠ PurpleAir API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"Error fetching current data from API: Timeout after {max_retries} attempts (timeout={timeout}s). PurpleAir API may be slow or unavailable.")
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"⚠ PurpleAir API error (attempt {attempt + 1}/{max_retries}): {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"Error fetching current data from API: {e}")
        except Exception as e:
            # Non-retryable errors (e.g., invalid response format)
            raise Exception(f"Error fetching current data from API: {e}")
    
    # Should not reach here, but just in case
    raise Exception(f"Error fetching current data from API: {last_error}")


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
    
    # Get date range from dataframe (pipeline standard: PST-naive everywhere)
    tz_local = 'America/Los_Angeles'
    start_date = pd.to_datetime(df['time_stamp'].min())
    end_date = pd.to_datetime(df['time_stamp'].max())
    if start_date.tz is not None:
        start_date = start_date.tz_convert(tz_local).tz_localize(None)
    if end_date.tz is not None:
        end_date = end_date.tz_convert(tz_local).tz_localize(None)
    current_time_local = pd.Timestamp.now(tz=tz_local).tz_localize(None)
    
    print(f"\nFetching wind direction data from Open-Meteo for prediction...")
    print(f"  Location: ({latitude}, {longitude})")
    print(f"  Date range: {start_date} to {end_date}")
    
    try:
        # Determine if we need historical or forecast data
        # Use Historical API when sensor data spans past dates (needed for 24h coverage)
        # Forecast API only returns from 00:00 today - would miss yesterday's hours
        today_start = pd.Timestamp.now(tz=tz_local).floor('D').tz_localize(None)
        needs_historical = start_date < today_start
        hours_ago = (current_time_local - end_date).total_seconds() / 3600
        
        if not needs_historical and hours_ago < 6:
            # Use forecast API only when all data is from today (no past dates)
            print(f"  Using Open-Meteo Forecast API (data is {hours_ago:.1f} hours old)")
            forecast_days = max(1, int((end_date - start_date).total_seconds() / 86400) + 1)
            forecast_days = min(forecast_days, 7)  # Open-Meteo forecast limit
            
            # Import here to ensure it's available
            from fetch_wind_openmeteo import fetch_forecast_wind_openmeteo
            wind_df = fetch_forecast_wind_openmeteo(latitude, longitude, forecast_days=forecast_days, height_meters=10)
            
            if wind_df is None or len(wind_df) == 0:
                print("⚠ Could not fetch forecast wind data from Open-Meteo.")
                return None
            
            # Filter to the date range we need (start_date/end_date already PST-naive)
            start_h = start_date.floor('h')
            end_h = end_date.ceil('h')
            wind_df = wind_df[
                (wind_df['timestamp_hour'] >= start_h) &
                (wind_df['timestamp_hour'] <= end_h)
            ].copy()
            
            print(f"✓ Weather data fetched from Open-Meteo Forecast: {len(wind_df)} hourly records")
            
        else:
            # Use historical API when data spans past dates (full 24h coverage)
            # Open-Meteo is hourly only; we need one record per hour for the PurpleAir window (24h = 24–25 hours)
            print(f"  Using Open-Meteo Historical API (data is {hours_ago:.1f} hours old)")
            from fetch_wind_openmeteo import fetch_historical_wind_openmeteo
            wind_df = fetch_historical_wind_openmeteo(
                latitude, longitude,
                start_date, end_date,
                height_meters=10
            )
            if wind_df is None or len(wind_df) == 0:
                print("⚠ Could not fetch historical wind data from Open-Meteo.")
                return None
            # Keep only hours that cover our PurpleAir window (API returns full calendar days)
            start_h = start_date.floor('h')
            end_h = end_date.ceil('h')
            wind_df = wind_df[
                (wind_df['timestamp_hour'] >= start_h) &
                (wind_df['timestamp_hour'] <= end_h)
            ].copy()
            print(f"✓ Wind data fetched from Open-Meteo Historical: {len(wind_df)} hourly records (covers {len(wind_df)}h for 30-min PurpleAir window)")
        
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
    Merge Open-Meteo weather (wind, temperature, humidity) into prediction dataframe.
    All weather except PM2.5 comes from Open-Meteo (matches training).
    
    Args:
        df: Sensor data DataFrame (PM2.5 from PurpleAir)
        wind_data: Tuple of (weather_df, station_info) or None
        
    Returns:
        DataFrame with merged weather (temperature_2m, relative_humidity_2m, wind)
    """
    if wind_data is None:
        # No weather data available, create empty columns
        df['wdir'] = np.nan
        df['wind_dir_x'] = np.nan
        df['wind_dir_y'] = np.nan
        df['wind_speed_10m'] = np.nan
        df['temperature_2m'] = np.nan
        df['relative_humidity_2m'] = np.nan
        return df
    
    wind_df, station_info = wind_data
    tz_local = 'America/Los_Angeles'
    
    # Drop placeholder weather columns from df so merge doesn't create _x/_y duplicates
    drop_before_merge = [c for c in ['wdir', 'wind_dir_x', 'wind_dir_y', 'wind_speed_10m', 'temperature_2m', 'relative_humidity_2m'] if c in df.columns]
    df = df.drop(columns=drop_before_merge, errors='ignore')
    
    # Build merge columns: wind + temp + humidity (Open-Meteo returns all in training schema)
    wind_df = wind_df.copy()
    merge_cols = ['timestamp_hour', 'wdir']
    if 'wind_speed_10m' in wind_df.columns:
        merge_cols.append('wind_speed_10m')
    elif 'wspd' in wind_df.columns:
        wind_df['wind_speed_10m'] = wind_df['wspd'] * 0.621371  # km/h -> mph
        merge_cols.append('wind_speed_10m')
    if 'temperature_2m' in wind_df.columns:
        merge_cols.append('temperature_2m')
    if 'relative_humidity_2m' in wind_df.columns:
        merge_cols.append('relative_humidity_2m')
    
    # Convert timestamps: pipeline standard is PST-naive. Do not assume naive = UTC (would shift 8h).
    df = df.copy()
    df['time_stamp'] = pd.to_datetime(df['time_stamp'])
    if getattr(df['time_stamp'].dtype, 'tz', None) is not None:
        df['time_stamp'] = df['time_stamp'].dt.tz_convert(tz_local).dt.tz_localize(None)
    df['timestamp_hour'] = df['time_stamp'].dt.floor('h')
    
    wind_df = wind_df.copy()
    wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour']).dt.floor('h')
    if getattr(wind_df['timestamp_hour'].dtype, 'tz', None) is not None:
        wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Merge Open-Meteo weather (wind + temp + humidity)
    df = df.merge(wind_df[merge_cols],
                  on='timestamp_hour',
                  how='left')
    matched = df['wdir'].notna().mean() if 'wdir' in df.columns else 0
    print(f"[DEBUG merge] matched_wdir_pct={matched*100:.1f}%  "
          f"sensor_hours=({df['timestamp_hour'].min()} .. {df['timestamp_hour'].max()})  "
          f"wind_hours=({wind_df['timestamp_hour'].min()} .. {wind_df['timestamp_hour'].max()})")
    
    # Ensure required columns exist
    for col in ['wind_speed_10m', 'temperature_2m', 'relative_humidity_2m']:
        if col not in df.columns:
            df[col] = np.nan
    
    # Forward-fill with 6-hour limit (same as training)
    df = df.sort_values('time_stamp').reset_index(drop=True)
    weather_cols_fill = ['wdir', 'wind_speed_10m', 'temperature_2m', 'relative_humidity_2m']
    for c in weather_cols_fill:
        if c in df.columns:
            df[c] = df.groupby('sensor_id')[c].ffill(limit=6)
            df[c] = df.groupby('sensor_id')[c].bfill(limit=1)
    
    # Replace any remaining NaN/None with 0 for feature engineering (avoids diff() errors)
    for c in ['temperature_2m', 'relative_humidity_2m']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
    # Convert to x, y components
    mask = df['wdir'].notna()
    df.loc[mask, 'wind_dir_x'] = np.cos(np.radians(df.loc[mask, 'wdir']))
    df.loc[mask, 'wind_dir_y'] = np.sin(np.radians(df.loc[mask, 'wdir']))
    df.loc[~mask, 'wind_dir_x'] = np.nan
    df.loc[~mask, 'wind_dir_y'] = np.nan
    
    wdir_pct = (df['wdir'].notna().sum() / len(df)) * 100
    temp_pct = (df['temperature_2m'].notna().sum() / len(df)) * 100 if 'temperature_2m' in df.columns else 0
    rh_pct = (df['relative_humidity_2m'].notna().sum() / len(df)) * 100 if 'relative_humidity_2m' in df.columns else 0
    print(f"✓ Open-Meteo weather merged: wdir {wdir_pct:.1f}%, temp {temp_pct:.1f}%, humidity {rh_pct:.1f}% coverage")
    
    return df


def log_feature_pipeline_signature(df_before_engineering, feature_row, feature_columns, context="prediction"):
    """
    Log a one-line "signature" to verify the same fixed pipeline is used across contexts.
    Helps diagnose API vs test-runner vs training alignment.
    
    Args:
        df_before_engineering: Raw df before engineer_features (for schema check)
        feature_row: Engineered feature row (single row DataFrame) for model
        feature_columns: List of feature names expected by model
        context: Label for logs (e.g. "API", "test", "validation")
    """
    # Schema check: relative_humidity_2m / temperature_2m exist before lag/rolling
    has_rh = 'relative_humidity_2m' in df_before_engineering.columns or 'humidity' in df_before_engineering.columns
    has_temp = 'temperature_2m' in df_before_engineering.columns or 'temperature' in df_before_engineering.columns
    schema_ok = "rh,temp:OK" if (has_rh and has_temp) else f"rh:{has_rh},temp:{has_temp}"
    
    # Missing features: columns expected by model but missing or NaN in feature_row
    missing_names = []
    nan_count = 0
    for i, col in enumerate(feature_columns):
        if col not in feature_row.columns:
            missing_names.append(col)
        else:
            val = feature_row[col].iloc[0] if len(feature_row) > 0 else feature_row[col].values[0]
            if pd.isna(val) or (isinstance(val, float) and np.isnan(val)):
                nan_count += 1
                missing_names.append(col)
    
    missing_count = len(missing_names)
    top_10 = missing_names[:10] if missing_names else []
    
    msg = (f"[FEATURE_SIGNATURE {context}] missing_count={missing_count}, "
           f"schema={schema_ok}, top_missing={top_10}")
    print(msg)
    return {"missing_count": missing_count, "schema_ok": has_rh and has_temp, "top_missing": top_10}


def dump_feature_row_sanity(feature_row, feature_columns=None, sensor_id=None, timestamp=None):
    """
    Dump actual feature values for one sensor+timestamp to verify pipeline alignment.
    Logs temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m,
    and a few lag features; confirms they are non-zero and plausible.
    """
    keys = ['temperature_2m', 'relative_humidity_2m', 'wind_speed_10m', 'wind_direction_10m',
            'wdir', 'wind_dir_x', 'wind_dir_y',
            'temperature_2m_lag_1', 'relative_humidity_2m_lag_1', 'pm2_5_atm', 'pm2_5_atm_lag_1']
    found = {}
    for k in keys:
        if k in feature_row.columns:
            v = feature_row[k].iloc[0] if len(feature_row) > 0 else feature_row[k].values[0]
            found[k] = float(v) if not (pd.isna(v) or (isinstance(v, float) and np.isnan(v))) else "NaN"
    
    hdr = f"[SANITY_DUMP] sensor={sensor_id} ts={timestamp}" if sensor_id or timestamp else "[SANITY_DUMP]"
    print(f"{hdr} {found}")
    return found


def log_live_data_integrity_weather(df):
    """
    Log weather coverage and ranges from merged dataframe (last 24h window).
    If any coverage < 95%, log [WARNING] Low weather coverage detected (do not stop).
    """
    n = len(df)
    if n == 0:
        return
    pct = lambda col: (df[col].notna().sum() / n * 100) if col in df.columns else 0.0
    temp_pct = pct('temperature_2m')
    rh_pct = pct('relative_humidity_2m')
    wind_pct = pct('wind_speed_10m')
    wdir_pct = pct('wdir')
    temp_range = f"{df['temperature_2m'].min():.1f}-{df['temperature_2m'].max():.1f}" if 'temperature_2m' in df.columns and df['temperature_2m'].notna().any() else "n/a"
    rh_range = f"{df['relative_humidity_2m'].min():.1f}-{df['relative_humidity_2m'].max():.1f}" if 'relative_humidity_2m' in df.columns and df['relative_humidity_2m'].notna().any() else "n/a"
    wind_range = f"{df['wind_speed_10m'].min():.1f}-{df['wind_speed_10m'].max():.1f}" if 'wind_speed_10m' in df.columns and df['wind_speed_10m'].notna().any() else "n/a"
    first_ts = df['time_stamp'].min()
    last_ts = df['time_stamp'].max()
    print(f"[WEATHER_COVERAGE]")
    print(f"temp_pct={temp_pct:.1f}% rh_pct={rh_pct:.1f}% wind_speed_pct={wind_pct:.1f}% wdir_pct={wdir_pct:.1f}%")
    print(f"temp_range={temp_range} F rh_range={rh_range} % wind_range={wind_range} mph")
    print(f"first_ts={first_ts} last_ts={last_ts}")
    if temp_pct < 95 or rh_pct < 95 or wind_pct < 95 or wdir_pct < 95:
        print(f"[WARNING] Low weather coverage detected")


def log_live_data_integrity_pm25(df, current_aqi):
    """Log PM2.5 sanity right before feature engineering: last 6 values, min, max, current_aqi."""
    if 'pm2_5_atm' not in df.columns or len(df) == 0:
        return
    last6 = df['pm2_5_atm'].tail(6).tolist()
    last6 = [round(float(x), 2) if pd.notna(x) else None for x in last6]
    mn = df['pm2_5_atm'].min()
    mx = df['pm2_5_atm'].max()
    mn = round(float(mn), 2) if pd.notna(mn) else None
    mx = round(float(mx), 2) if pd.notna(mx) else None
    print(f"[PM25_SANITY]")
    print(f"last6={last6}")
    print(f"min={mn} max={mx} current_aqi={int(current_aqi)}")


def log_live_parity(sensor_id, current_pm25, current_aqi, predictions, current_row):
    """One-line parity summary after predictions: sensor, pm25, aqi, pred1h, pred3h, temp, rh, wind, wdir."""
    pred1h = predictions['1h']['aqi']
    pred3h = predictions['3h']['aqi']
    temp = current_row.get('temperature_2m') or current_row.get('temperature')
    rh = current_row.get('relative_humidity_2m') or current_row.get('humidity')
    wind = current_row.get('wind_speed_10m')
    wdir = current_row.get('wdir')
    temp = f"{float(temp):.1f}" if pd.notna(temp) else "n/a"
    rh = f"{float(rh):.1f}" if pd.notna(rh) else "n/a"
    wind = f"{float(wind):.1f}" if pd.notna(wind) else "n/a"
    wdir = f"{float(wdir):.0f}" if pd.notna(wdir) else "n/a"
    print(f"[LIVE_PARITY] sensor={sensor_id} pm25={current_pm25:.2f} aqi={int(current_aqi)} pred1h={pred1h} pred3h={pred3h} temp={temp} rh={rh} wind={wind} wdir={wdir}")


def prepare_test_data_from_live_api(api_key, sensor_id, hours=24, data_dir=None):
    """
    Prepare test data using live API history (last 24 hours) instead of stale CSV.
    This ensures fresh historical context for accurate predictions.
    
    Args:
        api_key: PurpleAir API read key
        sensor_id: Sensor ID
        hours: Number of hours of history to fetch (default: 24)
        data_dir: Optional directory for sensor location info
        
    Returns:
        DataFrame with sensor data ready for prediction (standardized to PST, 30-min intervals)
    """
    # Fetch historical data from API (last 24 hours)
    hist_df = fetch_historical_sensor_data_api(api_key, sensor_id, hours=hours)
    
    if hist_df is None or len(hist_df) == 0:
        print(f"⚠ Could not fetch historical data from API, falling back to current data only")
        # Fall back to current data only
        current_df = fetch_current_sensor_data_api(api_key, sensor_id)
        if current_df is None or len(current_df) == 0:
            raise ValueError(f"Could not fetch any data from API for sensor {sensor_id}")
        return current_df
    
    # Fetch current live data
    current_df = fetch_current_sensor_data_api(api_key, sensor_id)
    if current_df is None or len(current_df) == 0:
        print(f"⚠ Could not fetch current data, using historical data only")
        return hist_df
    
    # Combine historical and current data
    # Remove duplicate if current timestamp matches last historical timestamp
    hist_last_time = hist_df['time_stamp'].iloc[-1]
    current_time = current_df['time_stamp'].iloc[0]
    
    if hist_last_time == current_time:
        # Current data is duplicate of last historical row, use historical only
        print(f"  Current data timestamp matches last historical row, using historical data")
        combined_df = hist_df.copy()
    else:
        # Combine and sort
        combined_df = pd.concat([hist_df, current_df], ignore_index=True)
        combined_df = combined_df.sort_values('time_stamp').reset_index(drop=True)
    
    # Add location data from sensor list so we always have lat/lon for Open-Meteo (API may not return them)
    if data_dir:
        locations_df = load_sensor_locations(data_dir)
        if locations_df is not None:
            sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
            if not sensor_locs.empty:
                combined_df['latitude'] = sensor_locs.iloc[0]['latitude']
                combined_df['longitude'] = sensor_locs.iloc[0]['longitude']
                combined_df['name'] = sensor_locs.iloc[0].get('name', f"Sensor {sensor_id}")
    
    # Ensure wind columns exist BEFORE fetching (in case fetch fails)
    if 'wdir' not in combined_df.columns:
        combined_df['wdir'] = np.nan
        combined_df['wind_dir_x'] = np.nan
        combined_df['wind_dir_y'] = np.nan
    
    # Fetch and merge wind data
    if WIND_FETCHING_AVAILABLE and 'latitude' in combined_df.columns and combined_df['latitude'].notna().any():
        try:
            sensor_lat = combined_df['latitude'].iloc[0]
            sensor_lon = combined_df['longitude'].iloc[0]
            wind_data = fetch_current_wind_data_for_prediction(combined_df, sensor_lat, sensor_lon)
            if wind_data is not None:
                combined_df = merge_wind_data_for_prediction(combined_df, wind_data)
        except Exception as e:
            # Wind fetch failed, but columns already exist (filled with NaN above)
            print(f"Warning: Wind data fetch failed: {e}")
    
    # Final check: ensure wind columns exist
    if 'wdir' not in combined_df.columns:
        combined_df['wdir'] = np.nan
    if 'wind_dir_x' not in combined_df.columns:
        combined_df['wind_dir_x'] = np.nan
    if 'wind_dir_y' not in combined_df.columns:
        combined_df['wind_dir_y'] = np.nan
    
    print(f"✓ Prepared {len(combined_df)} rows from live API (fresh history)")
    print(f"  Date range: {combined_df['time_stamp'].min()} to {combined_df['time_stamp'].max()}")
    
    return combined_df


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
    
    # Ensure wind columns exist BEFORE fetching (in case fetch fails)
    if 'wdir' not in df.columns:
        df['wdir'] = np.nan
        df['wind_dir_x'] = np.nan
        df['wind_dir_y'] = np.nan
    
    # Fetch and merge wind data
    if WIND_FETCHING_AVAILABLE and 'latitude' in df.columns and df['latitude'].notna().any():
        try:
            sensor_lat = df['latitude'].iloc[0]
            sensor_lon = df['longitude'].iloc[0]
            wind_data = fetch_current_wind_data_for_prediction(df, sensor_lat, sensor_lon)
            if wind_data is not None:
                df = merge_wind_data_for_prediction(df, wind_data)
        except Exception as e:
            # Wind fetch failed, but columns already exist (filled with NaN above)
            print(f"Warning: Wind data fetch failed in prepare_test_data_from_csv: {e}")
    
    # Final check: ensure wind columns exist
    if 'wdir' not in df.columns:
        df['wdir'] = np.nan
    if 'wind_dir_x' not in df.columns:
        df['wind_dir_x'] = np.nan
    if 'wind_dir_y' not in df.columns:
        df['wind_dir_y'] = np.nan
    
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
    
    # Drop PurpleAir humidity/temperature if present (we use Open-Meteo only) to avoid None overwriting
    for drop_col in ['humidity', 'temperature']:
        if drop_col in df.columns:
            df = df.drop(columns=[drop_col])
    
    # Ensure value_cols (pm2_5_atm, temperature_2m, relative_humidity_2m) have no None - feature_engineering create_lag_features diff() fails otherwise
    for col in ['pm2_5_atm', 'temperature_2m', 'relative_humidity_2m']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
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


def make_predictions(models, feature_row, feature_columns, current_pm25=None, current_aqi=None, 
                     ensemble_weight=None, ensemble_weight_1h_override=None, ensemble_weight_3h_override=None,
                     max_worsening_rate=0.2, bias_correction=0.0, bias_correction_3h=None):
    """
    Make predictions using the loaded models with optional ensemble with persistence.
    Uses regime-based ensemble weights (README / run_ensemble_evaluation.py):
    3 AQI buckets: 0–50, 51–100, 100+
    Blend in AQI space: ensemble_aqi = w_ml * pred_ml_aqi + (1 - w_ml) * current_aqi
    0–50: 1h 50/50, 3h 70/30 | 51–100: 1h 60/40, 3h 85/15 | 100+: 1h 40/60, 3h 40/60
    Phase 2.1 Refinements: 3h-only bias correction and stricter 3h rate-of-change cap.
    Phase 2.1.5: Direction-aware bias correction - applies only when predicting improvement
                 (health-conservative: limits false reassurance, allows worsening when supported).
    
    Args:
        models: Dictionary with models for '1h' and '3h'
        feature_row: DataFrame row with engineered features
        feature_columns: List of feature column names expected by model
        current_pm25: Current PM2.5 value for persistence baseline (optional)
        current_aqi: Current AQI value (optional, used for regime-based weighting)
        ensemble_weight: Base weight for ML prediction (deprecated, now uses 3-bucket weights)
        ensemble_weight_1h_override: If set, overrides 1h ML weight (e.g. 0.6).
        ensemble_weight_3h_override: If set, overrides 3h ML weight (e.g. 0.85).
        max_worsening_rate: Maximum allowed worsening rate per hour (default 0.2 = 20%)
        bias_correction: Bias correction factor for 1h (default 0.0 = disabled, not recommended)
        bias_correction_3h: Bias correction for 3h only (default None = auto from validation, ~3.3 μg/m³)
        
    Returns:
        Dictionary with predictions for both horizons
    """
    from aqi_utils import pm25_to_aqi, aqi_to_category, aqi_to_pm25
    
    predictions = {}
    
    # Calculate current AQI if not provided
    if current_aqi is None and current_pm25 is not None:
        current_aqi = pm25_to_aqi(current_pm25)
    
    # Determine regime-based ensemble weights (README / run_ensemble_evaluation.py)
    # 3 AQI buckets: 0–50, 51–100, 100+; blend in AQI space
    # 0–50: 1h 50/50, 3h 70/30 | 51–100: 1h 60/40, 3h 85/15 | 100+: 1h 40/60, 3h 40/60
    if current_aqi is not None:
        if current_aqi < 50:
            ensemble_weights = {'1h': 0.5, '3h': 0.7}
            bucket_name = '0-50'
        elif current_aqi < 100:
            ensemble_weights = {'1h': 0.6, '3h': 0.85}
            bucket_name = '51-100'
        else:
            ensemble_weights = {'1h': 0.4, '3h': 0.4}
            bucket_name = '100+'
    else:
        ensemble_weights = {'1h': 0.6, '3h': 0.85}  # fallback
        bucket_name = 'fallback'
    
    if ensemble_weight_1h_override is not None:
        ensemble_weights['1h'] = float(ensemble_weight_1h_override)
    if ensemble_weight_3h_override is not None:
        ensemble_weights['3h'] = float(ensemble_weight_3h_override)
    
    for horizon in ['1h', '3h']:
        model_info = models[horizon]
        
        # Get regime-specific ensemble weight
        horizon_ensemble_weight = ensemble_weights[horizon]
        
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
            missing_idx = np.where(np.isnan(X[0]))[0]
            missing_names = [feature_columns[i] for i in missing_idx[:10]]
            print(f"  Note: {nan_count} feature values are NaN (filled with 0): top_missing={missing_names}")
            # Fill with 0 to match training behavior (training does fillna(0))
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Predict PM2.5 using ML model
        pm25_model = model_info['pm25_model']
        ml_predicted_pm25 = pm25_model.predict(X)[0]
        
        # Ensure reasonable values (minimum 0.1 to avoid unrealistic 0.0 predictions)
        ml_predicted_pm25 = max(0.1, min(1000.0, float(ml_predicted_pm25)))
        
        # Ensemble with persistence if current_pm25 is provided (README: blend in AQI space)
        if current_pm25 is not None and not pd.isna(current_pm25):
            pred_ml_aqi = pm25_to_aqi(ml_predicted_pm25)
            cur_aqi = current_aqi if current_aqi is not None else pm25_to_aqi(current_pm25)
            ensemble_aqi = horizon_ensemble_weight * pred_ml_aqi + (1 - horizon_ensemble_weight) * cur_aqi
            ensemble_aqi = max(0, min(500, round(ensemble_aqi)))
            predicted_pm25 = float(aqi_to_pm25(ensemble_aqi))
            print(f"  Using ensemble: {int(horizon_ensemble_weight*100)}% ML + {int((1-horizon_ensemble_weight)*100)}% persistence (AQI bucket: {bucket_name})")
            
            # Apply rate-of-change cap (Phase 2.1)
            # Limit how much the prediction can worsen per hour
            if current_pm25 > 0:
                hours_ahead = 1.0 if horizon == '1h' else 3.0
                max_allowed = current_pm25 * (1 + max_worsening_rate * hours_ahead)
                if predicted_pm25 > max_allowed:
                    predicted_pm25 = max_allowed
                    # Note: We don't cap improvements, only worsening
            
            # Apply stricter 3h rate-of-change cap (Phase 2.1 Refinements)
            if horizon == '3h' and current_aqi is not None:
                if current_aqi < 100:
                    # Normal regime: cap worsening to +30 AQI over 3 hours
                    max_aqi_allowed = current_aqi + 30
                    predicted_aqi_temp = pm25_to_aqi(predicted_pm25)
                    if predicted_aqi_temp > max_aqi_allowed:
                        predicted_pm25 = float(aqi_to_pm25(max_aqi_allowed))
                else:
                    # High AQI regime: optional tighter cap (+20 AQI over 3h)
                    max_aqi_allowed = current_aqi + 20
                    predicted_aqi_temp = pm25_to_aqi(predicted_pm25)
                    if predicted_aqi_temp > max_aqi_allowed:
                        predicted_pm25 = float(aqi_to_pm25(max_aqi_allowed))
            
            # Apply bias correction (Phase 2.1 Refinements: 3h only)
            # Phase 2.1.5: Direction-aware bias correction (health-conservative)
            if horizon == '3h':
                # Use provided bias_correction_3h or default from validation
                if bias_correction_3h is None:
                    # Default: 22% of estimated 3h bias from validation (9.31 μg/m³)
                    # Adjusted from 0.35 to 0.22 to avoid overcorrection
                    estimated_3h_bias = 9.31
                    correction_factor = 0.22
                    bias_correction_3h = correction_factor * estimated_3h_bias
                
                # Store pre-bias value for logging
                predicted_pm25_pre_bias = predicted_pm25
                bias_applied = False
                applied_correction = 0.0
                
                # Phase 2.1.5: Direction-aware bias correction (health-conservative)
                # Apply bias correction ONLY when predicting improvement (pred < current)
                # This limits false reassurance while allowing worsening when supported
                if current_pm25 is not None and predicted_pm25 < current_pm25:
                    # Predicting improvement - limit optimism by moving toward current
                    delta = current_pm25 - predicted_pm25
                    applied_correction = min(bias_correction_3h, delta)
                    predicted_pm25 = predicted_pm25 + applied_correction  # Move toward current
                    bias_applied = True
                # If pred >= current (worsening/flat), do NOT apply bias correction
                # This allows worsening when evidence supports it (health-conservative)
                
                # Temporary diagnostic logging for 3h forecast
                print(f"  [3h DIAGNOSTIC] current_pm25={current_pm25:.2f}, raw_ML={ml_predicted_pm25:.2f}, "
                      f"ensemble_pre_bias={predicted_pm25_pre_bias:.2f}, bias_applied={bias_applied}, "
                      f"bias_amount={bias_correction_3h:.2f}, applied_correction={applied_correction:.2f}, "
                      f"final_3h={predicted_pm25:.2f}")
            elif bias_correction > 0:
                # 1h bias correction (not recommended, but kept for compatibility)
                predicted_pm25 = max(0.1, predicted_pm25 - bias_correction)
            
            # Ensure reasonable values after ensemble (minimum 0.1 to avoid unrealistic 0.0)
            predicted_pm25 = max(0.1, min(1000.0, predicted_pm25))
        else:
            # No ensemble, use ML prediction only
            predicted_pm25 = ml_predicted_pm25
            
            # Apply stricter 3h rate-of-change cap (Phase 2.1 Refinements)
            if horizon == '3h' and current_aqi is not None:
                predicted_aqi_temp = pm25_to_aqi(predicted_pm25)
                if current_aqi < 100:
                    max_aqi_allowed = current_aqi + 30
                    if predicted_aqi_temp > max_aqi_allowed:
                        predicted_pm25 = aqi_to_pm25(max_aqi_allowed)
                else:
                    max_aqi_allowed = current_aqi + 20
                    if predicted_aqi_temp > max_aqi_allowed:
                        predicted_pm25 = aqi_to_pm25(max_aqi_allowed)
            
            # Apply bias correction (Phase 2.1 Refinements: 3h only)
            # FIX: Make bias correction conditional and prevent overshoot
            # Only subtract the "excess above current", not a fixed amount
            if horizon == '3h':
                if bias_correction_3h is None:
                    estimated_3h_bias = 9.31
                    correction_factor = 0.22  # Adjusted from 0.35 to 0.22
                    bias_correction_3h = correction_factor * estimated_3h_bias
                
                # Store pre-bias value for logging
                predicted_pm25_pre_bias = predicted_pm25
                bias_applied = False
                applied_correction = 0.0
                
                # Phase 2.1.5: Direction-aware bias correction (health-conservative)
                # Apply bias correction ONLY when predicting improvement (pred < current)
                # This limits false reassurance while allowing worsening when supported
                if current_pm25 is not None and predicted_pm25 < current_pm25:
                    # Predicting improvement - limit optimism by moving toward current
                    delta = current_pm25 - predicted_pm25
                    applied_correction = min(bias_correction_3h, delta)
                    predicted_pm25 = predicted_pm25 + applied_correction  # Move toward current
                    bias_applied = True
                # If pred >= current (worsening/flat), do NOT apply bias correction
                # This allows worsening when evidence supports it (health-conservative)
                
                # Temporary diagnostic logging for 3h forecast
                print(f"  [3h DIAGNOSTIC] current_pm25={current_pm25:.2f}, raw_ML={ml_predicted_pm25:.2f}, "
                      f"ensemble_pre_bias={predicted_pm25_pre_bias:.2f}, bias_applied={bias_applied}, "
                      f"bias_amount={bias_correction_3h:.2f}, applied_correction={applied_correction:.2f}, "
                      f"final_3h={predicted_pm25:.2f}")
            elif bias_correction > 0:
                predicted_pm25 = max(0.1, predicted_pm25 - bias_correction)
        
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
        
        # Ensure predicted_pm25 is a scalar float (not numpy array) before rounding
        if isinstance(predicted_pm25, np.ndarray):
            predicted_pm25 = float(predicted_pm25.item())
        else:
            predicted_pm25 = float(predicted_pm25)
        
        pred_dict = {
            'pm25_ugm3': round(predicted_pm25, 2),
            'aqi': int(predicted_aqi),
            'category': predicted_category
        }
        if horizon == '1h':
            pred_dict['ml_pm25_ugm3'] = round(float(ml_predicted_pm25), 2)
        if horizon == '3h':
            pred_dict['ml_pm25_ugm3'] = round(float(ml_predicted_pm25), 2)
        predictions[horizon] = pred_dict
    
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
            if 'temperature_2m' in current_row and pd.notna(current_row.get('temperature_2m')):
                print(f"  Temperature: {current_row['temperature_2m']:.1f}°F (Open-Meteo)")
            elif 'temperature' in current_row and pd.notna(current_row.get('temperature')):
                print(f"  Temperature: {current_row['temperature']:.1f}°F")
            if 'relative_humidity_2m' in current_row and pd.notna(current_row.get('relative_humidity_2m')):
                print(f"  Humidity: {current_row['relative_humidity_2m']:.1f}% (Open-Meteo)")
            elif 'humidity' in current_row and pd.notna(current_row.get('humidity')):
                print(f"  Humidity: {current_row['humidity']:.1f}%")
            if 'latitude' in current_row and pd.notna(current_row['latitude']):
                print(f"  Location: ({current_row['latitude']:.4f}, {current_row['longitude']:.4f})")
        else:
            # Live API mode: fetch 24h history + current from PurpleAir API, plus Open-Meteo wind
            if not api_key:
                raise ValueError("API key required for live data. Use --api-key option or --use-csv for historical data.")
            
            try:
                test_df = prepare_test_data_from_live_api(api_key, sensor_id, hours=24, data_dir=data_dir)
                current_row = test_df.iloc[-1]  # Most recent row
            except Exception as e:
                print(f"⚠ Warning: prepare_test_data_from_live_api failed: {e}")
                print(f"  Falling back to current data only (limited features)")
                current_df = fetch_current_sensor_data_api(api_key, sensor_id)
                if current_df is None or len(current_df) == 0:
                    raise ValueError(f"Could not fetch any data from PurpleAir API for sensor {sensor_id}")
                test_df = current_df.copy()
                if 'latitude' not in test_df.columns or test_df['latitude'].isna().all():
                    locations_df = load_sensor_locations(data_dir)
                    if locations_df is not None:
                        sensor_locs = locations_df[locations_df['sensor_id'] == int(sensor_id)]
                        if not sensor_locs.empty:
                            test_df['latitude'] = sensor_locs.iloc[0]['latitude']
                            test_df['longitude'] = sensor_locs.iloc[0]['longitude']
                if WIND_FETCHING_AVAILABLE and 'latitude' in test_df.columns and test_df['latitude'].notna().any():
                    sensor_lat = test_df['latitude'].iloc[0]
                    sensor_lon = test_df['longitude'].iloc[0]
                    wind_data = fetch_current_wind_data_for_prediction(test_df, sensor_lat, sensor_lon)
                    if wind_data is not None:
                        test_df = merge_wind_data_for_prediction(test_df, wind_data)
                current_row = test_df.iloc[0]
            current_pm25 = current_row['pm2_5_atm']
            current_aqi = pm25_to_aqi(current_pm25)
            current_category = aqi_to_category(current_aqi)
            
            print(f"\nCurrent LIVE Conditions (from PurpleAir API):")
            print(f"  Timestamp: {current_row['time_stamp']}")
            print(f"  PM2.5: {current_pm25:.2f} μg/m³")
            print(f"  AQI: {int(current_aqi)} ({current_category})")
            if 'temperature_2m' in current_row and pd.notna(current_row.get('temperature_2m')):
                print(f"  Temperature: {current_row['temperature_2m']:.1f}°F (Open-Meteo)")
            elif 'temperature' in current_row and pd.notna(current_row.get('temperature')):
                print(f"  Temperature: {current_row['temperature']:.1f}°F")
            if 'relative_humidity_2m' in current_row and pd.notna(current_row.get('relative_humidity_2m')):
                print(f"  Humidity: {current_row['relative_humidity_2m']:.1f}% (Open-Meteo)")
            elif 'humidity' in current_row and pd.notna(current_row.get('humidity')):
                print(f"  Humidity: {current_row['humidity']:.1f}%")
            if 'latitude' in current_row and pd.notna(current_row['latitude']):
                print(f"  Location: ({current_row['latitude']:.4f}, {current_row['longitude']:.4f})")
        
        # Live Data Integrity logging (live API path only: after weather merge, before prediction)
        if not use_csv:
            log_live_data_integrity_weather(test_df)
            log_live_data_integrity_pm25(test_df, current_aqi)
        
        # Prepare features
        print(f"\nPreparing features...")
        feature_row = prepare_features_for_prediction(test_df, sensor_id)
        print(f"✓ Features prepared ({len(feature_row.columns)} columns)")
        
        # Get feature columns (use 1h model's features as reference)
        feature_columns = models['1h']['feature_columns']
        print(f"✓ Using {len(feature_columns)} features from model")
        
        # API signature logging: missing_count, schema check, top 10 missing
        log_feature_pipeline_signature(test_df, feature_row, feature_columns, context="test")
        # Sanity dump: actual feature values for key weather/lag cols
        dump_feature_row_sanity(feature_row, feature_columns, sensor_id=sensor_id,
                                timestamp=test_df['time_stamp'].iloc[-1] if 'time_stamp' in test_df.columns else None)
        
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
        
        if not use_csv:
            log_live_parity(sensor_id, current_pm25, current_aqi, predictions, current_row)
        
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
