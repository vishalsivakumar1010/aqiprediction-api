#!/usr/bin/env python3
"""
Load Wind Direction Data from Open-Meteo CSV File

This module provides functions to load wind direction data from Open-Meteo CSV files
and merge it with PurpleAir sensor data for retraining.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def load_openmeteo_csv(csv_path):
    """
    Load wind direction data from Open-Meteo CSV file.
    
    Args:
        csv_path: Path to Open-Meteo CSV file
        
    Returns:
        DataFrame with columns: timestamp_hour, wdir, wspd (optional)
    """
    print(f"\n{'='*80}")
    print(f"LOADING WIND DATA FROM OPEN-METEO CSV")
    print(f"{'='*80}")
    print(f"File: {csv_path}")
    
    # Open-Meteo CSVs have metadata rows, then header row starting with 'time'
    # Find the header row
    with open(csv_path, 'r') as f:
        lines = f.readlines()
        header_line = None
        for i, line in enumerate(lines):
            if line.strip().startswith('time,'):
                header_line = i
                break
    
    if header_line is None:
        raise ValueError("Could not find 'time,' header row in CSV file")
    
    # Read from header line
    df = pd.read_csv(csv_path, skiprows=header_line)
    
    # Open-Meteo CSV columns: time, wind_speed_10m (km/h), wind_direction_10m (°)
    # Handle different possible column names
    time_col = None
    wdir_col = None
    wspd_col = None
    
    for col in df.columns:
        if col.strip().lower() == 'time':
            time_col = col
        elif 'wind_direction' in col.lower() or 'winddirection' in col.lower():
            wdir_col = col
        elif 'wind_speed' in col.lower() or 'windspeed' in col.lower():
            wspd_col = col
    
    if time_col is None:
        raise ValueError(f"Could not find 'time' column. Available columns: {list(df.columns)}")
    if wdir_col is None:
        raise ValueError(f"Could not find wind_direction column. Available columns: {list(df.columns)}")
    
    # Create standardized DataFrame
    wind_df = pd.DataFrame({
        'timestamp_hour': pd.to_datetime(df[time_col]),
        'wdir': pd.to_numeric(df[wdir_col], errors='coerce')
    })
    
    # Add wind speed if available
    if wspd_col:
        wind_df['wspd'] = pd.to_numeric(df[wspd_col], errors='coerce')
    else:
        wind_df['wspd'] = np.nan
    
    # Remove rows with NaN wind direction
    initial_count = len(wind_df)
    wind_df = wind_df.dropna(subset=['wdir'])
    removed = initial_count - len(wind_df)
    
    if removed > 0:
        print(f"⚠ Removed {removed} rows with missing wind direction")
    
    # Coverage statistics
    coverage_pct = (len(wind_df) / initial_count * 100) if initial_count > 0 else 0.0
    
    print(f"\n✓ Data loaded successfully")
    print(f"  Total hourly records: {initial_count}")
    print(f"  Records with wind direction: {len(wind_df)} ({coverage_pct:.1f}%)")
    print(f"  Date range: {wind_df['timestamp_hour'].min()} to {wind_df['timestamp_hour'].max()}")
    print(f"  Wind direction range: {wind_df['wdir'].min():.0f}° to {wind_df['wdir'].max():.0f}°")
    if wspd_col and wind_df['wspd'].notna().any():
        print(f"  Wind speed range: {wind_df['wspd'].min():.2f} to {wind_df['wspd'].max():.2f} km/h")
    
    # Ensure timestamp_hour is timezone-naive (America/Los_Angeles equivalent)
    # Open-Meteo data is already in the timezone specified during download
    if wind_df['timestamp_hour'].iloc[0].tz is not None:
        # Convert to local timezone then make naive
        wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
    else:
        # Already timezone-naive, assume it's in local time
        pass
    
    return wind_df


def merge_openmeteo_wind(df, csv_path):
    """
    Load Open-Meteo CSV and merge with PurpleAir dataframe.
    
    This is a convenience function that loads the CSV and merges in one step.
    
    Args:
        df: PurpleAir DataFrame with time_stamp column
        csv_path: Path to Open-Meteo CSV file
        
    Returns:
        DataFrame with merged wind data (wdir, wind_dir_x, wind_dir_y columns)
    """
    # Load wind data from CSV
    wind_df = load_openmeteo_csv(csv_path)
    
    # Use the existing merge function from prepare_full_dataset
    # But first create a dummy station_info for compatibility
    station_info = {
        'station_id': 'openmeteo',
        'station_name': 'Open-Meteo Grid Data',
        'distance_km': 0.0,
        'test_coverage_pct': 100.0,
        'actual_coverage_pct': (wind_df['wdir'].notna().sum() / len(wind_df) * 100) if len(wind_df) > 0 else 0.0,
        'latitude': 37.50439,  # From CSV metadata
        'longitude': -121.997345  # From CSV metadata
    }
    
    # Import merge function from prepare_full_dataset
    # For now, let's implement the merge directly
    df = df.copy()
    tz_local = 'America/Los_Angeles'
    
    print(f"\n{'='*80}")
    print(f"MERGING WIND DIRECTION DATA")
    print(f"{'='*80}")
    
    # Convert PurpleAir timestamps to timezone-naive local time
    df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
    df['time_stamp'] = df['time_stamp'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Create hourly timestamp for merging
    df['timestamp_hour'] = df['time_stamp'].dt.floor('H')
    
    # Ensure wind_df timestamp_hour is timezone-naive
    wind_df = wind_df.copy()
    wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour'])
    if wind_df['timestamp_hour'].iloc[0].tz is not None:
        wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Merge wind direction data
    print(f"Merging wind direction data...")
    initial_rows = len(df)
    
    df = df.merge(wind_df[['timestamp_hour', 'wdir']], 
                  on='timestamp_hour', 
                  how='left')
    
    # Forward-fill missing wdir values with limit of 6 hours
    print(f"Forward-filling missing values (max 6 hours)...")
    df['wdir'] = df.groupby('sensor_id')['wdir'].ffill(limit=6)
    
    # Calculate coverage
    non_null_count = df['wdir'].notna().sum()
    non_null_pct = (non_null_count / len(df)) * 100
    
    print(f"\n✓ Merge complete")
    print(f"  Initial rows: {initial_rows:,}")
    print(f"  Rows with wind direction: {non_null_count:,} / {len(df):,} ({non_null_pct:.2f}%)")
    
    if station_info:
        print(f"\nData Source Information:")
        print(f"  Source: {station_info['station_name']}")
        print(f"  Coverage: {station_info['actual_coverage_pct']:.2f}%")
    
    # Convert wind direction to x, y components
    print(f"\nConverting wind direction to x, y components...")
    wdir_rad = np.radians(df['wdir'])
    df['wind_dir_x'] = np.cos(wdir_rad)
    df['wind_dir_y'] = np.sin(wdir_rad)
    
    # Set NaN for x and y where wdir was NaN
    df.loc[df['wdir'].isna(), 'wind_dir_x'] = np.nan
    df.loc[df['wdir'].isna(), 'wind_dir_y'] = np.nan
    
    print(f"✓ Created wind_dir_x and wind_dir_y columns")
    
    return df


if __name__ == "__main__":
    # Test the function
    csv_path = "/Users/vishalsivakumar/Downloads/PAIC Data 2 Months/open-meteo-37.50N122.00W18m.csv"
    wind_df = load_openmeteo_csv(csv_path)
    print(f"\n✓ Test successful! Loaded {len(wind_df)} records")
    print(f"\nSample data:")
    print(wind_df.head(10))
