#!/usr/bin/env python3
"""
Fetch Wind Direction Data from Open-Meteo API

This module provides functions to fetch wind direction and speed data from Open-Meteo
for both historical (training) and forecast (inference) purposes.

Open-Meteo API: https://open-meteo.com/en/docs
"""

import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


def fetch_historical_wind_openmeteo(latitude, longitude, start_date, end_date, 
                                    height_meters=10, timezone='America/Los_Angeles',
                                    include_temp_humidity=True):
    """
    Fetch historical weather from Open-Meteo Archive API.
    Returns wind, temperature, and humidity (all weather except PM2.5).
    
    Args:
        latitude: Latitude (e.g., 37.5483 for Fremont, CA)
        longitude: Longitude (e.g., -121.9886 for Fremont, CA)
        start_date: Start date (datetime or string like '2025-01-01')
        end_date: End date (datetime or string like '2026-01-08')
        height_meters: Wind data height (10 or 100 meters, default: 10)
        timezone: Timezone (default: 'America/Los_Angeles')
        include_temp_humidity: If True (default), fetch temperature_2m and relative_humidity_2m
        
    Returns:
        DataFrame with columns: timestamp_hour, wdir, wind_speed_10m, temperature_2m, relative_humidity_2m
    """
    # Convert dates to strings if datetime
    if isinstance(start_date, datetime):
        start_date = start_date.strftime('%Y-%m-%d')
    if isinstance(end_date, datetime):
        end_date = end_date.strftime('%Y-%m-%d')
    
    print(f"\n{'='*80}")
    print(f"FETCHING HISTORICAL WIND DATA FROM OPEN-METEO")
    print(f"{'='*80}")
    print(f"Location: ({latitude}, {longitude})")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Wind height: {height_meters} meters")
    print(f"Timezone: {timezone}")
    
    # Open-Meteo Archive API endpoint
    base_url = "https://archive-api.open-meteo.com/v1/archive"
    
    # Hourly vars: wind + temp/humidity (matches training schema)
    hourly_vars = f'wind_direction_{height_meters}m,wind_speed_{height_meters}m'
    if include_temp_humidity:
        hourly_vars += ',temperature_2m,relative_humidity_2m'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': start_date,
        'end_date': end_date,
        'hourly': hourly_vars,
        'timezone': timezone,
        'temperature_unit': 'fahrenheit',   # Match training (04_merge_weather uses °F)
        'wind_speed_unit': 'mph'            # Match training
    }
    
    try:
        print(f"\nFetching data from Open-Meteo...")
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'hourly' not in data:
            print(f"✗ Error: No hourly data in API response")
            return None
        
        hourly_data = data['hourly']
        
        if not hourly_data or 'time' not in hourly_data:
            print(f"✗ Error: No time data in API response")
            return None
        
        # Create DataFrame
        timestamps = pd.to_datetime(hourly_data['time'])
        wind_direction = hourly_data.get(f'wind_direction_{height_meters}m', [])
        wind_speed = hourly_data.get(f'wind_speed_{height_meters}m', [])
        temp = hourly_data.get('temperature_2m', [np.nan] * len(timestamps))
        humidity = hourly_data.get('relative_humidity_2m', [np.nan] * len(timestamps))
        
        wind_df = pd.DataFrame({
            'timestamp_hour': timestamps,
            'wdir': wind_direction,
            'wind_speed_10m': wind_speed if wind_speed else [np.nan] * len(timestamps),
            'temperature_2m': temp,
            'relative_humidity_2m': humidity
        })
        
        # Remove rows with NaN wind direction
        initial_count = len(wind_df)
        wind_df = wind_df.dropna(subset=['wdir'])
        removed = initial_count - len(wind_df)
        
        if removed > 0:
            print(f"⚠ Removed {removed} rows with missing wind direction")
        
        # Coverage statistics
        coverage_pct = (len(wind_df) / initial_count * 100) if initial_count > 0 else 0.0
        
        print(f"\n✓ Data fetched successfully (temp, humidity, wind)")
        print(f"  Total hourly records: {initial_count}")
        print(f"  Records with wind direction: {len(wind_df)} ({coverage_pct:.1f}%)")
        print(f"  Wind direction range: {wind_df['wdir'].min():.0f}° to {wind_df['wdir'].max():.0f}°")
        if wind_speed and 'wind_speed_10m' in wind_df.columns:
            print(f"  Wind speed range: {wind_df['wind_speed_10m'].min():.2f} to {wind_df['wind_speed_10m'].max():.2f} mph")
        
        return wind_df
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching data from Open-Meteo API: {e}")
        return None
    except Exception as e:
        print(f"✗ Error processing Open-Meteo data: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_forecast_wind_openmeteo(latitude, longitude, height_meters=10, 
                                  forecast_days=1, timezone='America/Los_Angeles',
                                  include_temp_humidity=True):
    """
    Fetch forecast weather from Open-Meteo Forecast API.
    Returns wind, temperature, and humidity (all weather except PM2.5).
    
    Args:
        latitude: Latitude (e.g., 37.5483 for Fremont, CA)
        longitude: Longitude (e.g., -121.9886 for Fremont, CA)
        height_meters: Wind data height (10 or 100 meters, default: 10)
        forecast_days: Number of forecast days (default: 1)
        timezone: Timezone (default: 'America/Los_Angeles')
        include_temp_humidity: If True (default), fetch temperature_2m and relative_humidity_2m
        
    Returns:
        DataFrame with columns: timestamp_hour, wdir, wind_speed_10m, temperature_2m, relative_humidity_2m
    """
    print(f"\n{'='*80}")
    print(f"FETCHING FORECAST WIND DATA FROM OPEN-METEO")
    print(f"{'='*80}")
    print(f"Location: ({latitude}, {longitude})")
    print(f"Wind height: {height_meters} meters")
    print(f"Forecast days: {forecast_days}")
    print(f"Timezone: {timezone}")
    
    # Open-Meteo Forecast API endpoint
    base_url = "https://api.open-meteo.com/v1/forecast"
    
    hourly_vars = f'wind_direction_{height_meters}m,wind_speed_{height_meters}m'
    if include_temp_humidity:
        hourly_vars += ',temperature_2m,relative_humidity_2m'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': hourly_vars,
        'forecast_days': forecast_days,
        'timezone': timezone,
        'temperature_unit': 'fahrenheit',
        'wind_speed_unit': 'mph'
    }
    
    try:
        print(f"\nFetching forecast data from Open-Meteo...")
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'hourly' not in data:
            print(f"✗ Error: No hourly data in API response")
            return None
        
        hourly_data = data['hourly']
        
        if not hourly_data or 'time' not in hourly_data:
            print(f"✗ Error: No time data in API response")
            return None
        
        # Create DataFrame
        timestamps = pd.to_datetime(hourly_data['time'])
        wind_direction = hourly_data.get(f'wind_direction_{height_meters}m', [])
        wind_speed = hourly_data.get(f'wind_speed_{height_meters}m', [])
        temp = hourly_data.get('temperature_2m', [np.nan] * len(timestamps))
        humidity = hourly_data.get('relative_humidity_2m', [np.nan] * len(timestamps))
        
        wind_df = pd.DataFrame({
            'timestamp_hour': timestamps,
            'wdir': wind_direction,
            'wind_speed_10m': wind_speed if wind_speed else [np.nan] * len(timestamps),
            'temperature_2m': temp,
            'relative_humidity_2m': humidity
        })
        
        # Remove rows with NaN wind direction
        initial_count = len(wind_df)
        wind_df = wind_df.dropna(subset=['wdir'])
        removed = initial_count - len(wind_df)
        
        if removed > 0:
            print(f"⚠ Removed {removed} rows with missing wind direction")
        
        print(f"\n✓ Forecast data fetched successfully (temp, humidity, wind)")
        print(f"  Total hourly records: {len(wind_df)}")
        print(f"  Wind direction range: {wind_df['wdir'].min():.0f}° to {wind_df['wdir'].max():.0f}°")
        if wind_speed and 'wind_speed_10m' in wind_df.columns:
            print(f"  Wind speed range: {wind_df['wind_speed_10m'].min():.2f} to {wind_df['wind_speed_10m'].max():.2f} mph")
        
        return wind_df
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching data from Open-Meteo API: {e}")
        return None
    except Exception as e:
        print(f"✗ Error processing Open-Meteo data: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_openmeteo_fetch():
    """Test function to verify Open-Meteo API works."""
    print("Testing Open-Meteo API...")
    
    # Fremont, CA coordinates
    latitude = 37.5483
    longitude = -121.9886
    
    # Test historical data (last week)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print("\n1. Testing Historical API...")
    hist_df = fetch_historical_wind_openmeteo(latitude, longitude, start_date, end_date)
    
    if hist_df is not None and len(hist_df) > 0:
        print(f"\n✓ Historical API works! Retrieved {len(hist_df)} records")
        print(f"  Sample data:")
        print(hist_df.head(5))
    else:
        print("\n✗ Historical API test failed")
    
    # Test forecast data
    print("\n2. Testing Forecast API...")
    forecast_df = fetch_forecast_wind_openmeteo(latitude, longitude)
    
    if forecast_df is not None and len(forecast_df) > 0:
        print(f"\n✓ Forecast API works! Retrieved {len(forecast_df)} records")
        print(f"  Sample data:")
        print(forecast_df.head(5))
    else:
        print("\n✗ Forecast API test failed")
    
    return hist_df, forecast_df


if __name__ == "__main__":
    # Test the functions
    test_openmeteo_fetch()
