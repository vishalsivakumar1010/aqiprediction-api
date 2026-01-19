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
                                     height_meters=10, timezone='America/Los_Angeles'):
    """
    Fetch historical wind direction and speed from Open-Meteo Archive API.
    
    Args:
        latitude: Latitude (e.g., 37.5483 for Fremont, CA)
        longitude: Longitude (e.g., -121.9886 for Fremont, CA)
        start_date: Start date (datetime or string like '2025-01-01')
        end_date: End date (datetime or string like '2026-01-08')
        height_meters: Wind data height (10 or 100 meters, default: 10)
        timezone: Timezone (default: 'America/Los_Angeles')
        
    Returns:
        DataFrame with columns: timestamp_hour, wdir, wspd (wind speed, optional)
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
    
    # Parameters
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': start_date,
        'end_date': end_date,
        'hourly': f'wind_direction_{height_meters}m,wind_speed_{height_meters}m',
        'timezone': timezone
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
        
        # Create DataFrame
        wind_df = pd.DataFrame({
            'timestamp_hour': timestamps,
            'wdir': wind_direction,
            'wspd': wind_speed if wind_speed else [np.nan] * len(timestamps)
        })
        
        # Remove rows with NaN wind direction
        initial_count = len(wind_df)
        wind_df = wind_df.dropna(subset=['wdir'])
        removed = initial_count - len(wind_df)
        
        if removed > 0:
            print(f"⚠ Removed {removed} rows with missing wind direction")
        
        # Coverage statistics
        coverage_pct = (len(wind_df) / initial_count * 100) if initial_count > 0 else 0.0
        
        print(f"\n✓ Data fetched successfully")
        print(f"  Total hourly records: {initial_count}")
        print(f"  Records with wind direction: {len(wind_df)} ({coverage_pct:.1f}%)")
        print(f"  Wind direction range: {wind_df['wdir'].min():.0f}° to {wind_df['wdir'].max():.0f}°")
        if wind_speed:
            print(f"  Wind speed range: {wind_df['wspd'].min():.2f} to {wind_df['wspd'].max():.2f} m/s")
        
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
                                   forecast_days=1, timezone='America/Los_Angeles'):
    """
    Fetch forecast wind direction and speed from Open-Meteo Forecast API.
    
    Args:
        latitude: Latitude (e.g., 37.5483 for Fremont, CA)
        longitude: Longitude (e.g., -121.9886 for Fremont, CA)
        height_meters: Wind data height (10 or 100 meters, default: 10)
        forecast_days: Number of forecast days (default: 1)
        timezone: Timezone (default: 'America/Los_Angeles')
        
    Returns:
        DataFrame with columns: timestamp_hour, wdir, wspd (wind speed, optional)
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
    
    # Parameters
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': f'wind_direction_{height_meters}m,wind_speed_{height_meters}m',
        'forecast_days': forecast_days,
        'timezone': timezone
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
        
        # Create DataFrame
        wind_df = pd.DataFrame({
            'timestamp_hour': timestamps,
            'wdir': wind_direction,
            'wspd': wind_speed if wind_speed else [np.nan] * len(timestamps)
        })
        
        # Remove rows with NaN wind direction
        initial_count = len(wind_df)
        wind_df = wind_df.dropna(subset=['wdir'])
        removed = initial_count - len(wind_df)
        
        if removed > 0:
            print(f"⚠ Removed {removed} rows with missing wind direction")
        
        print(f"\n✓ Forecast data fetched successfully")
        print(f"  Total hourly records: {len(wind_df)}")
        print(f"  Wind direction range: {wind_df['wdir'].min():.0f}° to {wind_df['wdir'].max():.0f}°")
        if wind_speed:
            print(f"  Wind speed range: {wind_df['wspd'].min():.2f} to {wind_df['wspd'].max():.2f} m/s")
        
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
