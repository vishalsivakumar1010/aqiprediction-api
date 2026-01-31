"""
Phase 2: Step 4 - Merge Open-Meteo Weather Data
Merges hourly Open-Meteo weather data with 30-minute PM2.5 sensor data.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))


def load_openmeteo_data(weather_csv_path):
    """
    Load Open-Meteo weather data from CSV.
    
    Args:
        weather_csv_path: Path to Open-Meteo CSV file
        
    Returns:
        DataFrame with weather data
    """
    print(f"Loading Open-Meteo data from: {weather_csv_path}")
    
    # Read CSV, skipping header rows
    df = pd.read_csv(weather_csv_path, skiprows=3)
    
    # Rename columns to standardize
    df.columns = df.columns.str.strip()
    
    # Parse time column
    df['time'] = pd.to_datetime(df['time'])
    
    # Rename columns to match our naming convention
    column_mapping = {
        'temperature_2m (°F)': 'temperature_2m',
        'relative_humidity_2m (%)': 'relative_humidity_2m',
        'wind_speed_10m (mp/h)': 'wind_speed_10m',
        'wind_direction_10m (°)': 'wind_direction_10m'
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    # Ensure we have required columns
    required_cols = ['time', 'temperature_2m', 'relative_humidity_2m', 
                     'wind_speed_10m', 'wind_direction_10m']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Convert to PST (timezone-naive, assuming data is already in PST)
    # If timezone-aware, convert to PST first
    if df['time'].dt.tz is not None:
        df['time'] = df['time'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
    
    # Sort by time
    df = df.sort_values('time').reset_index(drop=True)
    
    print(f"Loaded {len(df):,} weather records")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")
    
    return df


def validate_timestamps(df):
    """
    Validate and fix sensor timestamps to ensure :00 or :30 alignment.
    
    Returns:
        df_clean: DataFrame with validated timestamps
        stats: Dictionary with validation statistics
    """
    df = df.copy()
    initial_count = len(df)
    
    # Ensure timezone-naive PST
    if df['time_stamp'].dt.tz is not None:
        df['time_stamp'] = df['time_stamp'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
    
    # Check alignment
    minutes = df['time_stamp'].dt.minute
    seconds = df['time_stamp'].dt.second
    
    # Round to nearest 30 minutes if within 2 minutes
    df['time_stamp_rounded'] = df['time_stamp'].dt.round('30min')
    time_diff = (df['time_stamp'] - df['time_stamp_rounded']).dt.total_seconds() / 60
    
    # Keep if within 2 minutes, otherwise drop
    keep_mask = time_diff.abs() <= 2
    
    # Apply rounding to kept rows
    df.loc[keep_mask, 'time_stamp'] = df.loc[keep_mask, 'time_stamp_rounded']
    
    # Drop misaligned rows
    df_clean = df[keep_mask].copy()
    df_clean = df_clean.drop(columns=['time_stamp_rounded'])
    
    # Ensure :00 or :30
    df_clean['time_stamp'] = df_clean['time_stamp'].dt.floor('30min')
    
    removed_count = initial_count - len(df_clean)
    
    stats = {
        'initial_samples': initial_count,
        'final_samples': len(df_clean),
        'removed_samples': removed_count,
        'removed_pct': (removed_count / initial_count * 100) if initial_count > 0 else 0
    }
    
    if removed_count > 0:
        print(f"  Removed {removed_count:,} misaligned timestamps ({stats['removed_pct']:.2f}%)")
    
    return df_clean, stats


def merge_weather_data(df_sensor, df_weather):
    """
    Merge hourly weather data with 30-minute sensor data.
    Uses last-known-hour forward fill strategy.
    
    Args:
        df_sensor: Sensor DataFrame with time_stamp
        df_weather: Weather DataFrame with time
        
    Returns:
        df_merged: Merged DataFrame
    """
    print("\nMerging weather data...")
    
    # Validate sensor timestamps
    print("Validating sensor timestamps...")
    df_sensor, ts_stats = validate_timestamps(df_sensor)
    
    # Prepare weather data for merging
    # Create a copy with rounded time for merging
    df_weather_merge = df_weather.copy()
    df_weather_merge['time_hour'] = df_weather_merge['time'].dt.floor('H')
    
    # Create mapping: for each 30-min timestamp, use the hour it belongs to
    df_sensor['time_hour'] = df_sensor['time_stamp'].dt.floor('H')
    
    # Merge on hour
    df_merged = df_sensor.merge(
        df_weather_merge[['time_hour', 'temperature_2m', 'relative_humidity_2m', 
                         'wind_speed_10m', 'wind_direction_10m']],
        on='time_hour',
        how='left'
    )
    
    # Drop the helper column
    df_merged = df_merged.drop(columns=['time_hour'])
    
    # Check for missing weather data
    missing_weather = df_merged[['temperature_2m', 'relative_humidity_2m', 
                                 'wind_speed_10m', 'wind_direction_10m']].isna().any(axis=1)
    missing_count = missing_weather.sum()
    
    if missing_count > 0:
        print(f"  Found {missing_count:,} rows with missing weather data")
        
        # Forward fill up to 2 hours
        print("  Forward-filling weather data (max 2 hours)...")
        weather_cols = ['temperature_2m', 'relative_humidity_2m', 
                       'wind_speed_10m', 'wind_direction_10m']
        
        # Sort by sensor and time for forward fill
        df_merged = df_merged.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
        
        # Forward fill within each sensor, limit to 4 readings (2 hours)
        for col in weather_cols:
            df_merged[col] = df_merged.groupby('sensor_id')[col].transform(
                lambda x: x.fillna(method='ffill', limit=4)
            )
        
        # Check remaining missing
        still_missing = df_merged[weather_cols].isna().any(axis=1).sum()
        if still_missing > 0:
            print(f"  Dropping {still_missing:,} rows with weather data missing beyond 2 hours")
            df_merged = df_merged[~df_merged[weather_cols].isna().any(axis=1)].copy()
    
    # Calculate wind direction components
    print("  Calculating wind direction components...")
    wind_dir_rad = np.radians(df_merged['wind_direction_10m'])
    df_merged['wind_dir_x'] = np.sin(wind_dir_rad)
    df_merged['wind_dir_y'] = np.cos(wind_dir_rad)
    
    # Also keep original wind direction as 'wdir'
    df_merged['wdir'] = df_merged['wind_direction_10m']
    
    print(f"\nMerge complete:")
    print(f"  Final rows: {len(df_merged):,}")
    print(f"  Date range: {df_merged['time_stamp'].min()} to {df_merged['time_stamp'].max()}")
    print(f"  Sensors: {df_merged['sensor_id'].nunique()}")
    
    return df_merged


def main():
    """Main execution function."""
    # Paths
    sensor_file = Path(__file__).parent.parent / "data" / "processed" / "purpleair_qc_cleaned.csv"
    weather_file = "/Users/vishalsivakumar/Downloads/open-meteo-37.50N122.00W18m-FinalSet.csv"
    output_dir = Path(__file__).parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: MERGING WEATHER DATA")
    print("="*70)
    
    # Load sensor data
    print(f"\nLoading sensor data from: {sensor_file}")
    df_sensor = pd.read_csv(sensor_file, parse_dates=['time_stamp'])
    print(f"Loaded {len(df_sensor):,} sensor records")
    
    # Load weather data
    print(f"\nLoading weather data from: {weather_file}")
    df_weather = load_openmeteo_data(weather_file)
    
    # Check date range overlap
    sensor_min = df_sensor['time_stamp'].min()
    sensor_max = df_sensor['time_stamp'].max()
    weather_min = df_weather['time'].min()
    weather_max = df_weather['time'].max()
    
    print(f"\nDate range check:")
    print(f"  Sensor:  {sensor_min} to {sensor_max}")
    print(f"  Weather: {weather_min} to {weather_max}")
    
    if sensor_min < weather_min:
        print(f"  ⚠️  Warning: Sensor data starts before weather data")
        print(f"     Will drop sensor rows before {weather_min}")
    
    if sensor_max > weather_max:
        print(f"  ⚠️  Warning: Sensor data extends beyond weather data")
        print(f"     Will drop sensor rows after {weather_max}")
    
    # Merge weather data
    df_merged = merge_weather_data(df_sensor, df_weather)
    
    # Drop rows outside weather coverage
    initial_count = len(df_merged)
    df_merged = df_merged[
        (df_merged['time_stamp'] >= weather_min) &
        (df_merged['time_stamp'] <= weather_max)
    ].copy()
    
    if len(df_merged) < initial_count:
        print(f"\n  Dropped {initial_count - len(df_merged):,} rows outside weather coverage")
    
    # Save merged data
    output_file = output_dir / "purpleair_with_weather.csv"
    df_merged.to_csv(output_file, index=False)
    
    print(f"\n{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"\nMerged data saved to: {output_file}")
    print(f"Final size: {len(df_merged):,} rows, {len(df_merged.columns)} columns")
    
    # Summary of weather columns
    print(f"\nWeather columns added:")
    weather_cols = ['temperature_2m', 'relative_humidity_2m', 'wind_speed_10m', 
                    'wind_direction_10m', 'wind_dir_x', 'wind_dir_y', 'wdir']
    for col in weather_cols:
        if col in df_merged.columns:
            non_null = df_merged[col].notna().sum()
            print(f"  {col}: {non_null:,} non-null values ({non_null/len(df_merged)*100:.1f}%)")


if __name__ == "__main__":
    main()
