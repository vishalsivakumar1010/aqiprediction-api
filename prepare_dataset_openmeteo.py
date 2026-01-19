#!/usr/bin/env python3
"""
Prepare Full Dataset with Open-Meteo Wind Data

This script prepares the complete dataset for training by:
1. Loading PurpleAir sensor data
2. Loading wind direction from Open-Meteo CSV file
3. Merging wind data with sensor data
4. Adding sensor locations
5. Saving complete dataset

Usage:
    python3 prepare_dataset_openmeteo.py --wind-csv path/to/openmeteo.csv
"""

import pandas as pd
import numpy as np
import os
import sys
import argparse
from datetime import datetime
from geopy.distance import geodesic
import warnings
warnings.filterwarnings('ignore')

# Import the load function we created
from load_wind_openmeteo_csv import load_openmeteo_csv

# Import from original prepare_full_dataset if needed
# For now, let's make this standalone


def load_purpleair_data(data_directory):
    """
    Load all PurpleAir sensor CSV files from the data directory.
    
    Args:
        data_directory: Path to directory containing sensor CSV files
        
    Returns:
        DataFrame with columns: sensor_id, time_stamp, humidity, temperature, pm2_5_atm
    """
    import glob
    
    csv_files = glob.glob(os.path.join(data_directory, "*30-Minute Average.csv"))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {data_directory}")
    
    all_data = []
    
    for file_path in csv_files:
        # Extract sensor ID from filename (first number before space)
        filename = os.path.basename(file_path)
        sensor_id = filename.split()[0]
        
        try:
            df = pd.read_csv(file_path)
            df['sensor_id'] = int(sensor_id)
            # Parse timestamps and ensure they're timezone-aware (convert to UTC)
            df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
            
            # Standardize column names
            df.columns = df.columns.str.replace('pm2.5_atm', 'pm2_5_atm')
            
            all_data.append(df)
            print(f"Loaded {len(df)} rows from sensor {sensor_id}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data was successfully loaded")
    
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    
    print(f"\n✓ Combined {len(combined_df)} rows from {len(csv_files)} sensors")
    print(f"Date range: {combined_df['time_stamp'].min()} to {combined_df['time_stamp'].max()}")
    
    return combined_df


def merge_wind_direction_openmeteo(df, wind_csv_path):
    """
    Load Open-Meteo CSV and merge wind direction with PurpleAir dataframe.
    
    Args:
        df: PurpleAir DataFrame with time_stamp column (30-minute intervals)
        wind_csv_path: Path to Open-Meteo CSV file
        
    Returns:
        DataFrame with added wdir, wind_dir_x, wind_dir_y columns
    """
    df = df.copy()
    tz_local = 'America/Los_Angeles'
    
    print(f"\n{'='*80}")
    print(f"LOADING AND MERGING OPEN-METEO WIND DATA")
    print(f"{'='*80}")
    
    # Load wind data from CSV
    wind_df = load_openmeteo_csv(wind_csv_path)
    
    # Convert PurpleAir timestamps to timezone-naive local time
    df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
    df['time_stamp'] = df['time_stamp'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Create hourly timestamp for merging (floor to hour)
    df['timestamp_hour'] = df['time_stamp'].dt.floor('H')
    
    # Ensure wind_df timestamp_hour is timezone-naive
    wind_df = wind_df.copy()
    wind_df['timestamp_hour'] = pd.to_datetime(wind_df['timestamp_hour'])
    if wind_df['timestamp_hour'].iloc[0].tz is not None:
        wind_df['timestamp_hour'] = wind_df['timestamp_hour'].dt.tz_convert(tz_local).dt.tz_localize(None)
    
    # Merge wind direction data
    print(f"\nMerging wind direction data...")
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
    
    if non_null_pct < 50:
        print(f"\n⚠ Warning: Only {non_null_pct:.1f}% of rows have wind direction data")
    elif non_null_pct < 80:
        print(f"\n⚠ Warning: {non_null_pct:.1f}% coverage - consider checking date range alignment")
    else:
        print(f"✓ Good coverage: {non_null_pct:.1f}%")
    
    # Convert wind direction to x, y components
    print(f"\nConverting wind direction to x, y components...")
    wdir_rad = np.radians(df['wdir'])
    df['wind_dir_x'] = np.cos(wdir_rad)
    df['wind_dir_y'] = np.sin(wdir_rad)
    
    # Set NaN for x and y where wdir was NaN
    df.loc[df['wdir'].isna(), 'wind_dir_x'] = np.nan
    df.loc[df['wdir'].isna(), 'wind_dir_y'] = np.nan
    
    print(f"✓ Created wind_dir_x and wind_dir_y columns")
    
    # Print sample merged data
    print(f"\nSample merged rows:")
    sample = df[df['wdir'].notna()].head(5)
    for idx, row in sample.iterrows():
        print(f"  {row['time_stamp']} | wdir={row['wdir']:.0f}° | wind_dir_x={row['wind_dir_x']:.3f} | wind_dir_y={row['wind_dir_y']:.3f}")
    
    return df


def add_sensor_locations(df, data_directory):
    """
    Add sensor location information to dataframe.
    
    Args:
        df: DataFrame with sensor_id column
        data_directory: Directory containing sensor_locations.pkl or sensor_locations.csv
        
    Returns:
        DataFrame with added latitude, longitude, name columns
    """
    import pickle
    
    # Try to load sensor locations
    location_paths = [
        os.path.join(data_directory, 'sensor_locations.pkl'),
        os.path.join(data_directory, 'sensor_locations.csv')
    ]
    
    locations_df = None
    for path in location_paths:
        if os.path.exists(path):
            try:
                if path.endswith('.pkl'):
                    with open(path, 'rb') as f:
                        locations_df = pickle.load(f)
                else:
                    locations_df = pd.read_csv(path)
                print(f"\n✓ Loaded sensor locations from {os.path.basename(path)}")
                break
            except Exception as e:
                print(f"Warning: Could not load {path}: {e}")
                continue
    
    if locations_df is None:
        print(f"\n⚠ Warning: Sensor locations not found. Skipping location data.")
        return df
    
    # Handle both DataFrame and dict formats
    if isinstance(locations_df, dict):
        # Convert dict to DataFrame
        locations_list = []
        for sensor_id, info in locations_df.items():
            row = {'sensor_id': sensor_id}
            if isinstance(info, dict):
                row.update(info)
            else:
                row['info'] = info
            locations_list.append(row)
        locations_df = pd.DataFrame(locations_list)
    
    # Merge location data
    if 'sensor_id' in locations_df.columns:
        # Get columns to merge (latitude, longitude, name if they exist)
        merge_cols = ['sensor_id']
        for col in ['latitude', 'longitude', 'name']:
            if col in locations_df.columns:
                merge_cols.append(col)
        
        df = df.merge(locations_df[merge_cols], 
                      on='sensor_id', 
                      how='left')
        
        locations_added = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        print(f"✓ Added location data: {locations_added:,} / {len(df):,} rows have locations")
    else:
        print(f"⚠ Warning: sensor_id column not found in locations file")
        print(f"  Available columns: {list(locations_df.columns)}")
    
    return df


def main():
    parser = argparse.ArgumentParser(description='Prepare dataset with Open-Meteo wind data')
    parser.add_argument('--data-dir', required=True, 
                        help='Directory containing PurpleAir sensor CSV files')
    parser.add_argument('--wind-csv', required=True,
                        help='Path to Open-Meteo CSV file')
    parser.add_argument('--output', default='purpleair_complete_with_wind_openmeteo.csv',
                        help='Output CSV file name (default: purpleair_complete_with_wind_openmeteo.csv)')
    
    args = parser.parse_args()
    
    print(f"{'='*80}")
    print(f"PREPARING DATASET WITH OPEN-METEO WIND DATA")
    print(f"{'='*80}")
    print(f"Data directory: {args.data_dir}")
    print(f"Wind CSV file: {args.wind_csv}")
    print(f"Output file: {args.output}")
    print(f"{'='*80}")
    
    # Step 1: Load PurpleAir data
    print(f"\n{'='*80}")
    print(f"STEP 1: LOADING PURPLEAIR SENSOR DATA")
    print(f"{'='*80}")
    df = load_purpleair_data(args.data_dir)
    
    # Step 2: Merge wind data from Open-Meteo CSV
    print(f"\n{'='*80}")
    print(f"STEP 2: MERGING OPEN-METEO WIND DATA")
    print(f"{'='*80}")
    df = merge_wind_direction_openmeteo(df, args.wind_csv)
    
    # Step 3: Add sensor locations
    print(f"\n{'='*80}")
    print(f"STEP 3: ADDING SENSOR LOCATIONS")
    print(f"{'='*80}")
    df = add_sensor_locations(df, args.data_dir)
    
    # Step 4: Save complete dataset
    print(f"\n{'='*80}")
    print(f"STEP 4: SAVING COMPLETE DATASET")
    print(f"{'='*80}")
    output_path = os.path.join(args.data_dir, args.output)
    df.to_csv(output_path, index=False)
    
    print(f"\n✓ Complete dataset saved to: {output_path}")
    print(f"\nDataset Summary:")
    print(f"  Total rows: {len(df):,}")
    print(f"  Sensors: {df['sensor_id'].nunique()}")
    print(f"  Date range: {df['time_stamp'].min()} to {df['time_stamp'].max()}")
    print(f"  Wind direction coverage: {df['wdir'].notna().sum():,} / {len(df):,} ({df['wdir'].notna().sum()/len(df)*100:.1f}%)")
    if 'latitude' in df.columns:
        print(f"  Location data: {df['latitude'].notna().sum():,} / {len(df):,} ({df['latitude'].notna().sum()/len(df)*100:.1f}%)")
    else:
        print(f"  Location data: Not available")
    
    print(f"\n{'='*80}")
    print(f"DATASET PREPARATION COMPLETE!")
    print(f"{'='*80}")
    print(f"\nNext steps:")
    print(f"  1. Use this dataset for training: {output_path}")
    print(f"  2. Run training script with this dataset")
    print(f"  3. Compare model performance with previous models")


if __name__ == "__main__":
    main()
