"""
Phase 2: Step 2 - Ingest PurpleAir Sensor Data
Loads all sensor CSV files and combines into a unified dataset.
"""

import pandas as pd
import numpy as np
import os
import glob
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))


def load_sensor_data(purpleair_dir, sensor_locations_file=None):
    """
    Load all PurpleAir sensor CSV files and combine into a unified dataset.
    
    Args:
        purpleair_dir: Path to directory containing sensor CSV files
        sensor_locations_file: Optional path to sensor locations CSV (for adding lat/lon)
        
    Returns:
        DataFrame with columns: sensor_id, time_stamp, pm2_5_atm, latitude, longitude
    """
    csv_files = glob.glob(os.path.join(purpleair_dir, "*30-Minute Average.csv"))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {purpleair_dir}")
    
    print(f"Found {len(csv_files)} sensor CSV files")
    
    # Load sensor locations if available
    sensor_locations = None
    if sensor_locations_file and os.path.exists(sensor_locations_file):
        sensor_locations = pd.read_csv(sensor_locations_file)
        print(f"Loaded sensor locations for {len(sensor_locations)} sensors")
    
    all_data = []
    
    for file_path in csv_files:
        # Extract sensor ID from filename (first number before space)
        filename = os.path.basename(file_path)
        sensor_id = int(filename.split()[0])
        
        try:
            df = pd.read_csv(file_path)
            
            # Standardize column names
            if 'pm2.5_atm' in df.columns:
                df = df.rename(columns={'pm2.5_atm': 'pm2_5_atm'})
            
            # Ensure we have the required columns
            if 'pm2_5_atm' not in df.columns:
                print(f"Warning: {filename} missing pm2_5_atm column, skipping")
                continue
            
            # Parse timestamps (handle timezone-aware timestamps)
            if 'time_stamp' in df.columns:
                df['time_stamp'] = pd.to_datetime(df['time_stamp'], utc=True)
                # Convert to PST and make timezone-naive
                if df['time_stamp'].dt.tz is not None:
                    df['time_stamp'] = df['time_stamp'].dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
            else:
                print(f"Warning: {filename} missing time_stamp column, skipping")
                continue
            
            # Add sensor ID
            df['sensor_id'] = sensor_id
            
            # Add location if available
            if sensor_locations is not None:
                sensor_info = sensor_locations[sensor_locations['sensor_id'] == sensor_id]
                if not sensor_info.empty:
                    df['latitude'] = sensor_info.iloc[0]['latitude']
                    df['longitude'] = sensor_info.iloc[0]['longitude']
                else:
                    print(f"Warning: No location data for sensor {sensor_id}")
                    df['latitude'] = np.nan
                    df['longitude'] = np.nan
            
            all_data.append(df)
            print(f"  ✓ Loaded {len(df):,} rows from sensor {sensor_id}")
            
        except Exception as e:
            print(f"  ✗ Error loading {filename}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data was successfully loaded")
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Sort by sensor_id and time_stamp
    combined_df = combined_df.sort_values(['sensor_id', 'time_stamp']).reset_index(drop=True)
    
    # Summary
    print(f"\n{'='*70}")
    print("INGESTION SUMMARY")
    print(f"{'='*70}")
    print(f"Total combined rows: {len(combined_df):,}")
    print(f"Number of sensors: {combined_df['sensor_id'].nunique()}")
    print(f"Date range: {combined_df['time_stamp'].min()} to {combined_df['time_stamp'].max()}")
    
    # Per-sensor summary
    sensor_summary = combined_df.groupby('sensor_id').agg({
        'time_stamp': ['min', 'max', 'count'],
        'pm2_5_atm': 'count'
    }).reset_index()
    sensor_summary.columns = ['sensor_id', 'first_date', 'last_date', 'total_readings', 'pm25_count']
    # Ensure datetime types
    sensor_summary['first_date'] = pd.to_datetime(sensor_summary['first_date'])
    sensor_summary['last_date'] = pd.to_datetime(sensor_summary['last_date'])
    sensor_summary['coverage_days'] = (sensor_summary['last_date'] - sensor_summary['first_date']).dt.days
    
    print(f"\nPer-sensor coverage:")
    print(sensor_summary[['sensor_id', 'coverage_days', 'total_readings']].to_string(index=False))
    
    return combined_df


def main():
    """Main execution function."""
    # Paths
    purpleair_dir = "/Users/vishalsivakumar/Library/Application Support/com.purpleair.data-download-tool/PurpleAir Download 1-25-2026-Fullset"
    sensor_locations_file = Path(__file__).parent.parent / "data" / "sensor_locations" / "sensor_locations.csv"
    output_dir = Path(__file__).parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("PHASE 2: INGESTING PURPLEAIR SENSOR DATA")
    print("="*70)
    
    # Load sensor data
    df = load_sensor_data(purpleair_dir, sensor_locations_file if sensor_locations_file.exists() else None)
    
    # Save raw combined data
    output_file = output_dir / "purpleair_combined_raw.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"\nRaw combined data saved to: {output_file}")
    print(f"Total size: {len(df):,} rows, {len(df.columns)} columns")


if __name__ == "__main__":
    main()
